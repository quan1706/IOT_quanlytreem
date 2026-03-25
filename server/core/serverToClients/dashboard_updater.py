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
        DashboardUpdater.add_system_log("Cry-Detection", "cry_detected", {"msg": message})
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
        DashboardUpdater.add_system_log(source, action, {"result": result})

    # ------------------------------------------------------------------
    # AI logs (Nghiệp vụ AI tư vấn)
    # ------------------------------------------------------------------
    @staticmethod
    def add_ai_log(query: str, response: str, action: str, status: str):
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
        DashboardUpdater.add_system_log("AI", entry.get("action", "-"), {
            "status": entry.get("status"),
            "q": entry.get("query", "")[:40],
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
    def add_system_log(name: str, action: str, data: dict):
        """
        Ghi một dòng log tổng hợp vào system_logs:
        - name   : nguồn gốc (vd: 'Telegram-Bot', 'AI', 'Cry-Detection')
        - action : hành động ngắn gọn (vd: 'phat_nhac', 'suggested', 'cry_detected')
        - data   : dict JSON tóm gọn sẽ hiển thị dạng inline
        """
        time_str = time.strftime("%H:%M:%S", time.localtime())
        entry = {
            "time": time_str,
            "name": name,
            "action": action,
            "json": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        }
        DASHBOARD_STATE["system_logs"].append(entry)
        if len(DASHBOARD_STATE["system_logs"]) > MAX_HISTORY:
            DASHBOARD_STATE["system_logs"].pop(0)

    # ------------------------------------------------------------------
    # Mode
    # ------------------------------------------------------------------
    @staticmethod
    def update_sensor_data(temp: float, humidity: float):
        """Cập nhật dữ liệu từ cảm biến lên dashboard state."""
        DASHBOARD_STATE["temp"] = temp
        DASHBOARD_STATE["humidity"] = humidity
        DashboardUpdater.add_system_log("Sensor", "update", {"t": temp, "h": humidity})

    @staticmethod
    def set_mode(mode: str):
        DASHBOARD_STATE["mode"] = mode
        logger = setup_logging()
        logger.bind(tag=TAG).info(f"[MODE CHANGE] Chế độ mới: {mode.upper()}")
        DashboardUpdater.add_system_log("System", "mode_change", {"mode": mode})

    @staticmethod
    def set_mock_mode(enabled: bool):
        DASHBOARD_STATE["mock_mode"] = enabled
        logger = setup_logging()
        status = "ON" if enabled else "OFF"
        logger.bind(tag=TAG).info(f"[MOCK MODE] Mock Data: {status}")
        DashboardUpdater.add_system_log("System", "mock_change", {"mock_mode": status})

    @staticmethod
    def get_state() -> dict:
        return DASHBOARD_STATE
