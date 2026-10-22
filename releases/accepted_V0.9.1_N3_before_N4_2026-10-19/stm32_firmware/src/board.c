#include "board.h"
#include "app_config.h"
#include "stm32f4xx.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_iwdg.h"
#include "stm32f4xx_rcc.h"

static volatile uint32_t s_millis;

static bool read_active_high(GPIO_TypeDef *port, uint16_t pin)
{
    return GPIO_ReadInputDataBit(port, pin) != Bit_RESET;
}

void board_init(void)
{
    GPIO_InitTypeDef gpio;
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA | RCC_AHB1Periph_GPIOB |
                          RCC_AHB1Periph_GPIOC, ENABLE);

    gpio.GPIO_Pin = STOP_KEY_PIN;
    gpio.GPIO_Mode = GPIO_Mode_IN;
    gpio.GPIO_OType = GPIO_OType_PP;
    gpio.GPIO_Speed = GPIO_Speed_2MHz;
    gpio.GPIO_PuPd = GPIO_PuPd_DOWN;
    GPIO_Init(STOP_KEY_PORT, &gpio);

    gpio.GPIO_Pin = MENU_KEY_PIN | ENTER_KEY_PIN | BOARD_A_PRESENT_PIN |
                    BOARD_B_PRESENT_PIN | POWER_GOOD_PIN;
    gpio.GPIO_PuPd = GPIO_PuPd_DOWN;
    GPIO_Init(GPIOC, &gpio);

    if (SysTick_Config(SystemCoreClock / 1000u) != 0u) {
        while (1) { }
    }

    IWDG_WriteAccessCmd(IWDG_WriteAccess_Enable);
    IWDG_SetPrescaler(IWDG_Prescaler_64);
    IWDG_SetReload(2000u);
    IWDG_ReloadCounter();
    IWDG_Enable();
}

uint32_t board_millis(void) { return s_millis; }
void board_tick_isr(void) { ++s_millis; }
void board_watchdog_feed(void) { IWDG_ReloadCounter(); }
bool board_stop_pressed(void) { return read_active_high(STOP_KEY_PORT, STOP_KEY_PIN); }
bool board_menu_pressed(void) { return read_active_high(MENU_KEY_PORT, MENU_KEY_PIN); }
bool board_enter_pressed(void) { return read_active_high(ENTER_KEY_PORT, ENTER_KEY_PIN); }

bool board_a_present(void)
{
#if DEVELOPMENT_BYPASS_SAFETY_INPUTS
    return true;
#else
    return read_active_high(BOARD_A_PRESENT_PORT, BOARD_A_PRESENT_PIN);
#endif
}

bool board_b_present(void)
{
#if DEVELOPMENT_BYPASS_SAFETY_INPUTS
    return true;
#else
    return read_active_high(BOARD_B_PRESENT_PORT, BOARD_B_PRESENT_PIN);
#endif
}

bool board_power_good(void)
{
#if DEVELOPMENT_BYPASS_SAFETY_INPUTS
    return true;
#else
    return read_active_high(POWER_GOOD_PORT, POWER_GOOD_PIN);
#endif
}
