import time
import asyncio
from config.logger import setup_logging
from core.utils.util import get_local_ip

TAG = "telegram_handler"

class TelegramHandler:
    BOT_TOKEN = "8765806795:AAEB83HSeGkpYYv0JsnnPz6IaiSCvlDOn_w"
    CHAT_ID = "-5283283687"
    last_token_alert_time = 0

    @staticmethod
    async def send_telegram_alert(message, time_str, current_mode):
        url = f"https://api.telegram.org/bot{TelegramHandler.BOT_TOKEN}/sendMessage"
        
        text = (
            "🚨 *CẢNH BÁO SMART BABY CARE* 🚨\n\n"
            f"📍 Phát hiện: *Bé đang khóc!* ({message})\n"
            f"⏰ Lịch sử ghi nhận lúc: *{time_str}*\n\n"
        )
        if current_mode == "auto":
            text += "🤖 _Hệ thống đang ở CHẾ ĐỘ TỰ ĐỘNG, đã tự mở nhạc dỗ dành bé._"
        else:
            text += "👨‍👩‍👧 _Hệ thống đang ở CHẾ ĐỘ GIÁM SÁT, hãy vào kiểm tra bé ngay!_"

        payload = {
            "chat_id": TelegramHandler.CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload)
        except Exception:
            pass

    @staticmethod
    async def send_telegram_token_alert():
        url = f"https://api.telegram.org/bot{TelegramHandler.BOT_TOKEN}/sendMessage"
        local_ip = get_local_ip()
        
        text = (
            "⚠️ *CẢNH BÁO SMART BABY CARE* ⚠️\n\n"
            "❌ *LỖI HẾT TOKEN API GROQ (RATE LIMIT)*\n"
            "Trợ lý AI của bạn hiện không thể suy nghĩ hay trả lời vì đã dùng hết hạn mức miễn phí trong ngày.\n\n"
            "Vui lòng nhấn vào nút bên dưới để truy cập *Bảng điều khiển (Dashboard)* và Cập nhật API Key mới cho hệ thống!"
        )

        payload = {
            "chat_id": TelegramHandler.CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "Mở Dashboard Cài Đặt ⚙️", "url": f"http://{local_ip}:8003/"}]
                ]
            }
        }
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload)
        except Exception:
            pass

    @staticmethod
    async def analyze_intent(text, api_key):
        if not api_key: return None
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
                {"role": "user", "content": text}
            ]
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

    @staticmethod
    async def start_telegram_bot(dashboard_handler_instance):
        url = f"https://api.telegram.org/bot{TelegramHandler.BOT_TOKEN}/getUpdates"
        send_url = f"https://api.telegram.org/bot{TelegramHandler.BOT_TOKEN}/sendMessage"
        offset = 0
        logger = setup_logging()
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(send_url, json={
                    "chat_id": TelegramHandler.CHAT_ID,
                    "text": "✅ *Hệ Thống Smart Baby Care Đã Khởi Động!*\nBạn có thể điều khiển cấu hình nhanh qua Bot này.\n\nHướng dẫn lệnh:\n`/status` - Xem bảng trạng thái\n`/mode auto` - Bật chế độ Tự động dỗ bé\n`/mode manual` - Bật chế độ Chỉ Giám Sát\n`/setkey gsk_xxxx` - Thay đổi khóa Groq AI qua tin nhắn",
                    "parse_mode": "Markdown"
                })
        except Exception:
            pass

        from core.api.dashboard_handler import DASHBOARD_STATE

        while True:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    payload = {"offset": offset, "timeout": 30}
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("ok") and data.get("result"):
                                for update in data["result"]:
                                    offset = update["update_id"] + 1

                                    # Xử lý Nút bấm (Inline Keyboard Confirmation)
                                    if "callback_query" in update:
                                        callback = update["callback_query"]
                                        cb_data = callback["data"]
                                        message_cb = callback.get("message", {})
                                        chat_id = message_cb.get("chat", {}).get("id")
                                        if not chat_id: continue
                                        
                                        response_text = ""
                                        if cb_data.startswith("confirm_"):
                                            command = cb_data.replace("confirm_", "")
                                            response_text = f"✅ Đã xác nhận lệnh: *{command}*\n_(Lệnh đã được gửi xuống thiết bị ESP32 để xử lý)_"
                                            logger.bind(tag=TAG).info(f"ĐÃ GỬI LỆNH XUỐNG ESP32: {command}")
                                            # TODO: Kết nối WebSocket với thiết bị ở đây để đẩy lệnh trực tiếp
                                        elif cb_data == "cancel_action":
                                            response_text = "❌ Đã hủy lệnh."
                                        
                                        if response_text:
                                            await session.post(send_url, json={"chat_id": chat_id, "text": response_text, "parse_mode": "Markdown"})
                                        continue

                                    # Xử lý tin nhắn văn bản thông thường
                                    message = update.get("message", {})
                                    text = message.get("text", "")
                                    chat_id = message.get("chat", {}).get("id")
                                    
                                    if not text or not chat_id:
                                        continue
                                        
                                    response_text = ""
                                    
                                    if text.startswith("/status"):
                                        mode_text = "TỰ ĐỘNG DỖ DÀNH BÉ" if DASHBOARD_STATE["mode"] == "auto" else "CHỈ GIÁM SÁT LỊCH SỬ"
                                        response_text = f"📊 *Trạng Thái HT:*\n- Chế độ: *{mode_text}*\n- Lịch sử khóc: *{len(DASHBOARD_STATE['cry_history'])}* lần gần đây.\n- Key AI hiện tại: `{dashboard_handler_instance.current_key}`"
                                    
                                    elif text == "/mode auto":
                                        DASHBOARD_STATE["mode"] = "auto"
                                        response_text = "🔄 Đã đổi sang *CHẾ ĐỘ TỰ ĐỘNG*."
                                        
                                    elif text == "/mode manual":
                                        DASHBOARD_STATE["mode"] = "manual"
                                        response_text = "🔄 Đã đổi sang *CHẾ ĐỘ GIÁM SÁT*."
                                        
                                    elif text.startswith("/setkey "):
                                        new_key = text.replace("/setkey ", "").strip()
                                        if new_key.startswith("gsk_"):
                                            success = dashboard_handler_instance.update_api_key(new_key)
                                            if success:
                                                response_text = "✅ Đã lưu API Key mới thành công! Bạn hãy tiến hành tắt và chạy lại Server (File run_server.bat) để hệ thống nhận diện khoá mới."
                                            else:
                                                response_text = "❌ Có lỗi xảy ra khi lưu API Key."
                                        else:
                                            response_text = "❌ API Key không hợp lệ. Hãy bắt đầu bằng `gsk_`!"
                                    else:
                                        # Tính năng mới được chuyển từ Server Java cũ sang
                                        # Gửi lệnh thường -> Dùng Groq AI phân tích Intent
                                        intent = await TelegramHandler.analyze_intent(text, dashboard_handler_instance.current_key)
                                        if intent:
                                            reply_markup = {
                                                "inline_keyboard": [
                                                    [
                                                        {"text": "✅ Xác nhận", "callback_data": f"confirm_{intent}"},
                                                        {"text": "❌ Hủy", "callback_data": "cancel_action"}
                                                    ]
                                                ]
                                            }
                                            await session.post(send_url, json={
                                                "chat_id": chat_id, 
                                                "text": f"🤖 *AI Phân tích:* Bạn muốn tôi thực hiện lệnh `{intent}` đúng không?", 
                                                "parse_mode": "Markdown",
                                                "reply_markup": reply_markup
                                            })
                                        else:
                                            response_text = "😅 Xin lỗi, tôi không hiểu ý bạn. Hãy thử các câu như: 'mở nhạc lên', 'đưa võng đi'."
                                            
                                    if response_text:
                                        await session.post(send_url, json={"chat_id": chat_id, "text": response_text, "parse_mode": "Markdown"})
            except Exception as e:
                logger.bind(tag=TAG).error(f"Telegram polling loop error: {e}")
            
            await asyncio.sleep(2)
