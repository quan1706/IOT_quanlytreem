"""
core/telegram/alerts.py

Domain-specific alert message templates dùng cho hệ thống Baby Care.
Layer trên TelegramClient — compose nội dung rồi gọi client.send_*.
"""
from config.logger import setup_logging
from core.telegram.client import TelegramClient

TAG = "TelegramAlerts"

# Global instance — được set bởi http_server.py khi TelegramBot khởi động
# Cho phép các module khác (listenMessageHandler, ...) gửi Telegram alert mà không cần truyền reference
_global_alerts: "TelegramAlerts | None" = None

class TelegramAlerts:
    """
    Tạo nội dung các loại thông báo (cry, token, startup, AI confirmation)
    rồi gửi qua TelegramClient.
    """

    def __init__(self, client: TelegramClient):
        self.client = client
        self.logger = setup_logging()
        self.msg_config = {}

    def set_msg_config(self, config: dict):
        """Được gọi bởi router để chia sẻ cấu hình tin nhắn."""
        self.msg_config = config

    @classmethod
    def set_global(cls, instance: "TelegramAlerts"):
        """Đăng ký instance toàn cục. Gọi từ http_server.py khi TelegramBot khởi động."""
        global _global_alerts
        _global_alerts = instance

    # ------------------------------------------------------------------
    # Baby cry (text-only)
    # ------------------------------------------------------------------
    async def send_cry_alert(
        self, message: str, time_str: str, current_mode: str
    ) -> bool:
        """Gửi cảnh báo bé khóc (không có ảnh)."""
        cry_cfg = self.msg_config.get("alerts", {}).get("cry", {})
        tmpl = cry_cfg.get("template", "🚨 CRY DETECTED: {message} at {time_str}")
        
        text = tmpl.format(message=message, time_str=time_str)
        
        if current_mode == "auto":
            text += cry_cfg.get("mode_auto", "🤖 AUTO MODE")
        else:
            text += cry_cfg.get("mode_manual", "👨‍👩‍👧 MONITOR MODE")

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
        token_cfg = self.msg_config.get("alerts", {}).get("token_limit", {})
        text = token_cfg.get("text", "⚠️ TOKEN LIMIT")
        btn_label = token_cfg.get("button", "⚙️ Dashboard")
        
        reply_markup = {
            "inline_keyboard": [
                [{"text": btn_label, "url": f"http://{local_ip}:8003/"}]
            ]
        }
        return await self.client.send_message(text=text, reply_markup=reply_markup)

    # ------------------------------------------------------------------
    # Startup notification
    # ------------------------------------------------------------------
    async def send_startup_message(self) -> bool:
        """Gửi thông báo khi server khởi động xong."""
        text = self.msg_config.get("alerts", {}).get("startup", {}).get("text", "✅ Bot Started")
        return await self.client.send_message(text=text)

    # ------------------------------------------------------------------
    # AI confirmation (xác nhận hành động AI gợi ý)
    # ------------------------------------------------------------------
    async def send_ai_confirmation(
        self, chat_id, reply_msg: str, intent: str
    ) -> bool:
        """Gửi tin nhắn xác nhận từ AI với 2 nút: Thực thi và Hủy bỏ."""
        conf_cfg = self.msg_config.get("alerts", {}).get("ai_confirmation", {})
        
        btn_ok = conf_cfg.get("btn_confirm", "🚀 Confirm")
        btn_no = conf_cfg.get("btn_cancel", "❌ Cancel")
        tmpl = conf_cfg.get("text", "🤖 Suggestion: {reply_msg}")

        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": btn_ok, "callback_data": f"ai_confirm_{intent}"},
                    {"text": btn_no, "callback_data": f"ai_cancel_{intent}"},
                ]
            ]
        }
        text = tmpl.format(reply_msg=reply_msg)
        return await self.client.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
