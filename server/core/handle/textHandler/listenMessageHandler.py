import time
import asyncio
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

from core.handle.receiveAudioHandle import startToChat
from core.handle.reportHandle import enqueue_asr_report
from core.handle.sendAudioHandle import send_stt_message, send_tts_message
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.utils.util import remove_punctuation_and_length
from core.providers.asr.dto.dto import InterfaceType

TAG = __name__

class ListenTextMessageHandler(TextMessageHandler):
    """Bộ xử lý tin nhắn Listen"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.LISTEN

    async def handle(self, conn: "ConnectionHandler", msg_json: Dict[str, Any]) -> None:
        if "mode" in msg_json:
            conn.client_listen_mode = msg_json["mode"]
            conn.logger.bind(tag=TAG).debug(
                f"Chế độ thu âm của client: {conn.client_listen_mode}"
            )
        if msg_json["state"] == "start":
            # Nếu TTS đang phát (vd: AI đang dỗ bé), abort ngay khi user nhấn nút
            # Điều này cho phép user ngắt lời AI bất kỳ lúc nào bằng nút nhấn
            if conn.client_is_speaking:
                from core.handle.abortHandle import handleAbortMessage
                conn.logger.bind(tag=TAG).info("[PTT] Nhấn nút trong khi TTS đang phát → Abort TTS")
                await handleAbortMessage(conn)
            # Reset audio buffer để chuẩn bị ghi âm mới
            conn.reset_audio_states()
        elif msg_json["state"] == "stop":
            conn.client_voice_stop = True
            if conn.asr is None:
                conn.logger.bind(tag=TAG).warning("ASR chưa được khởi tạo, bỏ qua sự kiện listen stop")
                return
            if conn.asr.interface_type == InterfaceType.STREAM:
                # Chế độ stream: gửi yêu cầu kết thúc
                asyncio.create_task(conn.asr._send_stop_request())
            else:
                # Chế độ không stream: kích hoạt nhận diện ASR hoặc xử lý YAMNet trực tiếp
                if len(conn.asr_audio) > 0:
                    asr_audio_task = conn.asr_audio.copy()
                    conn.reset_audio_states()

                    if getattr(conn, "client_listen_mode", "") == "cry_detect":
                        # Đưa audio vào YAMNet
                        from core.providers.classifier.yamnet_classifier import YamnetClassifier
                        # Cache instance để không phải initialize YAMNet (mất 2-3s) mỗi lần chạy
                        if not hasattr(conn.__class__, "yamnet"):
                            conn.__class__.yamnet = YamnetClassifier()
                        
                        if getattr(conn, "audio_format", "opus") == "opus":
                            pcm_data = b"".join(conn.asr.decode_opus(asr_audio_task))
                        else:
                            pcm_data = b"".join(asr_audio_task)
                            
                        # Phân tích bằng Google YAMNet (chạy nền để tránh nghẽn server)
                        sample_rate = getattr(conn, 'sample_rate', 16000)
                        
                        # Tách logic YAMNet ra hẳn luồng riêng để không chặn Event Loop (Giải quyết lỗi nghẽn server)
                        is_cry = await asyncio.to_thread(conn.__class__.yamnet.is_baby_cry, pcm_data, sample_rate)
                        
                        if is_cry:
                            from core.api.dashboard_handler import DashboardHandler, DASHBOARD_STATE
                            conn.logger.bind(tag=TAG).warning(f"YAMNet Classifier Succeeded: BÉ ĐANG KHÓC! Mode: {DASHBOARD_STATE['mode']}")
                            
                            # Ghi lịch sử lên web & Kiểm tra cooldown
                            from core.serverToClients import DashboardUpdater
                            if not DashboardUpdater.add_cry_event("YAMNet: Phát hiện bé khóc!"):
                                conn.logger.bind(tag=TAG).debug("YAMNet alert bị chặn bởi cooldown")
                                # Vẫn cần giải phóng ESP32
                                await send_tts_message(conn, "stop", None)
                                return

                            # Gửi Telegram alert (cho cả 2 mode, fire-and-forget)
                            try:
                                import time as _time
                                from core.telegram.alerts import _global_alerts
                                if _global_alerts:
                                    time_str_alert = _time.strftime("%H:%M:%S", _time.localtime())
                                    asyncio.create_task(
                                        _global_alerts.send_cry_alert(
                                            message="YAMNet phát hiện bé đang khóc!",
                                            time_str=time_str_alert,
                                            current_mode=DASHBOARD_STATE["mode"],
                                        )
                                    )
                                else:
                                    conn.logger.bind(tag=TAG).debug("Telegram chưa khởi tạo, bỏ qua alert")
                            except Exception as tg_err:
                                conn.logger.bind(tag=TAG).warning(f"Gửi Telegram alert thất bại (không nghẽn): {tg_err}")

                            if DASHBOARD_STATE["mode"] == "auto":
                                # Tự động an ủi bé
                                await startToChat(conn, "Hệ thống phát hiện tiếng bé khóc. Hãy nói một câu dỗ dành nhắc bé nín khóc thật nhẹ nhàng. Rất ngắn gọn thôi.")
                            else:
                                # Chế độ thủ công, không gọi AI, chỉ báo về web và Unblock ESP32
                                await send_tts_message(conn, "stop", None)
                        else:
                            conn.logger.bind(tag=TAG).info("YAMNet Classifier: ĐÂY KHÔNG PHẢI TIẾNG KHÓC (Còi xe, chó sủa...). Bỏ qua!")
                            # Giải phóng trạng thái THINKING của ESP32 để nó trở về IDLE (Quan trọng để nút BOOT hoạt động lại)
                            await send_tts_message(conn, "stop", None)
                    else:
                        if len(asr_audio_task) > 0:
                            await conn.asr.handle_voice_stop(conn, asr_audio_task)
        elif msg_json["state"] == "detect":
            conn.client_have_voice = False
            conn.reset_audio_states()
            if "text" in msg_json:
                conn.last_activity_time = time.time() * 1000
                original_text = msg_json["text"]  # Giữ nguyên văn bản gốc
                filtered_len, filtered_text = remove_punctuation_and_length(
                    original_text
                )

                # Nhận diện xem có phải từ đánh thức không
                is_wakeup_words = filtered_text in conn.config.get("wakeup_words")
                # Kiểm tra có bật chế độ phản hồi từ đánh thức không
                enable_greeting = conn.config.get("enable_greeting", True)

                if is_wakeup_words and not enable_greeting:
                    # Nếu là từ đánh thức nhưng tắt phản hồi → không cần trả lời
                    await send_stt_message(conn, original_text)
                    await send_tts_message(conn, "stop", None)
                    conn.client_is_speaking = False
                elif is_wakeup_words:
                    conn.just_woken_up = True
                    # Ghi nhận văn bản thuần (dùng lại chức năng báo cáo ASR, không cần dữ liệu âm thanh)
                    enqueue_asr_report(conn, "Xin chào bé!", [])
                    await startToChat(conn, "Xin chào bé!")
                else:
                    conn.just_woken_up = True
                    # Ghi nhận văn bản thuần (dùng lại chức năng báo cáo ASR, không cần dữ liệu âm thanh)
                    enqueue_asr_report(conn, original_text, [])
                    # Chuyển nội dung văn bản sang LLM để trả lời
                    await startToChat(conn, original_text)