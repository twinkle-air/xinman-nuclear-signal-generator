#ifndef TRANSPORT_H
#define TRANSPORT_H

#include <stddef.h>
#include <stdint.h>

void transport_init(void);
size_t transport_read(uint8_t *data, size_t capacity);
void transport_write(const uint8_t *data, size_t length);
void transport_rx_isr(void);
uint32_t transport_rx_overflows(void);

#endif
