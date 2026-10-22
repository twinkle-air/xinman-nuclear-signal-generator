#ifndef FPGA_LINK_H
#define FPGA_LINK_H

#include "device.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t clip_count[2];
    uint32_t event_count[2];
    uint32_t pileup_overflow[2];
    uint32_t active_generation;
    uint32_t error_flags;
} fpga_status_t;

void fpga_link_init(void);
bool fpga_link_probe(void);
bool fpga_link_write_channel(uint8_t channel, const channel_config_t *config);
bool fpga_link_commit(uint32_t generation);
bool fpga_link_start(void);
bool fpga_link_stop(void);
bool fpga_link_status(fpga_status_t *status);
bool fpga_link_data_begin(uint32_t bytes);
bool fpga_link_data_write(uint32_t offset, const uint8_t *data, size_t length);
bool fpga_link_data_end(uint32_t crc32);
bool fpga_link_select_preset(uint8_t preset_id);
const char *fpga_link_version(void);

#endif
