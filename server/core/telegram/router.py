"""
core/telegram/router.py

Routing logic cho Telegram Bot — xử lý commands, callback buttons, và AI chat.
Tách biệt khỏi polling loop (bot.py) để dễ đọc và mở rộng.
"""
from config.logger import setup_logging

TAG = "TelegramRouter"


class TelegramRouter:
    """
    Dispatch Telegram update đến handler phù hợp.

    Args:
        client:   TelegramClient instance (dùng chung 1 session)
        alerts:   TelegramAlerts instance (gửi thông báo domain-specific)
        config:   dict config toàn server
        dashboard_handler: DashboardHandler instance (cho /status, /setkey)
    """

    def __init__(self, client, alerts, config: dict, dashboard_handler):
        self.client = client
        self.alerts = alerts
        self.config = config
        self.dashboard_handler = dashboard_handler
        self.logger = setup_logging()
        self.conversation_history: dict[str, list] = {}

    # ------------------------------------------------------------------
    # Callback query (inline button)
    # ------------------------------------------------------------------
    async def handle_callback(self, callback: dict):
        """Xử lý khi người dùng nhấn inline keyboard button."""
        from core.serverToClients import DashboardUpdater, AIProcessor

        cb_data = callback["data"]
        cb_id = callback.get("id", "")
        message_cb = callback.get("message", {})
        chat_id = message_cb.get("chat", {}).get("id")
        if not chat_id:
            return

        if cb_data.startswith("confirm_"):
            command = cb_data.replace("confirm_", "")

            # 1. Ack callback query (bỏ spinner)
            await self.client.answer_callback_query(cb_id, text="⏳ Đang xử lý...")

            # 2. Log dashboard
            DashboardUpdater.add_action_log(
                action=command,
                source="telegram_button",
                result="Đã ghi log (chưa kết nối phần cứng)",
            )

            # 3. Reply Telegram
            from core.serverToClients.baby_actions import BabyCareAction
            action_obj = BabyCareAction.from_callback(cb_data)
            label = action_obj.button_label if action_obj else command
            reply_text = (
                f"✅ *Đã xác nhận lệnh: {label}*\n"
                f"_(Lệnh đã được ghi vào Dashboard.)_"
            )
            await self.client.send_message(chat_id, reply_text)

            self.logger.bind(tag=TAG).info(f"[CALLBACK] Người dùng nhấn '{command}'")

        elif cb_data.startswith("ai_confirm_"):
            command = cb_data.replace("ai_confirm_", "")
            await self.client.answer_callback_query(cb_id, text="🚀 Thực hiện...")
            await AIProcessor.execute_confirmed_action(command, chat_id, self.client)

        elif cb_data.startswith("ai_cancel_"):
            command = cb_data.replace("ai_cancel_", "")
            await self.client.answer_callback_query(cb_id, text="❌ Đã từ chối")
            await AIProcessor.cancel_suggested_action(command, chat_id, self.client)

    # ------------------------------------------------------------------
    # Text message routing
    # ------------------------------------------------------------------
    async def handle_message(self, message: dict, bot_username: str = ""):
        """Route tin nhắn text đến handler phù hợp."""
        from core.serverToClients import DashboardUpdater, AIProcessor
        from core.api.dashboard_handler import DASHBOARD_STATE

        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        chat_type = message.get("chat", {}).get("type")

        if not text or not chat_id:
            return

        self.logger.bind(tag=TAG).info(
            f"[MSG] chat_type={chat_type} text='{text[:60]}'"
        )

        # -- /status -------------------------------------------------------
        if text.startswith("/status"):
            await self._cmd_status(chat_id, DASHBOARD_STATE)
            return

        # -- /mode ---------------------------------------------------------
        if text.startswith("/mode "):
            await self._cmd_mode(chat_id, text)
            return

        # -- /setkey -------------------------------------------------------
        if text.startswith("/setkey "):
            await self._cmd_setkey(chat_id, text)
            return

        # -- Tin nhắn bình thường (AI) -------------------------------------
        is_mentioned = chat_type == "private" or (
            bot_username and f"@{bot_username}" in text
        )
        if not is_mentioned:
            return

        clean_text = text.replace(f"@{bot_username}", "").strip() if bot_username else text
        await self._handle_ai_message(chat_id, clean_text)

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    async def _cmd_status(self, chat_id, state: dict):
        from core.serverToClients import DashboardUpdater

        mode_text = (
            "TỰ ĐỘNG DỖ DÀNH BÉ" if state["mode"] == "auto" else "CHỈ GIÁM SÁT LỊCH SỬ"
        )
        response_text = (
            f"📊 *Trạng Thái HT:*\n"
            f"- Chế độ: *{mode_text}*\n"
            f"- Lịch sử khóc: *{len(state['cry_history'])}* lần gần đây.\n"
            f"- Hành động gần nhất: *{len(state.get('action_logs', []))}* mục.\n"
            f"- Key AI hiện tại: `{self.dashboard_handler.current_key}`"
        )
        DashboardUpdater.add_system_log("Command", "/status", {"mode": state["mode"]})
        await self.client.send_message(chat_id, response_text)

    async def _cmd_mode(self, chat_id, text: str):
        from core.serverToClients import DashboardUpdater

        new_mode = text.replace("/mode ", "").strip()
        if new_mode in ("auto", "manual"):
            DashboardUpdater.set_mode(new_mode)
            mode_label = "TỰ ĐỘNG DỖ DÀNH BÉ" if new_mode == "auto" else "CHỈ GIÁM SÁT"
            await self.client.send_message(chat_id, f"🔄 Đã đổi sang *{mode_label}*.")
        else:
            await self.client.send_message(
                chat_id, "❌ Lệnh không đúng. Dùng `/mode auto` hoặc `/mode manual`."
            )

    async def _cmd_setkey(self, chat_id, text: str):
        from core.serverToClients import DashboardUpdater

        new_key = text.replace("/setkey ", "").strip()
        if new_key.startswith("gsk_"):
            success = self.dashboard_handler.update_api_key(new_key)
            if success:
                msg = "✅ Đã lưu API Key mới thành công! Hãy restart Server để nhận khoá mới."
                DashboardUpdater.add_system_log("Command", "/setkey", {"result": "ok"})
            else:
                msg = "❌ Có lỗi xảy ra khi lưu API Key."
        else:
            msg = "❌ API Key không hợp lệ. Hãy bắt đầu bằng `gsk_`!"
        await self.client.send_message(chat_id, msg)

    # ------------------------------------------------------------------
    # AI message handling
    # ------------------------------------------------------------------
    async def _handle_ai_message(self, chat_id, clean_text: str):
        from core.serverToClients import DashboardUpdater, AIProcessor

        actual_key = self.config.get("LLM", {}).get("GroqLLM", {}).get("api_key", "")
        if not actual_key:
            actual_key = self.config.get("ASR", {}).get("GroqASR", {}).get("api_key", "")

        self.logger.bind(tag=TAG).info(
            f"[AI] Nhận message: '{clean_text}' | Key: {'OK' if actual_key else 'TRỐNG'}"
        )

        if not actual_key:
            await self.client.send_message(
                chat_id, "⚠️ Chưa có Groq API Key. Vui lòng cài key bằng /setkey gsk_xxx."
            )
            return

        history = self.conversation_history.get(str(chat_id), [])

        # Phân tích intent điều khiển thiết bị
        ai_result = await AIProcessor.analyze_intent_conversational(
            clean_text, actual_key, history=history
        )
        self.logger.bind(tag=TAG).info(f"[AI] Kết quả: {ai_result}")

        if ai_result:
            actions = ai_result["actions"]
            reply_msg = ai_result["reply"]

            history.append({"role": "user", "content": clean_text})
            history.append({"role": "assistant", "content": reply_msg})
            self.conversation_history[str(chat_id)] = history[-10:]

            DashboardUpdater.add_ai_log(
                query=clean_text,
                response=reply_msg,
                action=",".join(actions),
                status="suggested",
            )
            intent_key = "+".join(actions)
            await self.alerts.send_ai_confirmation(chat_id, reply_msg, intent_key)
        else:
            conv_reply = await AIProcessor.chat_conversational(clean_text, actual_key)
            response_text = conv_reply or "Tôi đang lắng nghe bạn! 😊"

            history.append({"role": "user", "content": clean_text})
            history.append({"role": "assistant", "content": response_text})
            self.conversation_history[str(chat_id)] = history[-10:]

            DashboardUpdater.add_system_log("Chat", "conversation", {"q": clean_text[:40]})
            await self.client.send_message(chat_id, response_text)
