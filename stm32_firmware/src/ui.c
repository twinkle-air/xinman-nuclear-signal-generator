#include "ui.h"
#include "app_config.h"
#include "board.h"
#include "device.h"
#include "lcd.h"
#include "lcd_init.h"
#include <stdio.h>
#include <string.h>

static uint32_t s_last_refresh;
static bool s_force;
static char s_lines[8][22];
static uint8_t s_preset;
static bool s_menu_was_down;
static bool s_enter_was_down;
static uint32_t s_last_input;
static const char *const s_presets[] = {"Am-241", "Cs-137", "Co-60"};

static void draw_line(uint16_t y, const char *text, uint16_t color)
{
    char padded[22];
    (void)snprintf(padded, sizeof(padded), "%-20.20s", text);
    LCD_ShowString(0u, y, (const u8 *)padded, color, BLACK, 12u, 0u);
}

static void refresh(void)
{
    uint16_t state_color = g_device.state == DEVICE_RUNNING ? GREEN :
                           g_device.state == DEVICE_ERROR ? RED : YELLOW;
    (void)snprintf(s_lines[0], sizeof(s_lines[0]), "NUCSIGNAL %s", FW_VERSION);
    (void)snprintf(s_lines[1], sizeof(s_lines[1]), "STATE:%s", device_state_name(g_device.state));
    (void)snprintf(s_lines[2], sizeof(s_lines[2]), "SRC:%.16s", g_device.source_name);
    (void)snprintf(s_lines[3], sizeof(s_lines[3]), "C1 %.1fV %.0fus N%.0f%%", (double)g_device.active[0].amplitude_v,
                   (double)g_device.active[0].fwhm_us, (double)g_device.active[0].noise_percent);
    (void)snprintf(s_lines[4], sizeof(s_lines[4]), "C2 %.1fV %.0fus N%.0f%%", (double)g_device.active[1].amplitude_v,
                   (double)g_device.active[1].fwhm_us, (double)g_device.active[1].noise_percent);
    (void)snprintf(s_lines[5], sizeof(s_lines[5]), "FPGA:%s PG:%s", g_device.fpga_online ? "OK" : "NO", g_device.power_good ? "OK" : "NO");
#if BASIC_SPI_BENCH
    (void)snprintf(s_lines[3], sizeof(s_lines[3]), "C1 code:%u tau:%.0f", (unsigned)(g_device.active[0].amplitude_v*BENCH_CODE_SCALE+0.5f), (double)g_device.active[0].decay_us);
    (void)snprintf(s_lines[4], sizeof(s_lines[4]), "C2 unavailable");
    (void)snprintf(s_lines[5], sizeof(s_lines[5]), "FPGA:%s BENCH", g_device.fpga_online ? "OK" : "NO");
#endif
    (void)snprintf(s_lines[6], sizeof(s_lines[6]), "CLIP:%lu/%lu", (unsigned long)g_device.clip_count[0], (unsigned long)g_device.clip_count[1]);
    (void)snprintf(s_lines[7], sizeof(s_lines[7]), "ERR:%s", device_error_name(g_device.error));
    draw_line(0u, s_lines[0], CYAN);
    draw_line(16u, s_lines[1], state_color);
    for (uint8_t i = 2u; i < 8u; ++i) draw_line((uint16_t)(i * 16u), s_lines[i], i == 7u && g_device.error != DEV_OK ? RED : WHITE);
}

void ui_init(void)
{
    LCD_Init();
    LCD_Fill(0u, 0u, LCD_W, LCD_H, BLACK);
    s_force = true;
}

void ui_poll(void)
{
    uint32_t now = board_millis();
    if (now - s_last_input >= 10u) {
        bool menu = board_menu_pressed();
        bool enter = board_enter_pressed();
        s_last_input = now;
        if (menu && !s_menu_was_down) {
            s_preset = (uint8_t)((s_preset + 1u) % 3u);
            s_force = true;
        }
        if (enter && !s_enter_was_down) {
            if (g_device.state == DEVICE_ERROR) {
                (void)device_clear_error();
            } else if (g_device.state == DEVICE_RUNNING) {
                device_stop();
            } else if (g_device.state == DEVICE_CONFIGURED) {
                (void)device_start();
            } else if (device_select_preset(s_preset, s_presets[s_preset])) {
                (void)device_commit();
            }
            s_force = true;
        }
        s_menu_was_down = menu;
        s_enter_was_down = enter;
    }
    if (s_force || now - s_last_refresh >= DISPLAY_PERIOD_MS) {
        s_last_refresh = now; s_force = false; refresh();
    }
}

void ui_force_refresh(void) { s_force = true; }
