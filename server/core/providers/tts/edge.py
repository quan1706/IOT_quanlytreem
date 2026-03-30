import os
import uuid
import edge_tts
from datetime import datetime
from core.providers.tts.base import TTSProviderBase


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        if config.get("private_voice"):
            self.voice = config.get("private_voice")
        else:
            self.voice = config.get("voice")
        self.audio_file_type = config.get("format", "mp3")

    def generate_filename(self, extension=".mp3"):
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    async def text_to_speak(self, text, output_file):
        try:
            communicate = edge_tts.Communicate(text, voice=self.voice)
            if output_file:
                # Đảm bảo thư mục tồn tại và tạo tệp trống
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                with open(output_file, "wb") as f:
                    pass

                # Ghi luồng dữ liệu âm thanh
                with open(output_file, "ab") as f:  # Chuyển sang chế độ nối thêm để tránh ghi đè
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":  # Chỉ xử lý các khối dữ liệu âm thanh
                            f.write(chunk["data"])
            else:
                # Trả về dữ liệu âm thanh nhị phân
                audio_bytes = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_bytes += chunk["data"]
                return audio_bytes
        except Exception as e:
            error_msg = f"Yêu cầu Edge TTS thất bại: {e}"
            raise Exception(error_msg)  # Ném ngoại lệ để bên gọi xử lý