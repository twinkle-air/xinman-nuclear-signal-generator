#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#ifndef BASIC_SPI_BENCH
#define BASIC_SPI_BENCH 0
#endif
#if BASIC_SPI_BENCH
#if NUCLEAR_BENCH
#define FW_VERSION             "F405-N3.0.0"
#else
#define FW_VERSION             "F405-B2.0.0"
#endif
#define OUTPUT_CHANNELS        1u
/* Code-domain compatibility scale, NOT calibrated output volts. */
#define BENCH_CODE_SCALE       (255.0f / 6.24f)
#else
#define FW_VERSION             "F405-1.0.0"
#define OUTPUT_CHANNELS        2u
#endif
#define FPGA_VERSION_FALLBACK  "FPGA-OFFLINE"
#define CAL_VERSION            "CAL-DEFAULT-1"
#define PROTOCOL_VERSION       1u
#define UART_BAUDRATE          115200u
#define PROTOCOL_MAX_PAYLOAD   1024u
#define SIGNAL_BUFFER_SIZE     48000u
#define DISPLAY_PERIOD_MS      100u
#define STATUS_PERIOD_MS       1u
#define FPGA_POLL_PERIOD_MS    100u
#define PC_LINK_TIMEOUT_MS     2000u

/* Vendor LCD wiring: software SPI on PB4..PB9. */
/* FPGA control SPI1: PA4=CS, PA5=SCK, PA6=MISO, PA7=MOSI. */
#define FPGA_CS_PORT           GPIOA
#define FPGA_CS_PIN            GPIO_Pin_4
#define FPGA_READY_PORT        GPIOC
#define FPGA_READY_PIN         GPIO_Pin_4
#define FPGA_IRQ_PORT          GPIOC
#define FPGA_IRQ_PIN           GPIO_Pin_5
#define FPGA_RESET_PORT        GPIOC
#define FPGA_RESET_PIN         GPIO_Pin_3

/* Safety inputs are active-high. Adapt these macros to the final C board. */
#define BOARD_A_PRESENT_PORT   GPIOC
#define BOARD_A_PRESENT_PIN    GPIO_Pin_0
#define BOARD_B_PRESENT_PORT   GPIOC
#define BOARD_B_PRESENT_PIN    GPIO_Pin_1
#define POWER_GOOD_PORT        GPIOC
#define POWER_GOOD_PIN         GPIO_Pin_2

/* On-board keys: WK_UP=PA0, extra keys PC8/PC9. */
#define STOP_KEY_PORT          GPIOA
#define STOP_KEY_PIN           GPIO_Pin_0
#define MENU_KEY_PORT          GPIOC
#define MENU_KEY_PIN           GPIO_Pin_8
#define ENTER_KEY_PORT         GPIOC
#define ENTER_KEY_PIN          GPIO_Pin_9

/* Development mode permits operation without final A/B board presence wires. */
#ifndef DEVELOPMENT_BYPASS_SAFETY_INPUTS
#define DEVELOPMENT_BYPASS_SAFETY_INPUTS 0
#endif

#endif
