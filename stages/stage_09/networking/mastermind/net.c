#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include "net.h"
#include "logger.h"

int net_create_tcp_listener(uint16_t *out_port)
{
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return -1;

    int on = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(0);

    if (bind(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(sock);
        return -1;
    }

    if (listen(sock, 5) < 0) {
        close(sock);
        return -1;
    }

    socklen_t len = sizeof(addr);
    if (getsockname(sock, (struct sockaddr *)&addr, &len) < 0) {
        close(sock);
        return -1;
    }

    *out_port = ntohs(addr.sin_port);
    logger_log("tcp listener created on port %u", *out_port);
    return sock;
}

int net_create_udp_socket(uint16_t *out_port)
{
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) return -1;

    int on = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
#ifdef SO_REUSEPORT
    setsockopt(sock, SOL_SOCKET, SO_REUSEPORT, &on, sizeof(on));
#endif

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(0);

    if (bind(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(sock);
        return -1;
    }

    socklen_t len = sizeof(addr);
    if (getsockname(sock, (struct sockaddr *)&addr, &len) < 0) {
        close(sock);
        return -1;
    }

    *out_port = ntohs(addr.sin_port);
    logger_log("udp game socket created on port %u", *out_port);
    return sock;
}

int net_tcp_connect(const char *ip, uint16_t port)
{
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return -1;

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    if (inet_pton(AF_INET, ip, &addr.sin_addr) <= 0) {
        close(sock);
        return -1;
    }

    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(sock);
        return -1;
    }

    logger_log("connected via tcp to %s:%u", ip, port);
    return sock;
}

int net_tcp_send_line(int sock, const char *line)
{
    if (!line) return -1;
    size_t len = strlen(line);
    size_t sent = 0;

    while (sent < len) {
        ssize_t n = send(sock, line + sent, len - sent, 0);
        if (n <= 0) return -1;
        sent += (size_t)n;
    }

    if (len == 0 || line[len - 1] != '\n') {
        char nl = '\n';
        if (send(sock, &nl, 1, 0) <= 0) return -1;
    }

    logger_log("sent tcp line: %s", line);
    return 0;
}

int net_tcp_recv_line(int sock, char *buf, size_t cap)
{
    if (!buf || cap == 0) return -1;
    size_t cur = 0;

    while (cur + 1 < cap) {
        char c;
        ssize_t n = recv(sock, &c, 1, 0);
        if (n <= 0) return -1;
        if (c == '\r') continue;
        if (c == '\n') break;
        buf[cur++] = c;
    }

    buf[cur] = '\0';
    logger_log("recv tcp line: %s", buf);
    return (int)cur;
}
