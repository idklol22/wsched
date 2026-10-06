#include "udp_trans.h"
int udp_trans_send(int sock, const struct sockaddr_in *dest, const char *msg) {
    (void)sock; (void)dest; (void)msg; return -1;
}
int udp_trans_recv(int sock, struct sockaddr_in *src, char *out, size_t max_len, int timeout_ms) {
    (void)sock; (void)src; (void)out; (void)max_len; (void)timeout_ms; return -1;
}
