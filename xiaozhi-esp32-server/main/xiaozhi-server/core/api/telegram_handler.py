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
                                            
                                    if response_text:
                                        await session.post(send_url, json={"chat_id": chat_id, "text": response_text, "parse_mode": "Markdown"})
            except Exception as e:
                logger.bind(tag=TAG).error(f"Telegram polling loop error: {e}")
            
            await asyncio.sleep(2)
