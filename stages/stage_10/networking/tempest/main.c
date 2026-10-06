#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include "http.h"
#include "net.h"

static void print_trace(const char *s, char p)
{
    if (!s) return;
    int at_start = 1;
    for (const char *c = s; *c; c++) {
        if (at_start) {
            putchar(p);
            putchar(' ');
            at_start = 0;
        }
        putchar(*c);
        if (*c == '\n') {
            at_start = 1;
        }
    }
    if (!at_start) putchar('\n');
}

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
    if (argc == 2 && strcmp(argv[1], "--raw") == 0) {
        fprintf(stderr, "tempest: missing city argument\n");
        return 1;
    }

    int raw = (argc == 3 && strcmp(argv[2], "--raw") == 0);
    char *city = argv[1];

    char *enc = url_encode(city);
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

    int sr = net_send_all(sock, req, strlen(req), st, 10000);
    if (sr < 0) {
        close(sock);
        free(enc);
        free(req);
        fprintf(stderr, "tempest: send failed or timed out\n");
        return 1;
    }

    char *resp = NULL;
    size_t rlen = 0;
    int rr = net_recv_all(sock, &resp, &rlen, st, 10000);
    close(sock);

    if (rr < 0 || !resp) {
        free(enc);
        free(req);
        if (resp) free(resp);
        fprintf(stderr, "tempest: receive failed or timed out\n");
        return 1;
    }

    int status = 0;
    const char *body = NULL;
    int pr = parse_response(resp, &status, &body);

    int inv = 0;
    if (pr != 0 || status != 200) {
        inv = 1;
    } else if (body && (strstr(body, "location not found") || strstr(body, "Unknown location"))) {
        inv = 1;
    }
    if (raw) {
        print_trace(req, '>');
        print_trace(resp, '<');
        free(enc);
        free(req);
        free(resp);
        return 0;
    }

    if (inv) {
        fprintf(stderr, "tempest: invalid location\n");
        free(enc);
        free(req);
        free(resp);
        return 1;
    }

    printf("%s", body ? body : resp);
    free(enc);
    free(req);
    free(resp);
    return 0;
}
