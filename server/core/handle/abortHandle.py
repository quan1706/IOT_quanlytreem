import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
TAG = __name__


async def handleAbortMessage(conn: "ConnectionHandler"):
    conn.logger.bind(tag=TAG).info("Đã nhận tin nhắn Abort (Ngắt)")
    # Thiết lập trạng thái ngắt, sẽ tự động ngắt các tiến trình LLM, TTS đang chạy
    conn.client_abort = True
    conn.clear_queues()
    # Gửi lệnh ngắt trạng thái nói tới client (ESP32)
    await conn.websocket.send(
        json.dumps({"type": "tts", "state": "stop", "session_id": conn.session_id})
    )
    conn.clearSpeakStatus()
    conn.logger.bind(tag=TAG).info("Kết thúc xử lý tin nhắn Abort")
