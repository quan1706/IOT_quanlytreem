import asyncio
from aiohttp import web
from config.logger import setup_logging
from core.api.ota_handler import OTAHandler
from core.api.vision_handler import VisionHandler
from core.api.dashboard_handler import DashboardHandler
from core.api.pose_handler import PoseHandler

BABY_POSE_CHECK_INTERVAL_SECONDS = 300  # 5 phút một lần để check baby pose

TAG = __name__


class SimpleHttpServer:
    _instance = None  # Luu tru instance dang chay

    def __init__(self, config: dict):
        SimpleHttpServer._instance = self
        self.config = config
        self.logger = setup_logging()
        self.ota_handler = OTAHandler(config)
        self.vision_handler = VisionHandler(config)
        self.dashboard_handler = DashboardHandler(config)
        self.pose_handler = PoseHandler(config)
        self._visualizers = []  # Danh sách các stream đang kết nối từ Dashboard
        self.hq_priority_until = 0 # Timestamp đến khi nào thì ngừng ưu tiên HQ

    def _get_websocket_url(self, local_ip: str, port: int) -> str:
        """Lấy địa chỉ websocket

        Args:
            local_ip: Địa chỉ IP nội bộ
            port: Số cổng

        Returns:
            str: Địa chỉ websocket
        """
        server_config = self.config["server"]
        websocket_config = server_config.get("websocket")

        if websocket_config and "你" not in websocket_config:
            return websocket_config
        else:
            return f"ws://{local_ip}:{port}/xiaozhi/v1/"

    async def handle_stream(self, request):
        """
        MJPEG Stream relay cho Dashboard.
        Dùng kỹ thuật multipart/x-mixed-replace để đẩy ảnh liên tục.
        """
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'multipart/x-mixed-replace;boundary=frame',
                'Cache-Control': 'no-cache',
                'Connection': 'close',
                'Pragma': 'no-cache'
            }
        )
        await response.prepare(request)
        
        # Thêm vào danh sách visualizers
        # Tạo một queue riêng cho client này
        client_queue = asyncio.Queue()
        self._visualizers.append((response, client_queue))
        self.logger.bind(tag=TAG).info(f"Dashboard kết nối Live Stream. Tổng visualizers: {len(self._visualizers)}")
        
        try:
            # Giữ kết nối mở cho đến khi client ngắt
            while True:
                frame_data = await client_queue.get()
                if frame_data is None: # Signal to close the stream
                    break
                await response.write(frame_data)
        except Exception:
            pass
        finally:
            # Remove the client's response and queue from the list
            if (response, client_queue) in self._visualizers:
                self._visualizers.remove((response, client_queue))
            self.logger.bind(tag=TAG).info(f"Dashboard ngắt Live Stream. Còn lại: {len(self._visualizers)}")
            return response

    async def _broadcast_frame(self, image_bytes):
        """Đẩy frame ảnh tới tất cả các Dashboard đang xem."""
        if not self._visualizers:
            return

        # Prepare MJPEG frame
        header = (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(image_bytes)).encode() + b"\r\n\r\n"
        )
        footer = b"\r\n"
        data = header + image_bytes + footer

        # Gửi tới các client (dùng list copy để an toàn khi remove)
        for resp, client_queue in list(self._visualizers):
            try:
                # Đưa vào queue thay vì gửi trực tiếp để tránh block luồng xử lý ảnh
                if client_queue.full():
                    try: client_queue.get_nowait()
                    except: pass
                await client_queue.put(data)
            except Exception:
                pass

    async def _handle_cry(self, request):
        """
        Xử lý POST /api/cry — Nhận ảnh từ ESP32-CAM kèm metadata JSON.
        Gửi ảnh cảnh báo lên Telegram (kèm BabyCareAction buttons), log dashboard & server.
        """
        import time
        from core.serverToClients import DashboardUpdater
        from core.serverToClients.baby_actions import BabyCareAction

        try:
            self.logger.bind(tag=TAG).info("--- NHẬN YÊU CẦU CẢNH BÁO BÉ KHÓC TỪ HTTP ---")

            data = await request.post()

            # ── Đọc ảnh ─────────────────────────────────────────────────
            image_field = data.get('image') or data.get('photo')
            if not image_field:
                return web.json_response({"success": False, "error": "No image provided"}, status=400)
            image_bytes = image_field.file.read()

            # ── Broadcast tới các Dashboard đang xem (Live Feed) ─────────
            asyncio.create_task(self._broadcast_frame(image_bytes))

            # ── Bóc tách metadata (ESP32-CAM có thể gửi kèm field text) ─
            device_id  = data.get('device_id', 'ESP32-CAM')
            rms_level  = data.get('rms_level', 'N/A')
            timestamp  = data.get('timestamp', '')
            time_str   = time.strftime('%H:%M:%S', time.localtime())

            self.logger.bind(tag=TAG).warning(
                f"[CRY-CAM] device={device_id} | rms={rms_level} | ts={timestamp}"
            )

            # ── Log vào Dashboard & server console ───────────────────────
            log_msg = f"Phát hiện bé khóc (Camera | device={device_id} | rms={rms_level})"
            DashboardUpdater.add_cry_event(log_msg)
            DashboardUpdater.add_system_log(
                from_node="ESPCAM",
                to_node="Server",
                data={"event": "cry_detected", "device": device_id, "rms": rms_level}
            )

            # ── Caption theo đúng format giao diện Telegram ──────────────
            caption = (
                f"⚠️ *PHÁT HIỆN TRẺ ĐANG KHÓC!*\n"
                f"Label: _Cảnh báo từ {device_id}_\n"
                f"Hãy chọn hành động bên dưới:"
            )

            # ── Gửi ảnh + BabyCareAction buttons lên Telegram ───────────
            if hasattr(self, '_telegram_bot') and self._telegram_bot:
                asyncio.create_task(
                    self._telegram_bot.alerts.send_photo_alert(image_bytes, caption)
                )

            return web.json_response({"success": True, "message": "Alert received and processing"})

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi xử lý /api/cry: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    def drop_all_streams(self):
        """Đóng tất cả các luồng MJPEG đang mở và tạm dừng nhận frame mới để ưu tiên HQ Capture."""
        import time
        self.hq_priority_until = time.time() + 2.0 # Ưu tiên HQ trong 2 giây tới
        
        self.logger.bind(tag=TAG).info(f"--- [CLEANUP] Đang đóng {len(self._visualizers)} luồng stream để ưu tiên HQ Capture ---")
        for resp, q in list(self._visualizers):
            try:
                # Gửi None báo hiệu kết thúc vòng lặp handle_stream
                asyncio.create_task(q.put(None))
            except Exception:
                pass
        self._visualizers.clear()

    async def _handle_frame(self, request):
        """
        POST /api/vision/frame — Chấp nhận frame ảnh từ ESP32-CAM (Cực kỳ linh hoạt).
        """
        import time
        if time.time() < self.hq_priority_until:
            # Từ chối nhận frame thường để ESP32-CAM rảnh tay gửi ảnh HQ
            return web.Response(status=503) # Service Unavailable
        # Thêm log verify headers để debug
        # self.logger.bind(tag=TAG).debug(f"H-FRAME: {request.headers}")
        
        try:
            image_bytes = None
            
            # Sử dụng wait_for để tránh treo server nếu client không gửi đủ data
            if request.content_type.startswith('multipart/'):
                try:
                    data = await asyncio.wait_for(request.post(), timeout=5.0)
                    image_field = data.get('image') or data.get('photo') or data.get('file')
                    if not image_field and len(data) > 0:
                        for key in data:
                            if hasattr(data[key], 'file'):
                                image_field = data[key]
                                break
                    if image_field:
                        image_bytes = image_field.file.read()
                except asyncio.TimeoutError:
                    self.logger.bind(tag=TAG).warning("Timeout khi parse multipart frame")
                except Exception as e:
                    self.logger.bind(tag=TAG).debug(f"Lỗi parse multipart frame, thử read raw: {e}")
            
            # Fallback: đọc raw body
            if not image_bytes:
                try:
                    image_bytes = await asyncio.wait_for(request.read(), timeout=3.0)
                    if image_bytes and b'\xff\xd8' in image_bytes:
                        start = image_bytes.find(b'\xff\xd8')
                        end = image_bytes.rfind(b'\xff\xd9')
                        if end != -1 and end > start:
                            image_bytes = image_bytes[start:end+2]
                except Exception:
                    pass

            if image_bytes and len(image_bytes) > 100:
                asyncio.create_task(self._broadcast_frame(image_bytes))
                return web.json_response({"success": True})
            
            return web.json_response({"success": False, "error": "No data"}, status=400)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi _handle_frame: {e}")
            return web.json_response({"success": False}, status=500)

    async def _handle_hq_capture(self, request):
        """Handler cho lấy ảnh HQ (chụp ảnh đơn)."""
        import time
        if request.method == "GET":
             return web.json_response({
                "status": "ready",
                "message": "Endpoint is active. Use POST to upload HQ image.",
                "details": {
                    "client_max_size": "16MB",
                    "priority_active": time.time() < self.hq_priority_until
                }
            })

        print(f"--- [HTTP] HQ_CAPTURE FROM {request.remote} ---", flush=True)
        self.logger.bind(tag=TAG).info("--- [HQ] NHẬN YÊU CẦU POST ---")
        import os
        from core.serverToClients import DashboardUpdater
        
        try:
            content_type = request.headers.get('Content-Type', 'unknown')
            content_len = request.headers.get('Content-Length', 'unknown')
            self.logger.bind(tag=TAG).info(f"--- [HQ] NHẬN YÊU CẦU: Type={content_type}, Len={content_len} ---")
            
            image_bytes = None
            try:
                body = await asyncio.wait_for(request.read(), timeout=20.0)
                self.logger.bind(tag=TAG).info(f"--- [HQ] Đã đọc xong body: {len(body)} bytes ---")
            except asyncio.TimeoutError:
                self.logger.bind(tag=TAG).error("--- [HQ] Timeout (20s) khi đọc raw body. Đang đóng socket. ---")
                if request.transport:
                    request.transport.close()
                return web.json_response({"success": False, "error": "Read timeout"}, status=408)

            # Trích xuất JPEG marker: start=FF D8, end=FF D9
            if body and b'\xff\xd8' in body:
                start = body.find(b'\xff\xd8')
                end = body.rfind(b'\xff\xd9')
                if end != -1 and end > start:
                    image_bytes = body[start:end+2]
                    self.logger.bind(tag=TAG).info(f"--- [HQ] Đã trích xuất JPEG ({len(image_bytes)} bytes) ---")
            
            if not image_bytes and (len(body) > 1000):
                if 'image/jpeg' in content_type.lower() or 'octet-stream' in content_type.lower():
                    image_bytes = body
                    self.logger.bind(tag=TAG).info("--- [HQ] Dùng toàn bộ raw body làm ảnh ---")

            if not image_bytes or len(image_bytes) < 1000:
                self.logger.bind(tag=TAG).error("--- [HQ] KHÔNG TÌM THẤY ẢNH HỢP LỆ TRONG BODY ---")
                return web.json_response({"success": False, "error": "No valid JPEG data"}, status=400)
                
            save_dir = os.path.join(os.getcwd(), "data", "captures")
            os.makedirs(save_dir, exist_ok=True)
            filename = f"hq_{int(time.time())}.jpg"
            filepath = os.path.join(save_dir, filename)
            
            with open(filepath, "wb") as f:
                f.write(image_bytes)
                
            self.logger.bind(tag=TAG).info(f"✅ [HQ] Đã lưu ảnh thành công: {filename}")
            DashboardUpdater.add_system_log("Server", "Web", f"Đã lưu ảnh HQ: {filename}")
            
            if hasattr(self, '_telegram_bot') and self._telegram_bot:
                caption = (
                    f"📸 *ẢNH TỪ HỆ THỐNG*\n"
                    f"Loại: Ảnh chất lượng cao (HQ)\n"
                    f"Trạng thái: Thành công\n"
                    f"Kích thước: {len(image_bytes) // 1024} KB\n"
                    f"Thời gian: {time.strftime('%H:%M:%S')}"
                )
                asyncio.create_task(self._telegram_bot.alerts.send_photo_alert(image_bytes, caption))
                self.logger.bind(tag=TAG).info("🚀 [HQ] Đã đẩy task gửi Telegram")
                
            return web.json_response({"success": True, "file": filename})

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"❌ [HQ] Lỗi xử lý tổng thể: {e}")
            import traceback
            self.logger.bind(tag=TAG).error(traceback.format_exc())
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def _handle_vision_log(self, request):
        """Handler cho log gửi từ ESP32-CAM."""
        from core.serverToClients import DashboardUpdater
        try:
            data = await request.json()
            msg = data.get("msg", "No message")
            DashboardUpdater.add_system_log("ESPCAM", "Server", msg)
            return web.json_response({"success": True})
        except Exception:
            return web.json_response({"success": False}, status=500)

    async def _periodic_pose_check(self):
        """Task nền: gửi lệnh check pose mỗi 5 phút một lần cho các thiết bị ESP32."""
        from core.serverToClients.esp32_commander import ESP32Commander
        while True:
            await asyncio.sleep(BABY_POSE_CHECK_INTERVAL_SECONDS)
            self.logger.bind(tag=TAG).info("[AUTO POSE CHECK] Đang gửi lệnh chụp ảnh Baby Pose...")
            # Gửi lệnh 'capture_hq' thay vì 'capture_pose' để ESPCAM chụp ảnh đẹp
            await ESP32Commander().execute_command("capture_hq")

    async def start(self):
        try:
            server_config = self.config["server"]
            read_config_from_api = self.config.get("read_config_from_api", False)
            host = server_config.get("ip", "0.0.0.0")
            port = int(server_config.get("http_port", 8003))

            if port:
                async def debug_middleware(app, handler):
                    async def middleware_handler(request):
                        self.logger.bind(tag=TAG).info(f"[HTTP] {request.method} {request.path} from {request.remote}")
                        return await handler(request)
                    return middleware_handler

                app = web.Application(
                    middlewares=[debug_middleware],
                    client_max_size=16 * 1024 * 1024  # 16MB
                )
                
                if not read_config_from_api:
                    # Nếu không bật console điều khiển thông minh, chỉ chạy module đơn, thì cần thêm giao diện OTA đơn giản, dùng để gửi địa chỉ websocket
                    app.add_routes(
                        [
                            web.get("/xiaozhi/ota/", self.ota_handler.handle_get),
                            web.post("/xiaozhi/ota/", self.ota_handler.handle_post),
                            web.options(
                                "/xiaozhi/ota/", self.ota_handler.handle_options
                            ),
                            # Giao diện tải xuống, chỉ cung cấp tải xuống data/bin/*.bin
                            web.get(
                                "/xiaozhi/ota/download/{filename}",
                                self.ota_handler.handle_download,
                            ),
                            web.options(
                                "/xiaozhi/ota/download/{filename}",
                                self.ota_handler.handle_options,
                            ),
                        ]
                    )
                # Thêm routes (đường dẫn)
                app.add_routes(
                    [
                        web.get("/mcp/vision/explain", self.vision_handler.handle_get),
                        web.post(
                            "/mcp/vision/explain", self.vision_handler.handle_post
                        ),
                        web.options(
                            "/mcp/vision/explain", self.vision_handler.handle_options
                        ),
                        web.get("/", self.dashboard_handler.handle_get_index),
                        web.get("/api/dashboard/state", self.dashboard_handler.handle_get_state),
                        web.get("/api/dashboard/logs", self.dashboard_handler.handle_get_logs),
                        web.get("/api/dashboard/sensors", self.dashboard_handler.handle_get_sensors),
                        web.get("/api/dashboard/chart", self.dashboard_handler.handle_get_chart),
                        web.post("/api/dashboard/mode", self.dashboard_handler.handle_post_mode),
                        web.post("/api/dashboard/command", self.dashboard_handler.handle_post_command),
                        web.post("/api/dashboard/chat", self.dashboard_handler.handle_post_chat),
                        web.post("/api/dashboard/apikey", self.dashboard_handler.handle_post_apikey),
                        
                        # Route Baby Care
                        web.post("/api/cry", self._handle_cry),
                        web.post("/api/vision/frame", self._handle_frame),
                        web.get("/api/vision/stream", self.handle_stream),
                        web.post("/api/vision/pose", self.pose_handler.handle_post),
                        web.post("/api/vision/log", self._handle_vision_log),
                        web.route("*", "/api/vision/hq_capture", self._handle_hq_capture),
                    ]
                )

                # Chạy dịch vụ
                runner = web.AppRunner(app)
                await runner.setup()
                site = web.TCPSite(runner, host, port)
                await site.start()
                
                # Khởi động Telegram Bot (từ package mới)
                from core.telegram import TelegramBot
                from core.telegram.alerts import TelegramAlerts
                self._telegram_bot = TelegramBot(self.config, self.dashboard_handler)
                # Đăng ký global alerts instance để listenMessageHandler có thể gửi cry alert
                TelegramAlerts.set_global(self._telegram_bot.alerts)
                self.pose_handler.set_telegram_alerts(self._telegram_bot.alerts)
                asyncio.create_task(self._telegram_bot.start())

                # Chạy task kiểm tra periodic baby pose
                asyncio.create_task(self._periodic_pose_check())

                # Duy trì dịch vụ hoạt động
                while True:
                    await asyncio.sleep(3600)  # Kiểm tra mỗi giờ một lần
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Khởi động máy chủ HTTP thất bại: {e}")
            import traceback

            self.logger.bind(tag=TAG).error(f"Ngăn xếp lỗi: {traceback.format_exc()}")
            raise
