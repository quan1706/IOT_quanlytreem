/**
 * telegram_notify.ino
 * Gửi cảnh báo qua Telegram Bot API khi phát hiện em bé khóc.
 * Dùng thư viện UniversalTelegramBot (cài từ Library Manager).
 *
 * Cài đặt thư viện cần thiết:
 *   - "Universal Telegram Bot" by Brian Lough
 *   - "ArduinoJson" by Benoit Blanchon (>= v6)
 *
 * Public API:
 *   void telegram_send_alert(const char* label, float confidence)
 */

#include "config.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>

// ─────────────────────────────────────────────
// Module-private objects
// ─────────────────────────────────────────────
static WiFiClientSecure  secured_client;
static UniversalTelegramBot* bot = nullptr;

// ─────────────────────────────────────────────
// Khởi tạo bot — gọi sau khi WiFi đã connected
// ─────────────────────────────────────────────
void telegram_begin() {
    secured_client.setInsecure();  // bỏ qua SSL cert verify (đơn giản cho ESP32)
    bot = new UniversalTelegramBot(TELEGRAM_BOT_TOKEN, secured_client);
    Serial.println("[Telegram] Bot da san sang.");
}

// ─────────────────────────────────────────────
// Gửi tin nhắn test khi khởi động (xác nhận kết nối)
// ─────────────────────────────────────────────
void telegram_send_test() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[Telegram Test] Khong co WiFi.");
        return;
    }
    if (bot == nullptr) {
        telegram_begin();
    }
    bool ok = bot->sendMessage(TELEGRAM_CHAT_ID, "✅ Baby Guard ONLINE - He thong dang hoat dong!", "");
    if (ok) {
        Serial.println("[Telegram Test] Gui test OK!");
    } else {
        Serial.println("[Telegram Test] GUI THAT BAI! Kiem tra BOT_TOKEN va CHAT_ID.");
    }
}

// ─────────────────────────────────────────────
// Gửi tin nhắn cảnh báo đến TELEGRAM_CHAT_ID
// Chỉ gửi khi WiFi đang connected & bot đã init
// ─────────────────────────────────────────────
void telegram_send_alert(const char* label, float confidence) {
    // Lazy init: allocate SSL client + bot only on first real alert
    if (bot == nullptr) {
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[Telegram] Khong co WiFi, bo qua gui tin.");
            return;
        }
        telegram_begin();
    }
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[Telegram] Khong co WiFi, bo qua gui tin.");
        return;
    }

    // Giới hạn tần suất gửi: tối đa 1 tin mỗi TELEGRAM_COOLDOWN_MS
    static uint32_t lastSent = 0;
    if (millis() - lastSent < TELEGRAM_COOLDOWN_MS) return;
    lastSent = millis();

    // Tạo nội dung tin nhắn
    String msg = "🚨 *CANH BAO BABY GUARD*\n";
    msg += "Phat hien: *" + String(label) + "*\n";
    msg += "Do tin cay: *" + String(confidence * 100, 1) + "%*\n";
    msg += "⏰ " + String(millis() / 1000) + "s ke tu khoi dong";

    bool ok = bot->sendMessage(TELEGRAM_CHAT_ID, msg, "Markdown");
    if (ok) {
        Serial.println("[Telegram] Da gui canh bao thanh cong!");
    } else {
        Serial.println("[Telegram] Loi gui tin nhan.");
    }
}
