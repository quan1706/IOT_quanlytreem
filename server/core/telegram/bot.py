"""
core/telegram/bot.py

Telegram Bot polling loop + lifecycle management.
Chịu trách nhiệm DUY NHẤT: long-polling getUpdates rồi dispatch đến Router.
"""
import asyncio
from config.logger import setup_logging
from core.telegram.client import TelegramClient
from core.telegram.alerts import TelegramAlerts
from core.telegram.router import TelegramRouter

TAG = "TelegramBot"


class TelegramBot:
    """
    Quản lý vòng đời Telegram Bot.

    Args:
        config: dict config toàn server (chứa telegram.bot_token, telegram.chat_id)
        dashboard_handler: DashboardHandler instance
    """

    def __init__(self, config: dict, dashboard_handler):
        tg_config = config.get("telegram", {})
        bot_token = tg_config.get("bot_token", "")
        chat_id = tg_config.get("chat_id", "")

        self.client = TelegramClient(bot_token=bot_token, default_chat_id=chat_id)
        self.alerts = TelegramAlerts(client=self.client)
        self.router = TelegramRouter(
            client=self.client,
            alerts=self.alerts,
            config=config,
            dashboard_handler=dashboard_handler,
        )
        self.logger = setup_logging()
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def start(self):
        """Khởi động polling loop. Non-blocking (phải gọi bằng create_task)."""
        self._running = True
        self.logger.bind(tag=TAG).info("Telegram Bot đang khởi động...")

        # Lấy bot username
        bot_info = await self.client.get_me()
        bot_username = bot_info.get("username", "")
        self.logger.bind(tag=TAG).info(f"Bot username: @{bot_username}")

        # Gửi thông báo khởi động
        try:
            await self.alerts.send_startup_message()
        except Exception:
            pass

        # Polling loop
        offset = 0
        while self._running:
            try:
                updates = await self.client.get_updates(offset=offset)
                if updates:
                    self.logger.bind(tag=TAG).info(
                        f"[POLL] Nhận {len(updates)} update(s)"
                    )
                for update in updates:
                    offset = update["update_id"] + 1

                    # Callback query (inline button)
                    if "callback_query" in update:
                        await self.router.handle_callback(update["callback_query"])
                        continue

                    # Text message
                    message = update.get("message")
                    if message:
                        await self.router.handle_message(message, bot_username)

            except Exception as e:
                import traceback
                self.logger.bind(tag=TAG).error(
                    f"Polling loop error: {e}\n{traceback.format_exc()}"
                )

            await asyncio.sleep(1)

    async def stop(self):
        """Graceful shutdown — dừng polling và đóng session."""
        self.logger.bind(tag=TAG).info("Đang dừng Telegram Bot...")
        self._running = False
        await self.client.close()
