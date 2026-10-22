#include "device.h"
#include "app_config.h"
#include "board.h"
#include "fpga_link.h"
#include "storage.h"
#include <string.h>

device_context_t g_device;

static bool finite_range(float value, float low, float high)
{
    return (value == value) && value >= low && value <= high;
}

static bool validate(const channel_config_t *c)
{
#if BASIC_SPI_BENCH
    #if NUCLEAR_BENCH
    if(c == NULL || c->enabled>1u || (c->waveform!=1u && c->waveform!=3u) || c->arrival_mode>1u ||
       c->pileup_mode!=0u || !finite_range(c->noise_percent,0.0f,32.0f) || c->seed==0u) return false;
#else
    if(c == NULL || c->enabled > 1u || c->waveform != 1u || c->arrival_mode != 0u ||
       c->pileup_mode != 0u || c->noise_percent != 0.0f) return false;
#endif
    if(!finite_range(c->amplitude_v, 0.0f, 6.24f) || !finite_range(c->baseline_v, 0.0f, 6.24f) ||
       !finite_range(c->decay_us, 1.0f, 100.0f) || !finite_range(c->interval_us, 128.0f, 10000.0f)) return false;
    #if NUCLEAR_BENCH
    float noise=c->noise_percent/BENCH_CODE_SCALE;
    return c->baseline_v>=noise && c->baseline_v+c->amplitude_v+noise<=6.24001f &&
           (c->arrival_mode==1u || c->interval_us>=5.0f*c->decay_us);
#else
    return c->baseline_v + c->amplitude_v <= 6.24001f && c->interval_us >= 5.0f*c->decay_us;
#endif
#else
    if (c == NULL || c->enabled > 1u || c->waveform > 3u || c->arrival_mode > 1u || c->pileup_mode > 1u) return false;
    if (!finite_range(c->amplitude_v, 0.0f, 5.0f) || !finite_range(c->baseline_v, 0.0f, 5.0f)) return false;
    if (!finite_range(c->rise_us, 0.02f, 10000.0f) || !finite_range(c->decay_us, 0.02f, 10000.0f)) return false;
    if (!finite_range(c->fwhm_us, 1.0f, 100.0f) || !finite_range(c->interval_us, 10.0f, 10000.0f)) return false;
    if (!finite_range(c->noise_percent, 0.0f, 20.0f)) return false;
    if ((c->waveform == 2u) && !(c->rise_us < c->decay_us)) return false;
    float sigma = 5.0f * c->noise_percent / 100.0f;
    return (c->baseline_v + c->amplitude_v + 3.0f * sigma) <= 5.001f;
#endif
}

void device_init(void)
{
    memset(&g_device, 0, sizeof(g_device));
    g_device.state = DEVICE_SELF_TEST;
    g_device.power_good = board_power_good();
    g_device.board_a_present = board_a_present();
    g_device.board_b_present = board_b_present();
    g_device.fpga_online = fpga_link_probe();
    g_device.last_host_ms = board_millis();
    memcpy(g_device.source_name, "none", 5u);

    for (uint8_t i = 0; i < 2u; ++i) {
        channel_config_t defaults = {1u, 1u, 0u, 0u, 1.0f, 0.0f, 1.0f, 10.0f, 10.0f, 1000.0f, 0.0f, 0x12345678u + i};
#if BASIC_SPI_BENCH
        defaults.enabled = i == 0u;
        defaults.amplitude_v = 224.0f / BENCH_CODE_SCALE;
        defaults.baseline_v = 16.0f / BENCH_CODE_SCALE;
        defaults.decay_us = 12.0f;
        defaults.fwhm_us = 12.0f * 0.69314718f;
#endif
        g_device.shadow[i] = defaults;
        g_device.active[i] = defaults;
    }
#if BASIC_SPI_BENCH
    g_device.transfer_valid = true;
    memcpy(g_device.source_name, "BENCH-EXP", 10u);
    if (g_device.fpga_online && !fpga_link_stop()) g_device.fpga_online = false;
#endif
    if (!g_device.power_good) device_raise_error(DEV_ERR_POWER);
    else if (!g_device.board_a_present || !g_device.board_b_present) device_raise_error(DEV_ERR_BOARD_MISSING);
    else if (!g_device.fpga_online) device_raise_error(DEV_ERR_FPGA);
    else g_device.state = DEVICE_IDLE;
}

void device_tick_1ms(void) { g_device.uptime_ms++; }

void device_poll(void)
{
    static uint32_t last_poll;
    g_device.power_good = board_power_good();
    g_device.board_a_present = board_a_present();
    g_device.board_b_present = board_b_present();
    if (board_stop_pressed()) device_stop();
    if (g_device.state == DEVICE_RUNNING && board_millis() - g_device.last_host_ms > PC_LINK_TIMEOUT_MS) {
        device_raise_error(DEV_ERR_TRANSFER);
    }
    if (!g_device.power_good) device_raise_error(DEV_ERR_POWER);
    if ((!g_device.board_a_present || !g_device.board_b_present) && g_device.state == DEVICE_RUNNING) device_raise_error(DEV_ERR_BOARD_MISSING);

    if ((board_millis() - last_poll) >= FPGA_POLL_PERIOD_MS) {
        fpga_status_t status;
        last_poll = board_millis();
        if (g_device.fpga_online && fpga_link_status(&status)) {
            memcpy(g_device.clip_count, status.clip_count, sizeof(status.clip_count));
            memcpy(g_device.event_count, status.event_count, sizeof(status.event_count));
            memcpy(g_device.pileup_overflow, status.pileup_overflow, sizeof(status.pileup_overflow));
            if (status.error_flags != 0u) device_raise_error(DEV_ERR_FPGA);
#if BASIC_SPI_BENCH
            if (g_device.state == DEVICE_RUNNING && status.active_generation != g_device.config_generation) device_raise_error(DEV_ERR_FPGA);
#endif
        } else if (g_device.fpga_online) {
            g_device.fpga_online = false;
            device_raise_error(DEV_ERR_FPGA);
        }
    }
}

bool device_set_channel(uint8_t channel, const channel_config_t *config)
{
    if ((channel >= OUTPUT_CHANNELS) || !validate(config)) return false;
    g_device.shadow[channel] = *config;
    return true;
}

bool device_commit(void)
{
    if (g_device.state == DEVICE_RUNNING || g_device.state == DEVICE_ERROR) return false;
    for (uint8_t ch=0; ch<OUTPUT_CHANNELS; ++ch) if (!validate(&g_device.shadow[ch])) return false;
#if NUCLEAR_BENCH
    if(g_device.shadow[0].waveform==3u && !g_device.transfer_valid) return false;
#endif
    uint32_t generation = g_device.config_generation + 1u;
    bool written = true;
    for (uint8_t ch=0; ch<OUTPUT_CHANNELS; ++ch) written = written && fpga_link_write_channel(ch, &g_device.shadow[ch]);
    if (!written || !fpga_link_commit(generation)) {
        device_raise_error(DEV_ERR_FPGA);
        return false;
    }
#if BASIC_SPI_BENCH
    g_device.transfer_valid = true;
#endif
    memcpy(g_device.active, g_device.shadow, sizeof(g_device.active));
    g_device.config_generation = generation;
    g_device.state = DEVICE_CONFIGURED;
    return true;
}

bool device_start(void)
{
    if (g_device.state != DEVICE_CONFIGURED || !g_device.fpga_online || !g_device.power_good ||
        !g_device.board_a_present || !g_device.board_b_present || !g_device.transfer_valid) return false;
    if (!fpga_link_start()) { device_raise_error(DEV_ERR_FPGA); return false; }
    g_device.state = DEVICE_RUNNING;
    return true;
}

bool device_select_preset(uint8_t preset_id, const char *name)
{
#if BASIC_SPI_BENCH
    (void)preset_id; (void)name;
    return false;
#else
    if (preset_id >= 3u || name == NULL || g_device.state == DEVICE_RUNNING ||
        g_device.state == DEVICE_ERROR || !fpga_link_select_preset(preset_id)) return false;
    size_t length = strlen(name);
    if (length >= sizeof(g_device.source_name)) length = sizeof(g_device.source_name) - 1u;
    memcpy(g_device.source_name, name, length);
    g_device.source_name[length] = '\0';
    g_device.transfer_valid = true;
    return true;
#endif
}

void device_stop(void)
{
    if (!fpga_link_stop()) {
        g_device.fpga_online = false;
        g_device.error = DEV_ERR_FPGA;
        g_device.state = DEVICE_ERROR;
        return;
    }
    if (g_device.state != DEVICE_ERROR) g_device.state = DEVICE_IDLE;
}

void device_raise_error(device_error_t error)
{
    (void)fpga_link_stop();
    g_device.error = error;
    g_device.state = DEVICE_ERROR;
}

bool device_clear_error(void)
{
    if (!board_power_good() || !board_a_present() || !board_b_present() || !fpga_link_probe()) return false;
    if (!fpga_link_stop()) return false;
    g_device.error = DEV_OK;
    g_device.fpga_online = true;
    g_device.state = DEVICE_IDLE;
    return true;
}

const char *device_state_name(device_state_t state)
{
    static const char *names[] = {"BOOT", "SELFTEST", "IDLE", "CONFIG", "RUN", "ERROR"};
    return state <= DEVICE_ERROR ? names[state] : "UNKNOWN";
}

const char *device_error_name(device_error_t error)
{
    static const char *names[] = {"OK", "BAD STATE", "BAD PARAM", "FPGA", "POWER", "BOARD", "TRANSFER", "CRC", "STORAGE"};
    return error <= DEV_ERR_STORAGE ? names[error] : "UNKNOWN";
}
