#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include "discovery.h"
#include "logger.h"

static struct peer_entry peers[MAX_PEERS];
static int peer_cnt = 0;
static int next_id = 1;

void disc_clear(void)
{
    memset(peers, 0, sizeof(peers));
    peer_cnt = 0;
    next_id = 1;
}

int disc_init_sock(uint16_t port)
{
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return -1;

    int on = 1;
    setsockopt(fd, SOL_SOCKET, SO_BROADCAST, &on, sizeof(on));
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
#ifdef SO_REUSEPORT
    setsockopt(fd, SOL_SOCKET, SO_REUSEPORT, &on, sizeof(on));
#endif

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    addr.sin_addr.s_addr = htonl(INADDR_ANY);

    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(fd);
        return -1;
    }

    return fd;
}

int disc_send_bcast(int sock, const char *name, uint16_t listen_port, int mode, uint16_t bcast_port)
{
    struct disc_pkt pkt;
    memset(&pkt, 0, sizeof(pkt));
    memcpy(pkt.magic, DISC_MAGIC, 4);
    strncpy(pkt.name, name, 31);
    pkt.port = htons(listen_port);
    pkt.mode = (uint8_t)mode;

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(bcast_port);
    addr.sin_addr.s_addr = htonl(INADDR_BROADCAST);

    ssize_t n = sendto(sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&addr, sizeof(addr));
    if (n == (ssize_t)sizeof(pkt)) {
        logger_log("sent discovery broadcast port=%u mode=%d", listen_port, mode);
        return 0;
    }
    return -1;
}

int disc_recv_pkt(int sock, const char *my_name, uint16_t my_port)
{
    struct disc_pkt pkt;
    struct sockaddr_in src;
    socklen_t slen = sizeof(src);

    ssize_t n = recvfrom(sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&src, &slen);
    if (n != (ssize_t)sizeof(pkt)) return 0;

    if (memcmp(pkt.magic, DISC_MAGIC, 4) != 0) return 0;

    char ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &src.sin_addr, ip, sizeof(ip));
    uint16_t port = ntohs(pkt.port);

    if (port == my_port && strcmp(pkt.name, my_name) == 0) {
        return 0;
    }

    time_t now = time(NULL);
    logger_log("recv discovery broadcast from %s (%s:%u)", pkt.name, ip, port);

    for (int i = 0; i < peer_cnt; i++) {
        if (strcmp(peers[i].ip, ip) == 0 && peers[i].port == port) {
            strncpy(peers[i].name, pkt.name, 31);
            peers[i].last_seen = now;
            peers[i].mode = pkt.mode;
            disc_prune();
            return 1;
        }
    }

    if (peer_cnt < MAX_PEERS) {
        peers[peer_cnt].id = next_id++;
        strncpy(peers[peer_cnt].name, pkt.name, 31);
        strncpy(peers[peer_cnt].ip, ip, INET_ADDRSTRLEN - 1);
        peers[peer_cnt].port = port;
        peers[peer_cnt].last_seen = now;
        peers[peer_cnt].mode = pkt.mode;
        peer_cnt++;
        disc_prune();
        return 1;
    }

    disc_prune();
    return 0;
}

void disc_prune(void)
{
    time_t now = time(NULL);
    int i = 0;
    while (i < peer_cnt) {
        if (now - peers[i].last_seen > 5) {
            for (int j = i; j < peer_cnt - 1; j++) {
                peers[j] = peers[j + 1];
            }
            peer_cnt--;
        } else {
            i++;
        }
    }
}

void disc_render(void)
{
    disc_prune();
    time_t now = time(NULL);

    printf("\033[H\033[J");
    printf("Players Online:\n");
    printf("%-8s %-12s %-15s %-7s %s\n", "ID", "Name", "IP Addr", "Port", "Last Seen");

    for (int i = 0; i < peer_cnt; i++) {
        long diff = (long)(now - peers[i].last_seen);
        if (diff < 0) diff = 0;
        char ls[32];
        snprintf(ls, sizeof(ls), "%ld s. ago", diff);
        printf("%-8d %-12s %-15s %-7u %s\n",
               peers[i].id, peers[i].name, peers[i].ip, peers[i].port, ls);
    }

    printf("____________________________________________________\n");
    printf("> ");
    fflush(stdout);
}

struct peer_entry *disc_find_peer(int id)
{
    for (int i = 0; i < peer_cnt; i++) {
        if (peers[i].id == id) return &peers[i];
    }
    return NULL;
}
