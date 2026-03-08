/*
 * ============================================================
 *  SMART BABY CARE - ESP32 DevKit V1 Firmware
 *  Phiên bản: 1.0.0
 *  Mô tả: Firmware cho hệ thống chăm sóc trẻ sơ sinh thông minh
 *          Kết nối tới Xiaozhi Server qua WebSocket
 *          Thu âm giọng nói (INMP441) → Gửi lên Server → Nhận phản hồi → Phát loa (MAX98357A)
 * ============================================================
 *  PHẦN CỨNG CẦN THIẾT:
 *  - ESP32 DevKit V1
 *  - Micro INMP441 (I2S Input)
 *  - Loa MAX98357A (I2S Output)
 *  - Màn hình TFT ST7789 240x240 (SPI)
 *  - Nút nhấn (BOOT GPIO0)
 *  - (Tùy chọn) Cảm biến DHT22 đo nhiệt độ phòng
 * ============================================================
 *  THƯ VIỆN CẦN CÀI TRONG ARDUINO IDE (Sketch → Include Library → Manage Libraries):
 *  1. WebSockets by Markus Sattler (tìm "WebSockets")
 *  2. ArduinoJson by Benoit Blanchon (tìm "ArduinoJson")
 *  3. TFT_eSPI by Bodmer (tìm "TFT_eSPI") → cần config User_Setup.h
 *  4. DHT sensor library by Adafruit (nếu dùng DHT22)
 * ============================================================
 */

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <driver/i2s.h>

// ============================================================
//  CẤU HÌNH WIFI & SERVER - SỬA THÔNG TIN NÀY CHO PHÙ HỢP
// ============================================================
const char* WIFI_SSID     = "Phòng 402";           // Tên WiFi nhà bạn
const char* WIFI_PASSWORD = "79797979";             // Mật khẩu WiFi (SỬA LẠI CHO ĐÚNG)

const char* SERVER_IP     = "192.168.100.206";      // IP máy tính chạy Server
const int   SERVER_PORT   = 8000;                   // Port WebSocket Server
const char* SERVER_PATH   = "/xiaozhi/v1/";         // Đường dẫn WebSocket

// ============================================================
//  CẤU HÌNH DEVICE ID - ĐỂ SERVER NHẬN DIỆN THIẾT BỊ
// ============================================================
const char* DEVICE_ID = "baby-care-esp32-001";
const char* CLIENT_ID = "baby-care-client";

// ============================================================
//  CẤU HÌNH CHÂN GPIO - SỬA THEO SƠ ĐỒ NỐI DÂY CỦA BẠN
// ============================================================

// --- Micro INMP441 (I2S Input - Thu âm) ---
#define I2S_MIC_PORT        I2S_NUM_0
#define I2S_MIC_WS          25    // Word Select (WS/LRCK)
#define I2S_MIC_SCK         26    // Serial Clock (SCK/BCLK)
#define I2S_MIC_SD          32    // Serial Data (SD/DIN)

// --- Loa MAX98357A (I2S Output - Phát âm) ---
// Dùng chung I2S_NUM_0, chuyển đổi RX/TX khi cần (ESP32 DevKit V1 chỉ ổn 1 port)
#define I2S_SPK_PORT        I2S_NUM_1
#define I2S_SPK_DIN         33    // Data In
#define I2S_SPK_BCLK        14    // Bit Clock
#define I2S_SPK_LRC         27    // Left/Right Clock

// --- Nút nhấn ---
#define BTN_TALK            0     // GPIO 0 = Nút BOOT trên board (Nhấn giữ để nói)
#define BTN_DEBOUNCE_MS     50    // Thời gian chống dội nút

// --- LED ---
#define LED_PIN             2     // LED trên board ESP32

// --- DHT22 Nhiệt độ (Tùy chọn - nếu không dùng thì comment dòng #define USE_DHT22) ---
// #define USE_DHT22
#ifdef USE_DHT22
  #include <DHT.h>
  #define DHT_PIN           16
  #define DHT_TYPE          DHT22
  DHT dht(DHT_PIN, DHT_TYPE);
#endif

// ============================================================
//  CẤU HÌNH I2S AUDIO
// ============================================================
#define SAMPLE_RATE         16000   // Tần số thu âm (16kHz - khớp với SenseVoice trên Server)
#define SAMPLE_BITS         16      // Độ sâu bit
#define AUDIO_BUFFER_SIZE   1024    // Kích thước buffer audio (bytes)

// ============================================================
//  CẤU HÌNH PHÁT HIỆN TIẾNG KHÓC (ĐƠN GIẢN - THEO NGƯỠNG ÂM LƯỢNG)
//  Lưu ý: Module AI nhận diện tiếng khóc YAMNet sẽ chạy trên Server Python
//  Phần này chỉ là bộ lọc sơ cấp ở phía ESP32
// ============================================================
#define CRY_DETECT_THRESHOLD    200     // Ngưỡng âm lượng để nghi là tiếng ồn/khóc (INMP441 trả về RMS nhỏ, tầm 300-600 là rất to)
#define CRY_DETECT_DURATION_MS  1000    // Liên tục vượt ngưỡng bao lâu (ms) thì báo (giảm xuống 1s cho nhạy)
#define CRY_CHECK_INTERVAL_MS   500     // Tần suất kiểm tra tiếng ồn

// ============================================================
//  CẤU HÌNH ĐO NHIỆT ĐỘ
// ============================================================
#define TEMP_READ_INTERVAL_MS   30000   // Đọc nhiệt độ mỗi 30 giây
#define TEMP_ALERT_HIGH         32.0    // Cảnh báo nếu nhiệt độ phòng > 32°C
#define TEMP_ALERT_LOW          20.0    // Cảnh báo nếu nhiệt độ phòng < 20°C

// ============================================================
//  BIẾN TOÀN CỤC
// ============================================================
WebSocketsClient webSocket;

// Trạng thái hệ thống
enum SystemState {
  STATE_CONNECTING,       // Đang kết nối WiFi/Server
  STATE_IDLE,             // Chờ lệnh (standby)
  STATE_LISTENING,        // Đang thu âm giọng nói (nhấn giữ nút)
  STATE_THINKING,         // Server đang xử lý
  STATE_SPEAKING,         // Đang phát âm thanh phản hồi
  STATE_CRY_DETECTED,     // Phát hiện tiếng khóc
  STATE_ERROR             // Lỗi
};
SystemState currentState = STATE_CONNECTING;

// Biến nút nhấn
bool btnPressed = false;
unsigned long btnLastDebounce = 0;

// Biến phát hiện tiếng khóc
unsigned long cryStartTime = 0;
bool cryActive = false;
unsigned long lastCryCheck = 0;

// Biến nhiệt độ
unsigned long lastTempRead = 0;
float currentTemp = 0.0;
float currentHumidity = 0.0;

// Biến WebSocket
bool wsConnected = false;
unsigned long lastReconnect = 0;
#define RECONNECT_INTERVAL 5000

// Buffer Audio
int16_t audioBuffer[AUDIO_BUFFER_SIZE / 2];

// ============================================================
//  KHỞI TẠO I2S - MICROPHONE (THU ÂM)
// ============================================================
void i2s_mic_init() {
  i2s_config_t i2s_config_mic = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config_mic = {
    .mck_io_num   = I2S_PIN_NO_CHANGE,   // Không dùng MCLK (tránh xung đột GPIO0)
    .bck_io_num   = I2S_MIC_SCK,
    .ws_io_num    = I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num  = I2S_MIC_SD
  };

  i2s_driver_install(I2S_MIC_PORT, &i2s_config_mic, 0, NULL);
  i2s_set_pin(I2S_MIC_PORT, &pin_config_mic);
  i2s_zero_dma_buffer(I2S_MIC_PORT);
  Serial.println("[AUDIO] Mic INMP441 initialized (I2S_NUM_0)");
}

// ============================================================
//  KHỞI TẠO I2S - LOA (PHÁT ÂM)
// ============================================================
void i2s_spk_init() {
  i2s_config_t i2s_config_spk = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 24000,  // Server TTS output at 24kHz
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config_spk = {
    .mck_io_num   = I2S_PIN_NO_CHANGE,   // Không dùng MCLK (tránh xung đột GPIO0)
    .bck_io_num   = I2S_SPK_BCLK,
    .ws_io_num    = I2S_SPK_LRC,
    .data_out_num = I2S_SPK_DIN,
    .data_in_num  = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_SPK_PORT, &i2s_config_spk, 0, NULL);
  i2s_set_pin(I2S_SPK_PORT, &pin_config_spk);
  i2s_zero_dma_buffer(I2S_SPK_PORT);
  Serial.println("[AUDIO] Speaker MAX98357A initialized (I2S_NUM_1)");
}

// ============================================================
//  KẾT NỐI WIFI
// ============================================================
void wifi_connect() {
  Serial.printf("[WIFI] Connecting to: %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 30) {
    delay(500);
    Serial.print(".");
    retries++;
    digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Nhấp nháy LED khi kết nối
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WIFI] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    digitalWrite(LED_PIN, HIGH);
  } else {
    Serial.println("\n[WIFI] Connection FAILED! Check SSID/Password.");
    currentState = STATE_ERROR;
  }
}

// ============================================================
//  XỬ LÝ SỰ KIỆN WEBSOCKET
// ============================================================
void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.println("[WS] Disconnected from server!");
      wsConnected = false;
      currentState = STATE_CONNECTING;
      break;

    case WStype_CONNECTED:
      Serial.printf("[WS] Connected to server: %s:%d%s\n", SERVER_IP, SERVER_PORT, SERVER_PATH);
      wsConnected = true;
      currentState = STATE_IDLE;
      digitalWrite(LED_PIN, HIGH);

      // Gửi hello message để Server nhận diện thiết bị
      sendHelloMessage();
      break;

    case WStype_TEXT: {
      Serial.printf("[WS] Received text: %s\n", payload);
      handleServerMessage((char*)payload);
      break;
    }

    case WStype_BIN:
      // Nhận dữ liệu audio binary từ server (TTS response)
      Serial.printf("[WS] Received audio binary: %d bytes\n", length);
      handleAudioResponse(payload, length);
      break;

    case WStype_ERROR:
      Serial.println("[WS] Error occurred!");
      break;

    case WStype_PING:
      Serial.println("[WS] Ping received");
      break;

    case WStype_PONG:
      Serial.println("[WS] Pong received");
      break;
  }
}

// ============================================================
//  GỬI HELLO MESSAGE - BẮT TAY VỚI SERVER
// ============================================================
void sendHelloMessage() {
  StaticJsonDocument<512> doc;
  doc["type"] = "hello";
  doc["version"] = 1;
  doc["transport"] = "websocket";

  JsonObject audio = doc.createNestedObject("audio_params");
  audio["format"] = "pcm";           // Gửi PCM thô (không mã hóa Opus)
  audio["sample_rate"] = SAMPLE_RATE;
  audio["channels"] = 1;
  audio["frame_duration"] = 60;

  // Thông tin thiết bị
  JsonObject features = doc.createNestedObject("features");
  features["baby_care"] = true;      // Đánh dấu đây là thiết bị Baby Care
  features["cry_detect"] = true;
  features["temp_sensor"] = true;

  String jsonStr;
  serializeJson(doc, jsonStr);
  webSocket.sendTXT(jsonStr);
  Serial.println("[WS] Sent hello message");
}

// ============================================================
//  XỬ LÝ TIN NHẮN TỪ SERVER
// ============================================================
void handleServerMessage(char* message) {
  StaticJsonDocument<1024> doc;
  DeserializationError err = deserializeJson(doc, message);

  if (err) {
    Serial.printf("[WS] JSON parse error: %s\n", err.c_str());
    return;
  }

  const char* type = doc["type"];
  if (!type) return;

  // Server trả lời "hello" → Xác nhận kết nối
  if (strcmp(type, "hello") == 0) {
    Serial.println("[WS] Server accepted connection! Ready.");
    currentState = STATE_IDLE;
  }
  // Server bắt đầu phản hồi giọng nói
  else if (strcmp(type, "tts") == 0) {
    const char* state = doc["state"];
    if (state && strcmp(state, "start") == 0) {
      Serial.println("[WS] TTS started - preparing speaker...");
      currentState = STATE_SPEAKING;
    }
    else if (state && strcmp(state, "stop") == 0) {
      Serial.println("[WS] TTS finished");
      currentState = STATE_IDLE;
    }
  }
  // Server yêu cầu dừng nói
  else if (strcmp(type, "stt") == 0) {
    const char* text = doc["text"];
    if (text) {
      Serial.printf("[STT] Recognized: %s\n", text);
    }
  }
  // Server trả lời văn bản (LLM response)
  else if (strcmp(type, "llm") == 0) {
    const char* text = doc["text"];
    if (text) {
      Serial.printf("[LLM] AI says: %s\n", text);
      // TODO: Hiển thị lên TFT LCD
    }
  }
}

// ============================================================
//  XỬ LÝ DỮ LIỆU AUDIO NHẬN TỪ SERVER (TTS)
// ============================================================
void handleAudioResponse(uint8_t* data, size_t length) {
  if (length == 0) return;

  // Phát âm thanh qua loa
  size_t bytesWritten = 0;
  i2s_write(I2S_SPK_PORT, data, length, &bytesWritten, portMAX_DELAY);
}

// ============================================================
//  THU ÂM VÀ GỬI AUDIO LÊN SERVER
// ============================================================
void recordAndSendAudio() {
  static unsigned long lastDebugPrint = 0;
  
  size_t bytesRead = 0;
  i2s_read(I2S_MIC_PORT, audioBuffer, AUDIO_BUFFER_SIZE, &bytesRead, portMAX_DELAY);

  if (bytesRead > 0 && wsConnected) {
    // Debug: In mức âm lượng mỗi 500ms để kiểm tra mic có hoạt động
    if (millis() - lastDebugPrint > 500) {
      lastDebugPrint = millis();
      long sumSquares = 0;
      int numSamples = bytesRead / 2;
      for (int i = 0; i < numSamples; i++) {
        sumSquares += (long)audioBuffer[i] * audioBuffer[i];
      }
      int rms = sqrt(sumSquares / numSamples);
      Serial.printf("[MIC-DEBUG] Audio RMS: %d, bytes: %d, samples: %d\n", rms, bytesRead, numSamples);
    }
    
    // Gửi dữ liệu audio raw (PCM 16-bit, 16kHz, mono) lên server
    webSocket.sendBIN((uint8_t*)audioBuffer, bytesRead);
  }
}

// ============================================================
//  BẮT ĐẦU / KẾT THÚC THU ÂM (PUSH-TO-TALK)
// ============================================================
void startListening() {
  Serial.println("[MIC] Start recording...");
  currentState = STATE_LISTENING;
  digitalWrite(LED_PIN, HIGH);

  // Gửi tín hiệu "bắt đầu nghe" cho server
  StaticJsonDocument<128> doc;
  doc["type"] = "listen";
  doc["state"] = "start";
  doc["mode"] = "manual"; // Chế độ nhấn giữ nút

  String jsonStr;
  serializeJson(doc, jsonStr);
  webSocket.sendTXT(jsonStr);

  // Chờ server xử lý listen message trước khi gửi audio
  delay(200);
  webSocket.loop(); // Xử lý WebSocket events trong lúc chờ
}

void stopListening() {
  Serial.println("[MIC] Stop recording. Sending to server...");
  currentState = STATE_THINKING;
  digitalWrite(LED_PIN, LOW);

  // Gửi tín hiệu "dừng nghe" cho server
  StaticJsonDocument<128> doc;
  doc["type"] = "listen";
  doc["state"] = "stop";

  String jsonStr;
  serializeJson(doc, jsonStr);
  webSocket.sendTXT(jsonStr);
}

// ============================================================
//  PHÁT HIỆN TIẾNG ỒN VÀ THU ÂM 5 GIÂY CHO YAMNET
// ============================================================
unsigned long lastCryDetectTime = 0;

void checkCryDetection() {
  if (currentState == STATE_LISTENING || currentState == STATE_SPEAKING || currentState == STATE_CRY_DETECTED) return;
  
  // NGHỈ 5 GIÂY: Sau khi gửi 1 file đi phân tích, nghỉ 5 giây không đo tiếng ồn để tránh nghẽn server
  if (millis() - lastCryDetectTime < 5000) return;
  
  if (millis() - lastCryCheck < CRY_CHECK_INTERVAL_MS) return;
  lastCryCheck = millis();

  // Đọc mẫu âm thanh nhỏ
  size_t bytesRead = 0;
  int16_t sampleBuffer[256];
  i2s_read(I2S_MIC_PORT, sampleBuffer, sizeof(sampleBuffer), &bytesRead, 100);

  if (bytesRead == 0) return;

  // Tính RMS (Root Mean Square) - đại diện cho mức âm lượng
  long sumSquares = 0;
  int numSamples = bytesRead / 2;
  for (int i = 0; i < numSamples; i++) {
    sumSquares += (long)sampleBuffer[i] * sampleBuffer[i];
  }
  int rms = sqrt(sumSquares / numSamples);

  // Kiểm tra vượt ngưỡng
  if (rms > CRY_DETECT_THRESHOLD) {
    Serial.printf("[CRY] High noise detected! RMS: %d (threshold: %d). Recording 5s for AI analysis...\n", rms, CRY_DETECT_THRESHOLD);
    
    currentState = STATE_CRY_DETECTED;
    digitalWrite(LED_PIN, HIGH);
    
    // Báo Server bắt đầu nghe mode cry_detect
    StaticJsonDocument<128> doc;
    doc["type"] = "listen";
    doc["state"] = "start";
    doc["mode"] = "cry_detect";
    String jsonStr;
    serializeJson(doc, jsonStr);
    webSocket.sendTXT(jsonStr);
    
    delay(100); // Cho server kịp chuyển mode
    
    // Đánh dấu thời điểm bắt đầu thu âm 5s
    cryStartTime = millis(); 
  }
}

// ============================================================
//  GỬI CẢNH BÁO TIẾNG KHÓC LÊN SERVER
// ============================================================
void sendCryAlert(int rmsLevel) {
  if (!wsConnected) return;

  StaticJsonDocument<256> doc;
  doc["type"] = "baby_event";
  doc["event"] = "cry_detected";
  doc["rms_level"] = rmsLevel;
  doc["timestamp"] = millis();
  doc["device_id"] = DEVICE_ID;

  String jsonStr;
  serializeJson(doc, jsonStr);
  webSocket.sendTXT(jsonStr);
  Serial.println("[CRY] Alert sent to server!");
}

// ============================================================
//  ĐỌC NHIỆT ĐỘ PHÒNG (NẾU CÓ CẢM BIẾN DHT22)
// ============================================================
void checkTemperature() {
#ifdef USE_DHT22
  if (millis() - lastTempRead < TEMP_READ_INTERVAL_MS) return;
  lastTempRead = millis();

  float t = dht.readTemperature();
  float h = dht.readHumidity();

  if (isnan(t) || isnan(h)) {
    Serial.println("[TEMP] Failed to read DHT22 sensor!");
    return;
  }

  currentTemp = t;
  currentHumidity = h;
  Serial.printf("[TEMP] Temperature: %.1f°C, Humidity: %.1f%%\n", t, h);

  // Gửi dữ liệu nhiệt độ lên server
  if (wsConnected) {
    StaticJsonDocument<256> doc;
    doc["type"] = "baby_event";
    doc["event"] = "temperature";
    doc["temperature"] = t;
    doc["humidity"] = h;
    doc["device_id"] = DEVICE_ID;

    String jsonStr;
    serializeJson(doc, jsonStr);
    webSocket.sendTXT(jsonStr);
  }

  // Cảnh báo nếu nhiệt độ bất thường
  if (t > TEMP_ALERT_HIGH) {
    Serial.printf("[TEMP] ⚠️ WARNING: Room too hot! %.1f°C\n", t);
  } else if (t < TEMP_ALERT_LOW) {
    Serial.printf("[TEMP] ⚠️ WARNING: Room too cold! %.1f°C\n", t);
  }
#endif
}

// ============================================================
//  XỬ LÝ NÚT NHẤN (PUSH-TO-TALK)
// ============================================================
void handleButton() {
  bool currentBtnState = (digitalRead(BTN_TALK) == LOW); // BOOT button active LOW

  if (currentBtnState != btnPressed) {
    if (millis() - btnLastDebounce > BTN_DEBOUNCE_MS) {
      btnLastDebounce = millis();
      btnPressed = currentBtnState;

      if (btnPressed && currentState == STATE_IDLE) {
        // Bắt đầu thu âm
        startListening();
      } else if (!btnPressed && currentState == STATE_LISTENING) {
        // Dừng thu âm, gửi lên server
        stopListening();
      }
    }
  }
}

// ============================================================
//  KẾT NỐI WEBSOCKET
// ============================================================
void websocket_connect() {
  // Tạo path với device-id trong query string (Server Xiaozhi hỗ trợ cách này)
  String fullPath = String(SERVER_PATH) + "?device-id=" + DEVICE_ID + "&client-id=" + CLIENT_ID;

  Serial.printf("[WS] Connecting to server: %s:%d%s\n", SERVER_IP, SERVER_PORT, fullPath.c_str());

  webSocket.begin(SERVER_IP, SERVER_PORT, fullPath.c_str());
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(RECONNECT_INTERVAL);
  webSocket.enableHeartbeat(15000, 3000, 2); // Ping mỗi 15s, timeout 3s, 2 lần thử

  Serial.println("[WS] WebSocket client started, waiting for connection...");
}

// ============================================================
//  IN TRẠNG THÁI HỆ THỐNG RA SERIAL (DEBUG)
// ============================================================
void printStatus() {
  static unsigned long lastPrint = 0;
  if (millis() - lastPrint < 10000) return; // In mỗi 10 giây
  lastPrint = millis();

  const char* stateNames[] = {
    "CONNECTING", "IDLE", "LISTENING", "THINKING", "SPEAKING", "CRY_DETECTED", "ERROR"
  };

  Serial.println("========================================");
  Serial.printf("  State: %s | WS: %s\n",
    stateNames[currentState],
    wsConnected ? "Connected" : "Disconnected");
  Serial.printf("  WiFi: %s | IP: %s\n",
    WiFi.isConnected() ? "OK" : "LOST",
    WiFi.localIP().toString().c_str());
  Serial.printf("  Free Heap: %d bytes\n", ESP.getFreeHeap());
#ifdef USE_DHT22
  Serial.printf("  Temp: %.1f°C | Humidity: %.1f%%\n", currentTemp, currentHumidity);
#endif
  Serial.println("========================================");
}

// ============================================================
//  SETUP - KHỞI TẠO HỆ THỐNG
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("╔═══════════════════════════════════════╗");
  Serial.println("║   🍼 SMART BABY CARE SYSTEM v1.0     ║");
  Serial.println("║   ESP32 DevKit V1 + Xiaozhi Server   ║");
  Serial.println("╚═══════════════════════════════════════╝");
  Serial.println();

  // Cấu hình GPIO
  pinMode(BTN_TALK, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Khởi tạo cảm biến nhiệt độ (nếu có)
#ifdef USE_DHT22
  dht.begin();
  Serial.println("[SENSOR] DHT22 initialized");
#endif

  // Khởi tạo I2S Audio
  i2s_mic_init();
  i2s_spk_init();

  // Kết nối WiFi
  wifi_connect();

  // Kết nối WebSocket tới Server
  if (WiFi.status() == WL_CONNECTED) {
    websocket_connect();
  }

  Serial.println();
  Serial.println("[SYSTEM] Setup complete! Hold BOOT button to talk.");
  Serial.printf("[SYSTEM] Server: ws://%s:%d%s\n", SERVER_IP, SERVER_PORT, SERVER_PATH);
  Serial.println();
}

// ============================================================
//  LOOP - VÒNG LẶP CHÍNH
// ============================================================
void loop() {
  // Duy trì kết nối WebSocket
  webSocket.loop();

  // Xử lý nút nhấn
  handleButton();

  // Nếu đang thu âm → liên tục gửi audio lên server
  if (currentState == STATE_LISTENING || currentState == STATE_CRY_DETECTED) {
    recordAndSendAudio();
    
    // Nếu ở chế độ bắt tiếng ồn, tự động dừng sau 5 giây
    if (currentState == STATE_CRY_DETECTED && (millis() - cryStartTime > 5000)) {
       Serial.println("[CRY] Finished 5s recording. Asking AI...");
       currentState = STATE_THINKING;
       digitalWrite(LED_PIN, LOW);
       
       StaticJsonDocument<128> doc;
       doc["type"] = "listen";
       doc["state"] = "stop";
       doc["mode"] = "cry_detect";
       String jsonStr;
       serializeJson(doc, jsonStr);
       webSocket.sendTXT(jsonStr);
       
       // Cập nhật mốc thời gian nghỉ ngơi
       lastCryDetectTime = millis();
    }
  }

  // Phát hiện tiếng khóc (chỉ khi không đang thu âm / phát âm)
  checkCryDetection();

  // Đọc nhiệt độ phòng
  checkTemperature();

  // In trạng thái debug
  printStatus();

  // Kiểm tra WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WIFI] Connection lost! Reconnecting...");
    wifi_connect();
    if (WiFi.status() == WL_CONNECTED) {
      websocket_connect();
    }
  }
}
