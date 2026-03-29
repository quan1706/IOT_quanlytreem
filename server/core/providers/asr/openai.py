import time
import os
from config.logger import setup_logging
from typing import Optional, Tuple, List
from core.providers.asr.dto.dto import InterfaceType
from core.providers.asr.base import ASRProviderBase

import requests

TAG = __name__
logger = setup_logging()

class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        self.interface_type = InterfaceType.NON_STREAM
        self.api_key = config.get("api_key")
        self.api_url = config.get("base_url")
        self.model = config.get("model_name")
        self.language = config.get("language", None)
        self.output_dir = config.get("output_dir")
        self.prompt = config.get("prompt", "quạt, nôi, bé, bật, tắt, nhạc, âm lượng") # Từ khóa gợi ý cho ASR
        self.delete_audio_file = delete_audio_file

        os.makedirs(self.output_dir, exist_ok=True)

    def requires_file(self) -> bool:
        return True

    def prefers_temp_file(self) -> bool:
        return True

    async def speech_to_text(self, opus_data: List[bytes], session_id: str, audio_format="opus", artifacts=None) -> Tuple[Optional[str], Optional[str]]:
        file_path = None
        try:
            if artifacts is None or artifacts.temp_path is None:
                return "", None
            file_path = artifacts.temp_path
                
            logger.bind(tag=TAG).info(f"file path: {file_path}")
            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }
            
            # Truyền tên model và ngôn ngữ qua tham số data
            data = {
                "model": self.model
            }
            if self.language:
                data["language"] = self.language
            if self.prompt:
                data["prompt"] = self.prompt  # Gợi ý từ khóa để Whisper nhận diện chính xác hơn


            with open(file_path, "rb") as audio_file:  # Dùng with để đảm bảo file được đóng
                files = {
                    "file": audio_file
                }

                start_time = time.time()
                response = requests.post(
                    self.api_url,
                    files=files,
                    data=data,
                    headers=headers
                )
                logger.bind(tag=TAG).debug(
                    f"Thời gian nhận diện giọng nói: {time.time() - start_time:.3f}s | Kết quả: {response.text}"
                )

            if response.status_code == 200:
                text = response.json().get("text", "")
                return text, file_path
            else:
                raise Exception(f"Yêu cầu API thất bại: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.bind(tag=TAG).error(f"Nhận diện giọng nói thất bại: {e}")
            return "", None
        
