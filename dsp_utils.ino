/**
 * dsp_utils.ino
 * Chứa các hàm toán học bổ trợ để lọc nhiễu và xác nhận tiếng khóc.
 */

#include <math.h>
#include "config.h"

// ─────────────────────────────────────────────
// 1. Tính độ lớn trung bình (RMS - Root Mean Square)
// Dùng để phát hiện xem có âm thanh nào không hay chỉ là im lặng.
// ─────────────────────────────────────────────
float calculate_rms(int16_t *buffer, uint32_t length) {
    double sum = 0;
    for (uint32_t i = 0; i < length; i++) {
        sum += (double)buffer[i] * (double)buffer[i];
    }
    return (float)sqrt(sum / (double)length);
}

// ─────────────────────────────────────────────
// 2. Tính tỉ lệ đổi dấu (ZCR - Zero Crossing Rate)
// Tiếng khóc có ZCR đặc trưng. Tiếng ồn trắng hoặc gió có ZCR rất cao.
// ─────────────────────────────────────────────
float calculate_zcr(int16_t *buffer, uint32_t length) {
    uint32_t crossings = 0;
    for (uint32_t i = 1; i < length; i++) {
        // Kiểm tra xem tín hiệu có đổi dấu từ i-1 sang i không
        if ((buffer[i-1] >= 0 && buffer[i] < 0) || (buffer[i-1] < 0 && buffer[i] >= 0)) {
            crossings++;
        }
    }
    return (float)crossings / (float)length;
}

// ─────────────────────────────────────────────
// 3. Thuật toán Goertzel (Lọc dải tần mục tiêu)
// Dùng để kiểm tra xem có năng lượng tại tần số f (ví dụ 450Hz) không.
// Nhẹ hơn rất nhiều so với chạy full FFT.
// ─────────────────────────────────────────────
float goertzel_mag(int16_t *buffer, uint32_t length, float target_freq, float sample_rate) {
    float k = 0.5f + ((float)length * target_freq) / sample_rate;
    float omega = (2.0f * M_PI * k) / (float)length;
    float sine = sin(omega);
    float cosine = cos(omega);
    float coeff = 2.0f * cosine;

    float q0 = 0, q1 = 0, q2 = 0;

    for (uint32_t i = 0; i < length; i++) {
        q0 = coeff * q1 - q2 + (float)buffer[i];
        q2 = q1;
        q1 = q0;
    }

    float magnitude = sqrt(q1 * q1 + q2 * q2 - q1 * q2 * coeff);
    return magnitude / (length / 2.0f); // Normalized magnitude
}
