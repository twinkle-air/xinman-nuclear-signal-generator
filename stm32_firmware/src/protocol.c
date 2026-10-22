#include "protocol.h"
#include "app_config.h"
#include "board.h"
#include "crc32.h"
#include "device.h"
#include "fpga_link.h"
#include "storage.h"
#include "transport.h"
#include "ui.h"
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <stdint.h>

enum {
    FLAG_ACK_REQ = 1u,
    FLAG_ACK = 2u,
    FLAG_ERROR = 4u,
    CMD_HELLO = 0x0001,
    CMD_GET_STATUS = 0x0002,
    CMD_SET_PARAM = 0x0010,
    CMD_COMMIT = 0x0011,
    CMD_DATA_BEGIN = 0x0020,
    CMD_DATA_CHUNK = 0x0021,
    CMD_DATA_END = 0x0022,
    CMD_START = 0x0030,
    CMD_STOP = 0x0031,
    CMD_SELECT_PRESET = 0x0040,
    CMD_READ_HIST = 0x0050,
    CMD_SAVE_PROFILE = 0x0060,
    CMD_LOAD_PROFILE = 0x0061
};

#define FRAME_OVERHEAD 16u
#define FRAME_MAX (PROTOCOL_MAX_PAYLOAD + FRAME_OVERHEAD)

static uint8_t s_input[FRAME_MAX];
static size_t s_input_length;
static uint8_t s_last_reply[FRAME_MAX];
static size_t s_last_reply_length;
static uint16_t s_last_sequence;
static uint16_t s_last_command;
static bool s_have_last;
static uint32_t s_transfer_bytes;
static uint32_t s_transfer_offset;
static uint32_t s_transfer_crc;
static bool s_transfer_active;

static uint16_t get_u16(const uint8_t *p) { return (uint16_t)p[0] | ((uint16_t)p[1] << 8u); }
static uint32_t get_u32(const uint8_t *p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8u) | ((uint32_t)p[2] << 16u) | ((uint32_t)p[3] << 24u); }
static void put_u16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8u); }
static void put_u32(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8u); p[2] = (uint8_t)(v >> 16u); p[3] = (uint8_t)(v >> 24u); }

static const char *json_value(const char *json, const char *key)
{
    static char pattern[40];
    (void)snprintf(pattern, sizeof(pattern), "\"%s\":", key);
    const char *p = strstr(json, pattern);
    if (p == NULL) return NULL;
    p += strlen(pattern);
    while (*p == ' ' || *p == '\t') ++p;
    return p;
}

static bool json_float(const char *json, const char *key, float *value)
{
    const char *p = json_value(json, key);
    char *end;
    if (p == NULL) return false;
    *value = strtof(p, &end);
    return end != p;
}

static bool json_u32(const char *json, const char *key, uint32_t *value)
{
    const char *p = json_value(json, key);
    char *end;
    if (p == NULL || *p < '0' || *p > '9') return false;
    errno = 0;
    unsigned long parsed = strtoul(p, &end, 10);
    if (end == p || errno == ERANGE || parsed > UINT32_MAX) return false;
    while (*end == ' ' || *end == '\t' || *end == '\r' || *end == '\n') ++end;
    if (*end != ',' && *end != '}' && *end != '\0') return false;
    *value = (uint32_t)parsed;
    return true;
}

static bool json_bool(const char *json, const char *key, uint8_t *value)
{
    const char *p = json_value(json, key);
    if (p == NULL) return false;
    if (strncmp(p, "true", 4u) == 0) { *value = 1u; return true; }
    if (strncmp(p, "false", 5u) == 0) { *value = 0u; return true; }
    return false;
}

static bool json_string(const char *json, const char *key, char *value, size_t capacity)
{
    const char *p = json_value(json, key);
    if (p == NULL || *p++ != '"' || capacity == 0u) return false;
    size_t count = 0u;
    while (*p != '\0' && *p != '"' && count + 1u < capacity) value[count++] = *p++;
    value[count] = '\0';
    return *p == '"';
}

static void send_reply(uint16_t command, uint16_t sequence, bool error,
                       const uint8_t *payload, uint32_t length)
{
    if (length > PROTOCOL_MAX_PAYLOAD) length = PROTOCOL_MAX_PAYLOAD;
    uint8_t *frame = s_last_reply;
    frame[0] = 0xA5u; frame[1] = 0x5Au;
    frame[2] = PROTOCOL_VERSION;
    frame[3] = error ? (FLAG_ACK | FLAG_ERROR) : FLAG_ACK;
    put_u16(frame + 4u, command);
    put_u16(frame + 6u, sequence);
    put_u32(frame + 8u, length);
    if (length != 0u && payload != NULL) memcpy(frame + 12u, payload, length);
    put_u32(frame + 12u + length, crc32_compute(frame + 2u, 10u + length));
    s_last_reply_length = 16u + length;
    s_last_sequence = sequence;
    s_last_command = command;
    s_have_last = true;
    transport_write(frame, s_last_reply_length);
}

static void send_text(uint16_t command, uint16_t sequence, bool error, const char *text)
{
    send_reply(command, sequence, error, (const uint8_t *)text, (uint32_t)strlen(text));
}

static bool parse_channel(const char *json, channel_config_t *config, uint8_t *channel)
{
    uint32_t ch;
    char text[24];
    if (!json_u32(json, "channel", &ch) || ch < 1u || ch > OUTPUT_CHANNELS) return false;
    *channel = (uint8_t)(ch - 1u);
    *config = g_device.shadow[*channel];
    (void)json_bool(json, "enabled", &config->enabled);
    if (json_string(json, "pulse_shape", text, sizeof(text))) config->waveform = strstr(text, "双") != NULL ? 2u : 1u;
    if (json_string(json, "arrival_mode", text, sizeof(text))) config->arrival_mode = strstr(text, "泊松") != NULL ? 1u : 0u;
    if (json_string(json, "pileup_mode", text, sizeof(text))) config->pileup_mode = strcmp(text, "PILEUP") == 0 ? 1u : 0u;
    (void)json_float(json, "amplitude_v", &config->amplitude_v);
    (void)json_float(json, "baseline_v", &config->baseline_v);
    (void)json_float(json, "rise_us", &config->rise_us);
    (void)json_float(json, "decay_us", &config->decay_us);
    (void)json_float(json, "mean_interval_us", &config->interval_us);
    (void)json_float(json, "noise_rms_percent", &config->noise_percent);
    if (json_value(json,"seed") != NULL && !json_u32(json,"seed",&config->seed)) return false;
#if BASIC_SPI_BENCH
    /* Bench output has not been calibrated: accept explicit DAC codes only. */
    if (strstr(json, "\"amplitude_v\"") || strstr(json, "\"baseline_v\"")) return false;
    uint32_t code;
    if (json_value(json,"dac_baseline_code") != NULL && !json_u32(json,"dac_baseline_code",&code)) return false;
    if (json_u32(json, "dac_baseline_code", &code)) {
        if (code > 255u) return false;
        config->baseline_v = (float)code / BENCH_CODE_SCALE;
    }
    if (json_value(json,"dac_amplitude_code") != NULL && !json_u32(json,"dac_amplitude_code",&code)) return false;
    if (json_u32(json, "dac_amplitude_code", &code)) {
        if (code > 255u) return false;
        config->amplitude_v = (float)code / BENCH_CODE_SCALE;
    }
#endif
#if NUCLEAR_BENCH
    uint32_t mode=0,noise=0,spectrum=0;
    if(!json_u32(json,"random_events",&mode) || mode>1u ||
       !json_u32(json,"noise_peak_codes",&noise) || noise>32u ||
       !json_u32(json,"spectrum_enabled",&spectrum) || spectrum>1u) return false;
    config->arrival_mode=(uint8_t)mode;config->noise_percent=(float)noise;
    config->waveform=spectrum ? 3u : 1u;
#if COMPETITION_BENCH
    uint32_t rms=0,pileup=0;
    char noise_kind[12];
    if(!json_string(json,"noise_mode",noise_kind,sizeof(noise_kind)) ||
       (strcmp(noise_kind,"gaussian")!=0 && strcmp(noise_kind,"uniform")!=0) ||
       !json_u32(json,"noise_rms_percent",&rms) || rms>20u ||
       !json_u32(json,"allow_pileup",&pileup) || pileup>1u) return false;
    config->noise_mode=(uint8_t)(strcmp(noise_kind,"gaussian")==0);
    if((config->noise_mode && noise) || (!config->noise_mode && rms)) return false;
    config->noise_percent=(float)(config->noise_mode ? rms : noise);
    config->pileup_mode=(uint8_t)pileup;
#endif
#endif
    config->fwhm_us = config->decay_us * 0.69314718f;
    return true;
}

static void handle_frame(uint16_t command, uint16_t sequence, const uint8_t *payload, uint32_t length)
{
    char json[PROTOCOL_MAX_PAYLOAD + 1u];
    char response[768];
    if (s_have_last && sequence == s_last_sequence && command == s_last_command) {
        transport_write(s_last_reply, s_last_reply_length);
        return;
    }
    if (length > PROTOCOL_MAX_PAYLOAD) { send_text(command, sequence, true, "payload too large"); return; }
    memcpy(json, payload, length); json[length] = '\0';
    g_device.last_host_ms = board_millis();

    switch (command) {
    case CMD_HELLO:
        (void)snprintf(response, sizeof(response),
            "{\"firmware\":\"%s\",\"fpga\":\"%s\",\"calibration\":\"%s\",\"transport\":\"CH340-USART1\",\"channels\":%u,\"bench\":%s}",
            FW_VERSION, fpga_link_version(), BASIC_SPI_BENCH ? "UNCALIBRATED-CODES" : CAL_VERSION,
            OUTPUT_CHANNELS, BASIC_SPI_BENCH ? "true" : "false");
        send_text(command, sequence, false, response);
        break;
    case CMD_GET_STATUS:
#if BASIC_SPI_BENCH
        (void)snprintf(response, sizeof(response),
            "{\"state\":\"%s\",\"error\":\"%s\",\"fpga\":%s,\"board_a\":null,\"board_b\":null,\"power_good\":null,\"safety_bypass\":true,\"generation\":%lu,\"dac_baseline_code\":%u,\"dac_amplitude_code\":%u,\"period_us\":%.0f,\"decay_us\":%.2f}",
            device_state_name(g_device.state), device_error_name(g_device.error),
            g_device.fpga_online ? "true" : "false", (unsigned long)g_device.config_generation,
            (unsigned)(g_device.active[0].baseline_v*BENCH_CODE_SCALE+0.5f),
            (unsigned)(g_device.active[0].amplitude_v*BENCH_CODE_SCALE+0.5f),
            (double)g_device.active[0].interval_us, (double)g_device.active[0].decay_us);
#if NUCLEAR_BENCH
        size_t used=strlen(response);
        if(used>0u) (void)snprintf(response+used-1u,sizeof(response)-used+1u,
            ",\"random_events\":%u,\"noise_peak_codes\":%u,\"spectrum_enabled\":%u,\"seed\":%lu,\"spectrum_crc32\":%lu,\"events\":%lu,\"clips\":%lu}",
            (unsigned)g_device.active[0].arrival_mode,
#if COMPETITION_BENCH
            g_device.active[0].noise_mode ? 0u :
#endif
            (unsigned)g_device.active[0].noise_percent,
            g_device.active[0].waveform==3u,(unsigned long)g_device.active[0].seed,
            (unsigned long)(g_device.transfer_valid ? s_transfer_crc : 0u),
            (unsigned long)g_device.event_count[0],(unsigned long)g_device.clip_count[0]);
#if COMPETITION_BENCH
        used=strlen(response);
        if(used>0u) (void)snprintf(response+used-1u,sizeof(response)-used+1u,
            ",\"noise_mode\":\"%s\",\"noise_rms_percent\":%u,\"allow_pileup\":%u}",
            g_device.active[0].noise_mode ? "gaussian" : "uniform",
            g_device.active[0].noise_mode ? (unsigned)g_device.active[0].noise_percent : 0u,
            (unsigned)g_device.active[0].pileup_mode);
#endif
#endif
#else
        (void)snprintf(response, sizeof(response),
            "{\"state\":\"%s\",\"error\":\"%s\",\"fpga\":%s,\"board_a\":%s,\"board_b\":%s,\"power_good\":%s,\"generation\":%lu,\"clip1\":%lu,\"clip2\":%lu,\"rx_overflow\":%lu}",
            device_state_name(g_device.state), device_error_name(g_device.error),
            g_device.fpga_online ? "true" : "false", g_device.board_a_present ? "true" : "false",
            g_device.board_b_present ? "true" : "false", g_device.power_good ? "true" : "false",
            (unsigned long)g_device.config_generation, (unsigned long)g_device.clip_count[0],
            (unsigned long)g_device.clip_count[1], (unsigned long)transport_rx_overflows());
#endif
        send_text(command, sequence, false, response);
        break;
    case CMD_SET_PARAM: {
        channel_config_t config; uint8_t channel;
        if (!parse_channel(json, &config, &channel) || !device_set_channel(channel, &config)) send_text(command, sequence, true, "invalid channel parameters or output envelope");
        else send_text(command, sequence, false, "{\"accepted\":true}");
        break;
    }
    case CMD_COMMIT:
        if (device_commit()) { ui_force_refresh(); send_text(command, sequence, false, "{\"committed\":true}"); }
        else send_text(command, sequence, true, "commit failed");
        break;
    case CMD_DATA_BEGIN: {
        uint32_t bytes = 0u;
#if NUCLEAR_BENCH
        if(g_device.state!=DEVICE_IDLE) {send_text(command,sequence,true,"table upload requires IDLE");break;}
#endif
        if (!json_u32(json, "bytes", &bytes) || bytes == 0u || bytes > SIGNAL_BUFFER_SIZE || !fpga_link_data_begin(bytes)) {
            send_text(command, sequence, true, "invalid transfer size or FPGA not ready"); break;
        }
        (void)json_string(json, "name", g_device.source_name, sizeof(g_device.source_name));
        s_transfer_bytes = bytes; s_transfer_offset = 0u; s_transfer_crc = 0u; s_transfer_active = true; g_device.transfer_valid = false;
        send_text(command, sequence, false, "{\"offset\":0}");
        break;
    }
    case CMD_DATA_CHUNK: {
        if (!s_transfer_active || length < 4u) { send_text(command, sequence, true, "no active transfer"); break; }
        uint32_t offset = get_u32(payload); size_t count = length - 4u;
        if (offset != s_transfer_offset || offset + count > s_transfer_bytes) { send_text(command, sequence, true, "unexpected chunk offset"); break; }
        size_t sent = 0u;
        while (sent < count) {
            size_t part = count - sent; if (part > 256u) part = 256u;
            if (!fpga_link_data_write(offset + (uint32_t)sent, payload + 4u + sent, part)) break;
            sent += part;
        }
        if (sent != count) { s_transfer_active = false; send_text(command, sequence, true, "FPGA transfer failed"); break; }
        s_transfer_crc = crc32_update(s_transfer_crc, payload + 4u, count);
        s_transfer_offset += (uint32_t)count;
        (void)snprintf(response, sizeof(response), "{\"offset\":%lu}", (unsigned long)s_transfer_offset);
        send_text(command, sequence, false, response);
        break;
    }
    case CMD_DATA_END: {
        uint32_t bytes, expected_crc;
        if (!s_transfer_active || !json_u32(json, "bytes", &bytes) || !json_u32(json, "crc32", &expected_crc) ||
            bytes != s_transfer_bytes || s_transfer_offset != bytes || expected_crc != s_transfer_crc || !fpga_link_data_end(expected_crc)) {
            s_transfer_active = false; send_text(command, sequence, true, "transfer CRC or length mismatch"); break;
        }
        s_transfer_active = false; g_device.transfer_valid = true;
        send_text(command, sequence, false, "{\"verified\":true}");
        break;
    }
    case CMD_START:
        if (device_start()) { ui_force_refresh(); send_text(command, sequence, false, "{\"running\":true}"); }
        else send_text(command, sequence, true, "device is not safely configured");
        break;
    case CMD_STOP:
        device_stop(); ui_force_refresh();
        send_text(command, sequence, g_device.state == DEVICE_ERROR, g_device.state == DEVICE_ERROR ? "stop or link failed" : "{\"running\":false}");
        break;
    case CMD_SELECT_PRESET:
        if (json_string(json, "name", response, sizeof(response))) {
            uint8_t preset = strcmp(response, "Am-241") == 0 ? 0u : strcmp(response, "Cs-137") == 0 ? 1u : strcmp(response, "Co-60") == 0 ? 2u : 0xFFu;
            if (device_select_preset(preset, response)) send_text(command, sequence, false, "{\"selected\":true}");
            else send_text(command, sequence, true, "unknown preset or FPGA rejected it");
        } else send_text(command, sequence, true, "preset name missing");
        break;
    case CMD_READ_HIST:
        (void)snprintf(response, sizeof(response),
            "{\"events\":[%lu,%lu],\"clips\":[%lu,%lu],\"pileup_overflow\":[%lu,%lu]}",
            (unsigned long)g_device.event_count[0], (unsigned long)g_device.event_count[1],
            (unsigned long)g_device.clip_count[0], (unsigned long)g_device.clip_count[1],
            (unsigned long)g_device.pileup_overflow[0], (unsigned long)g_device.pileup_overflow[1]);
        send_text(command, sequence, false, response);
        break;
    case CMD_SAVE_PROFILE: {
#if BASIC_SPI_BENCH
        send_text(command, sequence, true, "profiles unavailable in code-domain bench build"); break;
#endif
        uint32_t id = 0u; (void)json_u32(json, "id", &id);
        if (storage_save_profile((uint8_t)id, g_device.active)) send_text(command, sequence, false, "{\"saved\":true}");
        else send_text(command, sequence, true, "profile save failed");
        break;
    }
    case CMD_LOAD_PROFILE: {
#if BASIC_SPI_BENCH
        send_text(command, sequence, true, "profiles unavailable in code-domain bench build"); break;
#endif
        uint32_t id = 0u; (void)json_u32(json, "id", &id);
        if (storage_load_profile((uint8_t)id, g_device.shadow)) send_text(command, sequence, false, "{\"loaded\":true}");
        else send_text(command, sequence, true, "profile not found");
        break;
    }
    case 0x0070: /* Recover after initial FPGA-offline/power-up ordering errors. */
        if (device_clear_error()) send_text(command, sequence, false, "{\"recovered\":true}");
        else send_text(command, sequence, true, "FPGA probe/stop failed");
        break;
    default:
        send_text(command, sequence, true, "unsupported command");
        break;
    }
}

void protocol_init(void)
{
    s_input_length = 0u; s_have_last = false; s_transfer_active = false;
}

void protocol_feed(const uint8_t *data, size_t length)
{
    while (length-- != 0u) {
        if (s_input_length < sizeof(s_input)) s_input[s_input_length++] = *data++;
        else { memmove(s_input, s_input + 1u, sizeof(s_input) - 1u); s_input[sizeof(s_input) - 1u] = *data++; }
    }
}

void protocol_poll(void)
{
    while (s_input_length >= FRAME_OVERHEAD) {
        size_t start = 0u;
        while (start + 1u < s_input_length && !(s_input[start] == 0xA5u && s_input[start + 1u] == 0x5Au)) ++start;
        if (start != 0u) { memmove(s_input, s_input + start, s_input_length - start); s_input_length -= start; }
        if (s_input_length < FRAME_OVERHEAD) return;
        uint32_t length = get_u32(s_input + 8u);
        if (length > PROTOCOL_MAX_PAYLOAD) { memmove(s_input, s_input + 2u, s_input_length - 2u); s_input_length -= 2u; continue; }
        size_t total = 16u + length;
        if (s_input_length < total) return;
        uint32_t expected = get_u32(s_input + 12u + length);
        uint32_t actual = crc32_compute(s_input + 2u, 10u + length);
        if (expected == actual && s_input[2] == PROTOCOL_VERSION) {
            handle_frame(get_u16(s_input + 4u), get_u16(s_input + 6u), s_input + 12u, length);
        }
        memmove(s_input, s_input + total, s_input_length - total);
        s_input_length -= total;
    }
}
