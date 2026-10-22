#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stddef.h>
#include <stdint.h>

void protocol_init(void);
void protocol_feed(const uint8_t *data, size_t length);
void protocol_poll(void);

#endif
