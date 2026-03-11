import cv2
import mediapipe as mp
import numpy as np
import time
import os
from collections import deque
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ==========================================
# CẤU HÌNH (CONFIG)
# ==========================================
# Thay bằng IP ESP32-CAM của bạn: "http://192.168.1.100:81/stream"
# Để số 0 để dùng Webcam máy tính test trước
CAMERA_SOURCE = 0 

# Đường dẫn file Model (Đã tải sẵn cho bạn)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FACE_MODEL_PATH = os.path.join(BASE_DIR, 'face_landmarker.task')
POSE_MODEL_PATH = os.path.join(BASE_DIR, 'pose_landmarker.task')

# Chỉ số các bộ phận để tính toán đắp chăn (Pose Landmarks)
# 23, 24: Hông | 25, 26: Đầu gối | 27, 28: Cổ chân
LOWER_BODY_INDICES = [23, 24, 25, 26, 27, 28]

# ==========================================
# KHỞI TẠO AI (SETUP AI)
# ==========================================
# 1. Setup Face Detection
face_base_options = python.BaseOptions(model_asset_path=FACE_MODEL_PATH)
face_options = vision.FaceLandmarkerOptions(
    base_options=face_base_options,
    num_faces=1,
    running_mode=vision.RunningMode.IMAGE
)
face_detector = vision.FaceLandmarker.create_from_options(face_options)

# 2. Setup Pose Detection (Để nhận diện tứ chi)
pose_base_options = python.BaseOptions(model_asset_path=POSE_MODEL_PATH)
pose_options = vision.PoseLandmarkerOptions(
    base_options=pose_base_options,
    running_mode=vision.RunningMode.IMAGE
)
pose_detector = vision.PoseLandmarker.create_from_options(pose_options)

# Landmarks cho mắt (MediaPipe V3 Task indices)
LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
EAR_THRESH = 0.2
SLEEP_FRAME_THRESH = 10
CLOSED_FRAMES = 0

def calculate_ear(landmarks, eye_indices):
    try:
        p = [np.array([landmarks[i].x, landmarks[i].y]) for i in eye_indices]
        # vertical distances
        v1 = np.linalg.norm(p[1] - p[5])
        v2 = np.linalg.norm(p[2] - p[4])
        # horizontal distance
        h = np.linalg.norm(p[0] - p[3])
        return (v1 + v2) / (2.0 * h)
    except:
        return 1.0

def run_demo():
    global CLOSED_FRAMES
    cap = cv2.VideoCapture(CAMERA_SOURCE)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    fps_buffer = deque(maxlen=30)
    print("--- Đang khởi động AI Giám sát Bé ---")
    print("Nhấn 'q' để thoát.")

    while cap.isOpened():
        start_time = time.time()
        ret, frame = cap.read()
        if not ret:
            print("Không nhận được luồng video!")
            break

        # Chuyển đổi màu cho MediaPipe (BGR -> RGB)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # CHẠY AI QUÉT ẢNH
        face_result = face_detector.detect(mp_image)
        pose_result = pose_detector.detect(mp_image)

        # 1. LOGIC NHẬN DIỆN NẰM SẤP / NGỬA / NGỦ
        status = "No baby"
        color = (255, 255, 255) # White

        is_face_visible = len(face_result.face_landmarks) > 0
        is_body_visible = len(pose_result.pose_landmarks) > 0

        if is_face_visible:
            face_landmarks = face_result.face_landmarks[0]
            
            # Tính EAR để biết ngủ hay thức
            left_ear = calculate_ear(face_landmarks, LEFT_EYE_INDICES)
            right_ear = calculate_ear(face_landmarks, RIGHT_EYE_INDICES)
            avg_ear = (left_ear + right_ear) / 2.0
            
            # Hiển thị EAR lên màn hình để dễ căn chỉnh
            cv2.putText(frame, f"EAR: {avg_ear:.2f}", (300, 100), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

            # NGƯỠNG EAR (Nếu mắt nhắm, EAR sẽ nhỏ hơn 0.22 - 0.25)
            # Bạn có thể điều chỉnh 0.25 thành 0.28 nếu đeo kính
            IF_EYE_CLOSED = avg_ear < 0.25
            
            if IF_EYE_CLOSED:
                CLOSED_FRAMES += 1
            else:
                CLOSED_FRAMES = 0
            
            if CLOSED_FRAMES >= 5: # Giảm xuống 5 khung hình cho nhạy hơn
                status = "Sleeping (Dang Ngu)"
                color = (255, 255, 0) # Cyan
            else:
                status = "Awake (Nam Ngua - Safe)"
                color = (0, 255, 0) # Green
                
        elif is_body_visible:
            status = "ALERT: Prone (Nam Sap)"
            color = (0, 0, 255) # Red
            
        # 2. LOGIC TÍNH % ĐẮP CHĂN / CHE KHUẤT
        blanket_pct = 0
        if is_body_visible:
            landmarks = pose_result.pose_landmarks[0]
            # Đếm xem có bao nhiêu điểm chi dưới bị mờ/che khuất (visibility thấp)
            hidden_points = 0
            for idx in LOWER_BODY_INDICES:
                if landmarks[idx].visibility < 0.5:
                    hidden_points += 1
            
            blanket_pct = int((hidden_points / len(LOWER_BODY_INDICES)) * 100)

        # 3. HIỂN THỊ LÊN MÀN HÌNH
        # Vẽ các điểm nhận diện (Face Mesh)
        if is_face_visible:
            for pt in face_result.face_landmarks[0]:
                x, y = int(pt.x * frame.shape[1]), int(pt.y * frame.shape[0])
                cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)

        # Hiển thị thông tin
        cv2.rectangle(frame, (0, 0), (450, 120), (0, 0, 0), -1) # Khung đen nền
        cv2.putText(frame, f"Status: {status}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        cv2.putText(frame, f"Dap chan: {blanket_pct}%", (10, 65), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # Tính FPS
        fps = 1 / (time.time() - start_time)
        fps_buffer.append(fps)
        cv2.putText(frame, f"FPS: {sum(fps_buffer)/len(fps_buffer):.1f}", (10, 100), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

        cv2.imshow("DEMO SMART BABY MONITOR", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_demo()
