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
    // ── Dump RAW tất cả labels từ model ──
    ei_printf("  Raw labels (%d): ", EI_CLASSIFIER_LABEL_COUNT);
    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
        ei_printf("[%s]=", result->classification[i].label);
        ei_printf_float(result->classification[i].value);
        ei_printf("  ");
    }
    ei_printf("\n");

    // ── Tìm confidence: cry = label chứa "cry" hoặc "baby", noise = còn lại ──
    float cry_conf = 0, noise_conf = 0;
    const char* cry_label_found = nullptr;
    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
        const char* lbl = result->classification[i].label;
        // Tìm label có chữ "cry" hoặc "baby" (không phân biệt vị trí)
        if (strstr(lbl, "cry") != nullptr || strstr(lbl, "baby") != nullptr || 
            strstr(lbl, "Cry") != nullptr || strstr(lbl, "Baby") != nullptr) {
            cry_conf = result->classification[i].value;
            cry_label_found = lbl;
        } else {
            noise_conf = result->classification[i].value;
        }
    }

    // ── Tính RMS hiện tại ──
    float rms = calculate_rms(inference.buffer, inference.n_samples);

    // ── Kiểm tra ML threshold ──
    bool ml_ok = (cry_conf > CONFIDENCE_THRESHOLD);

    // ── Nếu ML pass → tính DSP ──
    float zcr = 0, freq_mag = 0;
    bool zcr_ok = false, freq_ok = false;
    if (ml_ok) {
        zcr = calculate_zcr(inference.buffer, inference.n_samples);
        freq_mag = goertzel_mag(inference.buffer, inference.n_samples,
                                GOERTZEL_TARGET_FREQ, EI_CLASSIFIER_FREQUENCY);
        zcr_ok  = (zcr >= ZCR_THRESHOLD_MIN && zcr <= ZCR_THRESHOLD_MAX);
        freq_ok = (freq_mag > 0.001f);
    }

    bool is_crying = ml_ok && zcr_ok && freq_ok;

    // ─────────────────────────────────────────────
    // LOG OUTPUT (dùng ei_printf_float thay vì %f)
    // ─────────────────────────────────────────────
    ei_printf("------------------------------------\n");
    ei_printf("[%s]  RMS: ", is_crying ? "CRYING" : "Noise");
    ei_printf_float(rms);
    ei_printf("\n");

    ei_printf("  ML Confidence:\n");
    ei_printf("    cry:   ");
    ei_printf_float(cry_conf);
    ei_printf("  %s (thresh: >", ml_ok ? "OK" : "FAIL");
    ei_printf_float(CONFIDENCE_THRESHOLD);
    ei_printf(")\n");
    ei_printf("    noise: ");
    ei_printf_float(noise_conf);
    ei_printf("\n");

    if (ml_ok) {
        ei_printf("  DSP Verification:\n");
        ei_printf("    ZCR:     ");
        ei_printf_float(zcr);
        ei_printf("  %s (range: ", zcr_ok ? "OK" : "FAIL");
        ei_printf_float(ZCR_THRESHOLD_MIN);
        ei_printf(" - ");
        ei_printf_float(ZCR_THRESHOLD_MAX);
        ei_printf(")\n");
        ei_printf("    FreqMag: ");
        ei_printf_float(freq_mag);
        ei_printf("  %s (thresh: >0.001)\n", freq_ok ? "OK" : "FAIL");
    }

    // ── In lý do bị reject ──
    if (ml_ok && !is_crying) {
        ei_printf("  -> Blocked by: ");
        if (!zcr_ok) { ei_printf("ZCR("); ei_printf_float(zcr); ei_printf(" ngoai range) "); }
        if (!freq_ok) { ei_printf("FreqMag("); ei_printf_float(freq_mag); ei_printf(" qua thap) "); }
        ei_printf("\n");
    }

    // ── Trigger alert ──
    if (is_crying) {
        ei_printf("  >>> GUI CANH BAO TELEGRAM <<<\n");
        telegram_send_alert(BABY_CRY_LABEL, cry_conf);
    }
    ei_printf("------------------------------------\n");
}

