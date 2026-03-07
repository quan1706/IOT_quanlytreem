/**
 * baby_guard.ino  —  Main Orchestrator
 *
 * Chỉ chứa setup() và loop(). Mọi logic được delegate
 * sang các module chuyên biệt:
 *   microphone.ino       → I2S init + audio capture
 *   classifier.ino       → Edge Impulse inference + alert
 *   wifi_manager.ino     → WiFi connect + auto-reconnect
 *   telegram_notify.ino  → Telegram Bot alert
 *   config.h             → pin defines, credentials & constants
 *   audio_types.h        → shared structs
 */

#include "config.h"
#include "audio_types.h"
#include <Baby_Cry_Detection_Large_Data_inferencing.h>

// ─────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    while (!Serial);
    Serial.println("AI Baby Cry Detection - Phong 402");

    // 1. Kết nối WiFi
    wifi_manager_begin();

    // 2. Khởi tạo microphone + cấp phát buffer
    //    (Telegram bot sẽ tự khởi tạo khi cần gửi tin nhắn đầu tiên,
    //     để dành RAM cho tensor arena.)
    if (!microphone_inference_start(EI_CLASSIFIER_RAW_SAMPLE_COUNT)) {
        ei_printf("ERR: Khong du bo nho RAM cho Model\r\n");
        return;
    }

    // (Bỏ test telegram ở đây vì SSL handshake tốn quá nhiều RAM,
    // dễ gây treo ESP32 khi đang khởi động I2S và Tensor Arena.
    // Bot sẽ tự init LAZY khi có cảnh báo đầu tiên).

    ei_printf("Dang lang nghe am thanh...\n");
}

// ─────────────────────────────────────────────
void loop() {
    // Giữ WiFi ổn định (auto-reconnect nếu mất kết nối)
    wifi_manager_loop();

    // 1. Chờ capture đủ 1 frame audio
    if (!microphone_inference_record()) {
        ei_printf("ERR: Loi ghi am\n");
        return;
    }

    // 2. Kiểm tra biên độ âm thanh (Amplitude Gate)
    // Nếu quá im lặng thì bỏ qua inference để tiết kiệm CPU
    float rms = calculate_rms(inference.buffer, inference.n_samples);
    if (DEBUG_DSP) {
        ei_printf("RMS: ");
        ei_printf_float(rms);
        ei_printf(" (Thresh: ");
        ei_printf_float(RMS_THRESHOLD);
        ei_printf(")\n");
    }
    
    if (rms < RMS_THRESHOLD) {
        if (DEBUG_DSP) Serial.println("-> Silence: Skipping inference.");
        return; 
    }

    // 3. Chuẩn bị signal cho Edge Impulse
    signal_t signal;
    signal.total_length = EI_CLASSIFIER_RAW_SAMPLE_COUNT;
    signal.get_data     = &microphone_audio_signal_get_data;

    // 4. Chạy classifier
    ei_impulse_result_t result = { 0 };
    if (!run_inference(&signal, &result)) return;

    // 5. Xử lý kết quả + gửi Telegram nếu phát hiện
    process_results(&result);
}