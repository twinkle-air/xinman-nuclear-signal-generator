#include "fpga_link.h"
#include "app_config.h"
#include "board.h"
#include "crc32.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_spi.h"
#include <string.h>
#if BASIC_SPI_BENCH
#include <math.h>
#endif

enum {
    FPGA_CMD_READ = 0x10,
    FPGA_CMD_WRITE = 0x20,
    FPGA_CMD_STREAM = 0x30,
    FPGA_REG_MAGIC = 0x0000,
    FPGA_REG_VERSION = 0x0004,
    FPGA_REG_CONTROL = 0x0010,
    FPGA_REG_STATUS = 0x0020,
    FPGA_REG_GENERATION = 0x0040,
    FPGA_REG_CH1 = 0x0100,
    FPGA_REG_CH2 = 0x0140,
    FPGA_REG_DATA_INFO = 0x0200,
    FPGA_REG_DATA_FIFO = 0x0208,
    FPGA_REG_PRESET = 0x0210
};

#define FPGA_MAGIC 0x4E534647u /* "NSFG" */

typedef struct __attribute__((packed)) {
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
} fpga_channel_wire_t;

static char s_version[16] = FPGA_VERSION_FALLBACK;
static bool s_spi_failed;
#if BASIC_SPI_BENCH
static uint8_t s_bench_wire[8];
#if NUCLEAR_BENCH
static uint8_t s_nuclear_wire[12];
#endif
#endif

static uint8_t spi_byte(uint8_t value)
{
    if (s_spi_failed) return 0u;
    uint32_t started = board_millis();
    while (SPI_I2S_GetFlagStatus(SPI1, SPI_I2S_FLAG_TXE) == RESET) {
        if (board_millis() - started >= 2u) { s_spi_failed = true; return 0u; }
    }
    SPI_I2S_SendData(SPI1, value);
    while (SPI_I2S_GetFlagStatus(SPI1, SPI_I2S_FLAG_RXNE) == RESET) {
        if (board_millis() - started >= 2u) { s_spi_failed = true; return 0u; }
    }
    return (uint8_t)SPI_I2S_ReceiveData(SPI1);
}

static void cs_settle(void)
{
    /* >1 us at 168 MHz; lets the FPGA's synchronizers observe CS/last ACK. */
    for (volatile uint32_t i = 0; i < 200u; ++i) __NOP();
}

static void select_fpga(bool select)
{
    if (select) GPIO_ResetBits(FPGA_CS_PORT, FPGA_CS_PIN);
    else GPIO_SetBits(FPGA_CS_PORT, FPGA_CS_PIN);
}

static bool ready(void)
{
    return GPIO_ReadInputDataBit(FPGA_READY_PORT, FPGA_READY_PIN) != Bit_RESET;
}

static bool transaction(uint8_t command, uint16_t address, const uint8_t *tx,
                        uint8_t *rx, uint16_t length)
{
    uint8_t header[5] = {command, (uint8_t)address, (uint8_t)(address >> 8u),
                         (uint8_t)length, (uint8_t)(length >> 8u)};
    uint32_t crc = crc32_compute(header, sizeof(header));
    if ((command != FPGA_CMD_READ) && (tx != NULL)) crc = crc32_update(crc, tx, length);
    if (!ready()) return false;
    s_spi_failed = false;

    select_fpga(true);
    cs_settle();
    for (size_t i = 0; i < sizeof(header); ++i) (void)spi_byte(header[i]);
    for (uint16_t i = 0; i < length; ++i) {
        uint8_t value = spi_byte((command == FPGA_CMD_READ) ? 0u : tx[i]);
        if (rx != NULL) rx[i] = value;
    }
    for (uint32_t shift = 0; shift < 32u; shift += 8u) (void)spi_byte((uint8_t)(crc >> shift));
    uint8_t ack = spi_byte(0u);
    cs_settle();
    select_fpga(false);
    cs_settle();
    return !s_spi_failed && ack == 0x79u;
}

void fpga_link_init(void)
{
    GPIO_InitTypeDef gpio;
    SPI_InitTypeDef spi;
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA | RCC_AHB1Periph_GPIOC, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_SPI1, ENABLE);

    GPIO_PinAFConfig(GPIOA, GPIO_PinSource5, GPIO_AF_SPI1);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource6, GPIO_AF_SPI1);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource7, GPIO_AF_SPI1);
    gpio.GPIO_Pin = GPIO_Pin_5 | GPIO_Pin_6 | GPIO_Pin_7;
    gpio.GPIO_Mode = GPIO_Mode_AF;
    gpio.GPIO_OType = GPIO_OType_PP;
    gpio.GPIO_PuPd = GPIO_PuPd_DOWN;
    gpio.GPIO_Speed = GPIO_Speed_100MHz;
    GPIO_Init(GPIOA, &gpio);

    gpio.GPIO_Pin = FPGA_CS_PIN;
    gpio.GPIO_Mode = GPIO_Mode_OUT;
    gpio.GPIO_PuPd = GPIO_PuPd_UP;
    GPIO_Init(FPGA_CS_PORT, &gpio);
    GPIO_SetBits(FPGA_CS_PORT, FPGA_CS_PIN);

    gpio.GPIO_Pin = FPGA_RESET_PIN;
    gpio.GPIO_Mode = GPIO_Mode_OUT;
    gpio.GPIO_PuPd = GPIO_PuPd_UP;
    GPIO_Init(FPGA_RESET_PORT, &gpio);
#if BASIC_SPI_BENCH
    GPIO_ResetBits(FPGA_RESET_PORT, FPGA_RESET_PIN);
    cs_settle();
#endif
    GPIO_SetBits(FPGA_RESET_PORT, FPGA_RESET_PIN);

    gpio.GPIO_Pin = FPGA_READY_PIN | FPGA_IRQ_PIN;
    gpio.GPIO_Mode = GPIO_Mode_IN;
    gpio.GPIO_PuPd = GPIO_PuPd_DOWN;
    GPIO_Init(GPIOC, &gpio);

    SPI_I2S_DeInit(SPI1);
    SPI_StructInit(&spi);
    spi.SPI_Direction = SPI_Direction_2Lines_FullDuplex;
    spi.SPI_Mode = SPI_Mode_Master;
    spi.SPI_DataSize = SPI_DataSize_8b;
    spi.SPI_CPOL = SPI_CPOL_Low;
    spi.SPI_CPHA = SPI_CPHA_1Edge;
    spi.SPI_NSS = SPI_NSS_Soft;
#if BASIC_SPI_BENCH
    spi.SPI_BaudRatePrescaler = SPI_BaudRatePrescaler_128; /* 656.25 kHz at 84 MHz. */
#else
    spi.SPI_BaudRatePrescaler = SPI_BaudRatePrescaler_8;
#endif
    spi.SPI_FirstBit = SPI_FirstBit_MSB;
    SPI_Init(SPI1, &spi);
    SPI_Cmd(SPI1, ENABLE);
}

bool fpga_link_probe(void)
{
    uint32_t magic = 0u;
    if (!transaction(FPGA_CMD_READ, FPGA_REG_MAGIC, NULL, (uint8_t *)&magic, sizeof(magic))) return false;
    if (magic != FPGA_MAGIC) return false;
    uint32_t version = 0u;
#if BASIC_SPI_BENCH
    uint32_t channels = 0u;
    if (!transaction(FPGA_CMD_READ, FPGA_REG_VERSION, NULL, (uint8_t *)&version, 4u) ||
        version !=
#if NUCLEAR_BENCH
        0x00030000u
#else
        0x00020000u
#endif
        || !transaction(FPGA_CMD_READ, 0x0008u, NULL, (uint8_t *)&channels, 4u) || channels != 1u) return false;
#endif
    if (transaction(FPGA_CMD_READ, FPGA_REG_VERSION, NULL, (uint8_t *)&version, sizeof(version))) {
        s_version[5] = (char)('0' + ((version >> 16u) & 0xFu));
        s_version[6] = '.';
        s_version[7] = (char)('0' + ((version >> 8u) & 0xFu));
        s_version[8] = '.';
        s_version[9] = (char)('0' + (version & 0xFu));
        s_version[10] = '\0';
        memcpy(s_version, "FPGA-", 5u);
    }
    return true;
}

bool fpga_link_write_channel(uint8_t channel, const channel_config_t *config)
{
#if BASIC_SPI_BENCH
    if (channel != 0u || config == NULL) return false;
    uint8_t base = (uint8_t)(config->baseline_v * BENCH_CODE_SCALE + 0.5f);
    uint8_t amp = (uint8_t)(config->amplitude_v * BENCH_CODE_SCALE + 0.5f);
    uint16_t period = (uint16_t)(config->interval_us + 0.5f);
    uint16_t alpha = (uint16_t)(expf(-1.0f / config->decay_us) * 65536.0f + 0.5f);
    uint8_t wire[8] = {config->enabled, base, amp, 0u, (uint8_t)period, (uint8_t)(period >> 8),
                       (uint8_t)alpha, (uint8_t)(alpha >> 8)};
    if (!transaction(FPGA_CMD_WRITE, FPGA_REG_CH1, wire, NULL, sizeof(wire))) return false;
#if NUCLEAR_BENCH
    uint32_t probability=(uint32_t)(4294967296.0/(double)period+0.5);
    uint8_t ext[12]={config->arrival_mode,(uint8_t)config->noise_percent,config->waveform==3u,0};
    memcpy(ext+4,&probability,4);memcpy(ext+8,&config->seed,4);
    if(!transaction(FPGA_CMD_WRITE,0x0110u,ext,NULL,12u)) return false;
    memcpy(s_nuclear_wire,ext,12u);
#endif
    memcpy(s_bench_wire, wire, sizeof(wire));
    return true;
#else
    fpga_channel_wire_t wire;
    if ((channel > 1u) || (config == NULL)) return false;
    memcpy(&wire, config, sizeof(wire));
    return transaction(FPGA_CMD_WRITE, channel == 0u ? FPGA_REG_CH1 : FPGA_REG_CH2,
                       (const uint8_t *)&wire, NULL, sizeof(wire));
#endif
}

bool fpga_link_commit(uint32_t generation)
{
    if (!transaction(FPGA_CMD_WRITE, FPGA_REG_GENERATION, (const uint8_t *)&generation, NULL, 4u)) return false;
    uint32_t command = 1u;
    if (!transaction(FPGA_CMD_WRITE, FPGA_REG_CONTROL, (const uint8_t *)&command, NULL, 4u)) return false;
#if BASIC_SPI_BENCH
    fpga_status_t status;
    uint8_t active[8];
#if NUCLEAR_BENCH
    uint8_t ext[12];
    if(!transaction(FPGA_CMD_READ,0x0120u,NULL,ext,12u) || memcmp(ext,s_nuclear_wire,12u)!=0) return false;
#endif
    return fpga_link_status(&status) && status.active_generation == generation && status.error_flags == 0u &&
           transaction(FPGA_CMD_READ, 0x0108u, NULL, active, sizeof(active)) &&
           memcmp(active, s_bench_wire, sizeof(active)) == 0;
#else
    return true;
#endif
}

bool fpga_link_start(void)
{
    uint32_t command = 2u;
    if (!transaction(FPGA_CMD_WRITE, FPGA_REG_CONTROL, (const uint8_t *)&command, NULL, 4u)) return false;
#if BASIC_SPI_BENCH
    uint32_t flags;
    return transaction(FPGA_CMD_READ, 0x0048u, NULL, (uint8_t *)&flags, 4u) && (flags & 3u) == 3u;
#else
    return true;
#endif
}

bool fpga_link_stop(void)
{
    uint32_t command = 4u;
    if (!transaction(FPGA_CMD_WRITE, FPGA_REG_CONTROL, (const uint8_t *)&command, NULL, 4u)) return false;
#if BASIC_SPI_BENCH
    uint32_t flags;
    return transaction(FPGA_CMD_READ, 0x0048u, NULL, (uint8_t *)&flags, 4u) && !(flags & 1u);
#else
    return true;
#endif
}

bool fpga_link_status(fpga_status_t *status)
{
    return (status != NULL) && transaction(FPGA_CMD_READ, FPGA_REG_STATUS, NULL,
                                            (uint8_t *)status, sizeof(*status));
}

bool fpga_link_data_begin(uint32_t bytes)
{
#if NUCLEAR_BENCH
    uint32_t clear=0;
    return bytes==256u && transaction(FPGA_CMD_WRITE,0x0180u,(uint8_t*)&clear,NULL,4u);
#endif
    return transaction(FPGA_CMD_WRITE, FPGA_REG_DATA_INFO, (const uint8_t *)&bytes, NULL, 4u);
}

bool fpga_link_data_write(uint32_t offset, const uint8_t *data, size_t length)
{
#if NUCLEAR_BENCH
    if(data==NULL || length==0u || offset>256u || length>256u-offset) return false;
    for(size_t i=0;i<length;i++) {
        uint16_t n=1u;
        uint8_t verify[32];uint16_t addr=(uint16_t)(0x0200u+offset+i);
        if(!transaction(FPGA_CMD_WRITE,addr,data+i,NULL,n) ||
           !transaction(FPGA_CMD_READ,addr,NULL,verify,n) || memcmp(data+i,verify,n)!=0) return false;
    }
    return true;
#else
    uint8_t frame[260];
    if ((data == NULL) || (length > 256u)) return false;
    memcpy(frame, &offset, 4u);
    memcpy(frame + 4u, data, length);
    return transaction(FPGA_CMD_STREAM, FPGA_REG_DATA_FIFO, frame, NULL, (uint16_t)(length + 4u));
#endif
}

bool fpga_link_data_end(uint32_t crc32)
{
#if NUCLEAR_BENCH
    (void)crc32;uint32_t valid=0;
    return transaction(FPGA_CMD_READ,0x0184u,NULL,(uint8_t*)&valid,4u) && valid==1u;
#else
    return transaction(FPGA_CMD_WRITE, FPGA_REG_DATA_INFO + 4u, (const uint8_t *)&crc32, NULL, 4u);
#endif
}

bool fpga_link_select_preset(uint8_t preset_id)
{
    uint32_t value = preset_id;
    return preset_id < 3u && transaction(FPGA_CMD_WRITE, FPGA_REG_PRESET,
                                          (const uint8_t *)&value, NULL, 4u);
}

const char *fpga_link_version(void) { return s_version; }
