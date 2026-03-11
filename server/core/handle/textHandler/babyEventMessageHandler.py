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

        # Chống spam: ít nhất 15s giữa các lần báo động
        current_time = time.time()
        if not hasattr(conn, "last_baby_event_time"):
            conn.last_baby_event_time = 0

        if current_time - conn.last_baby_event_time < 15:
            conn.logger.bind(tag=TAG).debug("Bỏ qua báo động để tránh spam")
            return

        conn.last_baby_event_time = current_time

        if event_type == "cry_detected":
            # ── Bóc tách JSON từ ESP32 ──────────────────────────────────
            rms_level = msg_json.get("rms_level", 0)
            device_id = msg_json.get("device_id", "unknown")
            timestamp = msg_json.get("timestamp", 0)
            time_str  = time.strftime("%H:%M:%S", time.localtime())

            conn.logger.bind(tag=TAG).warning(
                f"[CRY-ALERT] device={device_id} | rms={rms_level} | ts={timestamp}"
            )

            # ── Log vào Dashboard ────────────────────────────────────────
            from core.serverToClients import DashboardUpdater
            msg = f"Phát hiện bé khóc (Mic ESP32 | device={device_id} | rms={rms_level})"
            DashboardUpdater.add_cry_event(msg)
            DashboardUpdater.add_system_log(
                name="ESP32-Mic",
                action="cry_detected",
                data={"device": device_id, "rms": rms_level, "ts": timestamp}
            )

            # ── Gửi Telegram text alert (không ảnh — ảnh đến sau từ ESP32-CAM) ──
            from core.serverToClients import TelegramNotifier
            from core.serverToClients.baby_actions import BabyCareAction
            from core.api.telegram_handler import TelegramHandler

            notifier = TelegramNotifier(
                bot_token=TelegramHandler.BOT_TOKEN,
                chat_id=TelegramHandler.CHAT_ID
            )

            # Tạo caption ngắn gọn như giao diện người dùng mô tả
            action_list = "\n".join(
                f"  • {a.button_label} — {a.description}" for a in BabyCareAction
            )
            alert_text = (
                "⚠️ *PHÁT HIỆN TRẺ ĐANG KHÓC!*\n"
                f"Label: _Cảnh báo từ {device_id}_\n"
                f"⏰ Thời gian: *{time_str}*  |  RMS: `{rms_level}`\n\n"
                "Hành động có thể thực hiện:\n"
                f"{action_list}\n\n"
                "👉 Hãy chọn hành động bên dưới:"
            )
            reply_markup = BabyCareAction.get_inline_keyboard(cols=2)
            asyncio.create_task(
                notifier.send_message(TelegramHandler.CHAT_ID, alert_text, reply_markup=reply_markup)
            )

            # ── Dỗ bé bằng giọng TTS ────────────────────────────────────
            system_prompt = (
                "Đây là tình huống khẩn cấp: Hệ thống vừa phát hiện tiếng bé khóc. "
                "Hãy đưa ra 1 câu dỗ dành nhanh, nhẹ nhàng như 'Bé ngoan, nín đi nào. "
                "Mẹ đến ngay đây' hoặc 'Em bé đừng khóc, có mẹ đây rồi'. RẤT NGẮN GỌN."
            )
            await startToChat(conn, system_prompt)

        elif event_type == "temperature":
            temp     = msg_json.get("temperature")
            humidity = msg_json.get("humidity")
            device_id = msg_json.get("device_id", "unknown")
            conn.logger.bind(tag=TAG).info(
                f"Nhiệt độ hiện tại: {temp}°C | Độ ẩm: {humidity}% | device={device_id}"
            )
            from core.serverToClients import DashboardUpdater
            DashboardUpdater.add_system_log(
                name="ESP32-Sensor",
                action="temperature",
                data={"temp": temp, "humidity": humidity, "device": device_id}
            )

