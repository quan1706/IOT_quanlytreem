import json
import base64
import asyncio
from aiohttp import web
from config.logger import setup_logging
from core.api.base_handler import BaseHandler
from core.utils.util import is_valid_image_file
import google.generativeai as genai

TAG = "PoseHandler"
MAX_FILE_SIZE = 5 * 1024 * 1024

class PoseHandler(BaseHandler):
    def __init__(self, config: dict):
        super().__init__(config)
        self.logger = setup_logging()
        
        self.gemini_key = config.get("LLM", {}).get("GeminiLLM", {}).get("api_key", "")
        if not self.gemini_key:
            self.gemini_key = config.get("ASR", {}).get("GroqASR", {}).get("api_key", "")
            
        self.gemini_model_name = config.get("LLM", {}).get("GeminiLLM", {}).get("model_name", "gemini-1.5-flash")

        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)

    async def handle_post(self, request):
        """Xử lý POST /api/vision/pose từ ESP32-CAM"""
        try:
            self.logger.bind(tag=TAG).info("--- NHẬN ẢNH CHECK POSE TỪ ESP32-CAM ---")
            
            # Đọc multipart/form-data
            data = await request.post()
            image_field = data.get("image") or data.get("photo")
            if not image_field:
                return web.json_response({"success": False, "error": "No image provided"}, status=400)
                
            image_bytes = image_field.file.read()
            
            if len(image_bytes) > MAX_FILE_SIZE:
                return web.json_response({"success": False, "error": "Image too large"}, status=400)

            if not is_valid_image_file(image_bytes):
                return web.json_response({"success": False, "error": "Invalid image format"}, status=400)

            # Phân tích bằng Gemini
            if not self.gemini_key:
                self.logger.bind(tag=TAG).error("Chưa cấu hình Gemini API Key.")
                return web.json_response({"success": False, "error": "Missing API Key"}, status=500)

            from core.serverToClients import DashboardUpdater
            
            # Gọi Gemini API ngoại tuyến qua run_in_executor để không block event loop
            loop = asyncio.get_event_loop()
            result_text = await loop.run_in_executor(None, self._analyze_image_sync, image_bytes)
            
            self.logger.bind(tag=TAG).info(f"Kết quả phân tích từ Gemini: {result_text}")
            
            is_prone = "PRONE" in result_text.upper() or "ÚP" in result_text.upper() or "SẤP" in result_text.upper()
            
            # Cập nhật state toàn cục
            pose_status = "PRONE" if is_prone else "SUPINE"
            DashboardUpdater.update_pose(pose_status)
            
            if is_prone:
                self.logger.bind(tag=TAG).warning("🚨 Phát hiện trẻ đang nằm lật úp/sấp (PRONE)!")
                # Gửi cảnh báo Telegram
                if hasattr(self, '_telegram_alerts') and self._telegram_alerts:
                    caption = "🚨 *CẢNH BÁO NGUY HIỂM: PHÁT HIỆN BÉ NẰM ÚP (PRONE)*\n\nHệ thống AI (Gemini) phân tích hình ảnh và phát hiện bé đang trong tư thế nằm sấp. Vui lòng kiểm tra bé ngay lập tức để tránh rủi ro SIDS!"
                    asyncio.create_task(self._telegram_alerts.send_photo_alert(image_bytes, caption))
            else:
                self.logger.bind(tag=TAG).info("✅ Trẻ đang nằm ngửa (SUPINE) hoặc an toàn.")

            return web.json_response({
                "success": True, 
                "pose": "PRONE" if is_prone else "SUPINE",
                "raw_response": result_text
            })

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi xử lý pose: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    def _analyze_image_sync(self, image_bytes: bytes) -> str:
        """Hàm đồng bộ gọi Gemini SDK để phân tích ảnh."""
        model = genai.GenerativeModel(self.gemini_model_name)
        prompt = (
            "Bạn là một trợ lý AI phân tích tư thế ngủ của trẻ sơ sinh để phòng chống hội chứng SIDS. "
            "Hãy xem bức ảnh này và cho tôi biết bé đang nằm sấp/úp (nguy hiểm) hay nằm ngửa (an toàn) hay tư thế khác? "
            "Nếu nằm sấp/úp (chỉ thấy phần lưng/sau gáy/vai cao hơn mũi v.v.), hãy trả lời TỪ KHÓA ĐẦU TIÊN là PRONE. "
            "Nếu nằm ngửa (thấy rõ mặt, bụng), hãy trả lời TỪ KHÓA ĐẦU TIÊN là SUPINE. "
            "Phân tích ngắn gọn."
        )
        
        # Gemini nhận dict với mime_type và data
        image_parts = [
            {
                "mime_type": "image/jpeg",
                "data": image_bytes
            }
        ]
        
        response = model.generate_content([prompt, image_parts[0]])
        return response.text

    def set_telegram_alerts(self, alerts):
        """Được gọi từ http_server để gán TelegramAlerts."""
        self._telegram_alerts = alerts
