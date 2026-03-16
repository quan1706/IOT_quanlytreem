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
        
        # Tải cấu hình tin nhắn từ YAML
        from core.utils.util import load_telegram_config
        self.msg_config = load_telegram_config()
        # Chia sẻ config cho alerts
        if self.alerts:
            self.alerts.set_msg_config(self.msg_config)

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
            label = action_obj.get_label(self.msg_config) if action_obj else command
            
            tmpl = self.msg_config.get("callback", {}).get("confirmed", "Verified: {label}")
            reply_text = tmpl.format(label=label)
            await self.client.send_message(chat_id, reply_text)

            self.logger.bind(tag=TAG).info(f"[CALLBACK] Người dùng nhấn '{command}'")

        elif cb_data.startswith("ai_confirm_"):
            command = cb_data.replace("ai_confirm_", "")
            txt = self.msg_config.get("callback", {}).get("ai_executing", "🚀 Executing...")
            await self.client.answer_callback_query(cb_id, text=txt)
            await AIProcessor.execute_confirmed_action(command, chat_id, self.client, msg_config=self.msg_config)

        elif cb_data.startswith("ai_cancel_"):
            command = cb_data.replace("ai_cancel_", "")
            txt = self.msg_config.get("callback", {}).get("ai_cancelled", "❌ Cancelled")
            await self.client.answer_callback_query(cb_id, text=txt)
            await AIProcessor.cancel_suggested_action(command, chat_id, self.client, msg_config=self.msg_config)

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

        # 1. Làm sạch text (loại bỏ mention @bot_username nếu có)
        clean_text = text
        if bot_username and f"@{bot_username}" in text:
            # Chỉ loại bỏ mention bot, giữ nguyên phần còn lại
            clean_text = text.replace(f"@{bot_username}", "").strip()

        # 2. Kiểm tra Slash Commands dựa trên clean_text
        # -- /start (Welcome) ----------------------------------------------
        if clean_text.startswith("/start"):
            await self._cmd_welcome(chat_id)
            return

        # -- /help ---------------------------------------------------------
        if clean_text.startswith("/help"):
            await self._cmd_help(chat_id, bot_username=bot_username)
            return

        # -- /status -------------------------------------------------------
        if clean_text.startswith("/status"):
            await self._cmd_status(chat_id, DASHBOARD_STATE)
            return

        # -- /mode ---------------------------------------------------------
        if clean_text.startswith("/mode "):
            await self._cmd_mode(chat_id, clean_text)
            return

        # -- /setkey -------------------------------------------------------
        if clean_text.startswith("/setkey "):
            await self._cmd_setkey(chat_id, clean_text)
            return

        # -- /baby_chart ---------------------------------------------------
        if clean_text.startswith("/baby_chart"):
            # Thử parse số ngày: /baby_chart 7
            parts = clean_text.split()
            days = 1
            if len(parts) > 1 and parts[1].isdigit():
                days = int(parts[1])
            await self._cmd_baby_chart(chat_id, days=days)
            return

        # -- /bat_quat -----------------------------------------------------
        if clean_text.startswith("/bat_quat"):
            from core.serverToClients.esp32_commander import ESP32Commander
            success, msg = await ESP32Commander().execute_command("bat_quat")
            await self.client.send_message(chat_id, f"🌬️ *Lệnh Bật quạt:* {msg}")
            return

        # -- /tat_quat -----------------------------------------------------
        if clean_text.startswith("/tat_quat"):
            from core.serverToClients.esp32_commander import ESP32Commander
            success, msg = await ESP32Commander().execute_command("tat_quat")
            await self.client.send_message(chat_id, f"🛑 *Lệnh Tắt quạt:* {msg}")
            return

        # 3. Tin nhắn bình thường (AI)
        # Chỉ xử lý AI nếu là chat private HOẶC được nhắc tên (mention) trong group
        is_mentioned = chat_type == "private" or (
            bot_username and f"@{bot_username}" in text
        )
        if not is_mentioned:
            return

        await self._handle_ai_message(chat_id, clean_text)

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    async def _cmd_status(self, chat_id, state: dict, prefix: str = ""):
        from core.serverToClients import DashboardUpdater

        tmpl = self.msg_config.get("commands", {}).get("status", {}).get("text", "")
        if tmpl:
            response_text = (prefix + "\n\n" if prefix else "") + tmpl.format(
                mode=state['mode'].upper(),
                battery="85",
                esp_status="Đang kết nối ✅",
                temp=state.get('temp', '--'),
                humidity=state.get('humidity', '--'),
                baby_state="Bé đang ngủ ngon 😴",
                baby_posture="Nằm ngửa ✅",
                ai_key=self.dashboard_handler.current_key
            )
        else:
            # Fallback
            response_text = f"{prefix}\n\n⚙️ STATUS: {state['mode']}"

        DashboardUpdater.add_system_log("Command", "/status", {"mode": state["mode"]})
        await self.client.send_message(chat_id, response_text)

    async def _cmd_mode(self, chat_id, text: str):
        from core.serverToClients import DashboardUpdater

        new_mode = text.replace("/mode ", "").strip()
        if new_mode in ("auto", "manual"):
            DashboardUpdater.set_mode(new_mode)
            mode_label = "TỰ ĐỘNG DỖ DÀNH BÉ" if new_mode == "auto" else "CHỈ GIÁM SÁT"
            tmpl = self.msg_config.get("commands", {}).get("mode_changed", {}).get("text", "🔄 Mode: {mode_label}")
            await self.client.send_message(chat_id, tmpl.format(mode_label=mode_label))
        else:
            msg = self.msg_config.get("commands", {}).get("mode_error", {}).get("text", "❌ Error")
            await self.client.send_message(chat_id, msg)

    async def _cmd_setkey(self, chat_id, text: str):
        from core.serverToClients import DashboardUpdater

        new_key = text.replace("/setkey ", "").strip()
        if new_key.startswith("gsk_"):
            success = self.dashboard_handler.update_api_key(new_key)
            if success:
                msg = self.msg_config.get("commands", {}).get("setkey_success", {}).get("text", "✅ OK")
                DashboardUpdater.add_system_log("Command", "/setkey", {"result": "ok"})
            else:
                msg = self.msg_config.get("commands", {}).get("setkey_fail", {}).get("text", "❌ Fail")
        else:
            msg = self.msg_config.get("commands", {}).get("setkey_invalid", {}).get("text", "❌ Invalid")
        await self.client.send_message(chat_id, msg)

    async def _cmd_baby_chart(self, chat_id, prefix: str = "", days: int = 1):
        """Handler cho lệnh /baby_chart — hiển thị thống kê tiếng khóc kèm đánh giá AI."""
        from core.utils.chart_gen import generate_mock_cry_data, get_cry_chart_url
        from core.serverToClients.ai_processor import AIProcessor
        
        self.logger.bind(tag=TAG).info(f"[CMD] /baby_chart {days} days from {chat_id}")
        
        # 1. Lấy dữ liệu
        labels, values = generate_mock_cry_data(days=days)
        
        # 2. Tạo URL biểu đồ
        title_suffix = f"trong {days} ngày" if days > 1 else "trong 24h"
        title = f"Thống kê tiếng khóc {title_suffix}"
        chart_url = get_cry_chart_url(labels, values, title=title)
        
        # 3. Lấy đánh giá từ AI (Summarize)
        actual_key = self.config.get("LLM", {}).get("GroqLLM", {}).get("api_key", "")
        if not actual_key:
            actual_key = self.config.get("ASR", {}).get("GroqASR", {}).get("api_key", "")
            
        ai_summary = ""
        if actual_key and values:
            # Tạo chuỗi tóm tắt dữ liệu cho AI: chỉ lấy các mốc có giá trị cao hoặc đại diện
            # Nếu quá nhiều điểm, chỉ lấy top 10 điểm cao nhất và 5 điểm gần nhất
            indexed_values = list(enumerate(values))
            top_points = sorted(indexed_values, key=lambda x: x[1], reverse=True)[:10]
            recent_points = indexed_values[-5:]
            
            summary_points = sorted(list(set(top_points + recent_points)), key=lambda x: x[0])
            data_str = "\n".join([f"- {labels[i]}: {values[i]}" for i, v in summary_points])
            
            ai_summary = await AIProcessor.summarize_baby_condition(actual_key, data_str, days)
        
        # 4. Gửi cho người dùng
        cfg_key = f"baby_chart_{days}" if days in (1, 3, 7) else "baby_chart"
        base_caption = self.msg_config.get("commands", {}).get(cfg_key, {}).get("caption", "📊 Biểu đồ thống kê")
        
        caption = (prefix + "\n\n" if prefix else "") + base_caption
        if ai_summary:
            ai_prefix = self.msg_config.get("commands", {}).get("ai_summary_prefix", {}).get("text", "\n\n🤖 *Đánh giá từ Tiểu Bảo:*\n")
            caption += ai_prefix + ai_summary
            
        await self.client.send_photo_url(chat_id, chart_url, caption=caption)

    async def _cmd_welcome(self, chat_id, prefix: str = ""):
        """Chào mừng và giới thiệu hệ thống."""
        tmpl = self.msg_config.get("commands", {}).get("welcome", {}).get("text", "🍼 Welcome")
        msg = (prefix + "\n\n" if prefix else "") + tmpl
        await self.client.send_message(chat_id, msg)

    async def _cmd_help(self, chat_id, prefix: str = "", bot_username: str = ""):
        """Hướng dẫn sử dụng."""
        mention_text = f"`@{bot_username}`" if bot_username else "Bot"
        tmpl = self.msg_config.get("commands", {}).get("help", {}).get("text", "📚 Help")
        msg = (prefix + "\n\n" if prefix else "") + tmpl.format(mention_text=mention_text)
        await self.client.send_message(chat_id, msg)

    async def _execute_direct_command(self, chat_id, command_name: str, prefix: str = "", original_text: str = ""):
        """Thực thi một lệnh trực tiếp từ AI Tool (không cần confirm)."""
        if command_name == "baby_chart" or command_name == "baby_chart_1":
            await self._cmd_baby_chart(chat_id, prefix=prefix, days=1)
        elif command_name == "baby_chart_3":
            await self._cmd_baby_chart(chat_id, prefix=prefix, days=3)
        elif command_name == "baby_chart_7":
            await self._cmd_baby_chart(chat_id, prefix=prefix, days=7)
        elif command_name == "status":
            from core.api.dashboard_handler import DASHBOARD_STATE
            await self._cmd_status(chat_id, DASHBOARD_STATE, prefix=prefix)
        elif command_name == "cry_history_query":
            await self._cmd_cry_history(chat_id, prefix=prefix, original_text=original_text)
        elif command_name == "help":
            await self._cmd_help(chat_id, prefix=prefix)
        elif command_name == "welcome":
            await self._cmd_welcome(chat_id, prefix=prefix)

    async def _cmd_cry_history(self, chat_id, prefix: str = "", original_text: str = ""):
        """Handler cho lệnh cry_history_query — trả lời câu hỏi về lịch sử bé khóc."""
        from core.utils.chart_gen import generate_mock_cry_data
        from core.serverToClients.ai_processor import AIProcessor
        
        # 1. Lấy dữ liệu 24h qua
        labels, values = generate_mock_cry_data(days=1)
        
        # 2. Tóm tắt dữ liệu cho AI
        # Lấy các điểm bé khóc (values > 200)
        crying_points = []
        for i, v in enumerate(values):
            if v > 200:
                crying_points.append(f"- {labels[i]}: {v}")
        
        if not crying_points:
            data_str = "Bé không khóc trong 24 giờ qua."
        else:
            data_str = "Các mốc thời gian bé khóc (cường độ > 200):\n" + "\n".join(crying_points[:15])

        # 3. Gọi AI để trả lời dựa trên câu hỏi và dữ liệu
        actual_key = self.config.get("LLM", {}).get("GroqLLM", {}).get("api_key", "")
        if not actual_key:
            actual_key = self.config.get("ASR", {}).get("GroqASR", {}).get("api_key", "")
            
        question = original_text if original_text else "Tình hình bé khóc đêm qua thế nào?"
        answer = await AIProcessor.answer_history_question(actual_key, question, data_str)
        
        # 4. Gửi reply
        final_msg = (prefix + "\n\n" if prefix else "") + f"👶 *Tiểu Bảo trả lời:*\n{answer}"
        await self.client.send_message(chat_id, final_msg)

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
            clean_text, actual_key, history=history, msg_config=self.msg_config
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
            
            from core.utils.command_dispatcher import CommandDispatcher, CommandType
            
            # Phân tách lệnh query và control
            query_actions = []
            control_actions = []
            for act in actions:
                if CommandDispatcher.get_command_type(act) == CommandType.QUERY:
                    query_actions.append(act)
                else:
                    control_actions.append(act)

            # 1. Thực thi ngay các lệnh QUERY
            if query_actions:
                # Trộn reply_msg vào lệnh đầu tiên (thoát Markdown để tránh lỗi parse)
                from core.utils.util import escape_markdown
                main_prefix = escape_markdown(reply_msg)
                for i, act in enumerate(query_actions):
                    pfx = main_prefix if i == 0 else ""
                    await self._execute_direct_command(chat_id, act, prefix=pfx, original_text=clean_text)
                
            # 2. Gửi nút xác nhận cho các lệnh CONTROL (nếu có)
            if control_actions:
                intent_key = "+".join(control_actions)
                # Nếu đã gửi reply ở trên rồi thì không cần gửi lại trong confirmation
                confirm_text = reply_msg if not query_actions else ""
                await self.alerts.send_ai_confirmation(chat_id, confirm_text, intent_key)
            
            # Nếu không có control actions và cũng chưa gửi reply (vì k có query)
            if not query_actions and not control_actions and reply_msg:
                await self.client.send_message(chat_id, reply_msg)

        else:
            conv_reply = await AIProcessor.chat_conversational(clean_text, actual_key)
            default_reply = self.msg_config.get("commands", {}).get("ai_default_reply", {}).get("text", "😊")
            response_text = conv_reply or default_reply
            # ... rest of history logic ...

            history.append({"role": "user", "content": clean_text})
            history.append({"role": "assistant", "content": response_text})
            self.conversation_history[str(chat_id)] = history[-10:]

            DashboardUpdater.add_system_log("Chat", "conversation", {"q": clean_text[:40]})
            await self.client.send_message(chat_id, response_text)
