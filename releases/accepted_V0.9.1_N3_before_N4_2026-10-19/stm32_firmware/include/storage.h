#ifndef STORAGE_H
#define STORAGE_H

#include "device.h"
#include <stdbool.h>
#include <stdint.h>

typedef struct { float gain; float offset; } calibration_t;

void storage_init(void);
bool storage_save_profile(uint8_t id, const channel_config_t channels[2]);
bool storage_load_profile(uint8_t id, channel_config_t channels[2]);
const calibration_t *storage_calibration(uint8_t channel);
uint32_t storage_calibration_crc(void);

#endif
