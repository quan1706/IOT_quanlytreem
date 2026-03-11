"""
serverToClients/telegram_notifier.py

Module tập trung mọi tác vụ gửi tin nhắn từ Server -> Telegram Bot Client.
Thay thế các lời gọi aiohttp rải rác ở telegram_handler.py và messenger.py.
"""
import json
import aiohttp
from config.logger import setup_logging

TAG = "TelegramNotifier"


class TelegramNotifier:
    """
    Singleton helper để gửi tất cả các loại tin nhắn Telegram.
    """

    BOT_TOKEN = "8765806795:AAEB83HSeGkpYYv0JsnnPz6IaiSCvlDOn_w"
    CHAT_ID = "-1003755091801"

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or self.BOT_TOKEN
        self.chat_id = chat_id or self.CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.logger = setup_logging()

    # ------------------------------------------------------------------
    # Text message
    # ------------------------------------------------------------------
    async def send_message(self, chat_id, text: str, reply_markup: dict = None,
                           parse_mode: str = "Markdown") -> bool:
        """Gửi tin nhắn text thông thường tới một chat_id."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    result = await resp.json()
                    if result.get("ok"):
                        return True
                    else:
                        self.logger.bind(tag=TAG).warning(
                            f"Telegram sendMessage thất bại: {result}"
                        )
                        return False
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi kết nối sendMessage: {e}")
            return False

    # ------------------------------------------------------------------
    # Photo message
    # ------------------------------------------------------------------
    async def send_photo(self, chat_id, photo_data: bytes, caption: str,
                         reply_markup: dict = None) -> bool:
        """Gửi ảnh kèm caption và (tuỳ chọn) inline keyboard."""
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
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=form) as resp:
                    result = await resp.json()
                    if result.get("ok"):
                        self.logger.bind(tag=TAG).info("Đã gửi ảnh Telegram thành công")
                        return True
                    else:
                        self.logger.bind(tag=TAG).error(f"Lỗi gửi Telegram photo: {result}")
                        return False
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi kết nối sendPhoto: {e}")
            return False

    # ------------------------------------------------------------------
    # Answer callback query (dismiss loading spinner trên button)
    # ------------------------------------------------------------------
    async def answer_callback_query(self, callback_query_id: str,
                                    text: str = "", show_alert: bool = False) -> bool:
        """Xác nhận callback query để Telegram bỏ trạng thái loading trên button."""
        url = f"{self.base_url}/answerCallbackQuery"
        payload = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    return (await resp.json()).get("ok", False)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi answerCallbackQuery: {e}")
            return False

    # ------------------------------------------------------------------
    # Domain-specific alerts
    # ------------------------------------------------------------------
    async def send_cry_alert(self, message: str, time_str: str,
                             current_mode: str) -> bool:
        """Gửi cảnh báo bé khóc (không có ảnh)."""
        text = (
            "🚨 *CẢNH BÁO SMART BABY CARE* 🚨\n\n"
            f"📍 Phát hiện: *Bé đang khóc!* ({message})\n"
            f"⏰ Lịch sử ghi nhận lúc: *{time_str}*\n\n"
        )
        if current_mode == "auto":
            text += "🤖 _Hệ thống đang ở CHẾ ĐỘ TỰ ĐỘNG, đã tự mở nhạc dỗ dành bé._"
        else:
            text += "👨‍👩‍👧 _Hệ thống đang ở CHẾ ĐỘ GIÁM SÁT, hãy vào kiểm tra bé ngay!_"

        return await self.send_message(self.chat_id, text)

    async def send_photo_alert(self, photo_data: bytes, caption: str) -> bool:
        """Gửi ảnh cảnh báo kèm các nút điều khiển nhanh (lấy từ BabyCareAction enum)."""
        from core.serverToClients.baby_actions import BabyCareAction
        reply_markup = BabyCareAction.get_inline_keyboard(cols=2)
        return await self.send_photo(self.chat_id, photo_data, caption, reply_markup)

    async def send_token_alert(self, local_ip: str) -> bool:
        """Gửi cảnh báo hết token Groq."""
        text = (
            "⚠️ *CẢNH BÁO SMART BABY CARE* ⚠️\n\n"
            "❌ *LỖI HẾT TOKEN API GROQ (RATE LIMIT)*\n"
            "Trợ lý AI của bạn hiện không thể suy nghĩ hay trả lời vì đã dùng hết "
            "hạn mức miễn phí trong ngày.\n\n"
            "Vui lòng nhấn vào nút bên dưới để truy cập *Bảng điều khiển (Dashboard)* "
            "và Cập nhật API Key mới cho hệ thống!"
        )
        reply_markup = {
            "inline_keyboard": [
                [{"text": "Mở Dashboard Cài Đặt ⚙️", "url": f"http://{local_ip}:8003/"}]
            ]
        }
        return await self.send_message(self.chat_id, text, reply_markup=reply_markup)

    async def send_startup_message(self) -> bool:
        """Gửi thông báo khi server khởi động xong."""
        text = (
            "✅ *Hệ Thống Smart Baby Care Đã Khởi Động!*\n"
            "Bạn có thể điều khiển cấu hình nhanh qua Bot này.\n\n"
            "Hướng dẫn lệnh:\n"
            "`/status` - Xem bảng trạng thái\n"
            "`/mode auto` - Bật chế độ Tự động dỗ bé\n"
            "`/mode manual` - Bật chế độ Chỉ Giám Sát\n"
            "`/setkey gsk_xxxx` - Thay đổi khóa Groq AI qua tin nhắn"
        )
        return await self.send_message(self.chat_id, text)

    async def send_ai_confirmation(self, chat_id, reply_msg, intent) -> bool:
        """Gửi tin nhắn xác nhận từ AI với 2 nút: Thực thi và Hủy bỏ."""
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "🚀 Thực thi", "callback_data": f"ai_confirm_{intent}"},
                    {"text": "❌ Hủy bỏ", "callback_data": f"ai_cancel_{intent}"},
                ]
            ]
        }
        text = f"🤖 *AI gợi ý:* {reply_msg}\n\n_Bạn có muốn thực hiện hành động này không?_"
        return await self.send_message(chat_id, text, reply_markup=reply_markup)
