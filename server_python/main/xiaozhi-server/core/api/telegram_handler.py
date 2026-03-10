import time
import asyncio
import json
from config.logger import setup_logging
from core.utils.util import get_local_ip

TAG = "telegram_handler"


class TelegramHandler:
    BOT_TOKEN = "8765806795:AAEB83HSeGkpYYv0JsnnPz6IaiSCvlDOn_w"
    CHAT_ID = "-5283283687"
    last_token_alert_time = 0

    # ─────────────────────────────────────────────────────────────────────
    # Các hàm gửi Telegram cũ — GIỮ LẠI để tương thích ngược
    # (Sẽ dần dần chuyển hết sang TelegramNotifier)
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    async def send_telegram_alert(message, time_str, current_mode):
        from core.serverToClients import TelegramNotifier
        notifier = TelegramNotifier()
        await notifier.send_cry_alert(message, time_str, current_mode)

    @staticmethod
    async def send_telegram_token_alert():
        from core.serverToClients import TelegramNotifier
        notifier = TelegramNotifier()
        local_ip = get_local_ip()
        await notifier.send_token_alert(local_ip)

    # ─────────────────────────────────────────────────────────────────────
    # AI phân tích intent
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    async def analyze_intent(text, api_key):
        if not api_key:
            return None
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        prompt = (
            "Bạn là trợ lý AI cho hệ thống Baby Monitor thông minh. "
            "Nhiệm vụ của bạn là phân tích ý định (intent) của người dùng từ tin nhắn tiếng Việt. "
            "Các nhãn lệnh hợp lệ: \n"
            "- phat_nhac: Bật nhạc, phát nhạc ru bé, play music.\n"
            "- ru_vong: Bật võng, đưa nôi, swing.\n"
            "- dung: Dừng tất cả, tắt nhạc, dừng võng, stop.\n"
            "- hinh_anh: Xem camera, chụp ảnh bé, take photo.\n"
            "Quy tắc:\n"
            "1. Chỉ trả về DUY NHẤT mã lệnh (ví dụ: phat_nhac) hoặc 'none' nếu không rõ ràng.\n"
            "2. Không giải thích, không thêm văn bản thừa."
        )
        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
        }
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data["choices"][0]["message"]["content"].strip().lower()
                        return None if result == "none" else result
        except Exception:
            pass
        return None

    # ─────────────────────────────────────────────────────────────────────
    # Xử lý callback button (phat_nhac, ru_vong, dung, hinh_anh)
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    async def _handle_callback_query(callback, session, notifier, logger):
        """
        Xử lý khi người dùng nhấn nút inline keyboard trong Telegram.
        Thực hiện 4 việc:
          1. Ack callback để Telegram bỏ spinner trên button
          2. Gửi bot reply trong Telegram
          3. Ghi log server console
          4. Cập nhật action_logs trong Dashboard
        """
        from core.serverToClients import DashboardUpdater, ESP32Commander, AIProcessor

        cb_data = callback["data"]
        cb_id = callback.get("id", "")
        message_cb = callback.get("message", {})
        chat_id = message_cb.get("chat", {}).get("id")
        if not chat_id:
            return

        if cb_data.startswith("confirm_"):
            command = cb_data.replace("confirm_", "")

            # 1. Ack callback query (bỏ spinner)
            await notifier.answer_callback_query(cb_id, text="⏳ Đang xử lý...")

            # 2. Ghi log server + dashboard (không có phần cứng)
            from core.serverToClients import DashboardUpdater
            DashboardUpdater.add_action_log(
                action=command,
                source="telegram_button",
                result="Đã ghi log (chưa kết nối phần cứng)",
            )

            # 3. Gửi bot reply trong Telegram
            command_labels = {
                "phat_nhac": "🎵 Phát nhạc ru bé",
                "ru_vong":   "🔄 Đưa võng / nôi",
                "dung":      "⏹ Dừng tất cả thiết bị",
                "hinh_anh":  "📸 Chụp ảnh bé",
            }
            label = command_labels.get(command, command)
            reply_text = (
                f"✅ *Đã xác nhận lệnh: {label}*\n"
                f"_(Lệnh đã được ghi vào Dashboard.)_"
            )
            await notifier.send_message(chat_id, reply_text)

            logger.bind(tag=TAG).info(
                f"[TELEGRAM BTN] Người dùng nhấn '{command}'"
            )

        elif cb_data.startswith("ai_confirm_"):
            command = cb_data.replace("ai_confirm_", "")
            await notifier.answer_callback_query(cb_id, text="🚀 Thực hiện...")
            await AIProcessor.execute_confirmed_action(command, chat_id, notifier)

        elif cb_data.startswith("ai_cancel_"):
            command = cb_data.replace("ai_cancel_", "")
            await notifier.answer_callback_query(cb_id, text="❌ Đã từ chối")
            await AIProcessor.cancel_suggested_action(command, chat_id, notifier)

    # ─────────────────────────────────────────────────────────────────────
    # Vòng lặp polling chính
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    async def start_telegram_bot(dashboard_handler_instance):
        from core.serverToClients import TelegramNotifier, DashboardUpdater, AIProcessor
        from core.api.dashboard_handler import DASHBOARD_STATE

        notifier = TelegramNotifier()
        logger = setup_logging()
        url = f"https://api.telegram.org/bot{TelegramHandler.BOT_TOKEN}/getUpdates"
        offset = 0
        conversation_history = {}  # chat_id → list of {role, content}

        # Thông tin bot để nhận diện tag/mention
        bot_info = {}
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.telegram.org/bot{TelegramHandler.BOT_TOKEN}/getMe") as resp:
                    if resp.status == 200:
                        bot_info = (await resp.json()).get("result", {})
        except Exception:
            pass
        bot_username = bot_info.get("username", "")

        # Gửi thông báo khởi động
        try:
            await notifier.send_startup_message()
        except Exception:
            pass

        while True:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    payload = {"offset": offset, "timeout": 20}
                    logger.bind(tag=TAG).info(f"[POLL] Calling getUpdates offset={offset}")
                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            data = await response.json()
                            if not data.get("ok"):
                                logger.bind(tag=TAG).error(f"[POLL] Telegram error: {data}")
                            elif data.get("result"):
                                logger.bind(tag=TAG).info(f"[POLL] Got {len(data['result'])} update(s)")
                                for update in data["result"]:
                                    offset = update["update_id"] + 1

                                    # ── Xử lý nút bấm inline keyboard ──
                                    if "callback_query" in update:
                                        await TelegramHandler._handle_callback_query(
                                            update["callback_query"],
                                            session,
                                            notifier,
                                            logger,
                                        )
                                        continue

                                    # ── Xử lý tin nhắn text ──
                                    message = update.get("message", {})
                                    text = message.get("text", "")
                                    chat_id = message.get("chat", {}).get("id")
                                    chat_type = message.get("chat", {}).get("type") # private, group, supergroup

                                    if not text or not chat_id:
                                        continue

                                    logger.bind(tag=TAG).info(f"[MSG] chat_type={chat_type} text='{text[:60]}' bot_username='{bot_username}'")

                                    # Check if bot is mentioned or it's a private chat
                                    is_mentioned = False
                                    if chat_type == "private":
                                        is_mentioned = True
                                    elif bot_username and (f"@{bot_username}" in text):
                                        is_mentioned = True
                                    
                                    # Loại bỏ phần mention bot để AI xử lý nội dung sạch
                                    clean_text = text
                                    if bot_username:
                                        clean_text = text.replace(f"@{bot_username}", "").strip()

                                    response_text = ""

                                    if text.startswith("/status"):
                                        mode_text = (
                                            "TỰ ĐỘNG DỖ DÀNH BÉ"
                                            if DASHBOARD_STATE["mode"] == "auto"
                                            else "CHỈ GIÁM SÁT LỊCH SỬ"
                                        )
                                        response_text = (
                                            f"📊 *Trạng Thái HT:*\n"
                                            f"- Chế độ: *{mode_text}*\n"
                                            f"- Lịch sử khóc: *{len(DASHBOARD_STATE['cry_history'])}* lần gần đây.\n"
                                            f"- Hành động gần nhất: *{len(DASHBOARD_STATE.get('action_logs', []))}* mục.\n"
                                            f"- Key AI hiện tại: `{dashboard_handler_instance.current_key}`"
                                        )
                                        DashboardUpdater.add_system_log("Command", "/status", {"mode": DASHBOARD_STATE["mode"]})

                                    elif text.startswith("/mode "):
                                        new_mode = text.replace("/mode ", "").strip()
                                        if new_mode in ("auto", "manual"):
                                            DashboardUpdater.set_mode(new_mode)
                                            mode_label = "TỰ ĐỘNG DỖ DÀNH BÉ" if new_mode == "auto" else "CHỈ GIÁM SÁT"
                                            response_text = f"🔄 Đã đổi sang *{mode_label}*."
                                        else:
                                            response_text = "❌ Lệnh không đúng. Dùng `/mode auto` hoặc `/mode manual`."

                                    elif text.startswith("/setkey "):
                                        new_key = text.replace("/setkey ", "").strip()
                                        if new_key.startswith("gsk_"):
                                            success = dashboard_handler_instance.update_api_key(new_key)
                                            if success:
                                                response_text = (
                                                    "✅ Đã lưu API Key mới thành công! "
                                                    "Hãy restart Server để nhận khoá mới."
                                                )
                                                DashboardUpdater.add_system_log("Command", "/setkey", {"result": "ok"})
                                            else:
                                                response_text = "❌ Có lỗi xảy ra khi lưu API Key."
                                        else:
                                            response_text = "❌ API Key không hợp lệ. Hãy bắt đầu bằng `gsk_`!"

                                    else:
                                        # Xử lý AI khi được mention hoặc chat riêng
                                        if is_mentioned:
                                            actual_key = dashboard_handler_instance.config.get("LLM", {}).get("GroqLLM", {}).get("api_key", "")
                                            if not actual_key:
                                                actual_key = dashboard_handler_instance.config.get("ASR", {}).get("GroqASR", {}).get("api_key", "")

                                            logger.bind(tag=TAG).info(f"[AI] Nhận message: '{clean_text}' | Key: {'OK' if actual_key else 'TRỐNG'}")

                                            if not actual_key:
                                                await notifier.send_message(chat_id, "⚠️ Chưa có Groq API Key. Vui lòng cài key bằng /setkey gsk_xxx.")
                                                continue

                                            # Lấy lịch sử hội thoại cho chat_id này
                                            history = conversation_history.get(str(chat_id), [])

                                            # Thử phân tích intent điều khiển thiết bị
                                            ai_result = await AIProcessor.analyze_intent_conversational(clean_text, actual_key, history=history)
                                            logger.bind(tag=TAG).info(f"[AI] Kết quả: {ai_result}")

                                            if ai_result:
                                                # Có intent điều khiển → hỏi xác nhận
                                                actions = ai_result["actions"]
                                                reply_msg = ai_result["reply"]

                                                # Cập nhật history với tin người dùng + bot reply
                                                history.append({"role": "user", "content": clean_text})
                                                history.append({"role": "assistant", "content": reply_msg})
                                                conversation_history[str(chat_id)] = history[-10:]

                                                DashboardUpdater.add_ai_log(
                                                    query=clean_text,
                                                    response=reply_msg,
                                                    action=",".join(actions),
                                                    status="suggested"
                                                )
                                                # Gửi xác nhận với danh sách actions (chuỗi phân cách bởi "+")
                                                intent_key = "+".join(actions)
                                                await notifier.send_ai_confirmation(chat_id, reply_msg, intent_key)
                                            else:
                                                # Không có intent → gọi AI trò chuyện tự nhiên
                                                conv_reply = await AIProcessor.chat_conversational(clean_text, actual_key)
                                                response_text = conv_reply or "Tôi đang lắng nghe bạn! 😊"

                                                # Cập nhật history
                                                history.append({"role": "user", "content": clean_text})
                                                history.append({"role": "assistant", "content": response_text})
                                                conversation_history[str(chat_id)] = history[-10:]

                                                DashboardUpdater.add_system_log("Chat", "conversation", {"q": clean_text[:40]})

                                    if response_text:
                                        await notifier.send_message(chat_id, response_text)

            except Exception as e:
                import traceback
                logger.bind(tag=TAG).error(f"Telegram polling loop error: {e}\n{traceback.format_exc()}")

            await asyncio.sleep(1)

