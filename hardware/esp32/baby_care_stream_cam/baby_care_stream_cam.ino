#include "esp_camera.h"
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// --- CẤU HÌNH WIFI ---
const char* ssid = "Phòng 402";
const char* password = "79797979";

// --- CẤU HÌNH SERVER ---
const char* server_ip = "192.168.0.32";
const int   http_port = 8003;
const int   ws_port   = 8000;

// --- CẤU HÌNH CAMERA (AI-THINKER) ---
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

// --- BIẾN TOÀN CỤC ---
WebSocketsClient webSocket;
WiFiClient streamClient;
bool trigger_hq_capture = false;
const char* DEVICE_ID = "baby-cam-001";

void handlePreviewStream();
void handleHQCapture();
void sendChunk(String data);
void sendChunk(const uint8_t* data, size_t len);

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("[WS] Disconnected!");
      break;
    case WStype_CONNECTED:
      Serial.println("[WS] Connected!");
      {
        StaticJsonDocument<200> doc;
        doc["type"] = "hello";
        doc["device_id"] = DEVICE_ID;
        doc["role"] = "camera";
        String msg;
        serializeJson(doc, msg);
        webSocket.sendTXT(msg);
      }
      break;
    case WStype_TEXT:
      Serial.printf("[WS] Received: %s\n", payload);
      {
        StaticJsonDocument<200> doc;
        DeserializationError error = deserializeJson(doc, payload);
        if (!error) {
          const char* type_str = doc["type"];
          const char* cmd_str = doc["cmd"];
          if (type_str && strcmp(type_str, "cmd") == 0 && cmd_str && (strcmp(cmd_str, "capture_hq") == 0 || strcmp(cmd_str, "capture_pose") == 0)) {
            trigger_hq_capture = true;
            Serial.println(">>> TRIGGER HQ CAPTURE!");
          }
        }
      }
      break;
  }
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); 
  
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- ESP32-CAM Starting (v2.1 Staggered) ---");
  
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
  config.xclk_freq_hz = 10000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if(psramFound()){
    config.frame_size = FRAMESIZE_QVGA; 
    config.jpeg_quality = 15;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_QVGA; 
    config.jpeg_quality = 15;
    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x", err);
  } else {
    Serial.println("Camera Init Success.");
  }

  delay(2000);
  
  WiFi.begin(ssid, password);
  Serial.println("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected. IP: " + WiFi.localIP().toString());

  // THÊM DEVICE-ID VÀO URL WEBSOCKET (BẮT BUỘC THEO SERVER LOGIC)
  String ws_path = "/xiaozhi/v1/?device-id=" + String(DEVICE_ID);
  webSocket.begin(server_ip, ws_port, ws_path);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
}

void loop() {
  webSocket.loop();
  
  if (WiFi.status() == WL_CONNECTED) {
    if (trigger_hq_capture) {
      handleHQCapture();
    } else {
      handlePreviewStream();
    }
  }
  delay(1);
}

void handlePreviewStream() {
  if (!streamClient.connected()) {
    Serial.println("Reconnecting MJPEG Stream...");
    if (!streamClient.connect(server_ip, http_port)) {
      delay(500);
      return;
    }
    String boundary = "espframe";
    streamClient.println("POST /api/vision/mjpeg_push HTTP/1.1");
    streamClient.println("Host: " + String(server_ip));
    streamClient.println("Content-Type: multipart/x-mixed-replace; boundary=" + boundary);
    streamClient.println("Transfer-Encoding: chunked");
    streamClient.println("Connection: keep-alive");
    streamClient.println();
    Serial.println("MJPEG Stream connected!");
  }

  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) return;

  String boundary = "espframe";
  String head = "--" + boundary + "\r\nContent-Type: image/jpeg\r\nContent-Length: " + String(fb->len) + "\r\n\r\n";
  String tail = "\r\n";
  
  sendChunk(head);
  sendChunk(fb->buf, fb->len);
  sendChunk(tail);
  
  esp_camera_fb_return(fb);
  delay(10);
}

void handleHQCapture() {
  Serial.println("[CAPTURE] Starting HQ Capture...");
  
  if (streamClient.connected()) {
    streamClient.stop();
  }

  sensor_t * s = esp_camera_sensor_get();
  if (!s) return;
  
  s->set_framesize(s, FRAMESIZE_VGA); 
  s->set_quality(s, 10);
  delay(300);

  for(int i=0; i<3; i++) {
    camera_fb_t * tmp = esp_camera_fb_get();
    if(tmp) esp_camera_fb_return(tmp);
    delay(100);
  }

  camera_fb_t * fb = esp_camera_fb_get();
  if (fb) {
    WiFiClient client;
    if (client.connect(server_ip, http_port)) {
      String boundary = "---HQ-BOUNDARY---";
      String head = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"hq_photo.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n";
      String tail = "\r\n--" + boundary + "--\r\n";
      uint32_t totalLen = head.length() + fb->len + tail.length();

      client.println("POST /api/vision/hq_capture HTTP/1.1");
      client.println("Host: " + String(server_ip));
      client.println("Content-Type: multipart/form-data; boundary=" + boundary);
      client.print("Content-Length: "); client.println(totalLen);
      client.println();
      client.print(head);
      client.write(fb->buf, fb->len);
      client.print(tail);
      
      unsigned long timeout = millis();
      while (client.available() == 0) {
        if (millis() - timeout > 5000) {
          Serial.println(">>> HTTP HQ Timeout!");
          client.stop();
          esp_camera_fb_return(fb);
          return;
        }
      }
      String line = client.readStringUntil('\r');
      Serial.println(">>> HTTP HQ Response: " + line);
      client.stop();
    }
    esp_camera_fb_return(fb);
  }

  s->set_framesize(s, FRAMESIZE_QVGA);
  s->set_quality(s, 15);
  trigger_hq_capture = false;
  Serial.println("[CAPTURE] Finished HQ Capture.");
}

void sendChunk(String data) {
  streamClient.printf("%X\r\n", data.length());
  streamClient.print(data);
  streamClient.print("\r\n");
}

void sendChunk(const uint8_t* data, size_t len) {
  streamClient.printf("%X\r\n", len);
  streamClient.write(data, len);
  streamClient.print("\r\n");
}
