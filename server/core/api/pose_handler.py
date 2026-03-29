import json
import base64
import asyncio
from aiohttp import web
from config.logger import setup_logging
from core.api.base_handler import BaseHandler
from core.utils.util import is_valid_image_file, escape_markdown
from google import genai
from google.genai import types

TAG = "PoseHandler"
MAX_FILE_SIZE = 5 * 1024 * 1024

class PoseHandler(BaseHandler):
    def __init__(self, config: dict):
        super().__init__(config)
        self.logger = setup_logging()
        
        self.gemini_key = config.get("LLM", {}).get("GeminiLLM", {}).get("api_key", "")
        if not self.gemini_key:
            self.gemini_key = config.get("ASR", {}).get("GroqASR", {}).get("api_key", "")
            
        # Ưu tiên bản 2.5 flash như yêu cầu, nếu không có lấy từ config, mặc định là 2.0 flash
        self.gemini_model_name = config.get("LLM", {}).get("GeminiLLM", {}).get("model_name", "gemini-2.0-flash")
        if "1.5" in self.gemini_model_name:
             self.gemini_model_name = "gemini-2.0-flash" 

        self.client = None
        if self.gemini_key:
            try:
                self.client = genai.Client(api_key=self.gemini_key)
                self.logger.bind(tag=TAG).info(f"Khởi tạo Gemini Client (SDK mới) với model: {self.gemini_model_name}")
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"Lỗi khởi tạo Gemini SDK mới: {e}")
        
        # Cấu hình Groq Vision làm phương án dự phòng
        self.groq_key = config.get("LLM", {}).get("GroqLLM", {}).get("api_key", "")
        self.groq_model_name = "llama-3.2-11b-vision-preview"

    async def handle_post(self, request):
        """Xử lý POST /api/vision/pose từ ESP32-CAM"""
        try:
            self.logger.bind(tag=TAG).info("--- NHẬN ẢNH CHECK POSE TỪ ESP32-CAM (SDK NEW) ---")
            
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
            if not self.gemini_key or not self.client:
                self.logger.bind(tag=TAG).error("Chưa cấu hình Gemini API Key hoặc khởi tạo SDK thất bại.")
                return web.json_response({"success": False, "error": "Missing API Key"}, status=500)

            # Chạy nền phân tích để phản hồi HTTP ngay lập tức (tránh ESP32 timeout)
            asyncio.create_task(self._process_pose_background(image_bytes))

            return web.json_response({
                "success": True, 
                "message": f"Image received. Processing with {self.gemini_model_name} (SDK New)."
            })

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi xử lý pose: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def _process_pose_background(self, image_bytes: bytes):
        try:
            from core.serverToClients import DashboardUpdater
            
            loop = asyncio.get_event_loop()
            result_text = await loop.run_in_executor(None, self._analyze_image_sync, image_bytes)
            
            self.logger.bind(tag=TAG).info(f"Kết quả phân tích Gemini (SDK mới): {result_text}")
            
            # Nếu Gemini lỗi, thử dùng Groq Vision
            if "ERROR" in result_text.upper() or not result_text:
                if self.groq_key and "YOUR_GROQ" not in self.groq_key:
                    self.logger.bind(tag=TAG).warning("Đang chuyển sang Groq Vision dự phòng...")
                    result_text = await loop.run_in_executor(None, self._analyze_image_groq, image_bytes)
                    self.logger.bind(tag=TAG).info(f"Kết quả phân tích từ Groq Vision: {result_text}")
            
            # Xử lý kết quả cuối cùng
            is_error = "ERROR" in result_text.upper() or "EXCEPTION" in result_text.upper() or "400" in result_text
            is_prone = any(kw in result_text.upper() for kw in ["PRONE", "ÚP", "SẤP", "NẰM SẤP"])
            
            if is_error:
                self.logger.bind(tag=TAG).error(f"Cả hai AI đều thất bại: {result_text}")
                if hasattr(self, '_telegram_alerts') and self._telegram_alerts:
                    safe_error = escape_markdown(result_text)
                    caption = f"⚠️ *CẢNH BÁO: AI LỖI PHÂN TÍCH*\nEm không nhìn rõ được bé lúc này. Ba mẹ hãy tự xem ảnh để kiểm tra bé nhé!"
                    asyncio.create_task(self._telegram_alerts.send_photo_alert(image_bytes, caption))
                DashboardUpdater.update_pose("ERROR")
                return

            # Cập nhật state toàn cục
            pose_status = "PRONE" if is_prone else "SUPINE"
            DashboardUpdater.update_pose(pose_status)
            
            if is_prone:
                self.logger.bind(tag=TAG).warning("🚨 Phát hiện trẻ đang nằm lật úp/sấp (PRONE)!")
                if hasattr(self, '_telegram_alerts') and self._telegram_alerts:
                    caption = "🚨 *CẢNH BÁO NGUY HIỂM: PHÁT HIỆN BÉ NẰM ÚP (PRONE)*\n\nBa mẹ hãy kiểm tra bé ngay lập tức!"
                    asyncio.create_task(self._telegram_alerts.send_photo_alert(image_bytes, caption))
            else:
                self.logger.bind(tag=TAG).info("✅ Trẻ đang nằm ngửa (SUPINE) hoặc an toàn.")
                
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi xử lý nền pose: {e}")

    def _analyze_image_sync(self, image_bytes: bytes) -> str:
        """Hàm đồng bộ gọi Gemini SDK (google-genai) để phân tích ảnh."""
        if not self.client:
            return "ERROR: SDK client not initialized"
            
        prompt = (
            "Bạn là trợ lý AI giám sát an toàn cho trẻ sơ sinh. "
            "Nhìn vào ảnh này, bé đang nằm sấp/úp (PRONE) hay nằm ngửa (SUPINE)? "
            "Chỉ trả lời một trong hai từ khóa trên ở đầu câu. "
            "Nếu không chắc chắn, hãy cố gắng phân tích dựa trên vị trí của lưng và bụng."
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.gemini_model_name,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                ]
            )
            return response.text
        except Exception as e:
            err_msg = str(e)
            self.logger.bind(tag=TAG).error(f"Lỗi Gemini SDK (New): {err_msg}")
            return f"ERROR: {err_msg}"

    def _analyze_image_groq(self, image_bytes: bytes) -> str:
        """Hàm dự phòng sử dụng Groq Vision API."""
        import requests
        
        try:
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            headers = {
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": "application/json"
            }
            
            prompt = (
                "Bạn là trợ lý AI giám sát trẻ em. Hãy xem ảnh và cho biết bé đang nằm sấp (nguy hiểm) hay nằm ngửa (an toàn)? "
                "Trả lời từ khóa PRONE nếu nằm sấp, SUPINE nếu nằm ngửa. Ngắn gọn."
            )
            
            payload = {
                "model": self.groq_model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }
                ],
                "max_tokens": 100
            }
            
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=15)
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                err_body = response.text
                self.logger.bind(tag=TAG).error(f"Groq Vision Error ({response.status_code}): {err_body}")
                return f"GROQ_ERROR: {response.status_code}"
        except Exception as e:
            return f"GROQ_EXCEPTION: {str(e)}"

    def set_telegram_alerts(self, alerts):
        """Được gọi từ http_server để gán TelegramAlerts."""
        self._telegram_alerts = alerts
