/**
 * wifi_manager.ino
 * Quản lý kết nối WiFi: connect, auto-reconnect.
 *
 * Public API:
 *   void wifi_manager_begin()      — gọi 1 lần trong setup()
 *   bool wifi_is_connected()       — kiểm tra trạng thái
 *   void wifi_manager_loop()       — gọi trong loop() để auto-reconnect
 */

#include "config.h"
#include <WiFi.h>

// ─────────────────────────────────────────────
// Kết nối WiFi lần đầu, block cho đến khi thành công
// ─────────────────────────────────────────────
void wifi_manager_begin() {
    Serial.printf("[WiFi] Dang ket noi toi: %s\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    uint8_t retries = 0;
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
        if (++retries > 40) {  // 20 giây timeout
            Serial.println("\n[WiFi] TIMEOUT - tiep tuc khong co WiFi");
            return;
        }
    }

    Serial.printf("\n[WiFi] Ket noi thanh cong! IP: %s\n",
                  WiFi.localIP().toString().c_str());
}

// ─────────────────────────────────────────────
// Kiểm tra nhanh trạng thái WiFi
// ─────────────────────────────────────────────
bool wifi_is_connected() {
    return WiFi.status() == WL_CONNECTED;
}

// ─────────────────────────────────────────────
// Gọi trong loop() để tự reconnect nếu mất kết nối
// ─────────────────────────────────────────────
void wifi_manager_loop() {
    static uint32_t lastCheck = 0;
    if (millis() - lastCheck < 10000) return;  // kiểm tra mỗi 10 giây
    lastCheck = millis();

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[WiFi] Mat ket noi - dang thu lai...");
        WiFi.disconnect();
        WiFi.reconnect();
    }
}
