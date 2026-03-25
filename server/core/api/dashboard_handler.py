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

        self.current_key_llm = "Chưa có"
        self.current_key_asr = "Chưa có"
        try:
<<<<<<< HEAD
            val = self.config.get("LLM", {}).get("GroqLLM", {}).get("api_key", "")
            if not val:
                val = self.config.get("ASR", {}).get("GroqASR", {}).get("api_key", "")
            if val:
                self.current_key = val[:10] + "..." + val[-4:]
=======
            val_llm = self.config.get("LLM", {}).get("GroqLLM", {}).get("api_key", "")
            if val_llm:
                self.current_key_llm = val_llm[:10] + "..." + val_llm[-4:]
                
            val_asr = self.config.get("ASR", {}).get("GroqWhisper", {}).get("api_key", "")
            if val_asr:
                self.current_key_asr = val_asr[:10] + "..." + val_asr[-4:]
>>>>>>> 21d0dcacf57f6c54a16d10ea0205a89c5618a822
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────────
    # GET / — Serve dashboard_draft.html from disk
    # ──────────────────────────────────────────────────────────────────────────
    async def handle_get_index(self, request):
<<<<<<< HEAD
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
=======
        html_content = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Smart Baby Care Dashboard</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #121212;
                    color: #ffffff;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{ max-width: 860px; margin: 0 auto; }}
                h1 {{ text-align: center; color: #4CAF50; }}
                .card {{
                    background-color: #1e1e1e;
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 20px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                }}
                .btn {{
                    padding: 10px 20px; font-size: 16px; cursor: pointer;
                    border: none; border-radius: 5px; margin-right: 10px;
                    transition: background-color 0.3s;
                }}
                .btn-manual {{ background-color: #2196F3; color: white; }}
                .btn-auto   {{ background-color: #9C27B0; color: white; }}
                .btn-save   {{ background-color: #f44336; color: white; margin-top: 10px; }}
                input[type="text"] {{
                    width: calc(100% - 22px); padding: 10px; margin-top: 5px;
                    border-radius: 4px; border: 1px solid #555;
                    background-color: #2d2d2d; color: white;
                }}
                .history-list {{ list-style-type: none; padding: 0; }}
                .history-item {{
                    background-color: #2d2d2d; margin-bottom: 8px;
                    padding: 12px 15px; border-left: 5px solid #ff9800; border-radius: 4px;
                    font-size: 0.9em;
                }}
                .action-item {{
                    background-color: #1a2a1a; margin-bottom: 8px;
                    padding: 12px 15px; border-left: 5px solid #4CAF50; border-radius: 4px;
                    font-size: 0.9em;
                }}
                .action-item .badge {{
                    display: inline-block; padding: 2px 8px; border-radius: 10px;
                    font-size: 0.8em; font-weight: bold; margin-left: 8px;
                }}
                .badge-btn  {{ background: #2196F3; color: white; }}
                .badge-text {{ background: #9C27B0; color: white; }}
                .badge-web  {{ background: #f44336; color: white; }}
                #status {{ font-weight: bold; color: #4CAF50; }}
                .tab-bar {{ display: flex; gap: 10px; margin-bottom: 12px; }}
                .tab {{
                    padding: 8px 18px; cursor: pointer; border-radius: 6px;
                    background: #2d2d2d; color: #aaa; border: none; font-size: 0.95em;
                }}
                .tab.active {{ background: #4CAF50; color: white; }}
                .log-row {{
                    display: flex; gap: 8px; align-items: baseline;
                    padding: 7px 12px; border-bottom: 1px solid #2a2a2a;
                    font-size: 0.85em; font-family: monospace;
                }}
                .log-row:hover {{ background: #1d2d1d; }}
                .log-time  {{ color: #888; min-width: 70px; }}
                .log-name  {{ color: #64b5f6; min-width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
                .log-action{{ color: #a5d6a7; min-width: 120px; }}
                .log-json  {{ color: #ffe082; word-break: break-all; }}
                #sysLogPanel {{ max-height: 420px; overflow-y: auto; background:#111; border-radius:6px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🍼 Smart Baby Care Dashboard</h1>

                <div class="card">
                    <h2>Chế độ hoạt động hiện tại: <span id="status">Đang tải...</span></h2>
                    <p>
                        <button class="btn btn-manual" onclick="setMode('manual')">Chế Độ Giám Sát (Lưu lịch sử)</button>
                        <button class="btn btn-auto"   onclick="setMode('auto')">Chế Độ Tự Động (Tự an ủi bé)</button>
                    </p>
                    <p style="color: #aaa; font-size: 0.9em;">
                        - Chế Độ Giám Sát: Không làm phiền bé, chỉ cập nhật lịch sử cảnh báo khóc lên Dashboard.<br>
                        - Chế Độ Tự Động: Tự động phát giọng nói Dỗ dành bé khi phát hiện tiếng khóc.
                    </p>
                </div>

                <div class="card" style="border-left: 5px solid #f44336;">
                    <h2>⚙ Cài đặt Groq API Key</h2>
                    <p style="color: #aaa; font-size: 0.9em;">
                        Tách riêng 2 khóa API để tránh lỗi Rate Limit. Bạn cần tạo 2 mã riêng biệt tại web Groq.
                    </p>
                    <p>Key LLM (Bộ não suy nghĩ): <code>{self.current_key_llm}</code></p>
                    <input type="text" id="apiKeyLLM" placeholder="Nhập API Key LLM mới (tuỳ chọn)">
                    <p style="margin-top:10px;">Key ASR (Nghe giọng nói): <code>{self.current_key_asr}</code></p>
                    <input type="text" id="apiKeyASR" placeholder="Nhập API Key ASR mới (tuỳ chọn)">
                    <button class="btn btn-save" onclick="saveApiKeys()">Cập Nhật Các Key Đã Nhập</button>
                    <p id="apiMessage" style="color: #4CAF50; display: none; margin-top: 10px;">
                        Lưu thành công! Vui lòng reset lại Server Python nếu bạn đang gọi Voice.
                    </p>
                </div>

                <div class="card">
                    <div class="tab-bar">
                        <button class="tab active" id="tab-cry"    onclick="switchTab('cry')">😢 Lịch sử Khóc</button>
                        <button class="tab"        id="tab-action" onclick="switchTab('action')">🎮 Hành Động</button>
                        <button class="tab"        id="tab-ai"     onclick="switchTab('ai')">🤖 AI Tư Vấn</button>
                        <button class="tab"        id="tab-syslog" onclick="switchTab('syslog')">📋 System Log</button>
                    </div>

                    <!-- Tab lịch sử khóc -->
                    <div id="panel-cry">
                        <ul class="history-list" id="historyList"></ul>
                    </div>

                    <!-- Tab hành động -->
                    <div id="panel-action" style="display:none;">
                        <ul class="history-list" id="actionList"></ul>
                    </div>

                    <!-- Tab AI Tư Vấn -->
                    <div id="panel-ai" style="display:none;">
                        <ul class="history-list" id="aiList"></ul>
                    </div>

                    <!-- Tab System Log -->
                    <div id="panel-syslog" style="display:none;">
                        <div style="padding:8px 12px; color:#888; font-size:0.8em;">
                            Thời gian — Tên nguồn — Hành động — JSON tóm gọn
                        </div>
                        <div id="sysLogPanel"></div>
                    </div>
                </div>
            </div>

            <script>
                function switchTab(tab) {{
                    ['cry','action','ai','syslog'].forEach(t => {{
                        document.getElementById('panel-' + (t === 'syslog' ? 'syslog' : t)).style.display = tab === t ? '' : 'none';
                        document.getElementById('tab-' + (t === 'syslog' ? 'syslog' : t)).classList.toggle('active', tab === t);
                    }});
                }}

                const SOURCE_LABEL = {{
                    'telegram_button': ['Telegram Nút', 'badge-btn'],
                    'telegram_text':   ['Telegram Text', 'badge-text'],
                    'telegram_ai':     ['AI Xác nhận', 'badge-text'],
                    'dashboard_web':   ['Dashboard Web', 'badge-web'],
                }};

                async function fetchState() {{
                    try {{
                        let res  = await fetch('/api/dashboard/state');
                        let data = await res.json();

                        // Mode
                        document.getElementById('status').innerText =
                            data.mode === 'manual' ? 'GIÁM SÁT THỦ CÔNG' : 'TỰ ĐỘNG AN ỦI';
                        document.getElementById('status').style.color =
                            data.mode === 'manual' ? '#2196F3' : '#9C27B0';

                        // Cry history
                        let cryHtml = '';
                        [...data.cry_history].reverse().forEach(item => {{
                            cryHtml += `<li class="history-item"><strong>${{item.time}}</strong> — ${{item.message}}</li>`;
                        }});
                        if (!cryHtml) {{
                            cryHtml = '<li class="history-item" style="border-left-color:#4CAF50;">Chưa có dữ liệu. Bé đang ngủ rất ngoan! 😴</li>';
                        }}
                        document.getElementById('historyList').innerHTML = cryHtml;

                        // Action logs
                        let actionHtml = '';
                        [...(data.action_logs || [])].reverse().forEach(item => {{
                            let [srcLabel, srcClass] = SOURCE_LABEL[item.source] || [item.source, 'badge-btn'];
                            actionHtml += `
                                <li class="action-item">
                                    <strong>${{item.time}}</strong>
                                    <span class="badge ${{srcClass}}">${{srcLabel}}</span>
                                    — <code>${{item.action}}</code>
                                    <span style="color:#aaa;"> → ${{item.result}}</span>
                                </li>`;
                        }});
                        if (!actionHtml) {{
                            actionHtml = '<li class="action-item" style="border-left-color:#555;">Chưa có hành động điều khiển nào.</li>';
                        }}
                        document.getElementById('actionList').innerHTML = actionHtml;

                        // AI logs
                        let aiHtml = '';
                        const STATUS_BADGE = {{
                            'suggested': ['🎞 Gợi ý', '#ff9800'],
                            'confirmed': ['✅ Chấp nhận', '#4CAF50'],
                            'cancelled': ['❌ Từ chối', '#f44336'],
                        }};
                        [...(data.ai_logs || [])].reverse().forEach(item => {{
                            let [stLabel, stColor] = STATUS_BADGE[item.status] || [item.status, '#888'];
                            aiHtml += `
                                <li class="history-item" style="border-left-color: ${{stColor}}; background: #1a1a1a;">
                                    <strong>${{item.time}}</strong> — <span style="color:${{stColor}};">${{stLabel}}</span><br>
                                    <span style="color:#aaa;">User:</span> ${{item.query}}<br>
                                    <span style="color:#4CAF50;">AI:</span> ${{item.response}} 
                                    (<code>${{item.action}}</code>)
                                </li>`;
                        }});
                        if (!aiHtml) {{
                            aiHtml = '<li class="history-item" style="border-left-color:#555;">Chưa có thảo luận AI nào.</li>';
                        }}
                        document.getElementById('aiList').innerHTML = aiHtml;

                        // System logs
                        let sysHtml = '';
                        [...(data.system_logs || [])].reverse().forEach(item => {{
                            sysHtml += `<div class="log-row">
                                <span class="log-time">${{item.time}}</span>
                                <span class="log-name">${{item.name}}</span>
                                <span class="log-action">${{item.action}}</span>
                                <span class="log-json">${{item.json}}</span>
                            </div>`;
                        }});
                        if (!sysHtml) sysHtml = '<div class="log-row"><span class="log-time">—</span><span class="log-name" style="color:#555;">Chưa có log nào.</span></div>';
                        document.getElementById('sysLogPanel').innerHTML = sysHtml;

                    }} catch(e) {{ console.error('Lỗi lấy dữ liệu:', e); }}
                }}

                async function setMode(mode) {{
                    await fetch('/api/dashboard/mode', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{mode: mode}})
                    }});
                    fetchState();
                }}

                async function saveApiKeys() {{
                    let keyLLM = document.getElementById('apiKeyLLM').value.trim();
                    let keyASR = document.getElementById('apiKeyASR').value.trim();
                    if(keyLLM === '' && keyASR === '') {{
                        alert('Vui lòng nhập ít nhất 1 API key mới!');
                        return;
                    }}
                    let payload = {{}};
                    if(keyLLM.length > 0) {{
                        if(!keyLLM.startsWith('gsk_')) {{ alert('Key LLM phải bắt đầu bằng gsk_'); return; }}
                        payload.api_key_llm = keyLLM;
                    }}
                    if(keyASR.length > 0) {{
                        if(!keyASR.startsWith('gsk_')) {{ alert('Key ASR phải bắt đầu bằng gsk_'); return; }}
                        payload.api_key_asr = keyASR;
                    }}
                    
                    let res = await fetch('/api/dashboard/apikey', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify(payload)
                    }});
                    if(res.ok) {{
                        document.getElementById('apiMessage').style.display = 'block';
                        setTimeout(() => location.reload(), 2000);
                    }} else {{
                        alert('Có lỗi xảy ra khi lưu Key.');
                    }}
                }}

                setInterval(fetchState, 3000);
                fetchState();
            </script>
        </body>
        </html>
        """
        return web.Response(text=html_content, content_type="text/html")
>>>>>>> 21d0dcacf57f6c54a16d10ea0205a89c5618a822

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

    def update_api_keys(self, new_key_llm, new_key_asr):
        try:
            config_path = "data/.config.yaml"
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            if new_key_llm:
                content = re.sub(r"(GroqLLM:[\s\S]*?api_key:\s*)gsk_\w+", r"\g<1>" + new_key_llm, content)
            if new_key_asr:
                content = re.sub(r"(GroqWhisper:[\s\S]*?api_key:\s*)gsk_\w+", r"\g<1>" + new_key_asr, content)

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)

            if new_key_llm and "LLM" in self.config and "GroqLLM" in self.config["LLM"]:
                self.config["LLM"]["GroqLLM"]["api_key"] = new_key_llm
                self.current_key_llm = new_key_llm[:10] + "..." + new_key_llm[-4:]
            if new_key_asr and "ASR" in self.config and "GroqWhisper" in self.config["ASR"]:
                self.config["ASR"]["GroqWhisper"]["api_key"] = new_key_asr
                self.current_key_asr = new_key_asr[:10] + "..." + new_key_asr[-4:]

            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi cập nhật api key: {e}")
            return False

    async def handle_post_apikey(self, request):
        data = await request.json()
        new_key_llm = data.get("api_key_llm", "").strip()
        new_key_asr = data.get("api_key_asr", "").strip()

        if new_key_llm or new_key_asr:
            if self.update_api_keys(new_key_llm, new_key_asr):
                return web.json_response({"success": True})
            return web.json_response({"success": False, "error": "Lỗi quá trình lưu cấu hình"}, status=500)
        return web.json_response({"success": False, "error": "No API key provided"})

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
