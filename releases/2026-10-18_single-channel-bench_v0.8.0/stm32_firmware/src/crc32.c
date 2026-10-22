#include "crc32.h"

uint32_t crc32_update(uint32_t crc, const uint8_t *data, size_t length)
{
    crc = ~crc;
    while (length-- != 0u) {
        crc ^= *data++;
        for (uint32_t bit = 0; bit < 8u; ++bit) {
            crc = (crc >> 1u) ^ (0xEDB88320u & (uint32_t)-(int32_t)(crc & 1u));
        }
    }
    return ~crc;
}

uint32_t crc32_compute(const uint8_t *data, size_t length)
{
    return crc32_update(0u, data, length);
}
