"""
serverToClients/esp32_commander.py

Module chịu trách nhiệm gửi lệnh điều khiển từ Server -> ESP32.
"""
import json
import asyncio
from config.logger import setup_logging

TAG = "ESP32Commander"

class ESP32Connection:
    def __init__(self, websocket, device_id, role):
        self.websocket = websocket
        self.device_id = device_id
        self.metadata = {"role": role}

    async def send_message(self, message):
        """Gửi tin nhắn dưới dạng JSON hoặc raw bytes/string."""
        if isinstance(message, (dict, list)):
            data = json.dumps(message)
            await self.websocket.send(data)
        elif isinstance(message, bytes):
            await self.websocket.send(message)
        else:
            await self.websocket.send(str(message))

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
            cls._instance.connections = []
            cls._instance._is_playing_music = False
            cls._instance._music_task = None
        return cls._instance

    @staticmethod
    def _get_label(command: str) -> str:
        """Lấy label từ BabyCareAction enum thay vì hardcode."""
        from core.serverToClients.baby_actions import BabyCareAction
        action = BabyCareAction.from_callback(f"confirm_{command}")
        return action.button_label if action else f"Lệnh: {command}"

    def register_connection(self, ws_connection, device_id: str = "unknown", role: str = "unknown"):
        """Đăng ký WebSocket connection mới kèm metadata."""
        # Kiểm tra xem connection này đã tồn tại chưa
        for conn in self.connections:
            if conn.websocket == ws_connection:
                conn.device_id = device_id
                conn.metadata["role"] = role
                return

        new_conn = ESP32Connection(ws_connection, device_id, role)
        self.connections.append(new_conn)
        self.logger.bind(tag=TAG).info(
            f"[WS] Đã thêm ESP32 connection: {device_id} ({role}). Tổng số: {len(self.connections)}"
        )

    def unregister_connection(self, ws_connection):
        """Hủy đăng ký WebSocket connection khi ESP32 ngắt kết nối."""
        self.connections = [c for c in self.connections if c.websocket != ws_connection]
        self.logger.bind(tag=TAG).info(
            f"[WS] Đã xóa ESP32 connection. Tổng số: {len(self.connections)}"
        )

    async def play_music_task(self, filepath: str):
        """Stream file âm thanh xuống thẳng loa ESP32."""
        from core.utils.util import audio_to_data
        
        self._is_playing_music = True
        try:
            audio_chunks = await audio_to_data(filepath, is_opus=False, use_cache=False)
            start_msg = {"type": "tts", "state": "start"}
            for conn in list(self.connections):
                try: await conn.send_message(start_msg)
                except: pass

            for chunk in audio_chunks:
                if not self._is_playing_music: break
                for conn in list(self.connections):
                    try: await conn.send_message(chunk)
                    except: pass
                await asyncio.sleep(0.055) 

            stop_msg = {"type": "tts", "state": "stop"}
            for conn in list(self.connections):
                try: await conn.send_message(stop_msg)
                except: pass
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"[MUSIC] Lỗi stream nhạc: {e}")
        finally:
            self._is_playing_music = False

    async def execute_command(self, command: str) -> tuple[bool, str]:
        """Thực thi lệnh xuống ESP32."""
        from core.serverToClients.dashboard_updater import DashboardUpdater

        label = self._get_label(command)
        esp32_payload = {"type": "cmd", "cmd": command}

        self.logger.bind(tag=TAG).info(f"[COMMAND] Tiếp nhận lệnh: {command} ({label})")

        import os
        music_dir = os.path.join(os.getcwd(), "data", "music")
        os.makedirs(music_dir, exist_ok=True)

        if command == "ru_vong":
            self._is_playing_music = False
            filepath = os.path.join(music_dir, "nhacrubengu.mp3")
            if os.path.isfile(filepath):
                self._music_task = asyncio.create_task(self.play_music_task(filepath))
            else: return False, "⚠️ Không tìm thấy file nhạc ru bé."

        elif command == "phat_nhac":
            self._is_playing_music = False
            playlist = [f for f in os.listdir(music_dir) if f.lower().endswith(('.mp3', '.wav'))]
            if playlist:
                import random
                media_file = random.choice(playlist)
                filepath = os.path.join(music_dir, media_file)
                self._music_task = asyncio.create_task(self.play_music_task(filepath))
            else: return False, "⚠️ Thư mục nhạc trống!"

        if command in ("tat_noi", "dung"):
            self._is_playing_music = False

        DashboardUpdater.add_system_log("Server", "ESP", {"cmd": command, "payload": esp32_payload})

        if not self.connections:
            self.logger.bind(tag=TAG).warning(f"[COMMAND] Không có ESP32 kết nối cho lệnh '{command}'")
            return False, "⚠️ Thiết bị ESP32 chưa kết nối."

        # Pre-emption cho các lệnh chụp ảnh
        is_capture_cmd = command in ["capture_hq", "capture_pose", "check_baby_pose"]
        if is_capture_cmd:
            from core.http_server import SimpleHttpServer
            if SimpleHttpServer._instance:
                SimpleHttpServer._instance.drop_all_streams()
                await asyncio.sleep(0.3)
        
        sent_count = 0
        for conn in list(self.connections):
            if is_capture_cmd and conn.metadata.get("role") != "camera":
                continue
            try:
                await conn.send_message(esp32_payload)
                sent_count += 1
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"Lỗi gửi lệnh {command} đến {conn.device_id}: {e}")
                if conn in self.connections: self.connections.remove(conn)

        if sent_count > 0:
            msg = f"✅ Lệnh `{label}` đã gửi thành công ({sent_count} thiết bị)."
            self.logger.bind(tag=TAG).info(f"[COMMAND] Đã gửi '{command}' đến {sent_count} thiết bị.")
            return True, msg
        
        return False, f"❌ Không tìm thấy thiết bị phù hợp để nhận lệnh `{label}`."
