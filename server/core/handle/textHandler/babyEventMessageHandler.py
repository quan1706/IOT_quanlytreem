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
        # Log TOÀN BỘ message nhận được để debug
        conn.logger.bind(tag=TAG).info(f"DEBUG: ESP32 sent message: {msg_json}")
        
        conn.logger.bind(tag=TAG).bind(tag=TAG).info(f"Nhận sự kiện Baby Care: {event_type} - {msg_json}")

        from core.telegram.alerts import _global_alerts

        if event_type == "cry_detected":
            # ── Log vào Dashboard & Chống Spam (Cooldown 60s toàn cục) ────
            from core.serverToClients import DashboardUpdater
            
            rms_level = msg_json.get("rms_level", 0)
            device_id = msg_json.get("device_id", "unknown")
            msg = f"Phát hiện bé khóc (Mic ESP32 | device={device_id} | rms={rms_level})"
            
            # add_cry_event trả về False nếu đang trong thời gian cooldown
            if not DashboardUpdater.add_cry_event(msg):
                conn.logger.bind(tag=TAG).debug("Bỏ qua báo động Khóc do đang trong thời gian cooldown")
                return
            
            # ── Bóc tách JSON từ ESP32 ──────────────────────────────────
            rms_level = msg_json.get("rms_level", 0)
            device_id = msg_json.get("device_id", "unknown")
            timestamp = msg_json.get("timestamp", 0)
            time_str  = time.strftime("%H:%M:%S", time.localtime())

            conn.logger.bind(tag=TAG).warning(
                f"[CRY-ALERT] device={device_id} | rms={rms_level} | ts={timestamp}"
            )

            # ── Log vào System Log (Event đã được add vào history ở trên) ──
            DashboardUpdater.add_system_log(
                from_node="ESP",
                to_node="Server",
                data={"event": "cry_detected", "rms": rms_level, "device": device_id}
            )

            # ── Gửi Telegram text alert ──────────────────────────────────
            from core.serverToClients.baby_actions import BabyCareAction

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
            
            if _global_alerts:
                asyncio.create_task(
                    _global_alerts.client.send_message(text=alert_text, reply_markup=reply_markup)
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
            # Log ra console mức DEBUG để tránh làm rối màn hình ba mẹ
            conn.logger.bind(tag=TAG).debug(
                f"Nhiệt độ hiện tại: {temp}°C | Độ ẩm: {humidity}% | device={device_id}"
            )
            from core.serverToClients import DashboardUpdater
            DashboardUpdater.update_sensor_data(temp, humidity)
            DashboardUpdater.add_system_log(
                from_node="ESP",
                to_node="Server",
                data={"temp": temp, "humidity": humidity, "device": device_id}
            )
            
            # ── Cập nhật vào bộ nhớ AI (Context) ──────────────────────────
            if hasattr(conn, "iot_descriptors") and device_id in conn.iot_descriptors:
                device = conn.iot_descriptors[device_id]
                for prop in device.properties:
                    if prop["name"] == "temperature":
                        prop["value"] = temp
                    elif prop["name"] == "humidity":
                        prop["value"] = humidity
                conn.logger.bind(tag=TAG).debug(f"Đã đồng bộ Nhiệt độ ({temp}) & Độ ẩm ({humidity}) vào Context AI")

        elif event_type == "temperature_alert":
            temp = msg_json.get("temperature")
            device_id = msg_json.get("device_id", "unknown")
            time_str = time.strftime("%H:%M:%S", time.localtime())
            
            conn.logger.bind(tag=TAG).warning(f"⚠️ CẢNH BÁO NHIỆT ĐỘ CAO: {temp}°C từ {device_id}")

            # ── Gửi Telegram alert với lựa chọn bật quạt ──────────────────
            from core.serverToClients.baby_actions import BabyCareAction

            alert_text = (
                "⚠️ *CẢNH BÁO: PHÒNG QUÁ NÓNG!*\n"
                f"Nhiệt độ hiện tại: *{temp}°C*\n"
                f"⏰ Thời gian: *{time_str}*\n\n"
                "Bạn có muốn bật quạt cho bé không?"
            )
            
            # Chỉ hiển thị nút Bật quạt và Dừng
            custom_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": BabyCareAction.FAN_ON.button_label, "callback_data": BabyCareAction.FAN_ON.callback_data},
                        {"text": BabyCareAction.STOP_ALL.button_label, "callback_data": BabyCareAction.STOP_ALL.callback_data}
                    ]
                ]
            }
            
            async def send_with_log():
                if _global_alerts:
                    success = await _global_alerts.client.send_message(text=alert_text, reply_markup=custom_keyboard)
                    conn.logger.bind(tag=TAG).info(f"Telegram Alert Send Result: {success}")
                # Tự động bật quạt ngay lập tức
                from core.serverToClients.esp32_commander import ESP32Commander
                await ESP32Commander().execute_command("bat_quat")
                conn.logger.bind(tag=TAG).info("Đã tự động gửi lệnh Bật quạt do nhiệt độ cao")

            asyncio.create_task(send_with_log())

        elif event_type == "temperature_report":
            temp = msg_json.get("temperature")
            humidity = msg_json.get("humidity")
            device_id = msg_json.get("device_id", "unknown")
            
            # Cập nhật DASHBOARD_STATE
            from core.serverToClients import DashboardUpdater
            DashboardUpdater.update_sensor_data(temp, humidity)
            
            # Gửi tin nhắn định kỳ tới Telegram
            report_text = (
                "📊 *CẬP NHẬT TRẠNG THÁI ĐỊNH KỲ*\n"
                f"Nhiệt độ: *{temp}°C*\n"
                f"Độ ẩm: *{humidity}%*\n"
                "Hệ thống vẫn đang hoạt động ổn định."
            )
            async def send_periodic_with_log():
                if _global_alerts:
                    success = await _global_alerts.client.send_message(text=report_text)
                    conn.logger.bind(tag=TAG).info(f"Telegram Periodic Report Result: {success}")

            asyncio.create_task(send_periodic_with_log())

        elif event_type == "fan_status":
            status = msg_json.get("status")
            source = msg_json.get("source", "unknown")
            device_id = msg_json.get("device_id", "unknown")
            
            conn.logger.bind(tag=TAG).info(f"Trạng thái quạt từ {device_id}: {status} (nguồn: {source})")
            
            # Cập nhật DASHBOARD_STATE và log hệ thống
            from core.serverToClients import DashboardUpdater
            DashboardUpdater.add_system_log(
                from_node="ESP",
                to_node="Server",
                data={"status": status, "source": source, "device": device_id}
            )

            # ── Gửi thông báo vào Telegram ──────────────────────────────
            icon = "🌬️" if status == "on" else "🛑"
            label = "BẬT" if status == "on" else "TẮT"
            source_map = {
                "physical_button": "Nút nhấn vật lý",
                "server": "Bot Telegram/App",
                "voice": "Lệnh giọng nói"
            }
            src_label = source_map.get(source, source)
            
            notify_text = (
                f"{icon} *THÔNG BÁO QUẠT*\n"
                f"Trạng thái: *{label}*\n"
                f"Nguồn điều khiển: _{src_label}_"
            )
            if _global_alerts:
                asyncio.create_task(_global_alerts.client.send_message(text=notify_text))
