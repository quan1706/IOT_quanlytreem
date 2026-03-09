import json
import time
import asyncio
import re
from aiohttp import web
from config.logger import setup_logging

TAG = __name__

# Global state
DASHBOARD_STATE = {
    "mode": "manual",  # 'manual' (giám sát) hoăc 'auto' (tự động an ủi)
    "cry_history": []
}

class DashboardHandler:
    last_token_alert_time = 0

    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        
        # Try to read current Key to show safely
        self.current_key = "Chưa có"
        try:
            val = self.config.get("LLM", {}).get("GroqLLM", {}).get("api_key", "")
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
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                }}
                h1 {{
                    text-align: center;
                    color: #4CAF50;
                }}
                .card {{
                    background-color: #1e1e1e;
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 20px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                }}
                .btn {{
                    padding: 10px 20px;
                    font-size: 16px;
                    cursor: pointer;
                    border: none;
                    border-radius: 5px;
                    margin-right: 10px;
                    transition: background-color 0.3s;
                }}
                .btn-manual {{ background-color: #2196F3; color: white; }}
                .btn-auto {{ background-color: #9C27B0; color: white; }}
                .btn-save {{ background-color: #f44336; color: white; margin-top: 10px; }}
                input[type="text"] {{
                    width: calc(100% - 22px);
                    padding: 10px;
                    margin-top: 5px;
                    border-radius: 4px;
                    border: 1px solid #555;
                    background-color: #2d2d2d;
                    color: white;
                }}
                .history-list {{
                    list-style-type: none;
                    padding: 0;
                }}
                .history-item {{
                    background-color: #2d2d2d;
                    margin-bottom: 10px;
                    padding: 15px;
                    border-left: 5px solid #ff9800;
                    border-radius: 4px;
                }}
                #status {{ font-weight: bold; color: #4CAF50; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🍼 Smart Baby Care Dashboard</h1>
                
                <div class="card">
                    <h2>Chế độ hoạt động hiện tại: <span id="status">Đang tải...</span></h2>
                    <p>
                        <button class="btn btn-manual" onclick="setMode('manual')">Chế Độ Giám Sát (Lưu lịch sử)</button>
                        <button class="btn btn-auto" onclick="setMode('auto')">Chế Độ Tự Động (Tự an ủi bé)</button>
                    </p>
                    <p style="color: #aaa; font-size: 0.9em;">
                        - Chế Độ Giám Sát: Không làm phiền bé, chỉ cập nhật lịch sử cảnh báo khóc lên Dashboard.<br>
                        - Chế Độ Tự Động: Tự động phát giọng nói Dỗ dành bé khi phát hiện tiếng khóc.
                    </p>
                </div>

                <div class="card" style="border-left: 5px solid #f44336;">
                    <h2>⚙ Cài đặt Groq API Key (Khi hết hạn mức/Token)</h2>
                    <p style="color: #aaa; font-size: 0.9em;">Nếu hệ thống báo <b>Rate limit reached (lỗi token)</b>, hãy dán API Key (gsk_...) mới vào đây. Hệ thống sẽ áp dụng ngay lập tức!</p>
                    <p>Key hiện tại: <code>{self.current_key}</code></p>
                    <input type="text" id="apiKeyInput" placeholder="Nhập Groq API Key mới (bắt đầu bằng gsk_...)">
                    <button class="btn btn-save" onclick="saveApiKey()">Cập Nhật API Key Mới</button>
                    <p id="apiMessage" style="color: #4CAF50; display: none; margin-top: 10px;">Lưu thành công! Vui lòng reset lại Server Python nếu bạn đang gọi Voice.</p>
                </div>

                <div class="card">
                    <h2>Lịch sử Nhận Diện Tiếng Khóc</h2>
                    <ul class="history-list" id="historyList">
                    </ul>
                </div>
            </div>

            <script>
                async function fetchState() {{
                    try {{
                        let response = await fetch('/api/dashboard/state');
                        let data = await response.json();
                        
                        document.getElementById('status').innerText = 
                            data.mode === 'manual' ? 'GIÁM SÁT THỦ CÔNG' : 'TỰ ĐỘNG AN ỦI';
                            
                        document.getElementById('status').style.color = 
                            data.mode === 'manual' ? '#2196F3' : '#9C27B0';

                        let historyHtml = '';
                        let reversedHistory = [...data.cry_history].reverse();
                        reversedHistory.forEach(item => {{
                            historyHtml += `<li class="history-item">
                                <strong>${{item.time}}</strong> - ${{item.message}}
                            </li>`;
                        }});
                        if (reversedHistory.length === 0) {{
                            historyHtml = '<li class="history-item" style="border-left-color: #4CAF50;">Chưa có dữ liệu nào. Bé đang ngủ rất ngoan! 😴</li>';
                        }}
                        
                        document.getElementById('historyList').innerHTML = historyHtml;
                    }} catch(e) {{
                        console.error('Lỗi lấy dữ liệu:', e);
                    }}
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
                    let response = await fetch('/api/dashboard/apikey', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{api_key: key}})
                    }});
                    if(response.ok) {{
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
        return web.Response(text=html_content, content_type='text/html')

    async def handle_get_state(self, request):
        return web.json_response(DASHBOARD_STATE)

    async def handle_post_mode(self, request):
        data = await request.json()
        DASHBOARD_STATE["mode"] = data.get("mode", "manual")
        return web.json_response({"success": True, "mode": DASHBOARD_STATE["mode"]})

    def update_api_key(self, new_key):
        try:
            config_path = "data/.config.yaml"
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            import re
            updated_content = re.sub(r'api_key:\s*gsk_\w+', f'api_key: {new_key}', content)
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
            return web.json_response({"success": False, "error": "Lỗi quá trình lưu cấu hình"}, status=500)
        return web.json_response({"success": False, "error": "Invalid API key"})

    @staticmethod
    def add_token_alert():
        current_time = time.time()
        if current_time - DashboardHandler.last_token_alert_time < 300:
            return
            
        DashboardHandler.last_token_alert_time = current_time
        
        from core.api.telegram_handler import TelegramHandler
        asyncio.create_task(TelegramHandler.send_telegram_token_alert())

    @staticmethod
    def add_cry_event(message):
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        DASHBOARD_STATE["cry_history"].append({"time": time_str, "message": message})
        if len(DASHBOARD_STATE["cry_history"]) > 50:
            DASHBOARD_STATE["cry_history"].pop(0)
            
        from core.api.telegram_handler import TelegramHandler
        asyncio.create_task(TelegramHandler.send_telegram_alert(message, time_str, DASHBOARD_STATE["mode"]))

