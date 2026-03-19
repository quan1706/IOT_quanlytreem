"""
core/telegram/client.py

HTTP client cấp thấp giao tiếp với Telegram Bot API.
Sử dụng 1 shared aiohttp.ClientSession thay vì tạo mới mỗi request.
"""
import json
import aiohttp
from config.logger import setup_logging

TAG = "TelegramClient"


class TelegramClient:
    """
    Low-level Telegram Bot API client.
    Quản lý 1 shared aiohttp session và cung cấp các method cơ bản:
    send_message, send_photo, answer_callback_query, get_updates, get_me.
    """

    def __init__(self, bot_token: str, default_chat_id: str = None):
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.logger = setup_logging()
        self._session: aiohttp.ClientSession | None = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazily khởi tạo và tái sử dụng aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Đóng session khi shutdown."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Core API methods
    # ------------------------------------------------------------------
    async def send_message(
        self,
        chat_id=None,
        text: str = "",
        reply_markup: dict = None,
        parse_mode: str = "Markdown",
    ) -> bool:
        """Gửi tin nhắn text."""
        chat_id = chat_id or self.default_chat_id
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if result.get("ok"):
                    return True
                self.logger.bind(tag=TAG).warning(
                    f"sendMessage thất bại: {result}"
                )
                return False
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi sendMessage: {e}")
            return False

    async def send_photo(
        self,
        chat_id=None,
        photo_data: bytes = b"",
        caption: str = "",
        reply_markup: dict = None,
    ) -> bool:
        """Gửi ảnh kèm caption và (tuỳ chọn) inline keyboard."""
        chat_id = chat_id or self.default_chat_id
        url = f"{self.base_url}/sendPhoto"

        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        form.add_field("caption", caption)
        form.add_field("parse_mode", "Markdown")
        if reply_markup:
            form.add_field("reply_markup", json.dumps(reply_markup))
        form.add_field(
            "photo", photo_data, filename="baby_cry.jpg", content_type="image/jpeg"
        )

        try:
            session = await self._get_session()
            async with session.post(url, data=form) as resp:
                result = await resp.json()
                if result.get("ok"):
                    self.logger.bind(tag=TAG).info("Gửi ảnh Telegram thành công")
                    return True
                self.logger.bind(tag=TAG).error(f"sendPhoto thất bại: {result}")
                return False
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi sendPhoto: {e}")
            return False

    async def send_photo_url(
        self,
        chat_id=None,
        photo_url: str = "",
        caption: str = "",
        reply_markup: dict = None,
    ) -> bool:
        """Gửi ảnh qua URL kèm caption và (tuỳ chọn) inline keyboard."""
        chat_id = chat_id or self.default_chat_id
        url = f"{self.base_url}/sendPhoto"
        
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "Markdown",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if result.get("ok"):
                    self.logger.bind(tag=TAG).info("Gửi ảnh Telegram qua URL thành công")
                    return True
                self.logger.bind(tag=TAG).error(f"sendPhotoUrl thất bại: {result}")
                return False
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi sendPhotoUrl: {e}")
            return False

    async def edit_message_text(
        self, chat_id, message_id, text: str, parse_mode: str = "Markdown", reply_markup: dict = None
    ) -> bool:
        """Chỉnh sửa nội dung tin nhắn text."""
        url = f"{self.base_url}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if result.get("ok"):
                    return True
                return False
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi editMessageText: {e}")
            return False

    async def edit_message_caption(
        self, chat_id, message_id, caption: str, parse_mode: str = "Markdown", reply_markup: dict = None
    ) -> bool:
        """Chỉnh sửa caption của ảnh đã gửi."""
        url = f"{self.base_url}/editMessageCaption"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": caption,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if result.get("ok"):
                    self.logger.bind(tag=TAG).info("editMessageCaption thành công")
                    return True
                return False
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi editMessageCaption: {e}")
            return False

    async def answer_callback_query(
        self, callback_query_id: str, text: str = "", show_alert: bool = False
    ) -> bool:
        """Ack callback query => Telegram bỏ spinner trên button."""
        url = f"{self.base_url}/answerCallbackQuery"
        payload = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
        }
        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                return (await resp.json()).get("ok", False)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi answerCallbackQuery: {e}")
            return False

    async def set_my_commands(self, commands: list) -> bool:
        """Đăng ký danh sách các lệnh auto-complete với Telegram."""
        url = f"{self.base_url}/setMyCommands"
        payload = {"commands": commands}
        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if result.get("ok"):
                    self.logger.bind(tag=TAG).info("setMyCommands thành công")
                    return True
                self.logger.bind(tag=TAG).error(f"setMyCommands thất bại: {result}")
                return False
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi setMyCommands: {e}")
            return False

    async def get_updates(self, offset: int = 0, timeout: int = 20) -> list:
        """Long-polling getUpdates."""
        url = f"{self.base_url}/getUpdates"
        payload = {"offset": offset, "timeout": timeout}
        try:
            session = await self._get_session()
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout + 10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("ok"):
                        return data.get("result", [])
                    self.logger.bind(tag=TAG).error(f"getUpdates error: {data}")
                return []
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi getUpdates: {e}")
            return []

    async def get_me(self) -> dict:
        """Lấy thông tin bot (username, id, ...)."""
        url = f"{self.base_url}/getMe"
        try:
            session = await self._get_session()
            async with session.get(url) as resp:
                if resp.status == 200:
                    return (await resp.json()).get("result", {})
        except Exception:
            pass
        return {}
