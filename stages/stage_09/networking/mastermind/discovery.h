#ifndef DISCOVERY_H
#define DISCOVERY_H

#include <stdint.h>
#include <time.h>
#include <netinet/in.h>

#define DISC_MAGIC "MM26"
#define DISC_PORT 9999
#define MAX_PEERS 32

struct peer_entry {
    int id;
    char name[32];
    char ip[INET_ADDRSTRLEN];
    uint16_t port;
    time_t last_seen;
    int mode;
};

struct disc_pkt {
    char magic[4];
    char name[32];
    uint16_t port;
    uint8_t mode;
};

int disc_init_sock(uint16_t port);
int disc_send_bcast(int sock, const char *name, uint16_t listen_port, int mode, uint16_t bcast_port);
int disc_recv_pkt(int sock, const char *my_name, uint16_t my_port);
void disc_prune(void);
void disc_render(void);
struct peer_entry *disc_find_peer(int id);
void disc_clear(void);

#endif
