#include "transport.h"
#include "app_config.h"
#include "misc.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"

#define RX_SIZE 2048u
static volatile uint8_t s_rx[RX_SIZE];
static volatile uint16_t s_head;
static volatile uint16_t s_tail;
static volatile uint32_t s_overflow;

void transport_init(void)
{
    GPIO_InitTypeDef gpio;
    USART_InitTypeDef uart;
    NVIC_InitTypeDef nvic;

    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource9, GPIO_AF_USART1);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource10, GPIO_AF_USART1);

    gpio.GPIO_Pin = GPIO_Pin_9 | GPIO_Pin_10;
    gpio.GPIO_Mode = GPIO_Mode_AF;
    gpio.GPIO_OType = GPIO_OType_PP;
    gpio.GPIO_PuPd = GPIO_PuPd_UP;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOA, &gpio);

    USART_StructInit(&uart);
    uart.USART_BaudRate = UART_BAUDRATE;
    uart.USART_WordLength = USART_WordLength_8b;
    uart.USART_StopBits = USART_StopBits_1;
    uart.USART_Parity = USART_Parity_No;
    uart.USART_Mode = USART_Mode_Rx | USART_Mode_Tx;
    uart.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    USART_Init(USART1, &uart);
    USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);

    nvic.NVIC_IRQChannel = USART1_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority = 4u;
    nvic.NVIC_IRQChannelSubPriority = 0u;
    nvic.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&nvic);
    USART_Cmd(USART1, ENABLE);
}

void transport_rx_isr(void)
{
    if (USART_GetITStatus(USART1, USART_IT_RXNE) != RESET) {
        uint8_t byte = (uint8_t)USART_ReceiveData(USART1);
        uint16_t next = (uint16_t)((s_head + 1u) % RX_SIZE);
        if (next == s_tail) {
            ++s_overflow;
        } else {
            s_rx[s_head] = byte;
            s_head = next;
        }
    }
}

size_t transport_read(uint8_t *data, size_t capacity)
{
    size_t count = 0u;
    while ((count < capacity) && (s_tail != s_head)) {
        data[count++] = s_rx[s_tail];
        s_tail = (uint16_t)((s_tail + 1u) % RX_SIZE);
    }
    return count;
}

void transport_write(const uint8_t *data, size_t length)
{
    while (length-- != 0u) {
        while (USART_GetFlagStatus(USART1, USART_FLAG_TXE) == RESET) { }
        USART_SendData(USART1, *data++);
    }
    while (USART_GetFlagStatus(USART1, USART_FLAG_TC) == RESET) { }
}

uint32_t transport_rx_overflows(void) { return s_overflow; }
