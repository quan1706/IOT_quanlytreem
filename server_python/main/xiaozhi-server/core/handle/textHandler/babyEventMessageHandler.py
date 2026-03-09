import asyncio
from typing import Dict, Any, TYPE_CHECKING
import time

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

from core.handle.receiveAudioHandle import startToChat
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType

TAG = __name__

class BabyEventMessageHandler(TextMessageHandler):
    """Xử lý sự kiện từ hệ thống Baby Care (khóc, nhiệt độ)"""

    @property
    def message_type(self) -> Any:
        class DummyType:
            value = "baby_event"
        return DummyType

    async def handle(self, conn: "ConnectionHandler", msg_json: Dict[str, Any]) -> None:
        event_type = msg_json.get("event")
        conn.logger.bind(tag=TAG).info(f"Nhận sự kiện Baby Care: {event_type} - {msg_json}")
        
        # Ngừa việc báo liên tục trong 1 khoảng thời gian ngắn (chống spam)
        current_time = time.time()
        if not hasattr(conn, "last_baby_event_time"):
            conn.last_baby_event_time = 0
            
        if current_time - conn.last_baby_event_time < 15: # Ít nhất 15s giữa các lần báo động
            conn.logger.bind(tag=TAG).debug("Bỏ qua báo động để tránh spam")
            return
            
        conn.last_baby_event_time = current_time

        if event_type == "cry_detected":
            rms_level = msg_json.get("rms_level", 0)
            conn.logger.bind(tag=TAG).warning(f"PHÁT HIỆN BÉ KHÓC! RMS: {rms_level}")
            
            # Khởi tạo tin nhắn cho LLM
            system_prompt = "Đây là tình huống khẩn cấp: Hệ thống vừa phát hiện tiếng bé khóc. Hãy đưa ra 1 câu dỗ dành nhanh chóng, nhẹ nhàng như 'Bé ngoan, nín đi nào. Mẹ đến ngay đây' hoặc 'Em bé đừng khóc, có mẹ đây rồi'. RẤT NGẮN GỌN."
            
            # Gửi cho LLM để tạo phản hồi thoại (TTS)
            # Ta dùng hàm startToChat giống như khi nhận diện chữ từ giọng nói
            await startToChat(conn, system_prompt)
            
        elif event_type == "temperature":
            # Nếu bạn có thêm chức năng cảnh báo nhiệt độ
            temp = msg_json.get("temperature")
            conn.logger.bind(tag=TAG).info(f"Nhiệt độ hiện tại: {temp}")
