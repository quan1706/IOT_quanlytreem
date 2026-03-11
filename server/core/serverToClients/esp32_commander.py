"""
serverToClients/esp32_commander.py

Module chịu trách nhiệm gửi lệnh điều khiển từ Server -> ESP32.

Hiện tại đang chạy ở localhost nên chưa có kết nối WebSocket thật đến
thiết bị vật lý. Mỗi lời gọi execute_command() sẽ:
  1. Ghi log server rõ ràng
  2. Trả về tuple (success, message) để caller biết kết quả
  3. (TODO) Gửi qua WebSocket khi có public server / kết nối ổn định
"""
from config.logger import setup_logging

TAG = "ESP32Commander"


class ESP32Commander:
    """
    Thực thi lệnh điều khiển ESP32.
    Singleton – tất cả module dùng chung một instance.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.logger = setup_logging()
            # Placeholder: danh sách WebSocket connections đến ESP32
            cls._instance.connections = []
        return cls._instance

    @staticmethod
    def _get_label(command: str) -> str:
        """Lấy label từ BabyCareAction enum thay vì hardcode."""
        from core.serverToClients.baby_actions import BabyCareAction
        action = BabyCareAction.from_callback(f"confirm_{command}")
        return action.button_label if action else f"Lệnh: {command}"

    def register_connection(self, ws_connection):
        """Đăng ký WebSocket connection mới từ ESP32."""
        self.connections.append(ws_connection)
        self.logger.bind(tag=TAG).info(
            f"[WS] Đã thêm ESP32 connection. Tổng số: {len(self.connections)}"
        )

    def unregister_connection(self, ws_connection):
        """Hủy đăng ký WebSocket connection khi ESP32 ngắt kết nối."""
        if ws_connection in self.connections:
            self.connections.remove(ws_connection)
            self.logger.bind(tag=TAG).info(
                f"[WS] Đã xóa ESP32 connection. Tổng số: {len(self.connections)}"
            )

    async def execute_command(self, command: str) -> tuple[bool, str]:
        """
        Thực thi lệnh xuống ESP32.
        """
        import json
        from core.serverToClients.dashboard_updater import DashboardUpdater

        label = self._get_label(command)
        esp32_payload = {"cmd": command}

        self.logger.bind(tag=TAG).info(
            f"[COMMAND] Tiếp nhận lệnh: {command} ({label})"
        )

        # Log: Server → ESP32 JSON payload
        DashboardUpdater.add_system_log(
            "Server→ESP32",
            command,
            esp32_payload,
        )

        if not self.connections:
            msg = (
                f"⚙️ Lệnh `{label}` đã được ghi nhận.\n"
                "_Thiết bị ESP32 chưa kết nối WebSocket — lệnh sẽ được hàng đợi._"
            )
            self.logger.bind(tag=TAG).warning(
                f"[COMMAND] Không có ESP32 kết nối. Lệnh '{command}' chờ hàng đợi."
            )
            return False, msg

        sent_count = 0
        for ws in list(self.connections):
            try:
                await ws.send_str(json.dumps(esp32_payload))
                sent_count += 1
            except Exception as e:
                self.logger.bind(tag=TAG).error(
                    f"[COMMAND] Lỗi gửi WebSocket: {e}"
                )
                self.connections.remove(ws)

        if sent_count > 0:
            msg = f"✅ Lệnh `{label}` đã gửi xuống *{sent_count}* thiết bị ESP32 thành công!"
            self.logger.bind(tag=TAG).info(
                f"[COMMAND] Đã gửi '{command}' đến {sent_count} thiết bị."
            )
            return True, msg
        else:
            msg = f"❌ Không thể gửi lệnh `{label}` (kết nối bị mất)."
            return False, msg
