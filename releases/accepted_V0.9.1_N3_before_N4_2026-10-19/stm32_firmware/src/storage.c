#include "storage.h"
#include "crc32.h"
#include "stm32f4xx_flash.h"
#include <stddef.h>
#include <string.h>

#define PROFILE_COUNT 4u
#define STORAGE_ADDRESS 0x080E0000u
#define STORAGE_MAGIC 0x4E534346u
#define STORAGE_VERSION 1u

typedef struct {
    channel_config_t channels[2];
    uint32_t crc;
    uint32_t valid;
} profile_t;

typedef struct {
    uint32_t magic;
    uint32_t version;
    calibration_t calibration[2];
    profile_t profiles[PROFILE_COUNT];
    uint32_t crc;
} storage_blob_t;

static storage_blob_t s_blob;

static uint32_t blob_crc(const storage_blob_t *blob)
{
    return crc32_compute((const uint8_t *)blob, offsetof(storage_blob_t, crc));
}

static bool persist(void)
{
    s_blob.crc = blob_crc(&s_blob);
    FLASH_Unlock();
    FLASH_ClearFlag(FLASH_FLAG_EOP | FLASH_FLAG_OPERR | FLASH_FLAG_WRPERR |
                    FLASH_FLAG_PGAERR | FLASH_FLAG_PGPERR | FLASH_FLAG_PGSERR);
    if (FLASH_EraseSector(FLASH_Sector_11, VoltageRange_3) != FLASH_COMPLETE) {
        FLASH_Lock();
        return false;
    }
    const uint32_t *words = (const uint32_t *)&s_blob;
    for (size_t i = 0u; i < sizeof(s_blob) / sizeof(uint32_t); ++i) {
        if (FLASH_ProgramWord(STORAGE_ADDRESS + (uint32_t)(i * 4u), words[i]) != FLASH_COMPLETE) {
            FLASH_Lock();
            return false;
        }
    }
    FLASH_Lock();
    return memcmp((const void *)STORAGE_ADDRESS, &s_blob, sizeof(s_blob)) == 0;
}

void storage_init(void)
{
    const storage_blob_t *flash_blob = (const storage_blob_t *)STORAGE_ADDRESS;
    if (flash_blob->magic == STORAGE_MAGIC && flash_blob->version == STORAGE_VERSION &&
        flash_blob->crc == blob_crc(flash_blob)) {
        memcpy(&s_blob, flash_blob, sizeof(s_blob));
        return;
    }
    memset(&s_blob, 0, sizeof(s_blob));
    s_blob.magic = STORAGE_MAGIC;
    s_blob.version = STORAGE_VERSION;
    s_blob.calibration[0].gain = 1.0f;
    s_blob.calibration[1].gain = 1.0f;
}

bool storage_save_profile(uint8_t id, const channel_config_t channels[2])
{
    if ((id >= PROFILE_COUNT) || (channels == NULL)) return false;
    profile_t *profile = &s_blob.profiles[id];
    memcpy(profile->channels, channels, sizeof(profile->channels));
    profile->crc = crc32_compute((const uint8_t *)profile->channels, sizeof(profile->channels));
    profile->valid = 1u;
    return persist();
}

bool storage_load_profile(uint8_t id, channel_config_t channels[2])
{
    if ((id >= PROFILE_COUNT) || (channels == NULL)) return false;
    const profile_t *profile = &s_blob.profiles[id];
    if (profile->valid != 1u || profile->crc != crc32_compute((const uint8_t *)profile->channels, sizeof(profile->channels))) return false;
    memcpy(channels, profile->channels, sizeof(profile->channels));
    return true;
}

const calibration_t *storage_calibration(uint8_t channel)
{
    return channel < 2u ? &s_blob.calibration[channel] : NULL;
}

uint32_t storage_calibration_crc(void)
{
    return crc32_compute((const uint8_t *)s_blob.calibration, sizeof(s_blob.calibration));
}
