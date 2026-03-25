import json
import time
import random
import asyncio
import re
from aiohttp import web
from config.logger import setup_logging

TAG = __name__

# ──────────────────────────────────────────────────────────────────────────────
# Import DASHBOARD_STATE từ serverToClients (nguồn dữ liệu chung)
# ──────────────────────────────────────────────────────────────────────────────
from core.serverToClients.dashboard_updater import DASHBOARD_STATE

# Command map: from dashboard button id → ESP32 command string
_CMD_MAP = {
    "music":     "phat_nhac",
    "swing":     "ru_vong",
    "fan":       "bat_quat",
    "stop_all":  "dung",
    "check_pose": "capture_pose",
}

# Number of chart data points per range
_RANGE_POINTS = {"1h": 12, "5h": 30, "24h": 48}


def _build_mock_chart(n: int) -> dict:
    """Tạo dữ liệu mock cho chart với n điểm dữ liệu."""
    minutes_per_point = (60 if n == 12 else (10 if n == 30 else 30))
    labels = []
    now = time.time()
    for i in range(n):
        t = now - (n - 1 - i) * minutes_per_point * 60
        labels.append(time.strftime("%H:%M", time.localtime(t)))
    return {
        "labels": labels,
        "cry":    [round(100 + random.random() * 800, 1) for _ in range(n)],
        "temp":   [round(27 + random.random() * 4,   2) for _ in range(n)],
        "hum":    [round(55 + random.random() * 15,  1) for _ in range(n)],
    }


async def _call_llm(config: dict, message: str) -> str:
    """Gọi GeminiLLM (hoặc fallback LLM) từ cấu hình, trả về text report chuyên sâu."""
    try:
        import httpx
        llm_cfg = config.get("LLM", {}).get("GeminiLLM", {})
        api_key = llm_cfg.get("api_key", "")
        model = llm_cfg.get("model_name", "gemini-1.5-flash") # Dùng model stable nhất

        if not api_key or "your" in api_key.lower():
            return "Tiểu Bảo AI: Chưa cấu hình API key. Vui lòng kiểm tra config.yaml."

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        
        # Pediatric Expert Persona (Strengthened)
        system_prompt = (
            "Bạn là Tiểu Bảo AI - Cố vấn Nhi khoa Cao cấp và Chuyên gia Chăm sóc Trẻ sơ sinh.\n"
            "Mục tiêu: Cung cấp báo cáo phân tích chi tiết, khoa học và có tính hành động cao dựa trên dữ liệu IoT thực tế.\n"
            "Cấu trúc báo cáo bắt buộc (trình bày đẹp bằng Markdown):\n"
            "1. **Hiện trạng**: Tóm tắt nhanh các chỉ số cảm biến.\n"
            "2. **Phân tích**: Nhận định về xu hướng (nóng/lạnh, ẩm/khô, bất thường).\n"
            "3. **Khuyến nghị**: Các giải pháp cụ thể (điều chỉnh quạt, điều hòa, thay đổi tư thế, ru võng, phát nhạc).\n"
            "Phong cách: Chuyên gia, ấm áp, sâu sắc. Tránh trả lời ngắn gọn hời hợt.\n"
            "Tiêu chuẩn: Nhiệt độ lý tưởng 24-27°C, Độ ẩm 50-60%. Nếu nóng (>28) khuyên bật quạt, nếu lạnh (<23) khuyên đắp chăn.\n"
        )
        
        if "[CHART_DATA]" in message:
            message = message.replace("[CHART_DATA]", "Dưới đây là chuỗi dữ liệu xu hướng (trend data) từ biểu đồ:")
            system_prompt += "Hãy chú ý đến sự thay đổi của các chỉ số theo thời gian để đưa ra nhận định về xu hướng sức khỏe của bé."

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\nYêu cầu phân tích: {message}"}]
                }
            ],
            "generationConfig": {"maxOutputTokens": 800, "temperature": 0.8}
        }
        async with httpx.AsyncClient(timeout=40) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return (
                data["candidates"][0]["content"]["parts"][0]["text"].strip()
            )
    except Exception as e:
        return f"Tiểu Bảo AI: Lỗi hệ thống phân tích ({type(e).__name__})."


class DashboardHandler:
    last_token_alert_time = 0

    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()

        self.current_key = "Chưa có"
        try:
            val = self.config.get("LLM", {}).get("GroqLLM", {}).get("api_key", "")
            if not val:
                val = self.config.get("ASR", {}).get("GroqASR", {}).get("api_key", "")
            if val:
                self.current_key = val[:10] + "..." + val[-4:]
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────────
    # GET / — Serve dashboard_draft.html from disk
    # ──────────────────────────────────────────────────────────────────────────
    async def handle_get_index(self, request):
        try:
            with open("dashboard_draft.html", "r", encoding="utf-8") as f:
                html_content = f.read()
            return web.Response(text=html_content, content_type="text/html")
        except FileNotFoundError:
            return web.Response(
                text="<h1>dashboard_draft.html không tìm thấy</h1>",
                content_type="text/html",
                status=404,
            )

    # ──────────────────────────────────────────────────────────────────────────
    # GET /api/dashboard/state — full state (legacy / compat)
    # ──────────────────────────────────────────────────────────────────────────
    async def handle_get_state(self, request):
        return web.json_response(DASHBOARD_STATE)

    # ──────────────────────────────────────────────────────────────────────────
    # GET /api/dashboard/sensors — live sensor snapshot
    # ──────────────────────────────────────────────────────────────────────────
    async def handle_get_sensors(self, request):
        now = time.time()
        cry_within_60s = (now - DASHBOARD_STATE.get("last_cry_time", 0)) < 60
        payload = {
            "temp":       DASHBOARD_STATE.get("temp", 0.0),
            "humidity":   DASHBOARD_STATE.get("humidity", 0.0),
            "cry_status": cry_within_60s,
            "pose":       DASHBOARD_STATE.get("pose", "UNKNOWN"),
            "mode":       DASHBOARD_STATE.get("mode", "manual"),
        }
        return web.json_response(payload)

    # ──────────────────────────────────────────────────────────────────────────
    # GET /api/dashboard/chart?range=1h|5h|24h — mock chart data
    # ──────────────────────────────────────────────────────────────────────────
    async def handle_get_chart(self, request):
        range_param = request.rel_url.query.get("range", "24h")
        n = _RANGE_POINTS.get(range_param, 48)
        
        # Try reading from JSON file
        try:
            import os
            history_file = "data/chart_history.json"
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Slice the last n points
                return web.json_response({
                    "labels": data.get("labels", [])[-n:],
                    "cry":    data.get("cry", [])[-n:],
                    "temp":   data.get("temp", [])[-n:],
                    "hum":    data.get("hum", [])[-n:],
                })
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi đọc chart_history.json: {e}")

        # Fallback to mock
        data = _build_mock_chart(n)
        return web.json_response(data)

    # ──────────────────────────────────────────────────────────────────────────
    # POST /api/dashboard/command — send command to ESP32
    # ──────────────────────────────────────────────────────────────────────────
    async def handle_post_command(self, request):
        from core.serverToClients.dashboard_updater import DashboardUpdater
        from core.serverToClients.esp32_commander import ESP32Commander

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

        cmd_key = body.get("cmd", "")
        esp_cmd = _CMD_MAP.get(cmd_key, cmd_key)

        DashboardUpdater.add_action_log(esp_cmd, "dashboard_web", "Đang thực hiện")
        DashboardUpdater.add_system_log("Dashboard→ESP32", esp_cmd, {"src": "web_button"})

        success, msg = await ESP32Commander().execute_command(esp_cmd)

        DashboardUpdater.add_action_log(
            esp_cmd, "dashboard_web", "Thành công" if success else "Chưa có ESP32"
        )

        return web.json_response({"success": success, "message": msg})

    # ──────────────────────────────────────────────────────────────────────────
    # POST /api/dashboard/chat — AI chat via GeminiLLM
    # ──────────────────────────────────────────────────────────────────────────
    async def handle_post_chat(self, request):
        from core.serverToClients.dashboard_updater import DashboardUpdater

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

        message = body.get("message", "").strip()
        if not message:
            return web.json_response({"success": False, "error": "Empty message"}, status=400)

        # Nếu là phân tích chart, dùng đường thống nhất qua AIProcessor (cùng Gemini + prompt)
        if "[CHART_DATA]" in message:
            from core.serverToClients.ai_processor import AIProcessor
            from core.utils.chart_gen import build_chart_summary
            import os

            # Đọc dữ liệu đa cảm biến từ chart_history.json
            hist_labels, hist_cry, hist_temp, hist_hum = [], [], [], []
            try:
                hist_path = "data/chart_history.json"
                if os.path.exists(hist_path):
                    import json as _json
                    with open(hist_path, "r", encoding="utf-8") as f:
                        hist = _json.load(f)
                    hist_labels = hist.get("labels", [])
                    hist_cry    = hist.get("cry",    [])
                    hist_temp   = hist.get("temp",   [])
                    hist_hum    = hist.get("hum",    [])
            except Exception:
                pass

            # Cũng thêm context hiện tại từ DASHBOARD_STATE nếu không đủ điểm lịch sử
            current_ctx = ""
            if not hist_labels:
                current_ctx = message.replace("[CHART_DATA]", "").strip()

            data_summary = (
                build_chart_summary(
                    labels=hist_labels,
                    cry=hist_cry or None,
                    temp=hist_temp or None,
                    hum=hist_hum or None,
                ) if hist_labels else current_ctx or "Chưa có dữ liệu lịch sử."
            )

            reply = await AIProcessor.summarize_baby_condition(self.config, data_summary, days=1)
        else:
            # Chat thông thường: dùng GeminiLLM trực tiếp với persona chuyên gia đầy đủ
            reply = await _call_llm(self.config, message)

        DashboardUpdater.add_ai_log(
            query="[Phân tích biểu đồ]" if "[CHART_DATA]" in message else message,
            response=reply,
            action="chart_analysis" if "[CHART_DATA]" in message else "chat",
            status="confirmed",
        )

        return web.json_response({"success": True, "reply": reply})

    # ──────────────────────────────────────────────────────────────────────────
    # POST /api/dashboard/mode — set operating mode
    # ──────────────────────────────────────────────────────────────────────────
    async def handle_post_mode(self, request):
        from core.serverToClients.dashboard_updater import DashboardUpdater
        data = await request.json()
        new_mode = data.get("mode", "manual")

        if new_mode == "mock_toggle":
            current = DASHBOARD_STATE.get("mock_mode", False)
            DashboardUpdater.set_mock_mode(not current)
            return web.json_response({"success": True, "mock_mode": DASHBOARD_STATE["mock_mode"]})

        DashboardUpdater.add_system_log("Dashboard→Server", "set_mode", data)
        DashboardUpdater.set_mode(new_mode)
        return web.json_response({"success": True, "mode": DASHBOARD_STATE["mode"]})

    # ──────────────────────────────────────────────────────────────────────────
    # POST /api/dashboard/apikey — update Groq API key
    # ──────────────────────────────────────────────────────────────────────────
    def update_api_key(self, new_key):
        try:
            config_path = "data/.config.yaml"
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            updated_content = re.sub(r"api_key:\s*gsk_\w+", f"api_key: {new_key}", content)
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

            if "LLM" in self.config and "GroqLLM" in self.config["LLM"]:
                self.config["LLM"]["GroqLLM"]["api_key"] = new_key
            if "ASR" in self.config and "GroqWhisper" in self.config["ASR"]:
                self.config["ASR"]["GroqWhisper"]["api_key"] = new_key

            self.current_key = new_key[:10] + "..." + new_key[-4:]
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi cập nhật api key: {e}")
            return False

    async def handle_post_apikey(self, request):
        data = await request.json()
        new_key = data.get("api_key", "").strip()
        if new_key.startswith("gsk_"):
            if self.update_api_key(new_key):
                return web.json_response({"success": True})
            return web.json_response(
                {"success": False, "error": "Lỗi quá trình lưu cấu hình"}, status=500
            )
        return web.json_response({"success": False, "error": "Invalid API key"})

    # ──────────────────────────────────────────────────────────────────────────
    # Static helpers (kept for backward compat)
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def add_token_alert():
        current_time = time.time()
        if current_time - DashboardHandler.last_token_alert_time < 300:
            return
        DashboardHandler.last_token_alert_time = current_time
        from core.telegram import TelegramClient, TelegramAlerts
        from core.utils.util import get_local_ip
        import yaml
        try:
            with open("config.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            tg = cfg.get("telegram", {})
            client = TelegramClient(tg.get("bot_token", ""), tg.get("chat_id", ""))
            alerts = TelegramAlerts(client)
            asyncio.create_task(alerts.send_token_alert(get_local_ip()))
        except Exception:
            pass

    @staticmethod
    def add_cry_event(message):
        """Ghi nhận sự kiện bé khóc và gửi Telegram alert."""
        from core.serverToClients.dashboard_updater import DashboardUpdater
        if not DashboardUpdater.add_cry_event(message):
            return

        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        from core.telegram import TelegramClient, TelegramAlerts
        import yaml
        try:
            with open("config.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            tg = cfg.get("telegram", {})
            client = TelegramClient(tg.get("bot_token", ""), tg.get("chat_id", ""))
            alerts = TelegramAlerts(client)
            asyncio.create_task(alerts.send_cry_alert(message, time_str, DASHBOARD_STATE["mode"]))
        except Exception:
            pass
