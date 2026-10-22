#ifndef CRC32_H
#define CRC32_H
#include <stddef.h>
#include <stdint.h>
uint32_t crc32_update(uint32_t crc, const uint8_t *data, size_t length);
uint32_t crc32_compute(const uint8_t *data, size_t length);
#endif
