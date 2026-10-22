#ifndef BOARD_H
#define BOARD_H

#include <stdbool.h>
#include <stdint.h>

void board_init(void);
uint32_t board_millis(void);
void board_tick_isr(void);
void board_watchdog_feed(void);
bool board_stop_pressed(void);
bool board_menu_pressed(void);
bool board_enter_pressed(void);
bool board_a_present(void);
bool board_b_present(void);
bool board_power_good(void);

#endif
