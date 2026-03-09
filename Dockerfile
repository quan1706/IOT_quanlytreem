FROM python:3.10-slim

# Cài đặt các thư viện hệ thống cần thiết (Install system dependencies)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libopus0 ffmpeg locales && \
    sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Thiết lập biến môi trường ngôn ngữ
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    PYTHONIOENCODING=utf-8

# Thiết lập thư mục làm việc gốc cho Server
WORKDIR /opt/smart-baby-care/server

# Copy mã nguồn Python vào Container (chỉ lấy phần server_python để giảm dung lượng)
COPY ./server_python/main/xiaozhi-server /opt/smart-baby-care/server

# Cài đặt các thư viện Python cho Server
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt --default-timeout=120 --retries 5

# Cài đặt yt-dlp và ffmpeg-python bị thiếu trong requirements
RUN pip install --no-cache-dir yt-dlp ffmpeg-python

# Mở port cho Server hoạt động (8000: WebSocket, 8003: HTTP Dashboard)
EXPOSE 8000
EXPOSE 8003

# Lệnh khởi chạy server (Start application)
CMD ["python", "app.py"]
