/**
 * classifier.ino
 * Chạy Edge Impulse classifier và xử lý kết quả.
 *
 * Public API:
 *   bool run_inference(signal_t *signal, ei_impulse_result_t *result)
 *   void process_results(const ei_impulse_result_t *result)
 */

#include "config.h"
#include <Baby_Cry_Detection_Large_Data_inferencing.h>

// ─────────────────────────────────────────────
// Chạy model trên signal đã chuẩn bị
// Trả về false nếu Edge Impulse báo lỗi
// ─────────────────────────────────────────────
bool run_inference(signal_t *signal, ei_impulse_result_t *result) {
    EI_IMPULSE_ERROR err = run_classifier(signal, result, DEBUG_NN);

    if (err != EI_IMPULSE_OK) {
        ei_printf("ERR: Classifier failed (%d)\n", err);
        return false;
    }
    return true;
}

// ─────────────────────────────────────────────
// In kết quả ra Serial và trigger cảnh báo nếu cần
// ─────────────────────────────────────────────
void process_results(const ei_impulse_result_t *result) {
    for (size_t ix = 0; ix < EI_CLASSIFIER_LABEL_COUNT; ix++) {
        float confidence = result->classification[ix].value;

        if (confidence > CONFIDENCE_THRESHOLD) {
            const char *label = result->classification[ix].label;
            ei_printf("PHAT HIEN: %s (%.2f)\n", label, confidence);

            if (strcmp(label, BABY_CRY_LABEL) == 0) {
                Serial.println("!!! CANH BAO: EM BE DANG KHOC !!!");
                telegram_send_alert(label, confidence);  // Gửi Telegram
                // TODO: trigger LED / buzzer tại đây
            }
        }
    }
}
