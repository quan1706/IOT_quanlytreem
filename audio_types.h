/**
 * audio_types.h
 * Shared types và extern declarations để các file .ino khác dùng chung.
 */
#ifndef AUDIO_TYPES_H
#define AUDIO_TYPES_H

#include <stdint.h>

// ─────────────────────────────────────────────
// Audio Inference Buffer
// ─────────────────────────────────────────────
typedef struct {
    int16_t  *buffer;     // Pointer tới heap-allocated sample buffer
    uint8_t   buf_ready;  // 1 = buffer đã đầy, sẵn sàng classify
    uint32_t  buf_count;  // Số samples đã ghi vào buffer
    uint32_t  n_samples;  // Tổng số samples cần thiết (= EI_CLASSIFIER_RAW_SAMPLE_COUNT)
} inference_t;

// ─────────────────────────────────────────────
// Extern – defined in microphone.ino
// ─────────────────────────────────────────────
extern inference_t inference;
extern bool        record_status;

#endif // AUDIO_TYPES_H
