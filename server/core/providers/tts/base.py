import os
import re
import uuid
import queue
import asyncio
import threading
import traceback

from core.utils import p3
from datetime import datetime
from core.utils import textUtils
from typing import Callable, Any
from abc import ABC, abstractmethod
from config.logger import setup_logging
from core.utils import opus_encoder_utils
from core.utils.tts import MarkdownCleaner, convert_percentage_to_range
from core.utils.output_counter import add_device_output
from core.handle.reportHandle import enqueue_tts_report
from core.handle.sendAudioHandle import sendAudioMessage
from core.utils.util import audio_bytes_to_data_stream, audio_to_data_stream
from core.providers.tts.dto.dto import (
    TTSMessageDTO,
    SentenceType,
    ContentType,
    InterfaceType,
)

TAG = __name__
logger = setup_logging()


class TTSProviderBase(ABC):
    def __init__(self, config, delete_audio_file):
        self.interface_type = InterfaceType.NON_STREAM
        self.conn = None
        self.delete_audio_file = delete_audio_file
        self.audio_file_type = "wav"
        self.output_file = config.get("output_dir", "tmp/")
        self.tts_text_queue = queue.Queue()
        self.tts_audio_queue = queue.Queue()
        self.tts_audio_first_sentence = True
        self.before_stop_play_files = []

        self.tts_text_buff = []
        self.punctuations = (
            "。",
            "？",
            "?",
            "！",
            "!",
            "；",
            ";",
            "：",
        )
        self.first_sentence_punctuations = (
            "，",
            "~",
            "、",
            ",",
            "。",
            "？",
            "?",
            "！",
            "!",
            "；",
            ";",
            "：",
        )
        self.tts_stop_request = False
        self.processed_chars = 0
        self.is_first_sentence = True

    def generate_filename(self, extension=".wav"):
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    def handle_opus(self, opus_data: bytes):
        logger.bind(tag=TAG).debug(f"Đẩy dữ liệu vào hàng đợi, số khung hình ~~ {len(opus_data)}")
        self.tts_audio_queue.put((SentenceType.MIDDLE, opus_data, None))

    def handle_audio_file(self, file_audio: bytes, text):
        self.before_stop_play_files.append((file_audio, text))

    def to_tts_stream(self, text, opus_handler: Callable[[bytes], None] = None) -> None:
        text = MarkdownCleaner.clean_markdown(text)
        if not text or not text.strip():
            return None
        max_repeat_time = 5
        if self.delete_audio_file:
            # 需要删除文件的直接转为音频数据
            while max_repeat_time > 0:
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.text_to_speak(text, None), self.conn.loop
                    )
                    audio_bytes = future.result()
                    if audio_bytes:
                        self.tts_audio_queue.put((SentenceType.FIRST, None, text))
                        audio_bytes_to_data_stream(
                            audio_bytes,
                            file_type=self.audio_file_type,
                            is_opus=True,
                            callback=opus_handler,
                            sample_rate=self.conn.sample_rate,
                            opus_encoder=self.opus_encoder,
                        )
                        break
                    else:
                        max_repeat_time -= 1
                except Exception as e:
                    logger.bind(tag=TAG).warning(
                        f"Tạo giọng nói thất bại lần thứ {5 - max_repeat_time + 1}: {text}, lỗi: {e}"
                    )
                    max_repeat_time -= 1
            if max_repeat_time > 0:
                logger.bind(tag=TAG).info(
                    f"Tạo giọng nói thành công: {text}, thử lại {5 - max_repeat_time} lần"
                )
            else:
                logger.bind(tag=TAG).error(
                    f"Tạo giọng nói thất bại: {text}, vui lòng kiểm tra mạng hoặc dịch vụ"
                )
            return None
        else:
            tmp_file = self.generate_filename()
            try:
                while not os.path.exists(tmp_file) and max_repeat_time > 0:
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self.text_to_speak(text, tmp_file), self.conn.loop
                        )
                        future.result()
                    except Exception as e:
                        logger.bind(tag=TAG).warning(
                            f"Tạo giọng nói thất bại lần thứ {5 - max_repeat_time + 1}: {text}, lỗi: {e}"
                        )
                        # Tạo thất bại, xóa tệp
                        if os.path.exists(tmp_file):
                            os.remove(tmp_file)
                        max_repeat_time -= 1

                if max_repeat_time > 0:
                    logger.bind(tag=TAG).info(
                        f"Tạo giọng nói thành công: {text}:{tmp_file}, thử lại {5 - max_repeat_time} lần"
                    )
                else:
                    logger.bind(tag=TAG).error(
                        f"Tạo giọng nói thất bại: {text}, vui lòng kiểm tra mạng hoặc dịch vụ"
                    )
                self.tts_audio_queue.put((SentenceType.FIRST, None, text))
                self._process_audio_file_stream(tmp_file, callback=opus_handler)
            except Exception as e:
                logger.bind(tag=TAG).error(f"Failed to generate TTS file: {e}")
                return None
    
    def to_tts(self, text):
        text = MarkdownCleaner.clean_markdown(text)
        if not text or not text.strip():
            return None
        max_repeat_time = 5
        if self.delete_audio_file:
            # 需要删除文件的直接转为音频数据
            while max_repeat_time > 0:
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.text_to_speak(text, None), self.conn.loop
                    )
                    audio_bytes = future.result()
                    if audio_bytes:
                        audio_datas = []
                        audio_bytes_to_data_stream(
                            audio_bytes,
                            file_type=self.audio_file_type,
                            is_opus=True,
                            callback=lambda data: audio_datas.append(data),
                            sample_rate=self.conn.sample_rate,
                        )
                        return audio_datas
                    else:
                        max_repeat_time -= 1
                except Exception as e:
                    logger.bind(tag=TAG).warning(
                        f"Tạo giọng nói thất bại lần thứ {5 - max_repeat_time + 1}: {text}, lỗi: {e}"
                    )
                    max_repeat_time -= 1
            if max_repeat_time > 0:
                logger.bind(tag=TAG).info(
                    f"Tạo giọng nói thành công: {text}, thử lại {5 - max_repeat_time} lần"
                )
            else:
                logger.bind(tag=TAG).error(
                    f"Tạo giọng nói thất bại: {text}, vui lòng kiểm tra mạng hoặc dịch vụ"
                )
            return None
        else:
            tmp_file = self.generate_filename()
            try:
                while not os.path.exists(tmp_file) and max_repeat_time > 0:
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self.text_to_speak(text, tmp_file), self.conn.loop
                        )
                        future.result()
                    except Exception as e:
                        logger.bind(tag=TAG).warning(
                            f"Tạo giọng nói thất bại lần thứ {5 - max_repeat_time + 1}: {text}, lỗi: {e}"
                        )
                        # Tạo thất bại, xóa tệp
                        if os.path.exists(tmp_file):
                            os.remove(tmp_file)
                        max_repeat_time -= 1

                if max_repeat_time > 0:
                    logger.bind(tag=TAG).info(
                        f"Tạo giọng nói thành công: {text}:{tmp_file}, thử lại {5 - max_repeat_time} lần"
                    )
                else:
                    logger.bind(tag=TAG).error(
                        f"Tạo giọng nói thất bại: {text}, vui lòng kiểm tra mạng hoặc dịch vụ"
                    )

                return tmp_file
            except Exception as e:
                logger.bind(tag=TAG).error(f"Failed to generate TTS file: {e}")
                return None

    @abstractmethod
    async def text_to_speak(self, text, output_file):
        pass

    def audio_to_pcm_data_stream(
        self, audio_file_path, callback: Callable[[Any], Any] = None
    ):
        """Chuyển đổi tệp âm thanh sang mã hóa PCM"""
        return audio_to_data_stream(audio_file_path, is_opus=False, callback=callback, sample_rate=self.conn.sample_rate, opus_encoder=None)

    def audio_to_opus_data_stream(
        self, audio_file_path, callback: Callable[[Any], Any] = None
    ):
        """Chuyển đổi tệp âm thanh sang mã hóa Opus"""
        return audio_to_data_stream(audio_file_path, is_opus=True, callback=callback, sample_rate=self.conn.sample_rate, opus_encoder=self.opus_encoder)

    def tts_one_sentence(
        self,
        conn,
        content_type,
        content_detail=None,
        content_file=None,
        sentence_id=None,
    ):
        """Gửi một câu"""
        if not sentence_id:
            if conn.sentence_id:
                sentence_id = conn.sentence_id
            else:
                sentence_id = str(uuid.uuid4().hex)
                conn.sentence_id = sentence_id
        # Đối với văn bản câu đơn, thực hiện xử lý phân đoạn
        segments = re.split(r"([。！？!?；;\n])", content_detail)
        for seg in segments:
            self.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=content_type,
                    content_detail=seg,
                    content_file=content_file,
                )
            )

    async def open_audio_channels(self, conn):
        self.conn = conn

        # 根据conn的sample_rate创建编码器，如果子类已经创建则不覆盖（IndexTTS接口返回为24kHZ-待重采样处理）
        if not hasattr(self, 'opus_encoder') or self.opus_encoder is None:
            self.opus_encoder = opus_encoder_utils.OpusEncoderUtils(
                sample_rate=conn.sample_rate, channels=1, frame_size_ms=60
            )
 
        # Luồng xử lý tts
        self.tts_priority_thread = threading.Thread(
            target=self.tts_text_priority_thread, daemon=True
        )
        self.tts_priority_thread.start()
 
        # Luồng xử lý phát âm thanh
        self.audio_play_priority_thread = threading.Thread(
            target=self._audio_play_priority_thread, daemon=True
        )
        self.audio_play_priority_thread.start()
 
    # Ở đây mặc định là phương thức xử lý phi luồng (non-streaming)
    # Phương thức xử lý luồng vui lòng ghi đè trong lớp con
    def tts_text_priority_thread(self):
        while not self.conn.stop_event.is_set():
            try:
                message = self.tts_text_queue.get(timeout=1)
                if message.sentence_type == SentenceType.FIRST:
                    self.conn.client_abort = False
                if self.conn.client_abort:
                    logger.bind(tag=TAG).info("Nhận được thông báo ngắt, kết thúc luồng xử lý văn bản TTS")
                    continue
                if message.sentence_type == SentenceType.FIRST:
                    # Khởi tạo tham số
                    self.tts_stop_request = False
                    self.processed_chars = 0
                    self.tts_text_buff = []
                    self.is_first_sentence = True
                    self.tts_audio_first_sentence = True
                elif ContentType.TEXT == message.content_type:
                    self.tts_text_buff.append(message.content_detail)
                    segment_text = self._get_segment_text()
                    if segment_text:
                        self.to_tts_stream(segment_text, opus_handler=self.handle_opus)
                elif ContentType.FILE == message.content_type:
                    self._process_remaining_text_stream(opus_handler=self.handle_opus)
                    tts_file = message.content_file
                    if tts_file and os.path.exists(tts_file):
                        self._process_audio_file_stream(
                            tts_file, callback=self.handle_opus
                        )
                if message.sentence_type == SentenceType.LAST:
                    self._process_remaining_text_stream(opus_handler=self.handle_opus)
                    self.tts_audio_queue.put(
                        (message.sentence_type, [], message.content_detail)
                    )

            except queue.Empty:
                continue
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"Xử lý văn bản TTS thất bại: {str(e)}, loại: {type(e).__name__}, stack: {traceback.format_exc()}"
                )
                continue

    def _audio_play_priority_thread(self):
        # Danh sách văn bản và âm thanh cần báo cáo
        enqueue_text = None
        enqueue_audio = None
        while not self.conn.stop_event.is_set():
            text = None
            try:
                try:
                    sentence_type, audio_datas, text = self.tts_audio_queue.get(
                        timeout=0.1
                    )
                except queue.Empty:
                    if self.conn.stop_event.is_set():
                        break
                    continue

                if self.conn.client_abort:
                    logger.bind(tag=TAG).debug("Nhận được tín hiệu ngắt, bỏ qua dữ liệu âm thanh hiện tại")
                    enqueue_text, enqueue_audio = None, []
                    continue

                # Báo cáo khi nhận được văn bản tiếp theo bắt đầu hoặc kết thúc phiên
                if sentence_type is not SentenceType.MIDDLE:
                    # Báo cáo dữ liệu TTS
                    if enqueue_text is not None and enqueue_audio is not None:
                        enqueue_tts_report(self.conn, enqueue_text, enqueue_audio)
                    enqueue_audio = []
                    enqueue_text = text

                # Thu thập dữ liệu âm thanh báo cáo
                if isinstance(audio_datas, bytes) and enqueue_audio is not None:
                    enqueue_audio.append(audio_datas)
 
                # Gửi âm thanh
                future = asyncio.run_coroutine_threadsafe(
                    sendAudioMessage(self.conn, sentence_type, audio_datas, text),
                    self.conn.loop,
                )
                future.result()
 
                # Ghi lại đầu ra và báo cáo
                if self.conn.max_output_size > 0 and text:
                    add_device_output(self.conn.headers.get("device-id"), len(text))

            except Exception as e:
                logger.bind(tag=TAG).error(f"audio_play_priority_thread: {text} {e}")

    async def start_session(self, session_id):
        pass

    async def finish_session(self, session_id):
        pass

    async def close(self):
        """Phương thức dọn dẹp tài nguyên"""
        if hasattr(self, "ws") and self.ws:
            await self.ws.close()

    def _get_segment_text(self):
        # Hợp nhất văn bản hiện tại và xử lý phần chưa phân đoạn
        full_text = "".join(self.tts_text_buff)
        current_text = full_text[self.processed_chars :]  # 从未处理的位置开始
        last_punct_pos = -1

        # Chọn tập hợp dấu câu khác nhau tùy theo đó có phải câu đầu tiên hay không
        punctuations_to_use = (
            self.first_sentence_punctuations
            if self.is_first_sentence
            else self.punctuations
        )

        for punct in punctuations_to_use:
            pos = current_text.rfind(punct)
            if (pos != -1 and last_punct_pos == -1) or (
                pos != -1 and pos < last_punct_pos
            ):
                last_punct_pos = pos

        if last_punct_pos != -1:
            segment_text_raw = current_text[: last_punct_pos + 1]
            segment_text = textUtils.get_string_no_punctuation_or_emoji(
                segment_text_raw
            )
            self.processed_chars += len(segment_text_raw)  # 更新已处理字符位置

            # Nếu là câu đầu tiên, sau khi tìm thấy dấu phẩy đầu tiên, đặt cờ thành False
            if self.is_first_sentence:
                self.is_first_sentence = False

            return segment_text
        elif self.tts_stop_request and current_text:
            segment_text = current_text
            self.is_first_sentence = True  # Đặt lại cờ
            return segment_text
        else:
            return None

    def _process_audio_file_stream(
        self, tts_file, callback: Callable[[Any], Any]
    ) -> None:
        """Xử lý tệp âm thanh và chuyển đổi sang định dạng đã chỉ định

        Args:
            tts_file: Đường dẫn tệp âm thanh
            callback: Hàm xử lý tệp
        """
        if tts_file.endswith(".p3"):
            p3.decode_opus_from_file_stream(tts_file, callback=callback)
        elif self.conn.audio_format == "pcm":
            self.audio_to_pcm_data_stream(tts_file, callback=callback)
        else:
            self.audio_to_opus_data_stream(tts_file, callback=callback)

        if (
            self.delete_audio_file
            and tts_file is not None
            and os.path.exists(tts_file)
            and tts_file.startswith(self.output_file)
        ):
            os.remove(tts_file)

    def _process_before_stop_play_files(self):
        for audio_datas, text in self.before_stop_play_files:
            self.tts_audio_queue.put((SentenceType.MIDDLE, audio_datas, text))
        self.before_stop_play_files.clear()
        self.tts_audio_queue.put((SentenceType.LAST, [], None))

    def _process_remaining_text_stream(
        self, opus_handler: Callable[[bytes], None] = None
    ):
        """Xử lý văn bản còn lại và tạo giọng nói

        Returns:
            bool: Có xử lý văn bản thành công không
        """
        full_text = "".join(self.tts_text_buff)
        remaining_text = full_text[self.processed_chars :]
        if remaining_text:
            segment_text = textUtils.get_string_no_punctuation_or_emoji(remaining_text)
            if segment_text:
                self.to_tts_stream(segment_text, opus_handler=opus_handler)
                self.processed_chars += len(full_text)
                return True
        return False

    def _apply_percentage_params(self, config):
        """Áp dụng hàng loạt tham số phần trăm theo TTS_PARAM_CONFIG được định nghĩa trong lớp con"""
        for config_key, attr_name, min_val, max_val, base_val, transform in self.TTS_PARAM_CONFIG:
            if config_key in config:
                val = convert_percentage_to_range(config[config_key], min_val, max_val, base_val)
                setattr(self, attr_name, transform(val) if transform else val)
