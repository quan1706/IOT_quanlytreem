import time
import json
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from core.utils.util import audio_to_data
from core.handle.abortHandle import handleAbortMessage
from core.handle.intentHandler import handle_user_intent
from core.utils.output_counter import check_device_output_limit
from core.handle.sendAudioHandle import send_stt_message, SentenceType

TAG = __name__

# Thư mục chứa các tệp âm thanh hệ thống
ASSETS_DIR = "config/assets"


async def handleAudioMessage(conn: "ConnectionHandler", audio):
    # Kiểm tra xem đoạn âm thanh hiện tại có tiếng người nói không (VAD)
    have_voice = conn.vad.is_vad(conn, audio)
    # Nếu thiết bị vừa được đánh thức, tạm thời bỏ qua VAD (tránh nhận diện nhầm tiếng khởi động)
    if hasattr(conn, "just_woken_up") and conn.just_woken_up:
        have_voice = False
        # Đặt một độ trễ ngắn sau đó khôi phục lại VAD
        if not hasattr(conn, "vad_resume_task") or conn.vad_resume_task.done():
            conn.vad_resume_task = asyncio.create_task(resume_vad_detection(conn))
        return
    # Trong chế độ giám sát (manual) không được cắt ngang âm thanh đang phát
    if have_voice:
        if conn.client_is_speaking and conn.client_listen_mode != "manual":
            await handleAbortMessage(conn)
    # Kiểm tra thời gian nhàn rỗi lâu để tự động chào tạm biệt
    await no_voice_close_connect(conn, have_voice)
    # Nhận và xử lý âm thanh vào nhận diện giọng nói (ASR)
    await conn.asr.receive_audio(conn, audio, have_voice)


async def resume_vad_detection(conn: "ConnectionHandler"):
    # Đợi 2 giây sau đó khôi phục tính năng nhận diện giọng nói VAD
    await asyncio.sleep(2)
    conn.just_woken_up = False


async def startToChat(conn: "ConnectionHandler", text):
    # Kiểm tra xem đầu vào có phải là JSON (có chứa thông tin người nói) không
    speaker_name = None
    language_tag = None
    actual_text = text

    try:
        # Thử phân tích JSON
        if text.strip().startswith("{") and text.strip().endswith("}"):
            data = json.loads(text)
            if "speaker" in data and "content" in data:
                speaker_name = data["speaker"]
                language_tag = data["language"]
                actual_text = data["content"]
                conn.logger.bind(tag=TAG).info(f"Phân tích được người nói: {speaker_name}")

                # Sử dụng text có định dạng json một cách trực tiếp thay vì bóc tách text
                actual_text = text
    except (json.JSONDecodeError, KeyError):
        # Thiết lập thất bại, tiếp tục dùng văn bản thực tế
        pass

    # Bộ lọc ảo giác Whisper (Hallucination Filter)
    asr_config = conn.config.get("ASR", {}).get(conn.config.get("selected_module", {}).get("ASR", ""), {})
    filters = asr_config.get("hallucination_filters", [])
    for f in filters:
        if f.lower() in actual_text.lower():
            conn.logger.bind(tag=TAG).warning(f"Phát hiện ảo giác ASR: '{actual_text}' (khớp filter: '{f}'). Hủy xử lý.")
            # Thông báo cho người dùng là không nghe rõ thay vì trả lời lạc đề
            error_text = "Dạ, em nghe không rõ, ba mẹ nói lại giúp em nhé!"
            await send_stt_message(conn, error_text)
            conn.executor.submit(conn.chat, error_text)
            return

    # Lưu thông tin người nói xuống object kết nối
    if speaker_name:
        conn.current_speaker = speaker_name
    else:
        conn.current_speaker = None

    if conn.need_bind:
        await check_bind_device(conn)
        return

    # Nếu số lượng ký tự đầu ra vượt giới hạn ngày
    if conn.max_output_size > 0:
        if check_device_output_limit(
            conn.headers.get("device-id"), conn.max_output_size
        ):
            await max_out_size(conn)
            return
    # Trong chế độ manual sẽ không ngắt lời đang nói
    if conn.client_is_speaking and conn.client_listen_mode != "manual":
        await handleAbortMessage(conn)

    # Đầu tiên thực hiện phân tích Intent bằng nội dung thực tế
    intent_handled = await handle_user_intent(conn, actual_text)

    if intent_handled:
        # Nếu đã xử lý Intent bên trong (như bật nhạc, v.v), thì không chat tiếp với bot
        return

    # Không đúng ý định rẽ nhánh thì cứ tiếp tục gửi quy trình trò chuyện như thường cho LLM
    await send_stt_message(conn, actual_text)
    conn.executor.submit(conn.chat, actual_text)


async def no_voice_close_connect(conn: "ConnectionHandler", have_voice):
    if have_voice:
        conn.last_activity_time = time.time() * 1000
        return
    # Chỉ khi mốc thời gian đã được thiết lập mới bắt đầu đếm giờ kiểm tra Timeout
    if conn.last_activity_time > 0.0:
        no_voice_time = time.time() * 1000 - conn.last_activity_time
        close_connection_no_voice_time = int(
            conn.config.get("close_connection_no_voice_time", 120)
        )
        if (
            not conn.close_after_chat
            and no_voice_time > 1000 * close_connection_no_voice_time
        ):
            conn.close_after_chat = True
            conn.client_abort = False
            end_prompt = conn.config.get("end_prompt", {})
            if end_prompt and end_prompt.get("enable", True) is False:
                conn.logger.bind(tag=TAG).info("Đóng kết nối, không cần đọc thông báo chào tạm biệt")
                await conn.close()
                return
            prompt = end_prompt.get("prompt")
            if not prompt:
                prompt = "Dạ ba mẹ ơi, em xin phép đi nghỉ một lát nhé, khi nào cần em cứ gọi 'Xin chào bé' là được ạ!"
            await startToChat(conn, prompt)


async def max_out_size(conn: "ConnectionHandler"):
    # Đọc thoại thông báo hết Token/vượt giới hạn ngày
    conn.client_abort = False
    text = "Dạ xin lỗi ba mẹ, hôm nay em đã nói chuyện hơi nhiều rồi. Hẹn ba mẹ dịp khác em lại tâm sự tiếp nhé!"
    await send_stt_message(conn, text)
    file_path = f"{ASSETS_DIR}/max_output_size.wav"
    opus_packets = await audio_to_data(file_path)
    conn.tts.tts_audio_queue.put((SentenceType.LAST, opus_packets, text))
    conn.close_after_chat = True


async def check_bind_device(conn: "ConnectionHandler"):
    if conn.bind_code:
        # Check bind_code phải đủ 6 ký tự
        # Check if bind_code has 6 characters
        if len(conn.bind_code) != 6:
            conn.logger.bind(tag=TAG).error(f"Invalid bind_code format: {conn.bind_code}")
            text = "Dạ có lỗi định dạng mã kết nối, ba mẹ vui lòng kiểm tra lại cấu hình nhé."
            await send_stt_message(conn, text)
            return

        text = f"Dạ, anh chị vui lòng đăng nhập để điều khiển, nhập mã {conn.bind_code} và kết nối lại thiết bị nhé."
        await send_stt_message(conn, text)

        # Play notification sound
        music_path = f"{ASSETS_DIR}/bind_code.wav"
        opus_packets = await audio_to_data(music_path)
        conn.tts.tts_audio_queue.put((SentenceType.FIRST, opus_packets, text))

        # Đọc từng số trong mã
        for i in range(6):  # Chắc chắn có 6 số
            try:
                digit = conn.bind_code[i]
                num_path = f"config/assets/bind_code/{digit}.wav"
                num_packets = await audio_to_data(num_path)
                conn.tts.tts_audio_queue.put((SentenceType.MIDDLE, num_packets, None))
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"Lỗi âm thanh thông báo file số: {e}")
                continue
        conn.tts.tts_audio_queue.put((SentenceType.LAST, [], None))
    else:
        # Thông báo lỗi ko có thông tin cập nhật thiết bị gốc
        conn.client_abort = False
        text = f"Dạ em không tìm thấy phiên bản này, anh chị vui lòng kiểm tra lại tệp cập nhật nhé."
        await send_stt_message(conn, text)
        music_path = "config/assets/bind_not_found.wav"
        opus_packets = await audio_to_data(music_path)
        conn.tts.tts_audio_queue.put((SentenceType.LAST, opus_packets, text))
