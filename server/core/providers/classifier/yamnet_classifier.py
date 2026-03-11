import os
import numpy as np
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

class YamnetClassifier:
    def __init__(self):
        self.model = None
        self.class_map = None
        self.initialized = False
        self.init_model()

    def init_model(self):
        try:
            import tensorflow as tf
            import tensorflow_hub as hub
            import csv

            logger.bind(tag=TAG).info("Đang tải YAMNet AI model từ TensorFlow Hub (Model 521 âm thanh của Google)...")
            self.model = hub.load('https://tfhub.dev/google/yamnet/1')
            
            # Load class map
            class_map_path = self.model.class_map_path().numpy().decode('utf-8')
            with tf.io.gfile.GFile(class_map_path) as csvfile:
                reader = csv.DictReader(csvfile)
                self.class_map = [row['display_name'] for row in reader]

            self.initialized = True
            logger.bind(tag=TAG).info("YAMNet khởi tạo thành công!")
        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi khởi tạo YAMNet (Cần pip install tensorflow tensorflow-hub librosa): {e}")

    def is_baby_cry(self, pcm_data: bytes, sample_rate: int = 16000) -> bool:
        if not self.initialized:
            logger.bind(tag=TAG).warning("YAMNet chưa được khởi tạo. Bỏ qua phân tích và coi như tiếng khóc.")
            return True # Fallback về cách báo động cũ

        try:
            import librosa
            # Convert PCM to float32
            audio_int16 = np.frombuffer(pcm_data, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # KHUẾCH ĐẠI ÂM LƯỢNG (Normalize Audio) để YAMNet có thể nghe tiếng nhỏ
            max_amp = np.max(np.abs(audio_float32))
            if max_amp > 0:
                audio_float32 = audio_float32 / max_amp

            # YAMNet yêu cầu 16000Hz mono
            if sample_rate != 16000:
                audio_float32 = librosa.resample(y=audio_float32, orig_sr=sample_rate, target_sr=16000)

            # Chạy model
            scores, embeddings, spectrogram = self.model(audio_float32)
            
            # Lấy trung bình scores trong suốt thời gian audio (khoảng 3 giây)
            mean_scores = np.mean(scores.numpy(), axis=0)
            top_class_index = np.argmax(mean_scores)
            top_class_name = self.class_map[top_class_index]
            top_score = mean_scores[top_class_index]
            
            # Class tiếng khóc YAMNet: "Crying, sobbing" (19), "Baby cry, infant cry" (20), "Whimper" (21)
            baby_cry_score = mean_scores[19] + mean_scores[20] + mean_scores[21]

            logger.bind(tag=TAG).info(f"[YAMNET] Top âm thanh: {top_class_name} ({top_score:.2f}) | Độ chắc chắn Bé khóc: {baby_cry_score:.2f}")

            # Nếu điểm Baby Cry > 5% (Ngưỡng khá nhạy vì tiếng khóc có thể bị lẫn tiếng ồn)
            return baby_cry_score > 0.05
        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi phân tích YAMNet: {e}")
            return True
