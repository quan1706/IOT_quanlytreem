# NHỮNG Hạng Mục Cần Làm & Lưu Ý (Dành cho Đạt)

Danh sách các tính năng dự kiến triển khai tiếp theo và các điểm cần tối ưu.

### 1. Cảnh báo Trạng thái Kết nối (Hardware Offline Alert) 🚨
- **Vấn đề**: Khi người dùng chat với bot hoặc nhấn nút dỗ bé mà ESP32 chưa cắm điện hoặc mất mạng, server vẫn nhận lệnh nhưng thiết bị không thực thi được.
- **Giải pháp**: 
    - Kiểm tra `len(ESP32Commander().connections)`.
    - Nếu `= 0`, gửi ngay tin nhắn Telegram: *"⚠️ Cảnh báo: Thiết bị ESP32 hiện đang ngoại tuyến (Offline). Vui lòng kiểm tra kết nối phần cứng trước khi thực hiện lệnh!"*
    - Áp dụng cho cả: Phản hồi AI và Callback Button.

### 2. Tự động hóa dỗ bé (Auto-Care Logic) 🤖
- **Nâng cấp**: Khi bé khóc, nếu hệ thống ở `mode: auto`, AI sẽ tự động chọn hành động phù hợp (ví dụ: phát nhạc trước) mà không đợi người dùng nhấn nút.
- **AI Context**: Gửi thêm tình trạng bé (ví dụ: khóc to/nhỏ qua RMS) để AI quyết định hành động.

### 3. Cải thiện ESP32-CAM 📸
- **Tốc độ**: Giảm kích thước ảnh hoặc tăng baudrate để ảnh gửi về Telegram nhanh hơn.
- **Ổn định**: Xử lý trường hợp ảnh bị lỗi/corrupted khi gửi qua HTTP.

### 4. Thông tin Cảm biến (Environment Data) 🌡️
- **Tích hợp**: Đưa dữ liệu Nhiệt độ/Độ ẩm vào message cảnh báo bé khóc để người dùng biết bé khóc có phải do nóng/lạnh không.

### 5. Quản lý API Key 🔑
- Cần một cơ chế rotate key hoặc báo lỗi khi Groq API hết hạn mức (limit).
