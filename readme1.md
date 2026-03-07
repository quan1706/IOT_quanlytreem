# 📋 Các Đường Dẫn Vận Hành Hệ Thống (Baby Guard IoT)

Tài liệu này tổng hợp các đường dẫn (URL) quan trọng để cấu hình và kiểm tra hệ thống từ xa.

## 1. Cấu Hình Telegram Webhook
Đây là thao tác quan trọng nhất để Bot có thể nhận tin nhắn từ người dùng.
*   **Cú pháp:**
    `https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<URL_RENDER_CUA_BAN>/telegram/callback`
*   **Ví dụ với Token của bạn:**
    `https://api.telegram.org/bot8765806795:AAEB83HSeGkpYYv0JsnnPz6IaiSCvlDOn_w/setWebhook?url=https://YOUR_URL.onrender.com/telegram/callback`

---

## 2. Các Endpoint Hệ Thống (Dùng trên Render)

### 🖥️ Giao diện Dashboard
*   `https://<YOUR_URL>.onrender.com/` - Trang chủ giám sát thời gian thực.

### 🤖 Giám sát AI Chat
*   `https://<YOUR_URL>.onrender.com/chat` - Xem lịch sử phân tích của AI và trạng thái xác nhận.

### 🔌 API Tiếp nhận cảnh báo (Dùng cho ESP32)
*   `https://<YOUR_URL>.onrender.com/api/cry` - Endpoint nhận dữ liệu tiếng khóc và hình ảnh từ phần cứng.

### 📜 API Lấy Log (Cho AJAX Dashboard)
*   `https://<YOUR_URL>.onrender.com/api/logs` - Trả về dữ liệu JSON của toàn bộ nhật ký hệ thống.

---

## 🛠 Hướng dẫn gỡ lỗi nhanh
*   **Nếu Bot không trả lời:** Chạy lại URL ở mục 1 trong trình duyệt.
*   **Nếu Dashboard không hiện gì:** Kiểm tra xem trang có báo `OPERATIONAL` không.
*   **Nếu AI không phân tích:** Kiểm tra xem `GROQ_API_KEY` đã được điền đủ trong phần Environment trên Render chưa.
