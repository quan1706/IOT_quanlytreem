# 👶 Baby Cry Detector & Smart Soother (Server & Chatbot)

Dự án này là phần Backend (Spring Boot Server) và Bot (Telegram Chatbot) cho hệ thống IoT phát hiện trẻ khóc và điều hành các thiết bị hỗ trợ tự động (phát nhạc ru, bật chế độ ru trang/võng). Mạch thiết bị đầu cuối (ESP32-CAM và cảm biến/AI) sẽ đóng vai trò trigger sự kiện báo động, gửi dữ liệu cho hệ thống Backend này xử lý.

## 🗂️ Kiến trúc & Luồng thực thi (Giai đoạn 2)

Hệ thống tập trung vào việc nhận tín hiệu báo động từ thiết bị phần cứng, cấp báo cho người dùng qua Telegram và phản hồi lệnh điều khiển lại cho thiết bị vật lý dựa trên quyết định của người dùng.

### Sơ đồ Luồng hoạt động:

1. **[ESP32] -> [Server]**: Khi AI ESP32 xác nhận tiếng khóc diễn ra trong 6 giây:
   - ESP32 gọi HTTP GET đến ESP32-CAM để nhận ảnh JPEG.
   - ESP32 gọi HTTP POST đến Server Spring Boot tại endpoint `/cry` chứa hình ảnh chụp (multipart/form-data).
2. **[Server] -> [Telegram Bot]**: 
   - Server nhận ảnh và lập tức qua Telegram API gửi tin nhắn tới Telegram người dùng (chat_id đã cấu hình).
   - Nội dung bao gồm Ảnh + Cảnh báo: *"⚠️ Trẻ đang khóc! Chọn hành động:"*
   - Kèm theo 3 phím bấm (Inline Keyboard):
     - 🎵 Phát nhạc
     - 🔄 Ru võng
     - ⏹ Dừng
3. **[Người dùng] -> [Telegram Bot] -> [Server]**: Người dùng chọn một hành động bằng cách nhấn phím trên ứng dụng Telegram. Telegram gửi Callback Query (Webhook / Long Polling) về Server.
4. **[Server] -> [ESP32]**: 
   - Server phân tích Callback Query, ánh xạ thành lệnh.
   - Server thao tác gọi HTTP POST `/command` về lại địa chỉ IP nhận lệnh của ESP32 với body dạng JSON tương ứng với lệnh vừa nhận.
5. **[ESP32] thực thi**:
   - Nhận "phat_nhac" → Kích hoạt loa phát nhạc ru.
   - Nhận "ru_vong" → Kích hoạt servo quay/chế độ rung.
   - Nhận "dung" → Cắt loa + Tắt servo.

---

## 💻 Chi tiết các thành phần

### 1. Java Server (Spring Boot)
Đóng vai trò trung tâm điều phối (Backend Hub), thực hiện các tác vụ chính:
- **API Nhận Dữ Liệu (`POST /api/cry`)**: Tiếp nhận yêu cầu multipart file từ ESP32 khi có cảnh báo. Cầm lưu ảnh trên memory hoặc pass qua byte array format để forward thẳng lên Telegram.
- **Tích hợp Telegram API**: Sử dụng thư viện `TelegramBots` (hoặc HTTP REST Call trực tiếp đến `api.telegram.org`) để gọi phương thức `sendPhoto` với `reply_markup` chứa các nút `InlineKeyboardButton`.
- **Xử lý Callback (Telegram)**: Lắng nghe và xử lý sự kiện Callback Update từ Telegram khi người dùng nhấn nút, từ đó biết được hành động nào được chọn (vd: `action_play_music`).
- **REST Client điều khiển thiết bị**: Sử dụng `RestTemplate` hoặc `WebClient` thực hiện POST request để đẩy lệnh trực tiếp đến Node ESP32 có mở lắng nghe HTTP tại mạng nội bộ.

### 2. Telegram Bot
Đóng vai trò là Giao diện (UI/UX) chính để giao tiếp với phụ huynh/người giám sát.
- Cần tạo 1 con bot thông qua [@BotFather](https://t.me/BotFather) để lấy **Bot Token**.
- Tương tác với người dùng ở trạng thái thời gian thực theo cấu trúc: Hình ảnh gửi tức thời kèm Inline Menu Buttons trực quan.

### 3. ESP32 (Phần Lắng nghe lệnh)
- Server Spring Boot sẽ đóng vai trò là Client, gửi tín hiệu sang API được ESP32 mở sẵn.
- **Endpoint ESP32 lắng nghe**: `POST /command`
- **Payload**: `{"cmd": "<tên-lệnh>"}` (Ví dụ: `{"cmd": "phat_nhac"}`)

---

## 📡 API Contract (Đặc tả Giao thức giao tiếp)

### 1. ESP32 -> Server (Báo khóc & Gửi ảnh)
- **Method**: `POST`
- **Path**: `/api/cry` (Tại Server)
- **MIME Type**: `multipart/form-data`
- **Body**: 
  - `image`: Dữ liệu ảnh dạng byte/file `.jpeg`

### 2. Server -> ESP32 (Gửi lệnh điều khiển)
- **Method**: `POST`
- **Path**: `http://<IP-CỦA-ESP32>/command` (API của thiết bị ESP)
- **Content-Type**: `application/json`
- **Body Example**:
  ```json
  {
    "cmd": "phat_nhac" 
  }
  ```
- **Các Command map có thể có**: `"phat_nhac"`, `"ru_vong"`, `"dung"`.

### 3. Telegram Callback Payload mapping
Server tiếp nhận Callback Data (Nội dung ẩn dưới mỗi nút bấm Telegram) và map ánh xạ sang `cmd`:
- Callback Data `ACTION_PLAY_MUSIC` -> ESP command `{"cmd": "phat_nhac"}`
- Callback Data `ACTION_SWING` -> ESP command `{"cmd": "ru_vong"}`
- Callback Data `ACTION_STOP` -> ESP command `{"cmd": "dung"}`

---

## 🚀 Các bước Kế hoạch Triển khai Backend (Next Steps)

1. **Khởi tạo Dư án Spring Boot**: 
   - Quét từ Spring Initializr (`spring-boot-starter-web`, `lombok`).
   - Cài đặt dependency để kết nối Telegram: `telegrambots-spring-boot-starter` (của rubenlagus).
   - Cấu hình file `application.yml` hoặc `.properties` bổ sung `bot.token` và `bot.username`.
2. **Xây dựng Telegram Bot Service Layer**:
   - Kế thừa lớp `TelegramLongPollingBot` (Nếu dùng Long Polling) hoặc viết RestController riêng (Nếu dùng Webhook).
   - Thiết kế hàm tạo Custom Message kèm *InlineKeyboardButton*.
   - Đón hàm `onUpdateReceived` để bắt CallbackQuery khi nút được nhấn.
3. **Xây dựng API Controller Nhận thông tin (`/api/cry`)**:
   - Viết controller dùng annotation `@PostMapping("/api/cry")` đón `@RequestParam("image") MultipartFile image`.
   - Inject Bot Service vào để gửi ảnh sang Telegram ngay khi nhận được request hợp lệ.
4. **Tích hợp HTTP Client gửi lệnh tới ESP32**:
   - Tại vị trí xử lý `onUpdateReceived` sinh ra hàm gọi `RestTemplate.postForObject()` báo hiệu lệnh về địa chỉ IP của module ESP32.
   - *Lưu ý kiến trúc: Để việc gọi HTTP POST tới IP ESP32 trong mạng LAN trơn tru từ 1 server có thể được host trên cloud Internet, IP ESP32 này thường sẽ phải NAT Port hoặc cấu hình IP tĩnh mạng nội bộ. Hoặc hệ thống nên cân nhắc bổ sung giao thức MQTT Pub/Sub làm Middleware nếu không muốn ESP32 mở cổng HTTP trực tiếp.*
