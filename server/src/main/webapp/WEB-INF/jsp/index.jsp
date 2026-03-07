<%@ page language="java" contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" %>
    <%@ taglib prefix="c" uri="jakarta.tags.core" %>
        <!DOCTYPE html>
        <html lang="en">

        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>${title}</title>
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
            <style>
                :root {
                    --primary: #6366f1;
                    --primary-glow: rgba(99, 102, 241, 0.4);
                    --bg: #0f172a;
                    --card-bg: rgba(30, 41, 59, 0.7);
                    --text-main: #f8fafc;
                    --text-dim: #94a3b8;
                    --success: #22c55e;
                }

                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                    font-family: 'Outfit', sans-serif;
                }

                body {
                    background-color: var(--bg);
                    background-image:
                        radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
                        radial-gradient(at 100% 100%, rgba(99, 102, 241, 0.1) 0px, transparent 50%);
                    color: var(--text-main);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }

                .container {
                    width: 95%;
                    max-width: 800px;
                    margin: 20px auto;
                    animation: fadeIn 0.8s ease-out;
                }

                @keyframes fadeIn {
                    from {
                        opacity: 0;
                        transform: translateY(20px);
                    }

                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }

                .dashboard-card {
                    background: var(--card-bg);
                    backdrop-filter: blur(12px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 24px;
                    padding: 40px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                    text-align: center;
                }

                .logo {
                    font-size: 3rem;
                    margin-bottom: 20px;
                    display: inline-block;
                }

                h1 {
                    font-weight: 600;
                    font-size: 2rem;
                    margin-bottom: 8px;
                    background: linear-gradient(to right, #818cf8, #c084fc);
                    -webkit-background-clip: text;
                    background-clip: text;
                    -webkit-text-fill-color: transparent;
                }

                .status-badge {
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    background: rgba(34, 197, 94, 0.1);
                    color: var(--success);
                    padding: 6px 16px;
                    border-radius: 100px;
                    font-weight: 600;
                    font-size: 0.875rem;
                    margin-bottom: 24px;
                    border: 1px solid rgba(34, 197, 94, 0.2);
                }

                .pulse {
                    width: 8px;
                    height: 8px;
                    background: var(--success);
                    border-radius: 50%;
                    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
                    animation: pulse-green 2s infinite;
                }

                @keyframes pulse-green {
                    0% {
                        transform: scale(0.95);
                        box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
                    }

                    70% {
                        transform: scale(1);
                        box-shadow: 0 0 0 10px rgba(34, 197, 94, 0);
                    }

                    100% {
                        transform: scale(0.95);
                        box-shadow: 0 0 0 0 rgba(34, 197, 94, 0);
                    }
                }

                .info-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 16px;
                    margin-top: 32px;
                    text-align: left;
                }

                .info-item {
                    background: rgba(255, 255, 255, 0.03);
                    padding: 16px;
                    border-radius: 16px;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                }

                .info-label {
                    color: var(--text-dim);
                    font-size: 0.75rem;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    margin-bottom: 4px;
                }

                .info-value {
                    font-weight: 600;
                    font-size: 0.95rem;
                }

                .footer {
                    margin-top: 32px;
                    color: var(--text-dim);
                    font-size: 0.875rem;
                }

                .btn-test {
                    display: inline-block;
                    margin-top: 24px;
                    padding: 12px 24px;
                    background: var(--primary);
                    color: white;
                    text-decoration: none;
                    border-radius: 12px;
                    font-weight: 600;
                    transition: all 0.3s ease;
                    box-shadow: 0 4px 14px 0 var(--primary-glow);
                }

                .btn-test:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px 0 var(--primary-glow);
                }

                .card {
                    background: rgba(0, 0, 0, 0.2);
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 16px;
                    margin-top: 32px;
                    padding: 20px;
                    text-align: left;
                }

                .card-header {
                    font-weight: 600;
                    font-size: 1rem;
                    color: var(--text-main);
                    margin-bottom: 15px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }

                .card-header i {
                    color: var(--primary);
                }

                .log-container {
                    max-height: 250px;
                    overflow-y: auto;
                    padding-right: 10px;
                }

                .log-item {
                    background: rgba(255, 255, 255, 0.02);
                    border-left: 3px solid var(--primary);
                    padding: 10px 15px;
                    margin-bottom: 8px;
                    border-radius: 8px;
                    font-size: 0.85rem;
                    color: var(--text-dim);
                    word-break: break-all;
                }

                .log-container::-webkit-scrollbar {
                    width: 6px;
                }

                .log-container::-webkit-scrollbar-thumb {
                    background: var(--primary);
                    border-radius: 10px;
                }
            </style>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
        </head>

        <body>
            <div class="container">
                <div class="dashboard-card">
                    <div class="logo">👶</div>
                    <h1>Baby Guard Server</h1>

                    <div class="status-badge">
                        <div class="pulse"></div>
                        ${systemStatus != null ? systemStatus : "OPERATIONAL"}
                    </div>

                    <div class="info-grid">
                        <div class="info-item">
                            <p class="info-label">Version</p>
                            <p class="info-value">v1.0.0-PRO</p>
                        </div>
                        <div class="info-item">
                            <p class="info-label">Server Time</p>
                            <p class="info-value">${time}</p>
                        </div>
                        <div class="info-item" style="grid-column: span 2;">
                            <p class="info-label">Endpoints Operational</p>
                            <p class="info-value">/api/cry, /telegram/callback</p>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header">
                            <i class="fas fa-list-ul"></i> RECENT LOGS
                            <button onclick="testLog()"
                                style="margin-left: auto; background: none; border: 1px solid var(--primary); color: var(--primary); font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; cursor: pointer;">Test
                                Log</button>
                        </div>
                        <div class="log-container">
                            <c:if test="${empty logs}">
                                <div id="no-logs" class="log-item" style="color: #666;">No logs available yet...
                                    (Waiting for ESP32)</div>
                            </c:if>
                            <c:forEach var="log" items="${logs}">
                                <div class="log-item">${log}</div>
                            </c:forEach>
                        </div>
                    </div>

                    <a href="https://t.me/${botName}" target="_blank" class="btn-test">Open Bot on Telegram</a>

                    <p class="footer">Deepmind AI x Baby Guard Project</p>
                </div>
            </div>

            <script>
                function updateLogs() {
                    fetch('${pageContext.request.contextPath}/api/logs')
                        .then(response => {
                            if (!response.ok) throw new Error('Network response was not ok');
                            return response.json();
                        })
                        .then(logs => {
                            const container = document.querySelector('.log-container');
                            if (!Array.isArray(logs) || logs.length === 0) {
                                return;
                            }
                            let html = '';
                            logs.forEach(log => {
                                html += '<div class="log-item">' + log + '</div>';
                            });
                            container.innerHTML = html;
                        })
                        .catch(err => console.error('Lỗi khi cập nhật log:', err));
                }

                function testLog() {
                    fetch('${pageContext.request.contextPath}/api/test-log')
                        .then(() => updateLogs());
                }

                setInterval(updateLogs, 3000);
            </script>
        </body>

        </html>