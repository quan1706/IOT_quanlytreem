FROM python:3.10-slim

# Cài đặt các thư viện hệ thống cần thiết (Install system dependencies)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libopus0 ffmpeg locales && \
    sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Thiết lập biến môi trường ngôn ngữ (Set environment variables)
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    PYTHONIOENCODING=utf-8

# Thiết lập thư mục làm việc gốc cho toàn bộ dự án
WORKDIR /opt/smart-baby-care

# Cấu hình pip để tránh timeout
RUN pip config set global.timeout 120 && \
    pip config set install.retries 5

# Copy toàn bộ dự án (bao gồm cả thư mục server và thư mục ESP code) vào Container
COPY . /opt/smart-baby-care

# Cài đặt các thư viện Python cho Server
# Trỏ đến file requirements.txt ở bên trong thư mục con xiaozhi-esp32-server/main/xiaozhi-server/
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r xiaozhi-esp32-server/main/xiaozhi-server/requirements.txt --default-timeout=120 --retries 5

# Mở port cho Server hoạt động
EXPOSE 8000

# Đặt thư mục làm việc cuối cùng vào nơi chứa file app.py để tiện chạy server
WORKDIR /opt/smart-baby-care/xiaozhi-esp32-server/main/xiaozhi-server

# Lệnh khởi chạy server (Start application)
CMD ["python", "app.py"]
