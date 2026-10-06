#ifndef MASTERMIND_NET_H
#define MASTERMIND_NET_H

#include <stdint.h>
#include <stddef.h>

int net_create_tcp_listener(uint16_t *out_port);
int net_create_udp_socket(uint16_t *out_port);
int net_tcp_connect(const char *ip, uint16_t port);
int net_tcp_send_line(int sock, const char *line);
int net_tcp_recv_line(int sock, char *buf, size_t cap);

#endif
