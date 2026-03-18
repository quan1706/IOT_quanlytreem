import os
import io
import wave
import uuid
import json
import time
import queue
import shutil
import asyncio
import tempfile
import traceback
import threading
import opuslib_next

from abc import ABC, abstractmethod
from config.logger import setup_logging
from core.providers.asr.dto.dto import InterfaceType
from core.handle.receiveAudioHandle import startToChat
from core.handle.reportHandle import enqueue_asr_report
from core.utils.util import remove_punctuation_and_length
from core.handle.receiveAudioHandle import handleAudioMessage
from typing import Optional, Tuple, List, NamedTuple, TYPE_CHECKING


if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()


class ASRProviderBase(ABC):
    def __init__(self):
        pass

    # Mở kênh âm thanh
    async def open_audio_channels(self, conn: "ConnectionHandler"):
        conn.asr_priority_thread = threading.Thread(
            target=self.asr_text_priority_thread, args=(conn,), daemon=True
        )
        conn.asr_priority_thread.start()

    # Xử lý có thứ tự âm thanh ASR
    def asr_text_priority_thread(self, conn: "ConnectionHandler"):
        while not conn.stop_event.is_set():
            try:
                message = conn.asr_audio_queue.get(timeout=1)
                future = asyncio.run_coroutine_threadsafe(
                    handleAudioMessage(conn, message),
                    conn.loop,
                )
                future.result()
            except queue.Empty:
                continue
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"Xử lý văn bản ASR thất bại: {str(e)}, loại: {type(e).__name__}, stack trace: {traceback.format_exc()}"
                )
                continue

    # Nhận âm thanh
    async def receive_audio(self, conn: "ConnectionHandler", audio, audio_have_voice):
        if conn.client_listen_mode == "manual":
            # Chế độ thủ công: Bộ đệm âm thanh dùng cho nhận diện ASR
            conn.asr_audio.append(audio)
        else:
            # Chế độ tự động/thời gian thực: Sử dụng phát hiện VAD
            conn.asr_audio.append(audio)

            # Nếu không có giọng nói và trước đó cũng không có âm thanh, lưu đệm một phần âm thanh
            if not audio_have_voice and not conn.client_have_voice:
                conn.asr_audio = conn.asr_audio[-10:]
                return

            # Kích hoạt nhận diện khi phát hiện dừng giọng nói qua VAD trong chế độ tự động
            if conn.asr.interface_type != InterfaceType.STREAM and conn.client_voice_stop:
                asr_audio_task = conn.asr_audio.copy()
                conn.reset_audio_states()

                if len(asr_audio_task) > 15:
                    await self.handle_voice_stop(conn, asr_audio_task)

    # Xử lý dừng giọng nói
    async def handle_voice_stop(self, conn: "ConnectionHandler", asr_audio_task: List[bytes]):
        """Xử lý song song ASR và nhận diện giọng nói"""
        try:
            total_start_time = time.monotonic()

            # Chuẩn bị dữ liệu âm thanh
            if conn.audio_format == "pcm":
                pcm_data = asr_audio_task
            else:
                pcm_data = self.decode_opus(asr_audio_task)

            combined_pcm_data = b"".join(pcm_data)

            # Chuẩn bị trước dữ liệu WAV
            wav_data = None
            if conn.voiceprint_provider and combined_pcm_data:
                wav_data = self._pcm_to_wav(combined_pcm_data)

            # Định nghĩa tác vụ ASR
            asr_task = self.speech_to_text_wrapper(
                asr_audio_task, conn.session_id, conn.audio_format
            )

            if conn.voiceprint_provider and wav_data:
                voiceprint_task = conn.voiceprint_provider.identify_speaker(
                    wav_data, conn.session_id
                )
                # Chờ đợi song song hai kết quả
                asr_result, voiceprint_result = await asyncio.gather(
                    asr_task, voiceprint_task, return_exceptions=True
                )
            else:
                asr_result = await asr_task
                voiceprint_result = None

            # Ghi lại kết quả nhận diện - Kiểm tra xem có phải ngoại lệ không
            if isinstance(asr_result, Exception):
                logger.bind(tag=TAG).error(f"Nhận diện ASR thất bại: {asr_result}")
                raw_text = ""
            else:
                raw_text, _ = asr_result

            if isinstance(voiceprint_result, Exception):
                logger.bind(tag=TAG).error(f"Nhận diện giọng nói thất bại: {voiceprint_result}")
                speaker_name = ""
            else:
                speaker_name = voiceprint_result

            # Xác định loại kết quả ASR
            if isinstance(raw_text, dict):
                # Định dạng dict trả về từ FunASR
                if speaker_name:
                    raw_text["speaker"] = speaker_name

                # Ghi lại kết quả nhận diện
                if raw_text.get("language"):
                    logger.bind(tag=TAG).info(f"Ngôn ngữ nhận diện: {raw_text['language']}")
                if raw_text.get("emotion"):
                    logger.bind(tag=TAG).info(f"Cảm xúc nhận diện: {raw_text['emotion']}")
                if raw_text.get("content"):
                    logger.bind(tag=TAG).info(f"Văn bản nhận diện: {raw_text['content']}")
                if speaker_name:
                    logger.bind(tag=TAG).info(f"Người nói nhận diện: {speaker_name}")

                # Chuyển đổi thành chuỗi JSON cho quy trình tiếp theo
                enhanced_text = json.dumps(raw_text, ensure_ascii=False)
                content_for_length_check = raw_text.get("content", "")
            else:
                # Văn bản thuần trả về từ các ASR khác
                if raw_text:
                    logger.bind(tag=TAG).info(f"Văn bản nhận diện: {raw_text}")
                if speaker_name:
                    logger.bind(tag=TAG).info(f"Người nói nhận diện: {speaker_name}")

                # Xây dựng chuỗi JSON chứa thông tin người nói
                enhanced_text = self._build_enhanced_text(raw_text, speaker_name)
                content_for_length_check = raw_text

            # Giám sát hiệu suất
            total_time = time.monotonic() - total_start_time
            logger.bind(tag=TAG).debug(f"Tổng thời gian xử lý: {total_time:.3f}s")

            # Kiểm tra độ dài văn bản
            text_len, _ = remove_punctuation_and_length(content_for_length_check)
            self.stop_ws_connection()

            if text_len > 0:
                # Sử dụng module tùy chỉnh để báo cáo
                await startToChat(conn, enhanced_text)
                audio_snapshot = asr_audio_task.copy()
                enqueue_asr_report(conn, enhanced_text, audio_snapshot)
        except Exception as e:
            logger.bind(tag=TAG).error(f"Xử lý dừng giọng nói thất bại: {e}")
            import traceback

            logger.bind(tag=TAG).debug(f"Chi tiết ngoại lệ: {traceback.format_exc()}")

    def _build_enhanced_text(self, text: str, speaker_name: Optional[str]) -> str:
        """Xây dựng văn bản chứa thông tin người nói (chỉ dùng cho ASR văn bản thuần)"""
        if speaker_name and speaker_name.strip():
            return json.dumps(
                {"speaker": speaker_name, "content": text}, ensure_ascii=False
            )
        else:
            return text

    def _pcm_to_wav(self, pcm_data: bytes) -> bytes:
        """Chuyển đổi dữ liệu PCM sang định dạng WAV"""
        if len(pcm_data) == 0:
            logger.bind(tag=TAG).warning("Dữ liệu PCM trống, không thể chuyển đổi sang WAV")
            return b""

        # Đảm bảo độ dài dữ liệu là số chẵn (âm thanh 16-bit)
        if len(pcm_data) % 2 != 0:
            pcm_data = pcm_data[:-1]

        # Tạo đầu tệp WAV
        wav_buffer = io.BytesIO()
        try:
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)  # Đơn kênh
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(16000)  # Tần số lấy mẫu 16kHz
                wav_file.writeframes(pcm_data)

            wav_buffer.seek(0)
            wav_data = wav_buffer.read()

            return wav_data
        except Exception as e:
            logger.bind(tag=TAG).error(f"Chuyển đổi WAV thất bại: {e}")
            return b""

    def stop_ws_connection(self):
        pass

    async def close(self):
        pass

    class AudioArtifacts(NamedTuple):
        pcm_frames: List[bytes]
        """Danh sách các khung âm thanh PCM"""
        pcm_bytes: bytes
        """Dữ liệu byte âm thanh PCM sau khi hợp nhất"""
        file_path: Optional[str]
        """Đường dẫn tệp WAV"""
        temp_path: Optional[str]
        """Đường dẫn tệp WAV tạm thời"""

    def get_current_artifacts(self) -> Optional["ASRProviderBase.AudioArtifacts"]:
        return self._current_artifacts

    def requires_file(self) -> bool:
        """Có cần nhập tệp không"""
        return False

    def prefers_temp_file(self) -> bool:
        """Có ưu tiên dùng tệp tạm thời không"""
        return False

    def build_temp_file(self, pcm_bytes: bytes) -> Optional[str]:
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(pcm_bytes)
            return temp_path
        except Exception as e:
            logger.bind(tag=TAG).error(f"Tạo tệp âm thanh tạm thời thất bại: {e}")
            return None

    def save_audio_to_file(self, pcm_data: List[bytes], session_id: str) -> str:
        """Lưu dữ liệu PCM thành tệp WAV"""
        module_name = __name__.split(".")[-1]
        file_name = f"asr_{module_name}_{session_id}_{uuid.uuid4()}.wav"
        file_path = os.path.join(self.output_dir, file_name)

        with wave.open(file_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 2 bytes = 16-bit
            wf.setframerate(16000)
            wf.writeframes(b"".join(pcm_data))

        return file_path

    async def speech_to_text_wrapper(
        self, opus_data: List[bytes], session_id: str, audio_format="opus"
    ) -> Tuple[Optional[str], Optional[str]]:
        file_path = None
        temp_path = None
        try:
            if audio_format == "pcm":
                pcm_data = opus_data
            else:
                pcm_data = self.decode_opus(opus_data)
            combined_pcm_data = b"".join(pcm_data)

            free_space = shutil.disk_usage(self.output_dir).free
            if free_space < len(combined_pcm_data) * 2:
                raise OSError("Không đủ không gian đĩa")

            if self.requires_file() and self.prefers_temp_file():
                temp_path = self.build_temp_file(combined_pcm_data)

            if (hasattr(self, "delete_audio_file") and not self.delete_audio_file) or (
                self.requires_file() and not self.prefers_temp_file()
            ):
                file_path = self.save_audio_to_file(pcm_data, session_id)

            if len(combined_pcm_data) == 0:
                artifacts = None
            else:
                artifacts = ASRProviderBase.AudioArtifacts(
                    pcm_frames=pcm_data,
                    pcm_bytes=combined_pcm_data,
                    file_path=file_path,
                    temp_path=temp_path,
                )

            text, _ = await self.speech_to_text(
                opus_data, session_id, audio_format, artifacts
            )
            return text, file_path
        except OSError as e:
            logger.bind(tag=TAG).error(f"Lỗi thao tác tệp: {e}")
            return None, None
        except Exception as e:
            logger.bind(tag=TAG).error(f"Nhận diện giọng nói thất bại: {e}")
            return None, None
        finally:
            try:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
                if (
                    hasattr(self, "delete_audio_file")
                    and self.delete_audio_file
                    and file_path
                    and os.path.exists(file_path)
                ):
                    os.remove(file_path)
            except Exception as e:
                logger.bind(tag=TAG).error(f"Dọn dẹp tệp thất bại: {e}")

    @abstractmethod
    async def speech_to_text(
        self,
        opus_data: List[bytes],
        session_id: str,
        audio_format="opus",
        artifacts: Optional[AudioArtifacts] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Chuyển đổi dữ liệu giọng nói thành văn bản

        :param opus_data: Dữ liệu âm thanh Opus đầu vào
        :param session_id: ID phiên
        :param audio_format: Định dạng âm thanh, mặc định "opus"
        :param artifacts: Các thành phần âm thanh, bao gồm dữ liệu PCM, đường dẫn tệp, v.v.
        :return: Văn bản kết quả nhận diện và đường dẫn tệp (nếu có)
        """
        pass

    @staticmethod
    def decode_opus(opus_data: List[bytes]) -> List[bytes]:
        """Giải mã dữ liệu âm thanh Opus sang dữ liệu PCM"""
        decoder = None
        try:
            decoder = opuslib_next.Decoder(16000, 1)
            pcm_data = []
            buffer_size = 960  # 每次处理960个采样点 (60ms at 16kHz)

            for i, opus_packet in enumerate(opus_data):
                try:
                    if not opus_packet or len(opus_packet) == 0:
                        continue

                    pcm_frame = decoder.decode(opus_packet, buffer_size)
                    if pcm_frame and len(pcm_frame) > 0:
                        pcm_data.append(pcm_frame)

                except opuslib_next.OpusError as e:
                    logger.bind(tag=TAG).warning(f"Lỗi giải mã Opus, bỏ qua gói dữ liệu {i}: {e}")
                except Exception as e:
                    logger.bind(tag=TAG).error(f"Lỗi xử lý âm thanh, gói dữ liệu {i}: {e}")

            return pcm_data

        except Exception as e:
            logger.bind(tag=TAG).error(f"Đã xảy ra lỗi trong quá trình giải mã âm thanh: {e}")
            return []
        finally:
            if decoder is not None:
                try:
                    del decoder
                except Exception as e:
                    logger.bind(tag=TAG).debug(f"Lỗi khi giải phóng tài nguyên decoder: {e}")
