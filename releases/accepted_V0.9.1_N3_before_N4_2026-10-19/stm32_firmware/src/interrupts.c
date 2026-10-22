#include "board.h"
#include "transport.h"
#include "stm32f4xx.h"

void SysTick_Handler(void) { board_tick_isr(); }
void USART1_IRQHandler(void) { transport_rx_isr(); }

void HardFault_Handler(void)
{
    __disable_irq();
    while (1) { }
}
