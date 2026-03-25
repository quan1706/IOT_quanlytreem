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
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self.ota_handler = OTAHandler(config)
        self.vision_handler = VisionHandler(config)
        self.dashboard_handler = DashboardHandler(config)
        self.pose_handler = PoseHandler(config)

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
                name="ESP32-CAM",
                action="cry_detected",
                data={"device": device_id, "rms": rms_level, "ts": timestamp or time_str}
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

    async def _periodic_pose_check(self):
        """Task nền: gửi lệnh check pose mỗi 5 phút một lần cho các thiết bị ESP32."""
        from core.serverToClients.esp32_commander import ESP32Commander
        while True:
            await asyncio.sleep(BABY_POSE_CHECK_INTERVAL_SECONDS)
            self.logger.bind(tag=TAG).info("[AUTO POSE CHECK] Đang gửi lệnh chụp ảnh Baby Pose...")
            await ESP32Commander().execute_command("capture_pose")

    async def start(self):
        try:
            server_config = self.config["server"]
            read_config_from_api = self.config.get("read_config_from_api", False)
            host = server_config.get("ip", "0.0.0.0")
            port = int(server_config.get("http_port", 8003))

            if port:
                app = web.Application()
                
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
                        web.post("/api/dashboard/mode", self.dashboard_handler.handle_post_mode),
                        web.post("/api/dashboard/apikey", self.dashboard_handler.handle_post_apikey),
                        
                        # Route Baby Care - gọi thẳng method nội bộ
                        web.post("/api/cry", self._handle_cry),
                        web.post("/api/vision/pose", self.pose_handler.handle_post),
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
