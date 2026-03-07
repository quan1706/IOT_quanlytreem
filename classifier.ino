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
            ei_printf("ML DETECTION: %s (%.2f)\n", label, confidence);

            if (strcmp(label, BABY_CRY_LABEL) == 0) {
                // ─────────────────────────────────────────────
                // DSP Double-Confirmation
                // ─────────────────────────────────────────────
                float zcr = calculate_zcr(inference.buffer, inference.n_samples);
                float freq_mag = goertzel_mag(inference.buffer, inference.n_samples, 
                                             GOERTZEL_TARGET_FREQ, EI_CLASSIFIER_FREQUENCY);
                
                if (DEBUG_DSP) {
                    Serial.printf("DSP Confirm -> ZCR: %.2f (Range: %.2f-%.2f), FreqMag: %.4f\n", 
                                  zcr, (float)ZCR_THRESHOLD_MIN, (float)ZCR_THRESHOLD_MAX, freq_mag);
                }

                // Tiếng khóc em bé có ZCR trung bình (không quá thấp như tiếng u u, không quá cao như tiếng xì)
                // Và có năng lượng tập trung ở dải tần mục tiêu
                bool zcr_ok = (zcr >= ZCR_THRESHOLD_MIN && zcr <= ZCR_THRESHOLD_MAX);
                bool freq_ok = (freq_mag > 0.005f); // Ngưỡng nhỏ để xác nhận có năng lượng dải tần này

                if (zcr_ok && freq_ok) {
                    Serial.println("!!! CANH BAO: EM BE DANG KHOC (Verified by ML & DSP) !!!");
                    telegram_send_alert(label, confidence);
                } else {
                    Serial.printf("-> Rejected by DSP: ZCR_ok=%d, Freq_ok=%d\n", zcr_ok, freq_ok);
                }
            }
        }
    }
}
