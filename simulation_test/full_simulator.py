"""
simulation_test/full_simulator.py
==================================
Giả lập đầy đủ cả 2 thiết bị ESP32 khi bé khóc:

  1. ESP32 Mic (INMP441)  → WebSocket JSON  → ws://localhost:8000/xiaozhi/v1/
     Gửi: hello handshake → rồi gửi baby_event cry_detected

  2. ESP32-CAM            → HTTP POST multipart → http://localhost:8003/api/cry
     Gửi: ảnh + metadata (device_id, rms_level, timestamp)

Chạy:
  python simulation_test/full_simulator.py
  python simulation_test/full_simulator.py <đường_dẫn_ảnh>   # chỉ test CAM
  python simulation_test/full_simulator.py --ws-only          # chỉ test WebSocket
  python simulation_test/full_simulator.py --cam-only <ảnh>   # chỉ test CAM
"""

import asyncio
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request

# Fix Unicode output trên Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ─── Cấu hình ────────────────────────────────────────────────────────────────
WS_HOST    = "localhost"
WS_PORT    = 8000
WS_PATH    = "/xiaozhi/v1/"
HTTP_URL   = f"http://localhost:8003/api/cry"

DEVICE_ID_MIC = "baby-care-esp32-001"   # ID giống firmware thật
DEVICE_ID_CAM = "baby-care-cam-001"
CLIENT_ID     = "baby-care-client"
RMS_LEVEL     = 523                     # > ngưỡng 200 trong firmware

# Ảnh mặc định nếu không truyền tham số (ảnh placeholder 1x1 pixel JPEG)
_PLACEHOLDER_JPEG = bytes([
    0xff,0xd8,0xff,0xe0,0x00,0x10,0x4a,0x46,0x49,0x46,0x00,0x01,0x01,0x00,0x00,0x01,
    0x00,0x01,0x00,0x00,0xff,0xdb,0x00,0x43,0x00,0x08,0x06,0x06,0x07,0x06,0x05,0x08,
    0x07,0x07,0x07,0x09,0x09,0x08,0x0a,0x0c,0x14,0x0d,0x0c,0x0b,0x0b,0x0c,0x19,0x12,
    0x13,0x0f,0x14,0x1d,0x1a,0x1f,0x1e,0x1d,0x1a,0x1c,0x1c,0x20,0x24,0x2e,0x27,0x20,
    0x22,0x2c,0x23,0x1c,0x1c,0x28,0x37,0x29,0x2c,0x30,0x31,0x34,0x34,0x34,0x1f,0x27,
    0x39,0x3d,0x38,0x32,0x3c,0x2e,0x33,0x34,0x32,0xff,0xc0,0x00,0x0b,0x08,0x00,0x01,
    0x00,0x01,0x01,0x01,0x11,0x00,0xff,0xc4,0x00,0x1f,0x00,0x00,0x01,0x05,0x01,0x01,
    0x01,0x01,0x01,0x01,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x01,0x02,0x03,0x04,
    0x05,0x06,0x07,0x08,0x09,0x0a,0x0b,0xff,0xc4,0x00,0xb5,0x10,0x00,0x02,0x01,0x03,
    0x03,0x02,0x04,0x03,0x05,0x05,0x04,0x04,0x00,0x00,0x01,0x7d,0x01,0x02,0x03,0x00,
    0x04,0x11,0x05,0x12,0x21,0x31,0x41,0x06,0x13,0x51,0x61,0x07,0x22,0x71,0x14,0x32,
    0x81,0x91,0xa1,0x08,0x23,0x42,0xb1,0xc1,0x15,0x52,0xd1,0xf0,0x24,0x33,0x62,0x72,
    0x82,0x09,0x0a,0x16,0x17,0x18,0x19,0x1a,0x25,0x26,0x27,0x28,0x29,0x2a,0x34,0x35,
    0x36,0x37,0x38,0x39,0x3a,0x43,0x44,0x45,0x46,0x47,0x48,0x49,0x4a,0x53,0x54,0x55,
    0x56,0x57,0x58,0x59,0x5a,0x63,0x64,0x65,0x66,0x67,0x68,0x69,0x6a,0x73,0x74,0x75,
    0x76,0x77,0x78,0x79,0x7a,0x83,0x84,0x85,0x86,0x87,0x88,0x89,0x8a,0x92,0x93,0x94,
    0x95,0x96,0x97,0x98,0x99,0x9a,0xa2,0xa3,0xa4,0xa5,0xa6,0xa7,0xa8,0xa9,0xaa,0xb2,
    0xb3,0xb4,0xb5,0xb6,0xb7,0xb8,0xb9,0xba,0xc2,0xc3,0xc4,0xc5,0xc6,0xc7,0xc8,0xc9,
    0xca,0xd2,0xd3,0xd4,0xd5,0xd6,0xd7,0xd8,0xd9,0xda,0xe1,0xe2,0xe3,0xe4,0xe5,0xe6,
    0xe7,0xe8,0xe9,0xea,0xf1,0xf2,0xf3,0xf4,0xf5,0xf6,0xf7,0xf8,0xf9,0xfa,0xff,0xda,
    0x00,0x08,0x01,0x01,0x00,0x00,0x3f,0x00,0xfb,0x00,0x00,0x1f,0xff,0xd9,
])

# ═════════════════════════════════════════════════════════════════════════════
#  1. GIẢ LẬP ESP32 MIC  →  WebSocket JSON
# ═════════════════════════════════════════════════════════════════════════════
async def simulate_esp32_mic():
    """
    Giả lập ESP32 mic gửi WebSocket JSON về server.
    Luồng: hello → baby_event cry_detected
    """
    try:
        import websockets
    except ImportError:
        print("❌ Thiếu thư viện 'websockets'. Cài bằng: pip install websockets")
        return False

    ws_url = f"ws://{WS_HOST}:{WS_PORT}{WS_PATH}?device-id={DEVICE_ID_MIC}&client-id={CLIENT_ID}"
    print(f"\n{'='*55}")
    print("📡 [ESP32 MIC] Giả lập kết nối WebSocket...")
    print(f"   URL: {ws_url}")

    try:
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            print("✅ [ESP32 MIC] Đã kết nối WebSocket!")

            # ── Bước 1: Gửi hello (handshake) ──────────────────────────
            hello = {
                "type": "hello",
                "version": 1,
                "transport": "websocket",
                "audio_params": {
                    "format": "pcm",
                    "sample_rate": 16000,
                    "channels": 1,
                    "frame_duration": 60,
                },
                "features": {
                    "baby_care": True,
                    "cry_detect": True,
                    "temp_sensor": True,
                },
            }
            await ws.send(json.dumps(hello))
            print("📤 [ESP32 MIC] Gửi hello handshake")

            # Chờ phản hồi hello từ server
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(resp)
                if data.get("type") == "hello":
                    print(f"📥 [ESP32 MIC] Server chấp nhận: {data}")
                else:
                    print(f"📥 [ESP32 MIC] Nhận: {resp[:80]}")
            except asyncio.TimeoutError:
                print("⚠️  [ESP32 MIC] Timeout chờ hello từ server, tiếp tục...")

            # ── Bước 2: Gửi baby_event cry_detected ────────────────────
            await asyncio.sleep(1)
            cry_event = {
                "type": "baby_event",
                "event": "cry_detected",
                "rms_level": RMS_LEVEL,
                "timestamp": int(time.time() * 1000),
                "device_id": DEVICE_ID_MIC,
            }
            await ws.send(json.dumps(cry_event))
            print(f"🚨 [ESP32 MIC] Gửi cry_detected | rms={RMS_LEVEL} | device={DEVICE_ID_MIC}")
            print("✅ [ESP32 MIC] Hoàn thành. Server sẽ log + gửi Telegram text alert.")

            # Giữ kết nối 2s để server xử lý
            await asyncio.sleep(2)
            return True

    except ConnectionRefusedError:
        print(f"❌ [ESP32 MIC] Không thể kết nối WebSocket ws://{WS_HOST}:{WS_PORT}")
        print("   → Hãy đảm bảo server Python đang chạy (run_server.bat)")
        return False
    except Exception as e:
        print(f"❌ [ESP32 MIC] Lỗi WebSocket: {e}")
        return False


# ═════════════════════════════════════════════════════════════════════════════
#  2. GIẢ LẬP ESP32-CAM  →  HTTP POST multipart/form-data
# ═════════════════════════════════════════════════════════════════════════════
def simulate_esp32_cam(image_path: str = None):
    """
    Giả lập ESP32-CAM gửi ảnh + metadata về server qua HTTP POST /api/cry.
    """
    print(f"\n{'='*55}")
    print("📸 [ESP32-CAM] Giả lập gửi ảnh HTTP POST...")
    print(f"   URL: {HTTP_URL}")

    # Đọc ảnh hoặc dùng placeholder
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        filename  = os.path.basename(image_path)
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        print(f"   Ảnh: {image_path}")
    else:
        image_bytes = _PLACEHOLDER_JPEG
        filename    = "baby_cry_sim.jpg"
        mime_type   = "image/jpeg"
        print("   Ảnh: [placeholder 1x1 JPEG - không truyền ảnh thật]")

    print(f"   device_id = {DEVICE_ID_CAM} | rms = {RMS_LEVEL}")

    # Xây dựng multipart/form-data
    boundary = "----ESP32CAMSimBoundary" + os.urandom(8).hex()
    parts = []

    def add_text(name, value):
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode("utf-8")
        )

    add_text("device_id", DEVICE_ID_CAM)
    add_text("rms_level", str(RMS_LEVEL))
    add_text("timestamp", str(int(time.time() * 1000)))

    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8")
    )
    parts.append(image_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(parts)
    req  = urllib.request.Request(HTTP_URL, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(body)))

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            if result.get("success"):
                print("✅ [ESP32-CAM] Server nhận thành công!")
                print("   → Kiểm tra Dashboard (http://localhost:8003/) và Telegram.")
                return True
            else:
                print(f"❌ [ESP32-CAM] Server phản hồi lỗi: {result}")
    except urllib.error.URLError as e:
        print(f"❌ [ESP32-CAM] Không thể kết nối HTTP: {e.reason}")
        print("   → Hãy đảm bảo server Python đang chạy (run_server.bat)")
    except Exception as e:
        print(f"❌ [ESP32-CAM] Lỗi: {e}")
    return False


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════
async def main():
    args = sys.argv[1:]
    ws_only  = "--ws-only"  in args
    cam_only = "--cam-only" in args

    # Lấy đường dẫn ảnh (nếu có)
    image_path = None
    for a in args:
        if a not in ("--ws-only", "--cam-only") and not a.startswith("--"):
            image_path = a.strip('"').strip("'")
            break

    print("╔══════════════════════════════════════════════════════╗")
    print("║   🍼  SMART BABY CARE FULL SIMULATOR                 ║")
    print("║   Giả lập ESP32 Mic (WebSocket) + ESP32-CAM (HTTP)   ║")
    print("╚══════════════════════════════════════════════════════╝")

    if ws_only:
        # Chỉ test WebSocket
        await simulate_esp32_mic()
    elif cam_only:
        # Chỉ test HTTP
        simulate_esp32_cam(image_path)
    else:
        # Test cả 2 — ESP32 mic trước, sau đó ESP32-CAM 2 giây sau
        print("\n🔀 Chạy đồng thời cả 2 thiết bị (độ trễ 2s giữa mic và cam)")

        mic_task = asyncio.create_task(simulate_esp32_mic())
        await asyncio.sleep(2)          # Mic gửi trước, CAM gửi sau 2s để mô phỏng thực tế
        simulate_esp32_cam(image_path)
        await mic_task

    print(f"\n{'='*55}")
    print("🏁 Giả lập hoàn tất.")
    print()
    print("📋 Kiểm tra:")
    print("  • Server console   : log [CRY-ALERT] và [CRY-CAM]")
    print(f"  • Dashboard        : http://localhost:8003/  → tab 😢 và 📋")
    print("  • Telegram         : nhận text alert + ảnh + nút hành động")


if __name__ == "__main__":
    asyncio.run(main())
