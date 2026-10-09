#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netdb.h>
#include "net.h"

static long get_rem_ms(struct timespec st, long tms)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    long el = (now.tv_sec - st.tv_sec) * 1000 + (now.tv_nsec - st.tv_nsec) / 1000000;
    long rem = tms - el;
    return rem > 0 ? rem : 0;
}

int net_connect(const char *host, const char *port, struct timespec st, long tms)
{
    struct addrinfo hints, *res, *p;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    int rc = getaddrinfo(host, port, &hints, &res);
    if (rc != 0) return -1;

    int sock = -1;
    for (p = res; p != NULL; p = p->ai_next) {
        sock = socket(p->ai_family, p->ai_socktype, p->ai_protocol);
        if (sock < 0) continue;

        int fl = fcntl(sock, F_GETFL, 0);
        if (fl >= 0) fcntl(sock, F_SETFL, fl | O_NONBLOCK);

        int cr = connect(sock, p->ai_addr, p->ai_addrlen);
        if (cr == 0) {
            break;
        }
        if (cr < 0 && errno == EINPROGRESS) {
            long rem = get_rem_ms(st, tms);
            if (rem <= 0) {
                close(sock);
                sock = -1;
                break;
            }
            struct pollfd pfd = { .fd = sock, .events = POLLOUT, .revents = 0 };
            int pr = poll(&pfd, 1, (int)rem);
            if (pr > 0 && (pfd.revents & POLLOUT)) {
                int err = 0;
                socklen_t elen = sizeof(err);
                if (getsockopt(sock, SOL_SOCKET, SO_ERROR, &err, &elen) == 0 && err == 0) {
                    break;
                }
            }
        }
        close(sock);
        sock = -1;
    }

    freeaddrinfo(res);
    return sock;
}

int net_send_all(int fd, const char *buf, size_t len, struct timespec st, long tms)
{
    size_t sent = 0;
    while (sent < len) {
        long rem = get_rem_ms(st, tms);
        if (rem <= 0) return -1;

        struct pollfd pfd = { .fd = fd, .events = POLLOUT, .revents = 0 };
        int pr = poll(&pfd, 1, (int)rem);
        if (pr <= 0) return -1;
        if (!(pfd.revents & POLLOUT)) return -1;

        ssize_t n = send(fd, buf + sent, len - sent, 0);
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) continue;
            return -1;
        }
        if (n == 0) return -1;
        sent += (size_t)n;
    }
    return 0;
}

int net_recv_all(int fd, char **out, size_t *out_len, struct timespec st, long tms)
{
    size_t cap = 4096;
    size_t cur = 0;
    char *buf = malloc(cap);
    if (!buf) return -1;

    while (1) {
        long rem = get_rem_ms(st, tms);
        if (rem <= 0) {
            free(buf);
            return -1;
        }

        struct pollfd pfd = { .fd = fd, .events = POLLIN, .revents = 0 };
        int pr = poll(&pfd, 1, (int)rem);
        if (pr <= 0) {
            free(buf);
            return -1;
        }
        if (!(pfd.revents & (POLLIN | POLLHUP))) {
            free(buf);
            return -1;
        }

        if (cur + 2048 >= cap) {
            cap *= 2;
            char *nb = realloc(buf, cap);
            if (!nb) {
                free(buf);
                return -1;
            }
            buf = nb;
        }

        ssize_t n = recv(fd, buf + cur, cap - cur - 1, 0);
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) continue;
            free(buf);
            return -1;
        }
        if (n == 0) break;
        cur += (size_t)n;
    }

    buf[cur] = '\0';
    *out = buf;
    *out_len = cur;
    return 0;
}
