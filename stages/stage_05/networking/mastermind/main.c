#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <poll.h>
#include <time.h>
#include "discovery.h"

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    char name[32] = "player1";
    uint16_t bcast_port = DISC_PORT;
    int sock = disc_init_sock(bcast_port);
    if (sock < 0) {
        fprintf(stderr, "failed to bind discovery socket\n");
        return 1;
    }
    printf("discovery initialized on port %u for %s\n", bcast_port, name);
    disc_send_bcast(sock, name, 8000, 0, bcast_port);
    close(sock);
    return 0;
}
