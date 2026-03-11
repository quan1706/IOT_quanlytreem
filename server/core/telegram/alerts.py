"""
core/telegram/alerts.py

Domain-specific alert message templates dùng cho hệ thống Baby Care.
Layer trên TelegramClient — compose nội dung rồi gọi client.send_*.
"""
from config.logger import setup_logging
from core.telegram.client import TelegramClient

TAG = "TelegramAlerts"


class TelegramAlerts:
    """
    Tạo nội dung các loại thông báo (cry, token, startup, AI confirmation)
    rồi gửi qua TelegramClient.
    """

    def __init__(self, client: TelegramClient):
        self.client = client
        self.logger = setup_logging()

    # ------------------------------------------------------------------
    # Baby cry (text-only)
    # ------------------------------------------------------------------
    async def send_cry_alert(
        self, message: str, time_str: str, current_mode: str
    ) -> bool:
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

        return await self.client.send_message(text=text)

    # ------------------------------------------------------------------
    # Baby cry (photo + inline buttons)
    # ------------------------------------------------------------------
    async def send_photo_alert(self, photo_data: bytes, caption: str) -> bool:
        """Gửi ảnh cảnh báo kèm BabyCareAction buttons."""
        from core.serverToClients.baby_actions import BabyCareAction

        reply_markup = BabyCareAction.get_inline_keyboard(cols=2)
        return await self.client.send_photo(
            photo_data=photo_data, caption=caption, reply_markup=reply_markup
        )

    # ------------------------------------------------------------------
    # Token / API key warning
    # ------------------------------------------------------------------
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
        return await self.client.send_message(text=text, reply_markup=reply_markup)

    # ------------------------------------------------------------------
    # Startup notification
    # ------------------------------------------------------------------
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
        return await self.client.send_message(text=text)

    # ------------------------------------------------------------------
    # AI confirmation (xác nhận hành động AI gợi ý)
    # ------------------------------------------------------------------
    async def send_ai_confirmation(
        self, chat_id, reply_msg: str, intent: str
    ) -> bool:
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
        return await self.client.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
