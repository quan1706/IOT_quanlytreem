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
        # Kiểm tra xem connection này đã tồn tại chưa (dựa trên socket object)
        for conn in self.connections:
            if conn['ws'] == ws_connection:
                conn['device_id'] = device_id
                conn['role'] = role
                return

        self.connections.append({
            'ws': ws_connection,
            'device_id': device_id,
            'role': role
        })
        self.logger.bind(tag=TAG).info(
            f"[WS] Đã thêm ESP32 connection: {device_id} ({role}). Tổng số: {len(self.connections)}"
        )

    def unregister_connection(self, ws_connection):
        """Hủy đăng ký WebSocket connection khi ESP32 ngắt kết nối."""
        self.connections = [c for c in self.connections if c['ws'] != ws_connection]
        self.logger.bind(tag=TAG).info(
            f"[WS] Đã xóa ESP32 connection. Tổng số: {len(self.connections)}"
        )

    async def play_music_task(self, filepath: str):
        """Khởi chạy vòng lặp bất đồng bộ để stream file MP3 -> PCM 16kHz xuống thẳng loa ESP32."""
        from core.utils.util import audio_to_data
        import asyncio
        import json

        self._is_playing_music = True
        self.logger.bind(tag=TAG).info(f"[MUSIC] Đang tải file nhạc ra RAM: {filepath}")
        try:
            audio_chunks = await audio_to_data(filepath, is_opus=False, use_cache=False)
            
            self.logger.bind(tag=TAG).info(f"[MUSIC] Bắt đầu stream {len(audio_chunks)} chunks âm thanh...")
            total_duration = len(audio_chunks) * 0.06

            start_msg = json.dumps({"type": "tts", "state": "start"})
            for conn in list(self.connections):
                try: await conn['ws'].send(start_msg)
                except Exception: pass

            for chunk in audio_chunks:
                if not self._is_playing_music:
                    break

                for conn in list(self.connections):
                    try:
                        await conn['ws'].send(chunk)
                    except Exception:
                        pass
                
                await asyncio.sleep(0.055) 

            stop_msg = json.dumps({"type": "tts", "state": "stop"})
            for conn in list(self.connections):
                try: await conn['ws'].send(stop_msg)
                except Exception: pass

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"[MUSIC] Lỗi trong quá trình stream nhạc: {e}")
        finally:
            self._is_playing_music = False

    async def execute_command(self, command: str) -> tuple[bool, str]:
        """
        Thực thi lệnh xuống ESP32.
        """
        import json
        from core.serverToClients.dashboard_updater import DashboardUpdater

        label = self._get_label(command)
        esp32_payload = {"type": "cmd", "cmd": command}

        self.logger.bind(tag=TAG).info(
            f"[COMMAND] Tiếp nhận lệnh: {command} ({label})"
        )

        import os
        import asyncio
        CRADLE_MUSIC_FILE = "nhacrubengu.mp3"
        music_dir = os.path.join(os.getcwd(), "data", "music")
        os.makedirs(music_dir, exist_ok=True)

        if command == "ru_vong":
            self._is_playing_music = False
            filepath = os.path.join(music_dir, CRADLE_MUSIC_FILE)
            if os.path.isfile(filepath):
                self._music_task = asyncio.create_task(self.play_music_task(filepath))
            else:
                return False, f"⚠️ Không tìm thấy file nhạc ru bé."

        elif command == "phat_nhac":
            self._is_playing_music = False
            playlist = [f for f in os.listdir(music_dir) if f.lower().endswith(('.mp3', '.wav'))]
            if playlist:
                import random
                media_file = random.choice(playlist)
                filepath = os.path.join(music_dir, media_file)
                self._music_task = asyncio.create_task(self.play_music_task(filepath))
            else:
                return False, f"⚠️ Thư mục nhạc trống!"

        if command in ("tat_noi", "dung"):
            self._is_playing_music = False

        DashboardUpdater.add_system_log(
            from_node="Server",
            to_node="ESP",
            data={"cmd": command, "payload": esp32_payload}
        )

        if not self.connections:
            self.logger.bind(tag=TAG).warning(f"[COMMAND] Không có ESP32 kết nối cho lệnh '{command}'")
            return False, "⚠️ Thiết bị ESP32 chưa kết nối."

        sent_count = 0
        # Lọc thiết bị cho lệnh chụp ảnh
        is_capture_cmd = command in ("capture_hq", "capture_pose", "check_baby_pose")
        
        for conn in list(self.connections):
            # Nếu là lệnh chụp ảnh, chỉ gửi cho thiết bị có role là camera
            if is_capture_cmd and conn.get('role') != 'camera':
                continue
                
            try:
                await conn['ws'].send(json.dumps(esp32_payload))
                sent_count += 1
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"[COMMAND] Lỗi gửi WebSocket đến {conn.get('device_id')}: {e}")
                if conn in self.connections:
                    self.connections.remove(conn)

        if sent_count > 0:
            msg = f"✅ Lệnh `{label}` đã gửi thành công ({sent_count} thiết bị)."
            self.logger.bind(tag=TAG).info(f"[COMMAND] Đã gửi '{command}' đến {sent_count} thiết bị.")
            return True, msg
        else:
            msg = f"❌ Không tìm thấy thiết bị phù hợp để nhận lệnh `{label}`."
            return False, msg
