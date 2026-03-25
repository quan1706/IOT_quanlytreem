/*
 * ============================================================
 *  SMART BABY CARE - ESP32-CAM Streamer
 *  Mô tả: Firmware dành riêng cho ESP32-CAM để đẩy luồng video
 *          lên Dashboard qua MJPEG Relay.
 * ============================================================
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>

// --- CẤU HÌNH WIFI (Sửa theo thông tin nhà bạn) ---
const char* ssid = "Thành Đạt";
const char* password = "123456789";

// --- CẤU HÌNH SERVER ---
// Thay đổi IP này thành IP của máy chạy Python Server
const char* server_url = "http://172.20.10.3:8003/api/vision/frame";

// --- CẤU HÌNH CAMERA (AI-THINKER PINOUT) ---
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();

  // --- Cấu hình Camera ---
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Cấu hình chất lượng ảnh
  if(psramFound()){
    config.frame_size = FRAMESIZE_QVGA; // 320x240 - Nhanh hơn và mượt hơn
    config.jpeg_quality = 15;           // Tăng nén để truyền tải nhanh hơn
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_QVGA; 
    config.jpeg_quality = 15;
    config.fb_count = 1;
  }

  // Khởi tạo camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  // --- Kết nối WiFi ---
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) { delay(500); }
  }

  // Chụp ảnh
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    return;
  }

// --- Gửi ảnh lên Server (Manual Multipart POST với WiFiClient) ---
  WiFiClient client;
  if (!client.connect("172.20.10.3", 8003)) {
    Serial.println("Connection to server failed");
    esp_camera_fb_return( fb );
    return;
  }

  String boundary = "---ESP32CAM-BOUNDARY---";
  String head = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"frame.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n";
  String tail = "\r\n--" + boundary + "--\r\n";
  uint32_t totalLen = head.length() + fb->len + tail.length();

  client.println("POST /api/vision/frame HTTP/1.1");
  client.println("Host: 172.20.10.3");
  client.println("Content-Type: multipart/form-data; boundary=" + boundary);
  client.print("Content-Length: ");
  client.println(totalLen);
  client.println();
  client.print(head);
  client.write(fb->buf, fb->len);
  client.print(tail);

  // Chờ phản hồi ngắn gọn
  unsigned long timeout = millis();
  while (client.available() == 0) {
    if (millis() - timeout > 1000) {
      Serial.println(">>> Client Timeout !");
      client.stop();
      esp_camera_fb_return(fb);
      return;
    }
  }

  client.stop();
  esp_camera_fb_return(fb);

  // Điều chỉnh tốc độ khung hình
  // Giảm delay xuống 10ms để đạt tốc độ mượt mà nhất có thể
  delay(10); 
}
