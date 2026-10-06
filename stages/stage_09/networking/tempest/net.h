#ifndef NET_H
#define NET_H

#include <time.h>
#include <stddef.h>

int net_connect(const char *host, const char *port, struct timespec st, long tms);
int net_send_all(int fd, const char *buf, size_t len, struct timespec st, long tms);
int net_recv_all(int fd, char **out, size_t *out_len, struct timespec st, long tms);

#endif
