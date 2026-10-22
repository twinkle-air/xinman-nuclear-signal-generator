#include "delay.h"
#include "stm32f4xx.h"

void delay_init(u8 SYSCLK) { (void)SYSCLK; }

void delay_us(u32 nus)
{
    uint32_t cycles = (SystemCoreClock / 1000000u) * nus / 5u;
    while (cycles-- != 0u) __NOP();
}

void delay_ms(u16 nms)
{
    while (nms-- != 0u) delay_us(1000u);
}
