<%@ page language="java" contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" %>
    <%@ taglib uri="jakarta.tags.core" prefix="c" %>
        <!DOCTYPE html>
        <html>

        <head>
            <meta charset="UTF-8">
            <title>AI Chat Monitoring - Baby Guard</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
            <style>
                :root {
                    --bg-color: #0f172a;
                    --card-bg: #1e293b;
                    --accent: #38bdf8;
                    --text-main: #f8fafc;
                    --text-dim: #94a3b8;
                    --success: #22c55e;
                    --warning: #f59e0b;
                }

                body {
                    font-family: 'Inter', sans-serif;
                    background-color: var(--bg-color);
                    color: var(--text-main);
                    margin: 0;
                    padding: 40px;
                }

                .container {
                    max-width: 1000px;
                    margin: 0 auto;
                }

                header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 40px;
                }

                h1 {
                    margin: 0;
                    font-weight: 600;
                    color: var(--accent);
                }

                .back-btn {
                    color: var(--text-dim);
                    text-decoration: none;
                    padding: 8px 16px;
                    border: 1px solid var(--text-dim);
                    border-radius: 8px;
                    transition: 0.3s;
                }

                .back-btn:hover {
                    border-color: var(--accent);
                    color: var(--accent);
                }

                .chat-card {
                    background: var(--card-bg);
                    border-radius: 16px;
                    padding: 24px;
                    margin-bottom: 20px;
                    border-left: 4px solid var(--accent);
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                    animation: slideIn 0.5s ease;
                }

                @keyframes slideIn {
                    from {
                        opacity: 0;
                        transform: translateY(10px);
                    }
                }

                .chat-header {
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 12px;
                    font-size: 0.9rem;
                }

                .user-info {
                    font-weight: 600;
                    color: var(--accent);
                }

                .timestamp {
                    color: var(--text-dim);
                }

                .message-row {
                    margin-bottom: 15px;
                }

                .label {
                    color: var(--text-dim);
                    font-size: 0.8rem;
                    display: block;
                    margin-bottom: 4px;
                }

                .content {
                    font-size: 1.1rem;
                }

                .ai-analysis {
                    background: rgba(56, 189, 248, 0.1);
                    padding: 12px;
                    border-radius: 8px;
                    border: 1px dashed var(--accent);
                    margin-top: 15px;
                }

                .status {
                    display: inline-block;
                    margin-top: 10px;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.8rem;
                    font-weight: 600;
                }

                .status-Pending {
                    background: rgba(245, 158, 11, 0.2);
                    color: var(--warning);
                }

                .status-Executed {
                    background: rgba(34, 197, 94, 0.2);
                    color: var(--success);
                }

                .status-Cancelled {
                    background: rgba(239, 68, 68, 0.2);
                    color: #ef4444;
                }
            </style>
        </head>

        <body>
            <div class="container">
                <header>
                    <h1>🤖 AI Chat Monitor</h1>
                    <a href="index" class="back-btn">← Quay lại Dashboard</a>
                </header>

                <c:if test="${empty chatLogs}">
                    <div style="text-align: center; color: var(--text-dim); margin-top: 100px;">
                        Chưa có dữ liệu phân tích AI nào được ghi lại.
                    </div>
                </c:if>

                <c:forEach var="chat" items="${chatLogs}">
                    <div class="chat-card">
                        <div class="chat-header">
                            <span class="user-info">👤 ${chat.userName}</span>
                            <span class="timestamp">🕒 ${chat.timestamp}</span>
                        </div>
                        <div class="message-row">
                            <span class="label">TIN NHẮN NGƯỜI DÙNG:</span>
                            <div class="content">"${chat.userMessage}"</div>
                        </div>
                        <div class="ai-analysis">
                            <span class="label">🤖 AI ANALYZED INTENT:</span>
                            <div class="content" style="color: var(--accent); font-weight: 600;">
                                Lệnh được xác định: [${chat.aiAnalysis}]
                            </div>
                        </div>
                        <div class="status status-${chat.status.split(' ')[0]}">
                            Trạng thái: ${chat.status}
                        </div>
                    </div>
                </c:forEach>
            </div>
        </body>

        </html>