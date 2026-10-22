#include "board.h"
#include "device.h"
#include "fpga_link.h"
#include "protocol.h"
#include "storage.h"
#include "transport.h"
#include "ui.h"
#include "stm32f4xx.h"
#include <stddef.h>
#include <stdint.h>

int main(void)
{
    uint8_t input[256];
    uint32_t last_device_tick = 0u;

    board_init();
    transport_init();
    fpga_link_init();
    storage_init();
    protocol_init();
    device_init();
    ui_init();

    while (1) {
        size_t count = transport_read(input, sizeof(input));
        if (count != 0u) protocol_feed(input, count);
        protocol_poll();

        uint32_t now = board_millis();
        while (last_device_tick != now) {
            ++last_device_tick;
            device_tick_1ms();
        }
        device_poll();
        ui_poll();
        board_watchdog_feed();
        __WFI();
    }
}
