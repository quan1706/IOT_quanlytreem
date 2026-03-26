# PLAN: Baby Pose Check — Tích hợp Gemini AI vào luồng kiểm tra tư thế trẻ

## Bối cảnh & Vấn đề hiện tại

Hệ thống hiện có 2 bên logic liên quan đến chụp ảnh & phân tích tư thế, nhưng chúng **CHƯA NỐI VỚI NHAU**.

### Bên 1: Logic Upload ảnh (ESP32-CAM → Server)

ESP32-CAM firmware (`baby_care_stream_cam.ino`) xử lý cả `capture_hq` và `capture_pose` **giống hệt nhau**:
- Cả 2 lệnh đều set `trigger_hq_capture = true` (L69-70)
- Cả 2 đều gọi `handleHQCapture()` → POST ảnh lên **`/api/vision/hq_capture`** (L218)
- ESP32-CAM **KHÔNG BAO GIỜ** gọi `/api/vision/pose`

**Có 3 luồng kích hoạt chụp ảnh:**

| # | Trigger | Lệnh gửi ESP32 | ESP32 upload lên | Server handler |
|---|---------|-----------------|-------------------|----------------|
| A | Telegram `/check_baby_pose` | `capture_pose` | `/api/vision/hq_capture` | `_handle_hq_capture` |
| B | Periodic (5 phút/lần) | `capture_hq` | `/api/vision/hq_capture` | `_handle_hq_capture` |
| C | Baby cry alert | N/A (ESP tự gửi) | `/api/cry` | `_handle_cry` |

### Bên 2: Logic Phân tích ảnh bằng Gemini (PoseHandler)

`pose_handler.py` đã implement đầy đủ logic Gemini AI:
- Nhận ảnh từ `/api/vision/pose` (endpoint **không bao giờ được gọi** bởi ESP32!)
- Gọi Gemini API → phân tích PRONE/SUPINE
- Nếu PRONE → gửi cảnh báo Telegram (qua `_telegram_alerts`)
- Nếu SUPINE → chỉ log, **không cập nhật** `DASHBOARD_STATE`

### Kết quả: 2 bên hoàn toàn rời rạc

> [!CAUTION]
> - `_handle_hq_capture` chỉ lưu ảnh + gửi Telegram, **KHÔNG gọi Gemini phân tích**.
> - `_periodic_pose_check` gửi `capture_hq` chứ không phải `capture_pose` → ảnh về `hq_capture` → không phân tích.
> - `DASHBOARD_STATE["pose"]` luôn là `"UNKNOWN"` vì `DashboardUpdater.update_pose()` chưa bao giờ được gọi.
> - Telegram `/status` hiển thị `baby_posture="Nằm ngửa ✅"` **hardcoded** (router.py L367).

---

## Proposed Changes

### Phase 1: Nối logic Gemini AI vào luồng HQ Capture

#### [MODIFY] [http_server.py](file:///d:/CODE/GITCLONE/IOT_quanlytreem/server/core/http_server.py)

Trong `_handle_hq_capture()` (sau khi lưu ảnh thành công, trước khi gửi Telegram):
- Gọi `self.pose_handler._analyze_image_sync(image_bytes)` qua `run_in_executor`
- Xác định kết quả `PRONE` hay `SUPINE`
- Gọi `DashboardUpdater.update_pose(result)`
- Nếu `PRONE` → gửi caption cảnh báo nguy hiểm (thay vì caption chụp ảnh thông thường)
- Nếu `SUPINE` → gửi caption an toàn kèm kết quả AI

#### [MODIFY] [pose_handler.py](file:///d:/CODE/GITCLONE/IOT_quanlytreem/server/core/api/pose_handler.py)

Trong `handle_post()`:
- Thêm `DashboardUpdater.update_pose("PRONE" if is_prone else "SUPINE")` sau khi phân tích xong
- Đảm bảo endpoint vẫn hoạt động nếu bên ngoài gọi trực tiếp (ví dụ `test_pose.py`)

### Phase 2: Hiển thị tư thế động trên Status

#### [MODIFY] [router.py](file:///d:/CODE/GITCLONE/IOT_quanlytreem/server/core/telegram/router.py)

Trong `_cmd_status()` (L355-375):
- Thay `baby_posture="Nằm ngửa ✅"` bằng lookup từ `state.get("pose", "UNKNOWN")`
- Mapping: `PRONE` → `"Nằm sấp ⚠️"`, `SUPINE` → `"Nằm ngửa ✅"`, `UNKNOWN` → `"Chưa xác định ❓"`

---

## Verification Plan

### Test Script (Có sẵn)
- File: `test_pose.py` — test endpoint `/api/vision/pose` bằng cách POST ảnh trực tiếp
- **Chạy:** `python test_pose.py path/to/baby_photo.jpg`
- Xác nhận response chứa `"pose": "PRONE"` hoặc `"SUPINE"`

### Manual Verification (Cần user test)
1. Khởi động server (`python app.py`)
2. Gửi `/check_baby_pose` trên Telegram
3. Kiểm tra xem Telegram có nhận được ảnh kèm caption phân tích AI (PRONE hoặc SUPINE) hay không
4. Gửi `/status` trên Telegram → xác nhận trường "Tư thế bé" hiện kết quả thật thay vì giá trị cố định
5. Mở Dashboard web → xác nhận `pose` field trong `/api/dashboard/sensors` trả về giá trị đúng

> [!IMPORTANT]
> Test tự động chỉ cover được endpoint `/api/vision/pose`. Luồng chính qua `/api/vision/hq_capture` cần ESP32-CAM thật hoặc curl giả lập.

---

## Summary

Khối lượng thay đổi nhỏ — chỉ sửa 3 file Python, không thay đổi firmware ESP32-CAM.
