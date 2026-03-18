"""
Module quản lý gợi ý hệ thống (Prompt Manager)
Chịu trách nhiệm quản lý và cập nhật gợi ý hệ thống, bao gồm khởi tạo nhanh và tính năng tăng cường bất đồng bộ
"""

import os
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from config.logger import setup_logging
from jinja2 import Template

TAG = __name__

WEEKDAY_MAP = {
    "Monday": "Thứ Hai",
    "Tuesday": "Thứ Ba",
    "Wednesday": "Thứ Tư",
    "Thursday": "Thứ Năm",
    "Friday": "Thứ Sáu",
    "Saturday": "Thứ Bảy",
    "Sunday": "Chủ Nhật",
}

EMOJI_List = [
    "😶",
    "🙂",
    "😆",
    "😂",
    "😔",
    "😠",
    "😭",
    "😍",
    "😳",
    "😲",
    "😱",
    "🤔",
    "😉",
    "😎",
    "😌",
    "🤤",
    "😘",
    "😏",
    "😴",
    "😜",
    "🙄",
]


class PromptManager:
    """Trình quản lý gợi ý hệ thống, chịu trách nhiệm quản lý và cập nhật gợi ý hệ thống"""

    def __init__(self, config: Dict[str, Any], logger=None):
        self.config = config
        self.logger = logger or setup_logging()
        self.base_prompt_template = None
        self.last_update_time = 0
 
        # Nhập trình quản lý bộ đệm toàn cục
        from core.utils.cache.manager import cache_manager, CacheType

        self.cache_manager = cache_manager
        self.CacheType = CacheType
 
        # Khởi tạo nguồn ngữ cảnh
        from core.utils.context_provider import ContextDataProvider

        self.context_provider = ContextDataProvider(config, self.logger)
        self.context_data = {}

        self._load_base_template()

    def _load_base_template(self):
        """Tải mẫu gợi ý cơ bản"""
        try:
            template_path = self.config.get("prompt_template", None)
            if not template_path:
                template_path = "agent-base-prompt.txt"
            cache_key = f"prompt_template:{template_path}"

            # Lấy từ bộ đệm trước
            cached_template = self.cache_manager.get(self.CacheType.CONFIG, cache_key)
            if cached_template is not None:
                self.base_prompt_template = cached_template
                self.logger.bind(tag=TAG).debug("Tải mẫu gợi ý cơ bản từ bộ đệm")
                return
 
            # Bộ đệm không khớp, đọc từ tệp
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    template_content = f.read()

                # Lưu vào bộ đệm (loại CONFIG mặc định không tự động hết hạn, cần hủy thủ công)
                self.cache_manager.set(
                    self.CacheType.CONFIG, cache_key, template_content
                )
                self.base_prompt_template = template_content
                self.logger.bind(tag=TAG).debug("Tải mẫu gợi ý cơ bản thành công và đã lưu đệm")
            else:
                self.logger.bind(tag=TAG).warning(f"Không tìm thấy tệp {template_path}")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Tải mẫu gợi ý thất bại: {e}")

    def get_quick_prompt(self, user_prompt: str, device_id: str = None) -> str:
        """Lấy nhanh gợi ý hệ thống (sử dụng cấu hình người dùng)"""
        device_cache_key = f"device_prompt:{device_id}"
        cached_device_prompt = self.cache_manager.get(
            self.CacheType.DEVICE_PROMPT, device_cache_key
        )
        if cached_device_prompt is not None:
            self.logger.bind(tag=TAG).debug(f"Sử dụng gợi ý đã đệm của thiết bị {device_id}")
            return cached_device_prompt
        else:
            self.logger.bind(tag=TAG).debug(
                f"Thiết bị {device_id} không có gợi ý đệm, sử dụng gợi ý truyền vào"
            )

        # Sử dụng gợi ý truyền vào và lưu đệm (nếu có ID thiết bị)
        if device_id:
            device_cache_key = f"device_prompt:{device_id}"
            self.cache_manager.set(self.CacheType.CONFIG, device_cache_key, user_prompt)
            self.logger.bind(tag=TAG).debug(f"Gợi ý của thiết bị {device_id} đã được lưu đệm")
 
        self.logger.bind(tag=TAG).info(f"Sử dụng gợi ý nhanh: {user_prompt[:50]}...")
        return user_prompt

    def _get_current_time_info(self) -> tuple:
        """Lấy thông tin thời gian hiện tại"""
        from .current_time import (
            get_current_date,
            get_current_weekday,
            get_current_lunar_date,
        )

        today_date = get_current_date()
        today_weekday = get_current_weekday()
        lunar_date = get_current_lunar_date() + "\n"

        return today_date, today_weekday, lunar_date

    def _get_location_info(self, client_ip: str) -> str:
        """Lấy thông tin vị trí"""
        try:
            # Lấy từ bộ đệm trước
            cached_location = self.cache_manager.get(self.CacheType.LOCATION, client_ip)
            if cached_location is not None:
                return cached_location
 
            # Bộ đệm không khớp, gọi API để lấy
            from core.utils.util import get_ip_info
 
            ip_info = get_ip_info(client_ip, self.logger)
            city = ip_info.get("city", "Vị trí không xác định")
            location = f"{city}"
 
            # Lưu vào bộ đệm
            self.cache_manager.set(self.CacheType.LOCATION, client_ip, location)
            return location
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lấy thông tin vị trí thất bại: {e}")
            return "Vị trí không xác định"

    def _get_weather_info(self, conn: "ConnectionHandler", location: str) -> str:
        """Lấy thông tin thời tiết"""
        try:
            # Lấy từ bộ đệm trước
            cached_weather = self.cache_manager.get(self.CacheType.WEATHER, location)
            if cached_weather is not None:
                return cached_weather
 
            # Bộ đệm không khớp, gọi hàm get_weather để lấy
            from plugins_func.functions.get_weather import get_weather
            from plugins_func.register import ActionResponse
 
            # Gọi hàm get_weather
            result = get_weather(conn, location=location, lang="vi_VN")
            if isinstance(result, ActionResponse):
                weather_report = result.result
                self.cache_manager.set(self.CacheType.WEATHER, location, weather_report)
                return weather_report
            return "Lấy thông tin thời tiết thất bại"
 
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lấy thông tin thời tiết thất bại: {e}")
            return "Lấy thông tin thời tiết thất bại"

    def update_context_info(self, conn, client_ip: str):
        """Cập nhật đồng bộ thông tin ngữ cảnh"""
        try:
            local_address = ""
            if (
                client_ip
                and self.base_prompt_template
                and (
                    "local_address" in self.base_prompt_template
                    or "weather_info" in self.base_prompt_template
                )
            ):
                # Lấy thông tin vị trí (sử dụng đệm toàn cục)
                local_address = self._get_location_info(client_ip)

            if (
                self.base_prompt_template
                and "weather_info" in self.base_prompt_template
                and local_address
            ):
                # Lấy thông tin thời tiết (sử dụng đệm toàn cục)
                self._get_weather_info(conn, local_address)
 
            # Lấy dữ liệu ngữ cảnh cấu hình
            if hasattr(conn, "device_id") and conn.device_id:
                if (
                    self.base_prompt_template
                    and "dynamic_context" in self.base_prompt_template
                ):
                    self.context_data = self.context_provider.fetch_all(conn.device_id)
                else:
                    self.context_data = ""

            self.logger.bind(tag=TAG).debug(f"Cập nhật thông tin ngữ cảnh hoàn tất")
 
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Cập nhật thông tin ngữ cảnh thất bại: {e}")

    def build_enhanced_prompt(
        self, user_prompt: str, device_id: str, client_ip: str = None, *args, **kwargs
    ) -> str:
        """Xây dựng gợi ý hệ thống tăng cường"""
        if not self.base_prompt_template:
            return user_prompt

        try:
            # Lấy thông tin thời gian mới nhất (không đệm)
            today_date, today_weekday, lunar_date = self._get_current_time_info()

            # Lấy thông tin ngữ cảnh đã đệm
            local_address = ""
            weather_info = ""

            if client_ip:
                # Lấy thông tin vị trí (từ đệm toàn cục)
                local_address = (
                    self.cache_manager.get(self.CacheType.LOCATION, client_ip) or ""
                )
 
                # Lấy thông tin thời tiết (từ đệm toàn cục)
                if local_address:
                    weather_info = (
                        self.cache_manager.get(self.CacheType.WEATHER, local_address)
                        or ""
                    )

            # Lấy ngôn ngữ TTS đã chọn, giá trị mặc định là tiếng Việt
            language = (
                self.config.get("TTS", {})
                .get(self.config.get("selected_module", {}).get("TTS", ""), {})
                .get("language")
                or "tiếng Việt"
            )
            self.logger.bind(tag=TAG).debug(f"Đã lấy được ngôn ngữ đã chọn: {language}")

            # Thay thế các biến mẫu
            template = Template(self.base_prompt_template)
            enhanced_prompt = template.render(
                base_prompt=user_prompt,
                current_time="{{current_time}}",
                today_date=today_date,
                today_weekday=today_weekday,
                lunar_date=lunar_date,
                local_address=local_address,
                weather_info=weather_info,
                emojiList=EMOJI_List,
                device_id=device_id,
                client_ip=client_ip,
                dynamic_context=self.context_data,
                language=language,
                *args,
                **kwargs,
            )
            device_cache_key = f"device_prompt:{device_id}"
            self.cache_manager.set(
                self.CacheType.DEVICE_PROMPT, device_cache_key, enhanced_prompt
            )
            self.logger.bind(tag=TAG).info(
                f"Xây dựng gợi ý tăng cường thành công, độ dài: {len(enhanced_prompt)}"
            )
            return enhanced_prompt

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Xây dựng gợi ý tăng cường thất bại: {e}")
            return user_prompt
