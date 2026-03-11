import json
import os
import sys
import time
import mimetypes
import urllib.request
import urllib.error

# Thông tin Server Python cục bộ
LOCAL_SERVER_URL = "http://localhost:8003/api/cry"

class BabySimulator:
    def __init__(self, server_url=LOCAL_SERVER_URL):
        self.server_url = server_url

    def send_cry_alert(self, image_path, device_id="ESP32-CAM-SIM", rms_level=450):
        """
        Giả lập ESP32-CAM gửi ảnh + metadata tới Server Python.
        Gửi multipart/form-data với các field:
          - image      : file ảnh
          - device_id  : ID thiết bị
          - rms_level  : mức âm lượng phát hiện
          - timestamp  : thời điểm phát hiện (ms)
        """
        if not os.path.exists(image_path):
            print(f"❌ Lỗi: Không tìm thấy file ảnh tại: {image_path}")
            return False

        print(f"🚀 Đang gửi dữ liệu tới Server Python: {self.server_url}")
        print(f"   device_id  = {device_id}")
        print(f"   rms_level  = {rms_level}")

        boundary = '----SimulatorBoundary' + os.urandom(16).hex()
        parts = []

        def add_field(name, value):
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode('utf-8')
            )

        # Thêm metadata text fields
        add_field('device_id', device_id)
        add_field('rms_level', str(rms_level))
        add_field('timestamp', str(int(time.time() * 1000)))

        # Thêm file ảnh
        filename  = os.path.basename(image_path)
        mime_type = mimetypes.guess_type(image_path)[0] or 'image/jpeg'
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f'Content-Type: {mime_type}\r\n\r\n'.encode('utf-8')
        )
        with open(image_path, 'rb') as f:
            parts.append(f.read())
        parts.append(f'\r\n--{boundary}--\r\n'.encode('utf-8'))

        body = b''.join(parts)

        req = urllib.request.Request(self.server_url, data=body)
        req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
        req.add_header('Content-Length', len(body))

        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                if result.get("success"):
                    print("✅ GỬI TỚI SERVER THÀNH CÔNG!")
                    print("👉 Kiểm tra log server, Dashboard (Port 8003) và Telegram.")
                    return True
                else:
                    print(f"❌ Lỗi từ Server: {result}")
        except urllib.error.URLError as e:
            print(f"❌ Lỗi kết nối Server: {e.reason}")
            print("💡 Hãy đảm bảo đã chạy Server Python (run_server.bat) trước.")
        except Exception as e:
            print(f"❌ Lỗi: {e}")
        return False


def run_standalone():
    simulator = BabySimulator()
    print("--- SMART BABY CARE SIMULATOR (V4 - With Metadata) ---")
    print("------------------------------------------------------")

    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        print("💡 TIP: Bạn có thể kéo thả 1 file ảnh vào cửa sổ này.")
        path = input("Đường dẫn ảnh: ").strip().strip('"')

    if path and os.path.exists(path):
        simulator.send_cry_alert(path)
    else:
        print(f"❌ Đường dẫn không hợp lệ hoặc không có ảnh: {path}")


if __name__ == "__main__":
    run_standalone()

