#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include "http.h"
#include "net.h"

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "tempest: missing city argument\n");
        return 1;
    }
    if (argc > 3) {
        fprintf(stderr, "tempest: too many arguments\n");
        return 1;
    }
    if (argc == 3 && strcmp(argv[2], "--raw") != 0) {
        fprintf(stderr, "tempest: too many arguments\n");
        return 1;
    }

    char *enc = url_encode(argv[1]);
    if (!enc) {
        fprintf(stderr, "tempest: encoding error\n");
        return 1;
    }

    char *req = build_request(enc);
    if (!req) {
        free(enc);
        fprintf(stderr, "tempest: memory error\n");
        return 1;
    }

    struct timespec st;
    clock_gettime(CLOCK_MONOTONIC, &st);

    int sock = net_connect("wttr.is", "80", st, 10000);
    if (sock < 0) {
        free(enc);
        free(req);
        fprintf(stderr, "tempest: connection failed or timed out\n");
        return 1;
    }

    close(sock);
    free(enc);
    free(req);
    return 0;
}
