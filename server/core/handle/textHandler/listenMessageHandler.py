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
    """Listen消息处理器"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.LISTEN

    async def handle(self, conn: "ConnectionHandler", msg_json: Dict[str, Any]) -> None:
        if "mode" in msg_json:
            conn.client_listen_mode = msg_json["mode"]
            conn.logger.bind(tag=TAG).debug(
                f"客户端拾音模式：{conn.client_listen_mode}"
            )
        if msg_json["state"] == "start":
            # 设备从播放模式切回录音模式,清除所有音频状态和缓冲区
            conn.reset_audio_states()
        elif msg_json["state"] == "stop":
            conn.client_voice_stop = True
            if conn.asr is None:
                conn.logger.bind(tag=TAG).warning("ASR尚未初始化,忽略listen stop")
                return
            if conn.asr.interface_type == InterfaceType.STREAM:
                # 流式模式下，发送结束请求
                asyncio.create_task(conn.asr._send_stop_request())
            else:
                # 非流式模式：直接触发ASR识别或处理YAMNet
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
                original_text = msg_json["text"]  # 保留原始文本
                filtered_len, filtered_text = remove_punctuation_and_length(
                    original_text
                )

                # 识别是否是唤醒词
                is_wakeup_words = filtered_text in conn.config.get("wakeup_words")
                # 是否开启唤醒词回复
                enable_greeting = conn.config.get("enable_greeting", True)

                if is_wakeup_words and not enable_greeting:
                    # 如果是唤醒词，且关闭了唤醒词回复，就不用回答
                    await send_stt_message(conn, original_text)
                    await send_tts_message(conn, "stop", None)
                    conn.client_is_speaking = False
                elif is_wakeup_words:
                    conn.just_woken_up = True
                    # 上报纯文字数据（复用ASR上报功能，但不提供音频数据）
                    enqueue_asr_report(conn, "嘿，你好呀", [])
                    await startToChat(conn, "嘿，你好呀")
                else:
                    conn.just_woken_up = True
                    # 上报纯文字数据（复用ASR上报功能，但不提供音频数据）
                    enqueue_asr_report(conn, original_text, [])
                    # 否则需要LLM对文字内容进行答复
                    await startToChat(conn, original_text)