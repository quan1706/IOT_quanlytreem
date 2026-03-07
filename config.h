/**
 * config.h
 * Tập trung toàn bộ cấu hình phần cứng & tham số hệ thống.
 * Thay đổi giá trị tại đây để điều chỉnh toàn bộ dự án.
 */
#ifndef CONFIG_H
#define CONFIG_H

// ─────────────────────────────────────────────
// I2S Microphone Pins (INMP441)
// ─────────────────────────────────────────────
#define I2S_WS   25       // Word Select (LRCLK)
#define I2S_SD   32       // Serial Data  (DOUT)
#define I2S_SCK  26       // Bit Clock    (SCK)
#define I2S_PORT I2S_NUM_0

// ─────────────────────────────────────────────
// Audio Capture
// ─────────────────────────────────────────────
#define SAMPLE_BUFFER_SIZE  2048  // Số mẫu tạm 32-bit mỗi lần đọc I2S
#define SAMPLE_SHIFT        14    // >> 14 để chuyển 32-bit → 16-bit (x8 gain)

// ─────────────────────────────────────────────
// Classifier
// ─────────────────────────────────────────────
#define CONFIDENCE_THRESHOLD  0.70f   // Ngưỡng xác suất được coi là phát hiện
#define BABY_CRY_LABEL        "baby_cry"

// ─────────────────────────────────────────────
// Edge Impulse DSP
// ─────────────────────────────────────────────
#define EIDSP_QUANTIZE_FILTERBANK 0

// ─────────────────────────────────────────────
// WiFi
// ─────────────────────────────────────────────
#define WIFI_SSID       "Phòng 402"   // ← đổi thành SSID thật
#define WIFI_PASSWORD   "79797979"      // ← đổi thành password thật

// ─────────────────────────────────────────────
// Telegram Bot
// Hướng dẫn lấy token: chat với @BotFather trên Telegram
// Hướng dẫn lấy chat_id: chat với @userinfobot
// ─────────────────────────────────────────────
#define TELEGRAM_BOT_TOKEN   "8765806795:AAEB83HSeGkpYYv0JsnnPz6IaiSCvlDOn_w"   // ← token từ @BotFather
#define TELEGRAM_CHAT_ID     "5288120841"               // ← chat_id của bạn
#define TELEGRAM_COOLDOWN_MS 30000  // Gửi tối đa 1 tin mỗi 30 giây (tránh spam)

// ─────────────────────────────────────────────
// Debug
// ─────────────────────────────────────────────
#define DEBUG_NN false  // true = in raw NN output ra Serial

#endif // CONFIG_H
