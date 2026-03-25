"""
serverToClients/dashboard_updater.py

Module quản lý toàn bộ state của Dashboard và cung cấp phương thức
để mọi thành phần trong server cập nhật lịch sử sự kiện + ghi log console.
"""
import time
import json
import os
from config.logger import setup_logging

TAG = "DashboardUpdater"

# ──────────────────────────────────────────────────────────────────────────────
# Global shared state  (dùng chung qua toàn bộ tiến trình)
# ──────────────────────────────────────────────────────────────────────────────
DASHBOARD_STATE = {
    "mode": "manual",        # 'manual' (giám sát) hoặc 'auto' (tự động)
    "mock_mode": False,      # True: dùng dữ liệu mẫu, False: dùng dữ liệu thật
    "cry_history": [],       # Danh sách sự kiện bé khóc
    "action_logs": [],       # Danh sách hành động từ Telegram / ESP32
    "ai_logs": [],           # Danh sách log AI đỗ dành (query, response, action, status)
    "system_logs": [],       # Danh sách log hệ thống tổng hợp: time - name - action - json
    "temp": 0.0,             # Nhiệt độ hiện tại
    "humidity": 0.0,         # Độ ẩm hiện tại
    "last_cry_time": 0,      # Thời gian cuối cùng báo động khóc (cooldown toàn cục)
    "pose": "UNKNOWN",       # Tư thế bé gần nhất
    "cry_status": False,     # True nếu phát hiện khóc trong vòng 60 giây gần nhất
}

MAX_HISTORY = 50   # Giới hạn số bản ghi lưu trong bộ nhớ


class DashboardUpdater:
    """ 
    Tập trung mọi thao tác ghi vào DASHBOARD_STATE và logger server.
    """

    _instance = None  # Singleton

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.logger = setup_logging()
        return cls._instance

    # ------------------------------------------------------------------
    # Cry events
    # ------------------------------------------------------------------
    @staticmethod
    def add_cry_event(message: str, force: bool = False):
        """
        Ghi nhận sự kiện bé khóc:
        - Thêm vào cry_history
        - In log ra server console
        - Trả về True nếu thành công, False nếu bị chặn bởi cooldown
        """
        current_time = time.time()
        # Cooldown: 60 giây giữa các lần báo động khóc để tránh spam (Toàn cục)
        if not force and (current_time - DASHBOARD_STATE.get("last_cry_time", 0) < 60):
            return False

        DASHBOARD_STATE["last_cry_time"] = current_time
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        entry = {"time": time_str, "message": message}
        DASHBOARD_STATE["cry_history"].append(entry)
        if len(DASHBOARD_STATE["cry_history"]) > MAX_HISTORY:
            DASHBOARD_STATE["cry_history"].pop(0)

        logger = setup_logging()
        logger.bind(tag=TAG).warning(
            f"[CRY EVENT] {time_str} | {message}"
        )
        DashboardUpdater.add_system_log("ESP", "Server", {"event": "cry_detected", "msg": message})
        return True

    # ------------------------------------------------------------------
    # Action logs (từ Telegram button / lệnh text)
    # ------------------------------------------------------------------
    @staticmethod
    def add_action_log(action: str, source: str, result: str):
        """
        Ghi nhận hành động điều khiển:
        - action : tên lệnh (vd: phat_nhac, ru_vong)
        - source : 'telegram_button' | 'telegram_text' | 'dashboard_web'
        - result : kết quả / mô tả ('Đang thực hiện', 'Thành công', 'Lỗi: ...')

        - Thêm vào action_logs
        - In log ra server console (INFO)
        """
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        entry = {
            "time": time_str,
            "action": action,
            "source": source,
            "result": result,
        }
        DASHBOARD_STATE["action_logs"].append(entry)
        if len(DASHBOARD_STATE["action_logs"]) > MAX_HISTORY:
            DASHBOARD_STATE["action_logs"].pop(0)

        logger = setup_logging()
        logger.bind(tag=TAG).info(
            f"[ACTION] {time_str} | source={source} | action={action} | {result}"
        )
        # Chuyển source name sang chuẩn 5 nguồn
        src_map = {
            "telegram_button": "Tele",
            "telegram_text": "Tele",
            "telegram_ai": "Tele",
            "dashboard_web": "Web",
            "web_button": "Web",
            "web_ai": "Web",
            "ESP32-Mic": "ESP",
            "ESP32-Sensor": "ESP"
        }
        log_source = src_map.get(source, source)
        DashboardUpdater.add_system_log(log_source, "ESP", f"Action: {action}, Result: {result}")

    # ------------------------------------------------------------------
    # AI logs (Nghiệp vụ AI tư vấn)
    # ------------------------------------------------------------------
    @staticmethod
    def add_ai_log(query: str, response: str, action: str, status: str, from_node: str = "Server", to_node: str = "Tele"):
        """
        Ghi nhận log AI tư vấn:
        - status: 'suggested' | 'confirmed' | 'cancelled'
        """
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        entry = {
            "time": time_str,
            "query": query,
            "response": response,
            "action": action,
            "status": status
        }
        DASHBOARD_STATE["ai_logs"].append(entry)
        if len(DASHBOARD_STATE["ai_logs"]) > MAX_HISTORY:
            DASHBOARD_STATE["ai_logs"].pop(0)

        # 1. Log JSON to console (Server)
        logger = setup_logging()
        log_json = json.dumps(entry, ensure_ascii=False)
        logger.bind(tag=TAG).info(f"[AI EVENT JSON] {log_json}")
        DashboardUpdater.add_system_log(from_node, to_node, {
            "action": entry.get("action", "-"),
            "status": entry.get("status"),
            "query": entry.get("query", "")[:40],
        })

        # 2. Log to persistent file in data/
        try:
            log_dir = "data"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            log_file = os.path.join(log_dir, "ai_logs.json")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_json + "\n")
        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi ghi file ai_logs.json: {e}")

    # ------------------------------------------------------------------
    # System log – tổng hợp (time | name | action | json tóm gọn)
    # ------------------------------------------------------------------
    @staticmethod
    def add_system_log(from_node: str, to_node: str, data: any):
        """Ghi log hệ thống với format: {from, to, data}."""
        time_str = time.strftime("%H:%M:%S", time.localtime())
        entry = {
            "time": time_str,
            "from": from_node,
            "to": to_node,
            "data": json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
        }
        DASHBOARD_STATE["system_logs"].append(entry)
        if len(DASHBOARD_STATE["system_logs"]) > MAX_HISTORY:
            DASHBOARD_STATE["system_logs"].pop(0)
            
        # Ghi vào file data/system_logs.json
        try:
            import os
            # Lấy đường dẫn tuyệt đối đến thư mục server/data
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            log_path = os.path.join(data_dir, "system_logs.json")
            
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(DASHBOARD_STATE["system_logs"], f, ensure_ascii=False, indent=2)
        except Exception as e:
            from config.logger import setup_logging
            setup_logging().bind(tag="DashboardUpdater").error(f"Lỗi ghi file system_logs.json: {e}")

    # ------------------------------------------------------------------
    # Mode
    # ------------------------------------------------------------------
    @staticmethod
    def update_sensor_data(temp: float, humidity: float):
        """Cập nhật dữ liệu từ cảm biến lên dashboard state."""
        DASHBOARD_STATE["temp"] = temp
        DASHBOARD_STATE["humidity"] = humidity
        DashboardUpdater.add_system_log("ESP", "Server", {"t": temp, "h": humidity})
        
        # Ghi nhận vào lịch sử chart mỗi 10 phút (600s)
        now = time.time()
        if now - getattr(DashboardUpdater, "_last_chart_record", 0) > 600:
            DashboardUpdater._last_chart_record = now
            DashboardUpdater._record_chart_point(temp, humidity)

    @staticmethod
    def _record_chart_point(temp, hum):
        """Lưu điểm dữ liệu mới vào data/chart_history.json (rolling window)."""
        file_path = "data/chart_history.json"
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {"labels": [], "cry": [], "temp": [], "hum": []}

            time_str = time.strftime("%H:%M", time.localtime())
            
            # Thêm điểm mới
            data["labels"].append(time_str)
            data["temp"].append(round(temp, 2))
            data["hum"].append(round(hum, 1))
            
            # Cry value: lấy cường độ khóc cao nhất trong 10p qua (ví dụ)
            # Ở đây ta lấy logic đơn giản: nếu cry_status là True thì coi như có khóc
            cry_val = 500 if DASHBOARD_STATE.get("cry_status") else 50
            data["cry"].append(cry_val)

            # Giới hạn 144 điểm (tương đương 24h nếu 10p/điểm)
            for key in ["labels", "temp", "hum", "cry"]:
                if len(data[key]) > 144:
                    data[key].pop(0)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger = setup_logging()
            logger.bind(tag=TAG).error(f"Lỗi ghi chart_history: {e}")

    @staticmethod
    def set_mode(mode: str):
        DASHBOARD_STATE["mode"] = mode
        logger = setup_logging()
        logger.bind(tag=TAG).info(f"[MODE CHANGE] Chế độ mới: {mode.upper()}")
        DashboardUpdater.add_system_log("Web", "Server", {"action": "mode_change", "mode": mode})

    @staticmethod
    def set_mock_mode(enabled: bool):
        DASHBOARD_STATE["mock_mode"] = enabled
        logger = setup_logging()
        status = "ON" if enabled else "OFF"
        logger.bind(tag=TAG).info(f"[MOCK MODE] Mock Data: {status}")
        DashboardUpdater.add_system_log("Web", "Server", {"action": "mock_change", "mock_mode": status})

    @staticmethod
    def update_pose(pose: str):
        """Cập nhật tư thế bé gần nhất từ pose handler."""
        DASHBOARD_STATE["pose"] = pose.upper() if pose else "UNKNOWN"
        logger = setup_logging()
        logger.bind(tag=TAG).info(f"[POSE UPDATE] Tư thế mới: {DASHBOARD_STATE['pose']}")
        DashboardUpdater.add_system_log("ESPCAM", "Server", {"event": "pose_update", "pose": DASHBOARD_STATE["pose"]})

    @staticmethod
    def get_state() -> dict:
        return DASHBOARD_STATE
