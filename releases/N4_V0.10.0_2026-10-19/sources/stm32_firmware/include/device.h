#ifndef DEVICE_H
#define DEVICE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
    DEVICE_BOOT = 0,
    DEVICE_SELF_TEST,
    DEVICE_IDLE,
    DEVICE_CONFIGURED,
    DEVICE_RUNNING,
    DEVICE_ERROR
} device_state_t;

typedef enum {
    DEV_OK = 0,
    DEV_ERR_BAD_STATE,
    DEV_ERR_BAD_PARAM,
    DEV_ERR_FPGA,
    DEV_ERR_POWER,
    DEV_ERR_BOARD_MISSING,
    DEV_ERR_TRANSFER,
    DEV_ERR_CRC,
    DEV_ERR_STORAGE
} device_error_t;

typedef struct {
    uint8_t enabled;
    uint8_t waveform;
    uint8_t arrival_mode;
    uint8_t pileup_mode;
    float amplitude_v;
    float baseline_v;
    float rise_us;
    float decay_us;
    float fwhm_us;
    float interval_us;
    float noise_percent;
    uint32_t seed;
#if COMPETITION_BENCH
    uint8_t noise_mode; /* N4: 0 uniform peak codes, 1 Gaussian RMS percent FS. */
#endif
} channel_config_t;

typedef struct {
    device_state_t state;
    device_error_t error;
    channel_config_t active[2];
    channel_config_t shadow[2];
    uint32_t config_generation;
    uint32_t clip_count[2];
    uint32_t event_count[2];
    uint32_t pileup_overflow[2];
    uint32_t uptime_ms;
    uint32_t last_host_ms;
    bool fpga_online;
    bool board_a_present;
    bool board_b_present;
    bool power_good;
    bool transfer_valid;
    char source_name[32];
} device_context_t;

extern device_context_t g_device;

void device_init(void);
void device_tick_1ms(void);
void device_poll(void);
bool device_set_channel(uint8_t channel, const channel_config_t *config);
bool device_commit(void);
bool device_start(void);
bool device_select_preset(uint8_t preset_id, const char *name);
void device_stop(void);
void device_raise_error(device_error_t error);
bool device_clear_error(void);
const char *device_state_name(device_state_t state);
const char *device_error_name(device_error_t error);

#endif
