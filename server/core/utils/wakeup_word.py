import os
import re
import yaml
import time
import hashlib
import portalocker
from typing import Dict


class FileLock:
    def __init__(self, file, timeout=5):
        self.file = file
        self.timeout = timeout
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        while True:
            try:
                portalocker.lock(self.file, portalocker.LOCK_EX | portalocker.LOCK_NB)
                return self.file
            except portalocker.LockException:
                if time.time() - self.start_time > self.timeout:
                    raise TimeoutError("Quá hạn lấy khóa tệp")
                time.sleep(0.1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        portalocker.unlock(self.file)


class WakeupWordsConfig:
    def __init__(self):
        self.config_file = "data/.wakeup_words.yaml"
        self.assets_dir = "config/assets/wakeup_words"
        self._ensure_directories()
        self._config_cache = None
        self._last_load_time = 0
        self._cache_ttl = 1  # Thời gian hiệu lực của bộ đệm (giây)
        self._lock_timeout = 5  # Thời gian quá hạn khóa tệp (giây)

    def _ensure_directories(self):
        """Đảm bảo các thư mục cần thiết tồn tại"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)

    def _load_config(self) -> Dict:
        """Tải tệp cấu hình, sử dụng cơ chế bộ đệm"""
        current_time = time.time()
 
        # Nếu bộ đệm còn hiệu lực, trả về bộ đệm trực tiếp
        if (
            self._config_cache is not None
            and current_time - self._last_load_time < self._cache_ttl
        ):
            return self._config_cache

        try:
            with open(self.config_file, "a+", encoding="utf-8") as f:
                with FileLock(f, timeout=self._lock_timeout):
                    f.seek(0)
                    content = f.read()
                    config = yaml.safe_load(content) if content else {}
                    self._config_cache = config
                    self._last_load_time = current_time
                    return config
        except (TimeoutError, IOError) as e:
            print(f"Tải tệp cấu hình thất bại: {e}")
            return {}
        except Exception as e:
            print(f"Xảy ra lỗi không xác định khi tải tệp cấu hình: {e}")
            return {}

    def _save_config(self, config: Dict):
        """Lưu cấu hình vào tệp, sử dụng khóa tệp để bảo vệ"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                with FileLock(f, timeout=self._lock_timeout):
                    yaml.dump(config, f, allow_unicode=True)
                    self._config_cache = config
                    self._last_load_time = time.time()
        except (TimeoutError, IOError) as e:
            print(f"Lưu tệp cấu hình thất bại: {e}")
            raise
        except Exception as e:
            print(f"Xảy ra lỗi không xác định khi lưu tệp cấu hình: {e}")
            raise

    def get_wakeup_response(self, voice: str) -> Dict:
        voice = hashlib.md5(voice.encode()).hexdigest()
        """Lấy cấu hình phản hồi từ khóa đánh thức"""
        config = self._load_config()

        if not config or voice not in config:
            return None
 
        # Kiểm tra kích thước tệp
        file_path = config[voice]["file_path"]
        if not os.path.exists(file_path) or os.stat(file_path).st_size < (15 * 1024):
            return None

        return config[voice]

    def update_wakeup_response(self, voice: str, file_path: str, text: str):
        """Cập nhật cấu hình phản hồi từ khóa đánh thức"""
        try:
            # Lọc các biểu tượng cảm xúc (emoji)
            filtered_text = re.sub(r'[\U0001F600-\U0001F64F\U0001F900-\U0001F9FF]', '', text)
            
            config = self._load_config()
            voice_hash = hashlib.md5(voice.encode()).hexdigest()
            config[voice_hash] = {
                "voice": voice,
                "file_path": file_path,
                "time": time.time(),
                "text": filtered_text,
            }
            self._save_config(config)
        except Exception as e:
            print(f"Cập nhật cấu hình phản hồi từ khóa đánh thức thất bại: {e}")
            raise

    def generate_file_path(self, voice: str) -> str:
        """Tạo đường dẫn tệp âm thanh, sử dụng giá trị băm của voice làm tên tệp"""
        try:
            # Tạo giá trị băm của voice
            voice_hash = hashlib.md5(voice.encode()).hexdigest()
            file_path = os.path.join(self.assets_dir, f"{voice_hash}.wav")
 
            # Nếu tệp đã tồn tại, xóa nó trước
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Xóa tệp âm thanh đã tồn tại thất bại: {e}")
                    raise

            return file_path
        except Exception as e:
            print(f"Tạo đường dẫn tệp âm thanh thất bại: {e}")
            raise