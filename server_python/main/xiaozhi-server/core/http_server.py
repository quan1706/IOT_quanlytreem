import asyncio
from aiohttp import web
from config.logger import setup_logging
from core.api.ota_handler import OTAHandler
from core.api.vision_handler import VisionHandler
from core.api.dashboard_handler import DashboardHandler

TAG = __name__


class SimpleHttpServer:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self.ota_handler = OTAHandler(config)
        self.vision_handler = VisionHandler(config)
        self.dashboard_handler = DashboardHandler(config)

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
                    ]
                )

                # Chạy dịch vụ
                runner = web.AppRunner(app)
                await runner.setup()
                site = web.TCPSite(runner, host, port)
                await site.start()
                
                # Bắt đầu vòng lặp Telegram Bot
                from core.api.telegram_handler import TelegramHandler
                asyncio.create_task(TelegramHandler.start_telegram_bot(self.dashboard_handler))

                # Duy trì dịch vụ hoạt động
                while True:
                    await asyncio.sleep(3600)  # Kiểm tra mỗi giờ một lần
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Khởi động máy chủ HTTP thất bại: {e}")
            import traceback

            self.logger.bind(tag=TAG).error(f"Ngăn xếp lỗi: {traceback.format_exc()}")
            raise
