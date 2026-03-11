import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from core.handle.textMessageHandlerRegistry import TextMessageHandlerRegistry

TAG = __name__


class TextMessageProcessor:
    """Class chính để xử lý các tin nhắn văn bản từ ESP32"""

    def __init__(self, registry: TextMessageHandlerRegistry):
        self.registry = registry

    async def process_message(self, conn: "ConnectionHandler", message: str) -> None:
        """Cổng vào chính để xử lý tin nhắn"""
        try:
            # Phân tích tin nhắn chuỗi JSON
            msg_json = json.loads(message)

            # Xử lý tin nhắn dạng JSON object (dict)
            if isinstance(msg_json, dict):
                message_type = msg_json.get("type")

                # Ghi log: Đã nhận tin nhắn loại gì
                conn.logger.bind(tag=TAG).info(f"Đã nhận tin nhắn loại [{message_type}]: {message}")

                # Lấy và thực thi Handler (bộ xử lý) tương ứng với loại tin nhắn
                handler = self.registry.get_handler(message_type)
                if handler:
                    await handler.handle(conn, msg_json)
                else:
                    conn.logger.bind(tag=TAG).error(f"Nhận được thông báo loại không xác định: {message}")
            # Xử lý tin nhắn chỉ chứa số (ping/kết nối)
            elif isinstance(msg_json, int):
                conn.logger.bind(tag=TAG).info(f"Đã nhận tin nhắn dạng số: {message}")
                await conn.websocket.send(message)

        except json.JSONDecodeError:
            # Nếu không phải tin nhắn JSON thì tự động gửi trả lại (forward)
            conn.logger.bind(tag=TAG).error(f"Lỗi khi phân tích tin nhắn: {message}")
            await conn.websocket.send(message)
