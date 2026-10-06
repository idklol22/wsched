#ifndef UDP_TRANS_H
#define UDP_TRANS_H

#include <stdint.h>
#include <stddef.h>
#include <netinet/in.h>

#define CHUNK_MAGIC "MMCK"
#define ACK_MAGIC   "MMAC"
#define CHUNK_DATA_SIZE 24
#define MAX_CHUNKS 64

struct udp_chunk {
    char magic[4];
    uint32_t msg_id;
    uint16_t seq;
    uint16_t total;
    uint16_t len;
    char data[CHUNK_DATA_SIZE];
};

struct udp_ack {
    char magic[4];
    uint32_t msg_id;
    uint16_t seq;
};

int udp_trans_send(int sock, const struct sockaddr_in *dest, const char *msg);
int udp_trans_recv(int sock, struct sockaddr_in *src, char *out, size_t max_len, int timeout_ms);

#endif
