/**
 * microphone.ino
 * Quản lý toàn bộ I2S driver và FreeRTOS capture task cho INMP441.
 *
 * Public API (được gọi từ baby_guard.ino):
 *   bool microphone_inference_start(uint32_t n_samples)
 *   bool microphone_inference_record(void)
 *   int  microphone_audio_signal_get_data(size_t offset, size_t length, float *out_ptr)
 */

#include "config.h"
#include "audio_types.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/i2s.h"
#include <Baby_Cry_Detection_Large_Data_inferencing.h>  // numpy::int16_to_float

// ─────────────────────────────────────────────
// Module-private globals
// ─────────────────────────────────────────────
inference_t inference;
bool        record_status = true;

static int32_t raw_samples[SAMPLE_BUFFER_SIZE];  // Buffer 32-bit tạm của INMP441

// ─────────────────────────────────────────────
// FreeRTOS Task: liên tục đọc I2S và đổ vào inference.buffer
// ─────────────────────────────────────────────
static void capture_samples(void* arg) {
    size_t bytes_read;

    while (record_status) {
        i2s_read(I2S_PORT, (void*)raw_samples, sizeof(raw_samples),
                 &bytes_read, portMAX_DELAY);

        if (bytes_read > 0) {
            uint32_t samples_read = bytes_read / 4;  // 32-bit → đếm samples

            for (uint32_t i = 0; i < samples_read; i++) {
                // Chuyển 32-bit về 16-bit (dịch phải 14 bit = x8 gain)
                int16_t sample16 = (int16_t)(raw_samples[i] >> SAMPLE_SHIFT);
                inference.buffer[inference.buf_count++] = sample16;

                if (inference.buf_count >= inference.n_samples) {
                    inference.buf_count = 0;
                    inference.buf_ready = 1;
                }
            }
        }
    }

    vTaskDelete(NULL);
}

// ─────────────────────────────────────────────
// Khởi tạo I2S + cấp phát buffer + tạo FreeRTOS task
// ─────────────────────────────────────────────
bool microphone_inference_start(uint32_t n_samples) {
    inference.buffer = (int16_t *)malloc(n_samples * sizeof(int16_t));
    if (inference.buffer == NULL) return false;

    inference.buf_count = 0;
    inference.n_samples = n_samples;
    inference.buf_ready = 0;

    // I2S config cho INMP441 (24-bit output trong frame 32-bit, Left channel)
    i2s_config_t i2s_config = {
        .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate          = EI_CLASSIFIER_FREQUENCY,
        .bits_per_sample      = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_I2S | I2S_COMM_FORMAT_I2S_MSB),
        .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count        = 8,
        .dma_buf_len          = 512,
        .use_apll             = false
    };

    i2s_pin_config_t pin_config = {
        .bck_io_num   = I2S_SCK,
        .ws_io_num    = I2S_WS,
        .data_out_num = -1,  // RX only
        .data_in_num  = I2S_SD
    };

    i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
    i2s_set_pin(I2S_PORT, &pin_config);

    record_status = true;
    xTaskCreate(capture_samples, "CaptureSamples", 1024 * 32, NULL, 10, NULL);
    return true;
}

// ─────────────────────────────────────────────
// Chờ cho đến khi buffer đầy (blocking poll)
// ─────────────────────────────────────────────
bool microphone_inference_record(void) {
    while (inference.buf_ready == 0) {
        delay(10);
    }
    inference.buf_ready = 0;
    return true;
}

// ─────────────────────────────────────────────
// Callback của Edge Impulse signal_t: chuyển int16 → float
// ─────────────────────────────────────────────
int microphone_audio_signal_get_data(size_t offset, size_t length, float *out_ptr) {
    numpy::int16_to_float(&inference.buffer[offset], out_ptr, length);
    return 0;
}
