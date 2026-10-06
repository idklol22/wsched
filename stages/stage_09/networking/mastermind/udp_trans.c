#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <poll.h>
#include <time.h>
#include <sys/socket.h>
#include "udp_trans.h"
#include "logger.h"

static uint32_t global_msg_id = 1;

int udp_trans_send(int sock, const struct sockaddr_in *dest, const char *msg)
{
    if (!msg) return -1;
    size_t mlen = strlen(msg);
    uint16_t total = (mlen + CHUNK_DATA_SIZE - 1) / CHUNK_DATA_SIZE;
    if (total == 0) total = 1;
    if (total > MAX_CHUNKS) return -1;

    uint32_t mid = global_msg_id++;
    struct udp_chunk chunks[MAX_CHUNKS];

    size_t off = 0;
    for (uint16_t i = 0; i < total; i++) {
        memcpy(chunks[i].magic, CHUNK_MAGIC, 4);
        chunks[i].msg_id = mid;
        chunks[i].seq = i;
        chunks[i].total = total;
        size_t rem = mlen > off ? mlen - off : 0;
        size_t take = rem > CHUNK_DATA_SIZE ? CHUNK_DATA_SIZE : rem;
        chunks[i].len = (uint16_t)take;
        memset(chunks[i].data, 0, CHUNK_DATA_SIZE);
        if (take > 0) {
            memcpy(chunks[i].data, msg + off, take);
            off += take;
        }
    }

    for (uint16_t i = 0; i < total; i++) {
        sendto(sock, &chunks[i], sizeof(chunks[i]), 0,
               (const struct sockaddr *)dest, sizeof(*dest));
    }
    logger_log("sent %u udp chunks for msg %u", total, mid);
    return 0;
}

int udp_trans_recv(int sock, struct sockaddr_in *src, char *out, size_t max_len, int timeout_ms)
{
    if (!out || max_len == 0) return -1;
    struct pollfd pfd = { .fd = sock, .events = POLLIN, .revents = 0 };
    int pr = poll(&pfd, 1, timeout_ms);
    if (pr <= 0) return pr;

    struct udp_chunk chunk;
    socklen_t slen = sizeof(*src);
    ssize_t n = recvfrom(sock, &chunk, sizeof(chunk), 0, (struct sockaddr *)src, &slen);
    if (n < (ssize_t)sizeof(struct udp_chunk)) return 0;
    if (memcmp(chunk.magic, CHUNK_MAGIC, 4) != 0) return 0;

    struct udp_ack ack;
    memcpy(ack.magic, ACK_MAGIC, 4);
    ack.msg_id = chunk.msg_id;
    ack.seq = chunk.seq;
    sendto(sock, &ack, sizeof(ack), 0, (struct sockaddr *)src, slen);

    size_t cpy = chunk.len < max_len - 1 ? chunk.len : max_len - 1;
    memcpy(out, chunk.data, cpy);
    out[cpy] = '\0';
    return 1;
}
