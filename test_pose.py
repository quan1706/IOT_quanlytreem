import requests
import sys

def test_pose(image_path):
    url = "http://localhost:8003/api/vision/pose"
    print(f"Testing with image: {image_path}")
    
    try:
        with open(image_path, 'rb') as f:
            files = {'image': (image_path, f, 'image/jpeg')}
            response = requests.post(url, files=files)
            
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        print(response.json())
    except requests.exceptions.ConnectionError:
        print("Lỗi: Không thể kết nối tới server. Vui lòng đảm bảo server đang chạy (python app.py) ở port 8003.")
    except Exception as e:
        print(f"Lỗi: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Hãy chạy script kèm đường dẫn ảnh. VD: python test_pose.py C:\\path\\to\\baby_prone.png")
    else:
        test_pose(sys.argv[1])
