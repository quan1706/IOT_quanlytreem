import json
import time
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from core.utils import textUtils
from core.utils.util import audio_to_data
from core.providers.tts.dto.dto import SentenceType
from core.utils.audioRateController import AudioRateController

TAG = __name__
# Khoảng thời gian cho mỗi frame âm thanh (mili-giây)
AUDIO_FRAME_DURATION = 60
# Số lượng gói chờ trước khi phát, gửi thẳng để giảm độ trễ
PRE_BUFFER_COUNT = 5


async def sendAudioMessage(conn: "ConnectionHandler", sentenceType, audios, text):
    if conn.tts.tts_audio_first_sentence:
        conn.logger.bind(tag=TAG).info(f"Đang gửi câu nói bộ đệm đầu tiên: {text}")
        conn.tts.tts_audio_first_sentence = False
        await send_tts_message(conn, "start", None)

    if sentenceType == SentenceType.FIRST:
        # Xếp các gói âm thanh sau của cùng câu nói vào hàng đợi kiểm soát, các gói khác gửi thẳng
        if (
            hasattr(conn, "audio_rate_controller")
            and conn.audio_rate_controller
            and getattr(conn, "audio_flow_control", {}).get("sentence_id")
            == conn.sentence_id
        ):
            conn.audio_rate_controller.add_message(
                lambda: send_tts_message(conn, "sentence_start", text)
            )
        else:
            # Câu mới hoặc chưa khởi tạo kiểm soát luồng, Gửi ngay lập tức
            await send_tts_message(conn, "sentence_start", text)

    await sendAudio(conn, audios)
    # Gửi tín hiệu báo hiệu bắt đầu đọc
    if sentenceType is not SentenceType.MIDDLE:
        conn.logger.bind(tag=TAG).info(f"Gửi khung âm thanh: {sentenceType}, {text}")

    # Gửi tín hiệu kết thúc đoạn đọc (Nếu là đoạn text cuối)
    if sentenceType == SentenceType.LAST:
        await send_tts_message(conn, "stop", None)
        conn.client_is_speaking = False
        if conn.close_after_chat:
            await conn.close()


async def _wait_for_audio_completion(conn: "ConnectionHandler"):
    """
    Đợi hàng đợi âm thanh rỗng và đợi cho gói đệm (pre-buffer) chạy xong

    Args:
        conn: đối tượng ConnectionHandler
    """
    if hasattr(conn, "audio_rate_controller") and conn.audio_rate_controller:
        rate_controller = conn.audio_rate_controller
        conn.logger.bind(tag=TAG).debug(
            f"Đang chờ phát xong audio, hàng đợi còn {len(rate_controller.queue)} cục"
        )
        await rate_controller.queue_empty_event.wait()

        # Cho phép các gói đệm phát hết
        # Gói đầu gửi luôn, bù trừ mạng 2 gói, tính toán thời gian trễ
        frame_duration_ms = rate_controller.frame_duration
        pre_buffer_playback_time = (PRE_BUFFER_COUNT + 2) * frame_duration_ms / 1000.0
        await asyncio.sleep(pre_buffer_playback_time)

        conn.logger.bind(tag=TAG).debug("Phát file âm thanh hoàn tất")


async def _send_to_mqtt_gateway(
    conn: "ConnectionHandler", opus_packet, timestamp, sequence
):
    """
    Gửi gói âm thanh OPUS với 16-byte header tới mqtt_gateway
    Args:
        conn: Tham chiếu tới ConnectionHandler
        opus_packet: Gói dữ liệu opus
        timestamp: Dấu thời gian (timestamp)
        sequence: Số thứ tự (sequence)
    """
    # Thêm 16-byte header cho gói opus
    header = bytearray(16)
    header[0] = 1  # loại (type)
    header[2:4] = len(opus_packet).to_bytes(2, "big")  # chiều dài dữ liệu (payload length)
    header[4:8] = sequence.to_bytes(4, "big")  # số thứ tự (sequence)
    header[8:12] = timestamp.to_bytes(4, "big")  # dấu thời gian (timestamp)
    header[12:16] = len(opus_packet).to_bytes(4, "big")  # chiều dài opus (opus length)

    # Gửi gói hoàn chỉnh kèm header
    complete_packet = bytes(header) + opus_packet
    await conn.websocket.send(complete_packet)


async def sendAudio(
    conn: "ConnectionHandler", audios, frame_duration=AUDIO_FRAME_DURATION
):
    """
    Gửi gói âm thanh, dùng AudioRateController để điều khiển tốc độ mạng mượt mà

    Args:
        conn: Tham chiếu ConnectionHandler
        audios: Một gói opus đơn (bytes) HOẶC danh sách các gói opus
        frame_duration: Độ dài một frame (mili-giây), mặc định là AUDIO_FRAME_DURATION
    """
    if audios is None or len(audios) == 0:
        return

    send_delay = conn.config.get("tts_audio_send_delay", -1) / 1000.0
    is_single_packet = isinstance(audios, bytes)

    # Khởi tạo hoặc lấy đối tượng RateController
    rate_controller, flow_control = _get_or_create_rate_controller(
        conn, frame_duration, is_single_packet
    )

    # Chuyển đổi về list để xử lý cho đồng nhất
    audio_list = [audios] if is_single_packet else audios

    # Đẩy audio vào hàm xử lý gửi
    await _send_audio_with_rate_control(
        conn, audio_list, rate_controller, flow_control, send_delay
    )


def _get_or_create_rate_controller(
    conn: "ConnectionHandler", frame_duration, is_single_packet
):
    """
    Lấy đối tượng quản lý lưu lượng (RateController), hoặc tạo mới

    Args:
        conn: ConnectionHandler
        frame_duration: Độ dài frame
        is_single_packet: Có phải gói đơn không? (True: stream từng cục TTS, False: batch nhiều cục)

    Returns:
        (rate_controller, flow_control)
    """
    # Cờ kiểm tra có cần reset controller hay không
    need_reset = False

    if not hasattr(conn, "audio_rate_controller"):
        # Controller không tồn tại -> báo reset
        need_reset = True
    else:
        rate_controller = conn.audio_rate_controller

        # Task chạy ngầm đã dừng -> báo reset
        if (
            not rate_controller.pending_send_task
            or rate_controller.pending_send_task.done()
        ):
            need_reset = True
        # Sentence_id thay đổi (đọc câu khác) -> báo reset
        elif (
            getattr(conn, "audio_flow_control", {}).get("sentence_id")
            != conn.sentence_id
        ):
            need_reset = True

    if need_reset:
        # Khởi tạo rate_controller mới
        if not hasattr(conn, "audio_rate_controller"):
            conn.audio_rate_controller = AudioRateController(frame_duration)
        else:
            conn.audio_rate_controller.reset()

        # Khởi tạo flow_control state
        conn.audio_flow_control = {
            "packet_count": 0,
            "sequence": 0,
            "sentence_id": conn.sentence_id,
        }

        # Khởi tạo tiến trình chạy nền _start_background_sender
        _start_background_sender(
            conn, conn.audio_rate_controller, conn.audio_flow_control
        )

    return conn.audio_rate_controller, conn.audio_flow_control


def _start_background_sender(conn: "ConnectionHandler", rate_controller, flow_control):
    """
    Khởi động vòng lặp gửi ngầm

    Args:
        conn: Tham chiếu ConnectionHandler
        rate_controller: Controller điều tốc mạng
        flow_control: Controller quản lý gói
    """

    async def send_callback(packet):
        # Kiểm tra Client có gửi tín hiệu hủy không
        if conn.client_abort:
            raise asyncio.CancelledError("Client đã ngắt (Abort)")

        conn.last_activity_time = time.time() * 1000
        await _do_send_audio(conn, packet, flow_control)
        conn.client_is_speaking = True

    # Dùng start_sending để kích hoạt vòng lặp gọi queue lấy data bắn đi
    rate_controller.start_sending(send_callback)


async def _send_audio_with_rate_control(
    conn: "ConnectionHandler", audio_list, rate_controller, flow_control, send_delay
):
    """
    Sử dụng rate_controller để gửi audio êm ái hơn

    Args:
        conn: Tham chiếu tới ConnectionHandler
        audio_list: Danh sách gói tin âm thanh
        rate_controller: Điều tốc mạng 
        flow_control: Trạng thái luồng
        send_delay: Trễ cố định (giây), -1 là quản lý tự động (dynamic)
    """
    for packet in audio_list:
        if conn.client_abort:
            return

        conn.last_activity_time = time.time() * 1000

        # Pre-buffer: gửi thẳng những gói đầu tiên để triệt tiêu Ping / Lag trễ
        if flow_control["packet_count"] < PRE_BUFFER_COUNT:
            await _do_send_audio(conn, packet, flow_control)
            conn.client_is_speaking = True
        elif send_delay > 0:
            # Gửi theo Delay cố định
            await asyncio.sleep(send_delay)
            await _do_send_audio(conn, packet, flow_control)
            conn.client_is_speaking = True
        else:
            # Gửi theo Chế độ Động: chỉ bỏ vào hàng đợi cho tiến trình gửi nền tự bắn
            rate_controller.add_audio(packet)


async def _do_send_audio(conn: "ConnectionHandler", opus_packet, flow_control):
    """
    Thực thi việc push bắn gói tin qua websocket ra socket mạng
    """
    packet_index = flow_control.get("packet_count", 0)
    sequence = flow_control.get("sequence", 0)

    if conn.conn_from_mqtt_gateway:
        # Cập nhật Timestamp đối với các client qua gateway
        start_time = time.time()
        timestamp = int(start_time * 1000) % (2**32)
        await _send_to_mqtt_gateway(conn, opus_packet, timestamp, sequence)
    else:
        # Kiểm tra xem Client (vd Arduino ESP32) có chỉ định output pcm do không giải mã được Opus không
        if getattr(conn, 'audio_format', 'opus') == 'pcm':
            try:
                import opuslib_next
                sr = getattr(conn, 'sample_rate', 24000)
                if not hasattr(conn, '_opus_decoder'):
                    conn._opus_decoder = opuslib_next.Decoder(sr, 1)
                frame_size = int(sr * 60 / 1000)  # 1440 samples cho 60ms@24kHz
                pcm_data = conn._opus_decoder.decode(opus_packet, frame_size)
                await conn.websocket.send(pcm_data)
            except Exception as e:
                conn.logger.bind(tag="sendAudio").error(f"Lỗi giải mã Opus->PCM: {e}")
                await conn.websocket.send(opus_packet)
        else:
            # Gửi thẳng file định dạng Opus
            await conn.websocket.send(opus_packet)

    # Cập nhật thứ tự gói
    flow_control["packet_count"] = packet_index + 1
    flow_control["sequence"] = sequence + 1


async def send_tts_message(conn: "ConnectionHandler", state, text=None):
    """Gửi trạng thái TTS xuống thiết bị"""
    if text is None and state == "sentence_start":
        return
    message = {"type": "tts", "state": state, "session_id": conn.session_id}
    if text is not None:
        message["text"] = textUtils.check_emoji(text)

    # Kết thúc phát TTS
    if state == "stop":
        # Chơi file âm thanh báo hiệu dứt câu
        tts_notify = conn.config.get("enable_stop_tts_notify", False)
        if tts_notify:
            stop_tts_notify_voice = conn.config.get(
                "stop_tts_notify_voice", "config/assets/tts_notify.mp3"
            )
            audios = await audio_to_data(stop_tts_notify_voice, is_opus=True)
            await sendAudio(conn, audios)
        # Chờ toàn bộ gói được gửi đi khỏi bộ nhớ
        await _wait_for_audio_completion(conn)
        # Xoá trạng thái nói trên máy chủ
        conn.clearSpeakStatus()

    # Nhả ra websocket cho TBN
    await conn.websocket.send(json.dumps(message))


async def send_stt_message(conn: "ConnectionHandler", text):
    """Gửi khung log văn bản lên màn hình ESP32 (STT) """
    end_prompt_str = conn.config.get("end_prompt", {}).get("prompt")
    if end_prompt_str and end_prompt_str == text:
        await send_tts_message(conn, "start")
        return

    # Phân tích chuỗi đầu vào theo JSON, chiết xuất dữ liệu voice thô
    display_text = text
    try:
        # Thử ép qua parser JSON
        if text.strip().startswith("{") and text.strip().endswith("}"):
            parsed_data = json.loads(text)
            if isinstance(parsed_data, dict) and "content" in parsed_data:
                # Nếu chuỗi JSON có nhiều data dư thừa, chỉ bóc tag 'content' ra để in
                display_text = parsed_data["content"]
                # Cập nhật tên người nói vào phiên bản nối kết ConnectionHandler
                if "speaker" in parsed_data:
                    conn.current_speaker = parsed_data["speaker"]
    except (json.JSONDecodeError, TypeError):
        # Nếu đó chỉ là một string không hỗ trợ JSON thì cứ lấy y bản gốc
        display_text = text
    stt_text = textUtils.get_string_no_punctuation_or_emoji(display_text)
    await conn.websocket.send(
        json.dumps({"type": "stt", "text": stt_text, "session_id": conn.session_id})
    )
    await send_tts_message(conn, "start")
