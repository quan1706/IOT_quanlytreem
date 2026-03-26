"""
core/telegram/router.py

Routing logic cho Telegram Bot — xử lý commands, callback buttons, và AI chat.
Tách biệt khỏi polling loop (bot.py) để dễ đọc và mở rộng.
"""
from config.logger import setup_logging
from core.telegram.menu_builder import (
    get_main_reply_keyboard,
    get_monitor_inline_keyboard,
    get_control_inline_keyboard,
    get_settings_inline_keyboard,
    get_unified_inline_menu,
    get_chart_action_keyboard
)

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
        self.voice_mode_enabled: dict[str, bool] = {}
        
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

        if cb_data.startswith("menu_"):
            await self.client.answer_callback_query(cb_id)
            if cb_data == "menu_status":
                from core.api.dashboard_handler import DASHBOARD_STATE
                await self._cmd_status(chat_id, DASHBOARD_STATE)
            elif cb_data == "menu_cry_history":
                await self._cmd_cry_history(chat_id)
            elif cb_data == "menu_chart_1":
                await self._cmd_baby_chart(chat_id, days=1)
            elif cb_data == "menu_chart_7":
                await self._cmd_baby_chart(chat_id, days=7)
            elif cb_data == "menu_chart_combined":
                await self._cmd_combined_chart(chat_id)
            elif cb_data == "menu_ai_analyze_":
                pass # Sẽ xử lý bên dưới bằng startswith
            elif cb_data == "menu_mode_auto":
                await self._cmd_mode(chat_id, "/mode auto")
            elif cb_data == "menu_mode_manual":
                await self._cmd_mode(chat_id, "/mode manual")
            elif cb_data == "menu_mock_on":
                from core.serverToClients import DashboardUpdater
                DashboardUpdater.set_mock_mode(True)
                await self.client.send_message(chat_id, "✅ Đã BẬT chế độ dữ liệu mẫu.")
            elif cb_data == "menu_mock_off":
                from core.serverToClients import DashboardUpdater
                DashboardUpdater.set_mock_mode(False)
                await self.client.send_message(chat_id, "❌ Đã TẮT chế độ dữ liệu mẫu.")
            elif cb_data == "menu_voice_on":
                await self._cmd_voice_mode(chat_id, "/voice on")
            elif cb_data == "menu_voice_off":
                await self._cmd_voice_mode(chat_id, "/voice off")
            elif cb_data == "menu_help":
                bot_info = await self.client.get_me()
                await self._cmd_help(chat_id, bot_username=bot_info.get("username", ""))
            elif cb_data == "menu_help_setkey":
                await self.client.send_message(chat_id, "Để cài đặt API key của Groq, hãy gửi:\n`/setkey gsk_YOUR_API_KEY`")
            elif cb_data == "menu_cat_monitor":
                await self.client.send_message(chat_id, "📊 Menu Giám sát:", reply_markup=get_monitor_inline_keyboard())
            elif cb_data == "menu_cat_control":
                await self.client.send_message(chat_id, "🎛️ Menu Điều khiển:", reply_markup=get_control_inline_keyboard())
            elif cb_data == "menu_cat_setting":
                await self.client.send_message(chat_id, "🤖 Menu Cài đặt:", reply_markup=get_settings_inline_keyboard())
            elif cb_data == "menu_start":
                # Quay lại menu chính
                from core.telegram.menu_builder import get_unified_inline_menu
                await self.client.send_message(
                    chat_id, "✨ *Menu chính:* Chọn chức năng bên dưới:",
                    reply_markup=get_unified_inline_menu()
                )
            
            # --- Xử lý AI nhận xét biểu đồ ---
            if cb_data.startswith("menu_ai_analyze_"):
                target = cb_data.replace("menu_ai_analyze_", "")
                await self.client.answer_callback_query(cb_id, text="🤖 Tiểu Bảo đang phân tích...")

                from core.utils.chart_gen import build_chart_summary
                from core.serverToClients.ai_processor import AIProcessor
                import json, os

                days = 1 if target == "combined" else int(target)

                # Đọc dữ liệu đa cảm biến từ chart_history.json (nguồn chính xác từ Dashboard)
                hist_labels, hist_cry, hist_temp, hist_hum = [], [], [], []
                try:
                    n_points = 144 if days == 1 else days * 48
                    hist_path = "data/chart_history.json"
                    if os.path.exists(hist_path):
                        with open(hist_path, "r", encoding="utf-8") as f:
                            hist = json.load(f)
                        hist_labels = hist.get("labels", [])[-n_points:]
                        hist_cry    = hist.get("cry",    [])[-n_points:]
                        hist_temp   = hist.get("temp",   [])[-n_points:]
                        hist_hum    = hist.get("hum",    [])[-n_points:]
                except Exception:
                    pass

                # Fallback: sinh ngẫu nhiên nếu chưa có file (mock mode)
                if not hist_labels:
                    from core.utils.chart_gen import generate_mock_cry_data
                    hist_labels, hist_cry = generate_mock_cry_data(days=days)

                # Xây dựng chuỗi tóm tắt bằng hàm dùng chung
                data_summary = build_chart_summary(
                    labels=hist_labels,
                    cry=hist_cry or None,
                    temp=hist_temp or None,
                    hum=hist_hum or None,
                )

                # Gọi AI qua hàm thống nhất (Gemini, cùng prompt với Dashboard)
                summary = await AIProcessor.summarize_baby_condition(self.config, data_summary, days)

                # Cập nhật caption ảnh biểu đồ trên Telegram
                current_caption = message_cb.get("caption", "")
                ai_prefix = self.msg_config.get("commands", {}).get("ai_summary_prefix", {}).get("text", "\n\n🤖 *Nhận định từ Tiểu Bảo:*\n")
                new_caption = current_caption + ai_prefix + summary

                await self.client.edit_message_caption(chat_id, message_cb.get("message_id"), new_caption)
            return

        if cb_data.startswith("confirm_"):
            command = cb_data.replace("confirm_", "")

            # 1. Ack callback query (bỏ spinner)
            await self.client.answer_callback_query(cb_id, text="⏳ Đang xử lý...")

            # 2. Log dashboard
            DashboardUpdater.add_action_log(
                action=command,
                source="telegram_button",
                result="Đang gửi lệnh xuống thiết bị...",
            )

            # 3. Gửi lệnh xuống ESP32 trực tiếp
            from core.serverToClients.esp32_commander import ESP32Commander
            success, exec_msg = await ESP32Commander().execute_command(command)
            
            # Cập nhật kết quả vào log
            DashboardUpdater.add_action_log(
                action=command,
                source="telegram_button",
                result=exec_msg,
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

        chat_id = message.get("chat", {}).get("id")
        chat_type = message.get("chat", {}).get("type")
        is_voice_input = False
        voice = message.get("voice")

        if voice and chat_id:
            await self.client.send_message(chat_id, "⏳ Đang nhận dạng giọng nói...")
            text = await self._transcribe_voice(voice)
            if not text:
                await self.client.send_message(chat_id, "❌ Không thể nhận dạng được giọng nói.")
                return
            message["text"] = text
            is_voice_input = True

        text = message.get("text", "")

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
            await self._cmd_welcome(chat_id, chat_type=chat_type)
            return

        # -- Nhận diện phím Reply Keyboard ---------------------------------
        if clean_text == "📊 Giám sát":
            await self.client.send_message(chat_id, "Vui lòng chọn chức năng Giám sát:", reply_markup=get_monitor_inline_keyboard())
            return
        if clean_text == "🎛️ Điều khiển":
            await self.client.send_message(chat_id, "Vui lòng chọn chức năng Điều khiển:", reply_markup=get_control_inline_keyboard())
            return
        if clean_text == "🤖 AI & Cài đặt":
            await self.client.send_message(chat_id, "Vui lòng chọn Cài đặt hoặc hỏi AI:", reply_markup=get_settings_inline_keyboard())
            return

        # -- /help ---------------------------------------------------------
        if clean_text.startswith("/help"):
            await self._cmd_help(chat_id, bot_username=bot_username)
            return

        # -- /menu ---------------------------------------------------------
        if clean_text.startswith("/menu") or clean_text.lower() == "menu":
            await self._cmd_menu(chat_id)
            return

        # -- /status -------------------------------------------------------
        if clean_text.startswith("/status"):
            await self._cmd_status(chat_id, DASHBOARD_STATE)
            return

        # -- /voice --------------------------------------------------------
        if clean_text.startswith("/voice"):
            await self._cmd_voice_mode(chat_id, clean_text)
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

        # -- /check_baby_pose ----------------------------------------------
        if clean_text.startswith("/check_baby_pose") or clean_text.startswith("/pose"):
            from core.serverToClients.esp32_commander import ESP32Commander
            success, msg = await ESP32Commander().execute_command("capture_pose")
            
            if success:
                reply_txt = "📸 *Lệnh chụp ảnh:* Đã yêu cầu Camera kiểm tra tư thế bé! Vui lòng chờ vài giây..."
            else:
                reply_txt = f"❌ *Lỗi:* {msg}"
            
            await self.client.send_message(chat_id, reply_txt)
            return

        # 3. Tin nhắn bình thường (AI) hoặc Ping gọi Menu
        # Chỉ xử lý AI nếu là chat private HOẶC được nhắc tên (mention) trong group
        # HOẶC gọi tên gợi nhớ (tiểu bảo, bảo bảo,...)
        trigger_names = ["tiểu bảo", "bảo bảo", "bảo ơi", "tiểu bảo ơi", "bé ơi"]
        is_named = any(name in clean_text.lower() for name in trigger_names)

        is_mentioned = chat_type == "private" or (
            bot_username and f"@{bot_username}" in text
        ) or is_named

        if not is_mentioned:
            return

        # Nếu ping trống (@bot) hoặc gọi menu (@bot menu) -> mở menu luôn
        if clean_text.lower() in ("", "menu", "bảng điều khiển", "menu chính"):
            from core.telegram.menu_builder import get_unified_inline_menu
            await self.client.send_message(
                chat_id, "✨ Chọn chức năng bên dưới:", reply_markup=get_unified_inline_menu()
            )
            return

        await self._handle_ai_message(chat_id, clean_text, is_voice_input)

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    async def _cmd_status(self, chat_id, state: dict, prefix: str = ""):
        from core.serverToClients import DashboardUpdater

        tmpl = self.msg_config.get("commands", {}).get("status", {}).get("text", "")
        if tmpl:
            pose_val = state.get('pose', 'UNKNOWN')
            pose_str = "Chưa xác định ❓"
            if pose_val == "PRONE":
                pose_str = "Nằm sấp ⚠️"
            elif pose_val == "SUPINE":
                pose_str = "Nằm ngửa ✅"

            response_text = (prefix + "\n\n" if prefix else "") + tmpl.format(
                mode=state['mode'].upper(),
                battery="85",
                esp_status="Đang kết nối ✅",
                temp=state.get('temp', '--'),
                humidity=state.get('humidity', '--'),
                baby_state="Bé đang ngủ ngon 😴",
                baby_posture=pose_str,
                ai_key=self.dashboard_handler.current_key
            )
        else:
            # Fallback
            response_text = f"{prefix}\n\n⚙️ STATUS: {state['mode']}"

        DashboardUpdater.add_system_log("Tele", "Server", {"cmd": "/status", "mode": state["mode"]})
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

    async def _cmd_voice_mode(self, chat_id, text: str):
        new_mode = text.replace("/voice", "").strip().lower()
        if new_mode in ("on", "bật"):
            self.voice_mode_enabled[str(chat_id)] = True
            await self.client.send_message(chat_id, "🎙️ Đã BẬT chế độ phản hồi bằng giọng nói.")
        elif new_mode in ("off", "tắt"):
            self.voice_mode_enabled[str(chat_id)] = False
            await self.client.send_message(chat_id, "🔇 Đã TẮT chế độ phản hồi bằng giọng nói.")
        else:
            current = "BẬT" if self.voice_mode_enabled.get(str(chat_id)) else "TẮT"
            await self.client.send_message(chat_id, f"Trạng thái voice hiện tại: {current}.\nDùng `/voice on` hoặc `/voice off` để thay đổi.")

    async def _cmd_setkey(self, chat_id, text: str):
        from core.serverToClients import DashboardUpdater

        new_key = text.replace("/setkey ", "").strip()
        if new_key.startswith("gsk_"):
            success = self.dashboard_handler.update_api_key(new_key)
            if success:
                msg = self.msg_config.get("commands", {}).get("setkey_success", {}).get("text", "✅ OK")
                DashboardUpdater.add_system_log("Tele", "Server", {"cmd": "/setkey", "result": "ok"})
            else:
                msg = self.msg_config.get("commands", {}).get("setkey_fail", {}).get("text", "❌ Fail")
        else:
            msg = self.msg_config.get("commands", {}).get("setkey_invalid", {}).get("text", "❌ Invalid")
        await self.client.send_message(chat_id, msg)

    async def _cmd_baby_chart(self, chat_id, prefix: str = "", days: int = 1):
        """Handler cho lệnh /baby_chart — hiển thị thống kê kèm nút gọi AI nhận xét."""
        from core.utils.chart_gen import generate_mock_cry_data, get_cry_chart_url
        from core.telegram.menu_builder import get_chart_action_keyboard
        
        self.logger.bind(tag=TAG).info(f"[CMD] /baby_chart {days} days from {chat_id}")
        
        # 1. Lấy dữ liệu
        labels, values = generate_mock_cry_data(days=days)
        
        # Kiểm tra nếu dữ liệu là fallback
        is_fallback = False
        if days == 1 and labels and "/" in labels[0]:
            is_fallback = True
        
        # 2. Tạo URL biểu đồ
        title_suffix = f"trong {days} ngày" if days > 1 else "trong 24h"
        title = "Lịch sử gần nhất (Dữ liệu cũ)" if is_fallback else f"Thống kê tiếng khóc {title_suffix}"
            
        chart_url = get_cry_chart_url(labels, values, title=title)
        
        # 3. Caption & Keyboard
        base_caption = self.msg_config.get("commands", {}).get("baby_chart", {}).get("text", "📊 Biểu đồ:")
        caption = (prefix + "\n\n" if prefix else "") + base_caption
        if is_fallback:
            caption += "\n\n⚠️ *Lưu ý:* Không có dữ liệu trong 24h qua. Đang hiển thị các bản ghi gần nhất."
            
        caption += "\n\n💡 Nhấn nút dưới đây để *Tiểu Bảo* nhận xét về biểu đồ này."
        
        await self.client.send_photo_url(chat_id, chart_url, caption=caption, reply_markup=get_chart_action_keyboard(str(days)))

    async def _cmd_combined_chart(self, chat_id):
        """Xuất biểu đồ tổng hợp (Khóc + Nhiệt độ) kèm nút gọi AI nhận xét."""
        from core.utils.chart_gen import generate_combined_mock_data, get_dual_chart_url
        from core.serverToClients.dashboard_updater import DASHBOARD_STATE
        from core.telegram.menu_builder import get_chart_action_keyboard
        
        # Nếu không ở mock mode, có thể thông báo người dùng bật lên
        is_mock = DASHBOARD_STATE.get("mock_mode", False)
        
        # Luôn sinh dữ liệu mẫu cho tính năng này như yêu cầu (vì hiện tại chưa có DB nhiệt độ thật)
        labels, cry, temps = generate_combined_mock_data(days=1)
        
        title = "Biểu đồ Tổng hợp (Dữ liệu mẫu)" if is_mock else "Biểu đồ Tổng hợp (Demo)"
        chart_url = get_dual_chart_url(labels, cry, temps, title=title)
        
        caption = "📊 *Biểu đồ kết hợp Khóc & Nhiệt độ:*\n\n"
        caption += "- 🔴 Trục trái: Cường độ tiếng khóc (RMS)\n"
        caption += "- 🔵 Trục phải: Nhiệt độ môi trường (°C)\n\n"
        
        if not is_mock:
            caption += "💡 *Mẹo:* Bạn có thể bật 'Dữ liệu mẫu' trong phần Cài đặt để thấy các điểm tương quan giả lập."
            
        await self.client.send_photo_url(chat_id, chart_url, caption=caption)

    async def _cmd_welcome(self, chat_id, prefix: str = "", chat_type: str = "private"):
        """Chào mừng và giới thiệu hệ thống."""
        tmpl = self.msg_config.get("commands", {}).get("welcome", {}).get("text", "🍼 Welcome")
        msg = (prefix + "\n\n" if prefix else "") + tmpl
        
        # Luôn sử dụng Unified Inline Menu để tăng tính tương tác
        await self.client.send_message(chat_id, msg, reply_markup=get_unified_inline_menu())

    async def _cmd_menu(self, chat_id, prefix: str = ""):
        """Hiển thị menu điều khiển bằng nút bấm (Inline Keyboard)."""
        from core.serverToClients.baby_actions import BabyCareAction
        
        reply_markup = BabyCareAction.get_inline_keyboard(cols=2)
        msg = (prefix + "\n\n" if prefix else "") + "🎛 **BẢNG ĐIỀU KHIỂN NHANH:**\nChọn thiết bị bạn muốn điều khiển:"
        await self.client.send_message(chat_id, msg, reply_markup=reply_markup)

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

    async def _transcribe_voice(self, voice: dict) -> str:
        file_id = voice.get("file_id")
        if not file_id:
            return ""
            
        file_info = await self.client.get_file(file_id)
        file_path = file_info.get("file_path")
        if not file_path:
            return ""
            
        voice_data = await self.client.download_file(file_path)
        if not voice_data:
            return ""
            
        import tempfile
        import os
        from core.providers.asr.openai import ASRProvider
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(voice_data)
            temp_path = f.name
            
        try:
            asr_config = self.config.get("ASR", {}).get("GroqASR", {})
            provider = ASRProvider(asr_config, False)
            class MockArtifacts:
                def __init__(self, p):
                    self.temp_path = p
            
            text, _ = await provider.speech_to_text(None, None, "ogg", MockArtifacts(temp_path))
            return text
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi nhận dạng giọng nói Telegram: {e}")
            return ""
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def _send_voice_if_needed(self, chat_id, text, is_voice_input):
        if not text:
            return
            
        voice_mode = self.voice_mode_enabled.get(str(chat_id), False)
        if not (is_voice_input or voice_mode):
            return
            
        try:
            import edge_tts
            # Sử dụng voice tiếng Việt
            voice_config = self.config.get("TTS", {}).get("EdgeTTS", {})
            voice_name = voice_config.get("voice", "vi-VN-HoaiMyNeural")
            
            communicate = edge_tts.Communicate(text, voice=voice_name)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            if audio_data:
                await self.client.send_voice(chat_id, audio_data)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi tạo TTS Telegram: {e}")

    # ------------------------------------------------------------------
    # AI message handling
    # ------------------------------------------------------------------
    async def _handle_ai_message(self, chat_id, clean_text: str, is_voice_input: bool = False):
        from core.serverToClients import DashboardUpdater, AIProcessor

        actual_key = self.config.get("LLM", {}).get("GroqLLM", {}).get("api_key", "")
        if not actual_key:
            actual_key = self.config.get("ASR", {}).get("GroqASR", {}).get("api_key", "")

        self.logger.bind(tag=TAG).info(
            f"[AI] Nhận message: '{clean_text}' | Key: {'OK' if actual_key else 'TRỐNG'}"
        )
        DashboardUpdater.add_system_log("Tele", "Server", {"text": clean_text})

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
        
        # --- Fallback Regex (Nếu AI không nhận lệnh hoặc lỗi Rate Limit) ---
        if not ai_result or not ai_result.get("actions") or "none" in ai_result["actions"]:
            regex_actions = []
            if any(kw in clean_text.lower() for kw in ["ru nôi", "ru vong", "ru võng", "bật nôi", "đưa võng"]):
                regex_actions.append("ru_vong")
            if any(kw in clean_text.lower() for kw in ["tắt nôi", "dừng nôi", "ngừng nôi", "dừng nôi"]):
                regex_actions.append("tat_noi")
            if any(kw in clean_text.lower() for kw in ["bật quạt", "bat quat", "mở quạt"]):
                regex_actions.append("bat_quat")
            if any(kw in clean_text.lower() for kw in ["tắt quạt", "dừng quạt", "tat quat"]):
                regex_actions.append("tat_quat")
            if any(kw in clean_text.lower() for kw in ["dừng hết", "tắt hết", "dừng tất cả"]):
                regex_actions.append("dung")
            
            if regex_actions:
                ai_result = {
                    "actions": regex_actions,
                    "reply": "Tôi đã nhận ra lệnh của bạn, bạn có muốn thực hiện không?"
                }

        self.logger.bind(tag=TAG).info(f"[AI] Kết quả cuối cùng: {ai_result}")

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
            
            # 3. Nếu KHÔNG có action nào nhưng CÓ reply_msg từ AI (chat thông thường của Intent LLM)
            if not query_actions and not control_actions and reply_msg:
                await self.client.send_message(chat_id, reply_msg, reply_markup=get_unified_inline_menu())
                
            if reply_msg:
                await self._send_voice_if_needed(chat_id, reply_msg, is_voice_input)

        else:
            # Fallback nếu analyze_intent fail hoàn toàn (lỗi API hoặc parse)
            conv_reply = await AIProcessor.chat_conversational(clean_text, actual_key)
            default_reply = self.msg_config.get("commands", {}).get("ai_default_reply", {}).get("text", "😊")
            response_text = conv_reply or default_reply
            # ... rest of history logic ...
            history.append({"role": "user", "content": clean_text})
            history.append({"role": "assistant", "content": response_text})
            self.conversation_history[str(chat_id)] = history[-10:]

            DashboardUpdater.add_system_log("Tele", "Server", {"q": clean_text[:40]})
            self.logger.bind(tag=TAG).info(f"Fallback response len {len(response_text)}")
            if len(response_text.strip()) > 0:
                await self.client.send_message(chat_id, response_text, reply_markup=get_unified_inline_menu())
                await self._send_voice_if_needed(chat_id, response_text, is_voice_input)
