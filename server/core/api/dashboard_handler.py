import json
import time
import asyncio
import re
from aiohttp import web
from config.logger import setup_logging

TAG = __name__

# ──────────────────────────────────────────────────────────────────────────────
# Import DASHBOARD_STATE từ serverToClients (nguồn dữ liệu chung)
# ──────────────────────────────────────────────────────────────────────────────
from core.serverToClients.dashboard_updater import DASHBOARD_STATE


class DashboardHandler:
    last_token_alert_time = 0

    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()

        self.current_key = "Chưa có"
        try:
            # Ưu tiên lấy từ GroqLLM trước
            val = self.config.get("LLM", {}).get("GroqLLM", {}).get("api_key", "")
            if not val:
                # Nếu không có, thử lấy từ GroqASR (Whisper)
                val = self.config.get("ASR", {}).get("GroqASR", {}).get("api_key", "")
            
            if val:
                self.current_key = val[:10] + "..." + val[-4:]
        except Exception:
            pass

    async def handle_get_index(self, request):
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
                        Nếu hệ thống báo <b>Rate limit reached</b>, hãy dán API Key (gsk_...) mới vào đây.
                    </p>
                    <p>Key hiện tại: <code>{self.current_key}</code></p>
                    <input type="text" id="apiKeyInput" placeholder="Nhập Groq API Key mới (bắt đầu bằng gsk_...)">
                    <button class="btn btn-save" onclick="saveApiKey()">Cập Nhật API Key Mới</button>
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

                async function saveApiKey() {{
                    let key = document.getElementById('apiKeyInput').value;
                    if(!key.startsWith('gsk_')) {{
                        alert('API Key không hợp lệ! Vui lòng nhập key bắt đầu bằng chữ gsk_');
                        return;
                    }}
                    let res = await fetch('/api/dashboard/apikey', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{api_key: key}})
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

    async def handle_get_state(self, request):
        return web.json_response(DASHBOARD_STATE)

    async def handle_post_mode(self, request):
        from core.serverToClients import DashboardUpdater
        data = await request.json()
        new_mode = data.get("mode", "manual")
        # Log: Dashboard → Server JSON
        DashboardUpdater.add_system_log("Dashboard→Server", "set_mode", data)
        DashboardUpdater.set_mode(new_mode)
        return web.json_response({"success": True, "mode": DASHBOARD_STATE["mode"]})

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

    @staticmethod
    def add_token_alert():
        current_time = time.time()
        if current_time - DashboardHandler.last_token_alert_time < 300:
            return
        DashboardHandler.last_token_alert_time = current_time
        from core.telegram import TelegramClient, TelegramAlerts
        from core.utils.util import get_local_ip
        # Dùng config mặc định từ config.yaml
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
        from core.serverToClients import DashboardUpdater
        DashboardUpdater.add_cry_event(message)

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
