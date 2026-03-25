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

    async def play_music_task(self, filepath: str):
        """Khởi chạy vòng lặp bất đồng bộ để stream file MP3 -> PCM 16kHz xuống thẳng loa ESP32."""
        from core.utils.util import audio_to_data
        import asyncio
        import json

        self._is_playing_music = True
        self.logger.bind(tag=TAG).info(f"[MUSIC] Đang tải file nhạc ra RAM: {filepath}")
        try:
            # Dùng util.py có sẵn của dự án để ép mp3 về chuẩn raw PCM 16-bit 16kHz
            # is_opus=False -> trả về byte array
            audio_chunks = await audio_to_data(filepath, is_opus=False, use_cache=False)
            
            self.logger.bind(tag=TAG).info(f"[MUSIC] Bắt đầu stream {len(audio_chunks)} chunks âm thanh...")
            total_duration = len(audio_chunks) * 0.06
            self.logger.bind(tag=TAG).info(f"[MUSIC] Thời lượng bản nhạc: ~{total_duration:.1f} giây")

            # Báo hiệu cho ESP32 chuyển màn hình sang chế độ SPEAKING (tuỳ chọn)
            start_msg = json.dumps({"type": "tts", "state": "start"})
            for ws in list(self.connections):
                try: await ws.send(start_msg)
                except Exception: pass

            # Vòng lặp bắn từng mẩu âm thanh (60ms) xuống client
            # Không dùng await ws.send() block chết process mà xài sleep để dãn cách
            for chunk in audio_chunks:
                if not self._is_playing_music:
                    self.logger.bind(tag=TAG).info("[MUSIC] Đã bị ngắt (Interrupt) giữa chừng!")
                    break

                for ws in list(self.connections):
                    try:
                        await ws.send(chunk)
                    except Exception as e:
                        if ws in self.connections:
                            self.connections.remove(ws)
                
                # Sleep chuẩn 60ms - trừ đi tí xíu overhead 
                await asyncio.sleep(0.055) 

            # Báo hiệu kết thúc
            stop_msg = json.dumps({"type": "tts", "state": "stop"})
            for ws in list(self.connections):
                try: await ws.send(stop_msg)
                except Exception: pass

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"[MUSIC] Lỗi trong quá trình stream nhạc: {e}")
        finally:
            self.logger.bind(tag=TAG).info("[MUSIC] Kết thúc hàm stream!")
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

        # Xử lý đặc biệt cho lệnh nhạc & dừng
        import os
        import asyncio

        # Nhạc mặc định phát khi bật nôi (thay tên file này để đổi nhạc)
        CRADLE_MUSIC_FILE = "nhacrubengu.mp3"

        music_dir = os.path.join(os.getcwd(), "data", "music")
        os.makedirs(music_dir, exist_ok=True)

        if command == "ru_vong":
            # Bật nôi → phát nhạc ru ngủ cố định
            self._is_playing_music = False
            filepath = os.path.join(music_dir, CRADLE_MUSIC_FILE)
            if os.path.isfile(filepath):
                self.logger.bind(tag=TAG).info(f"[MUSIC] Bật nôi → phát nhạc ru bé: {CRADLE_MUSIC_FILE}")
                self._music_task = asyncio.create_task(self.play_music_task(filepath))
            else:
                self.logger.bind(tag=TAG).warning(f"[MUSIC] Không tìm thấy file nhạc: {filepath}")
                return False, f"⚠️ Không tìm thấy file nhạc ru bé `{CRADLE_MUSIC_FILE}`.\nHãy chép file vào thư mục `server/data/music/`."

        elif command == "phat_nhac":
            # Phát nhạc thủ công → chọn ngẫu nhiên trong thư mục
            self._is_playing_music = False
            playlist = [f for f in os.listdir(music_dir) if f.lower().endswith(('.mp3', '.wav'))]
            if playlist:
                import random
                media_file = random.choice(playlist)
                filepath = os.path.join(music_dir, media_file)
                self.logger.bind(tag=TAG).info(f"[MUSIC] Kích hoạt stream nhạc background... Chọn bài: {media_file}")
                self._music_task = asyncio.create_task(self.play_music_task(filepath))
            else:
                self.logger.bind(tag=TAG).warning(f"[MUSIC] Thư mục trống: {music_dir}")
                return False, f"⚠️ Mới nhận lệnh Phát nhạc nhưng mục tải bị trống!\nBạn nhớ chép các file bài hát (đuôi .mp3 hoặc .wav) vào thư mục `server/data/music/` nhé."

        if command in ("tat_noi", "dung"):
            if self._is_playing_music:
                self.logger.bind(tag=TAG).info("[MUSIC] Lệnh 'Dừng' -> Ngắt luồng nhạc!")
                self._is_playing_music = False

        # Log: Server → ESP JSON payload
        DashboardUpdater.add_system_log(
            from_node="Server",
            to_node="ESP",
            data={"cmd": command, "payload": esp32_payload}
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
                await ws.send(json.dumps(esp32_payload))
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
