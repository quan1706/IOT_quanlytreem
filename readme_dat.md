# LỊCH SỬ CÁC CHỨC NĂNG ĐÃ THỰC HIỆN HÔM NAY - 11/03/2026

Hệ thống **Smart Baby Care** đã được nâng cấp mạnh mẽ về khả năng cảnh báo, đồng bộ dữ liệu và điều khiển qua AI/Telegram.

### 1. Tái cấu trúc Hệ thống (Refactoring)
- **Loại bỏ package redundant**: Xóa bỏ package `baby_care` (handler.py, messenger.py) để tinh gọn kiến trúc.
- **Tích hợp trực tiếp**: Chuyển logic xử lý `/api/cry` trực tiếp vào `http_server.py`, gọi thẳng `TelegramNotifier`.

### 2. Hệ thống Cảnh báo Bé khóc (Cry Alert System)
- **Hỗ trợ Nguồn kép (Dual-Source)**:
    - **ESP32 Mic (WebSocket)**: Bóc tách JSON `{event: "cry_detected", rms_level, device_id, timestamp}`.
    - **ESP32-CAM (HTTP POST)**: Tiếp nhận ảnh thực tế từ camera tại `/api/cry`.
- **Thông báo Telegram Rich**:
    - **Caption chi tiết**: Hiển thị Device ID, mức âm thanh (RMS), thời gian thực.
    - **Action Buttons**: Tích hợp các nút điều khiển nhanh: *Ru võng, Phát nhạc, Chụp ảnh mới, Dừng tất cả*.
    - **Chống Spam**: Giới hạn thông báo tối thiểu mỗi 15 giây.

### 3. Quản lý Hành động (Standardized Actions)
- **Enum `BabyCareAction`**: Tạo file `core/serverToClients/baby_actions.py` để quản lý tập trung các hành động dỗ bé.
- **Đồng bộ AI**: Cập nhật `AIProcessor` để tự động lấy danh sách hành động từ Enum này vào prompt, giúp AI gợi ý chính xác và linh hoạt.

### 4. Ghi log & Giám sát (Logging & Monitoring)
- **Dashboard Integration**: Mọi sự kiện khóc được log vào mục "Lịch sử Khóc" và "System Log" trên trình duyệt.
- **Server Console**: Ghi log rõ ràng định dạng `[CRY-ALERT]` và `[CRY-CAM]` để dễ dàng debug.

### 5. Công cụ Giả lập (Testing Tools)
- **`full_simulator.py`**: Script mới giả lập đồng thời cả 2 thiết bị (Mic & Cam), hỗ trợ gửi metadata và ảnh placeholder.
- **`test_telegram.bat`**: Cập nhật file batch tiện ích để người dùng dễ dàng chạy test chỉ với 1 cú click (hỗ trợ kéo thả ảnh).
