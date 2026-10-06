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

static long get_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

int udp_trans_send(int sock, const struct sockaddr_in *dest, const char *msg)
{
    if (!msg) return -1;
    size_t mlen = strlen(msg);
    uint16_t total = (mlen + CHUNK_DATA_SIZE - 1) / CHUNK_DATA_SIZE;
    if (total == 0) total = 1;
    if (total > MAX_CHUNKS) return -1;

    uint32_t mid = global_msg_id++;
    struct udp_chunk chunks[MAX_CHUNKS];
    int acked[MAX_CHUNKS] = {0};

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
    logger_log("sent initial %u udp chunks for msg %u", total, mid);

    long last_send = get_ms();
    int retries = 0;
    int unacked = total;

    while (unacked > 0 && retries < 15) {
        long now = get_ms();
        long diff = now - last_send;
        long wait = 100 - diff;
        if (wait < 0) wait = 0;

        struct pollfd pfd = { .fd = sock, .events = POLLIN, .revents = 0 };
        int pr = poll(&pfd, 1, (int)wait);
        if (pr > 0 && (pfd.revents & POLLIN)) {
            struct udp_ack ack;
            struct sockaddr_in from;
            socklen_t flen = sizeof(from);
            ssize_t n = recvfrom(sock, &ack, sizeof(ack), 0,
                                 (struct sockaddr *)&from, &flen);
            if (n == (ssize_t)sizeof(ack)) {
                if (memcmp(ack.magic, ACK_MAGIC, 4) == 0 && ack.msg_id == mid) {
                    if (ack.seq < total && !acked[ack.seq]) {
                        acked[ack.seq] = 1;
                        unacked--;
                        logger_log("recv ack for msg %u chunk %u", mid, ack.seq);
                    }
                }
            }
        }

        now = get_ms();
        if (unacked > 0 && (now - last_send >= 100)) {
            retries++;
            for (uint16_t i = 0; i < total; i++) {
                if (!acked[i]) {
                    sendto(sock, &chunks[i], sizeof(chunks[i]), 0,
                           (const struct sockaddr *)dest, sizeof(*dest));
                }
            }
            logger_log("retransmitted unacked chunks for msg %u (retry %d)", mid, retries);
            last_send = now;
        }
    }

    if (unacked > 0) {
        logger_log("udp send failed for msg %u (max retries reached)", mid);
        return -1;
    }

    return 0;
}

int udp_trans_recv(int sock, struct sockaddr_in *src, char *out, size_t max_len, int timeout_ms)
{
    long st = get_ms();
    uint32_t cur_mid = 0;
    uint16_t total = 0;
    int got[MAX_CHUNKS] = {0};
    char parts[MAX_CHUNKS][CHUNK_DATA_SIZE];
    uint16_t lens[MAX_CHUNKS] = {0};
    int recvd = 0;

    while (1) {
        long now = get_ms();
        long el = now - st;
        if (timeout_ms > 0 && el >= timeout_ms) {
            return -1;
        }
        long wait = timeout_ms > 0 ? (timeout_ms - el) : 1000;
        if (wait <= 0) return -1;

        struct pollfd pfd = { .fd = sock, .events = POLLIN, .revents = 0 };
        int pr = poll(&pfd, 1, (int)wait);
        if (pr <= 0) {
            if (timeout_ms > 0) return -1;
            continue;
        }

        struct udp_chunk chunk;
        struct sockaddr_in from;
        socklen_t flen = sizeof(from);
        ssize_t n = recvfrom(sock, &chunk, sizeof(chunk), 0,
                             (struct sockaddr *)&from, &flen);
        if (n != (ssize_t)sizeof(chunk)) continue;
        if (memcmp(chunk.magic, CHUNK_MAGIC, 4) != 0) continue;

        struct udp_ack ack;
        memcpy(ack.magic, ACK_MAGIC, 4);
        ack.msg_id = chunk.msg_id;
        ack.seq = chunk.seq;
        sendto(sock, &ack, sizeof(ack), 0, (struct sockaddr *)&from, flen);
        logger_log("sent ack for msg %u chunk %u", chunk.msg_id, chunk.seq);

        if (cur_mid == 0) {
            cur_mid = chunk.msg_id;
            total = chunk.total;
            if (src) *src = from;
        }

        if (chunk.msg_id != cur_mid) continue;

        if (chunk.seq < total && !got[chunk.seq]) {
            got[chunk.seq] = 1;
            lens[chunk.seq] = chunk.len;
            memcpy(parts[chunk.seq], chunk.data, chunk.len);
            recvd++;
        }

        if (recvd == total && total > 0) {
            size_t off = 0;
            for (uint16_t i = 0; i < total; i++) {
                if (off + lens[i] < max_len) {
                    memcpy(out + off, parts[i], lens[i]);
                    off += lens[i];
                }
            }
            out[off] = '\0';
            logger_log("assembled msg %u len %zu", cur_mid, off);
            return (int)off;
        }
    }
}
