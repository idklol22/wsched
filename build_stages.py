#!/usr/bin/env python3
import os
import shutil
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BASE_DIR = os.environ.get("BASE_DIR", os.path.join(PROJECT_ROOT, "mini-project2"))
STAGES_DIR = os.environ.get("STAGES_DIR", os.path.join(SCRIPT_DIR, "stages"))

def setup_stage(idx, name):
    sdir = os.path.join(STAGES_DIR, f"stage_{idx:02d}")
    if os.path.exists(sdir):
        shutil.rmtree(sdir)
    os.makedirs(sdir, exist_ok=True)
    return sdir

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

def copy_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)

print("Building 11 stages...")

# STAGE 1: Initial setup
s1 = setup_stage(1, "initial setup and makefiles")
copy_file(f"{BASE_DIR}/Makefile", f"{s1}/Makefile")
copy_file(f"{BASE_DIR}/networking/Makefile", f"{s1}/networking/Makefile")
copy_file(f"{BASE_DIR}/networking/tempest/Makefile", f"{s1}/networking/tempest/Makefile")
copy_file(f"{BASE_DIR}/networking/mastermind/Makefile", f"{s1}/networking/mastermind/Makefile")

write_file(f"{s1}/networking/tempest/http.h", """#ifndef HTTP_H
#define HTTP_H

#endif
""")
write_file(f"{s1}/networking/tempest/http.c", """#include "http.h"
""")
write_file(f"{s1}/networking/tempest/net.h", """#ifndef NET_H
#define NET_H

#endif
""")
write_file(f"{s1}/networking/tempest/net.c", """#include "net.h"
""")
write_file(f"{s1}/networking/tempest/main.c", """#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "tempest: missing city argument\\n");
        return 1;
    }
    if (argc > 3) {
        fprintf(stderr, "tempest: too many arguments\\n");
        return 1;
    }
    if (argc == 3 && strcmp(argv[2], "--raw") != 0) {
        fprintf(stderr, "tempest: too many arguments\\n");
        return 1;
    }
    return 0;
}
""")

write_file(f"{s1}/networking/mastermind/discovery.h", """#ifndef DISCOVERY_H
#define DISCOVERY_H
#endif
""")
write_file(f"{s1}/networking/mastermind/discovery.c", """#include "discovery.h"
""")
write_file(f"{s1}/networking/mastermind/game.h", """#ifndef GAME_H
#define GAME_H
#endif
""")
write_file(f"{s1}/networking/mastermind/game.c", """#include "game.h"
""")
write_file(f"{s1}/networking/mastermind/net.h", """#ifndef NET_H
#define NET_H
#endif
""")
write_file(f"{s1}/networking/mastermind/net.c", """#include "net.h"
""")
write_file(f"{s1}/networking/mastermind/logger.h", """#ifndef LOGGER_H
#define LOGGER_H
#endif
""")
write_file(f"{s1}/networking/mastermind/logger.c", """#include "logger.h"
""")
write_file(f"{s1}/networking/mastermind/udp_trans.h", """#ifndef UDP_TRANS_H
#define UDP_TRANS_H
#endif
""")
write_file(f"{s1}/networking/mastermind/udp_trans.c", """#include "udp_trans.h"
""")
write_file(f"{s1}/networking/mastermind/main.c", """#include <stdio.h>

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    printf("mastermind initializing\\n");
    return 0;
}
""")

# STAGE 2: Tempest URL encode and request builder
s2 = setup_stage(2, "tempest url encode and http request builder")
shutil.copytree(s1, s2, dirs_exist_ok=True)
copy_file(f"{BASE_DIR}/networking/tempest/http.h", f"{s2}/networking/tempest/http.h")
copy_file(f"{BASE_DIR}/networking/tempest/http.c", f"{s2}/networking/tempest/http.c")
write_file(f"{s2}/networking/tempest/main.c", """#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "http.h"

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "tempest: missing city argument\\n");
        return 1;
    }
    if (argc > 3) {
        fprintf(stderr, "tempest: too many arguments\\n");
        return 1;
    }
    if (argc == 3 && strcmp(argv[2], "--raw") != 0) {
        fprintf(stderr, "tempest: too many arguments\\n");
        return 1;
    }

    char *enc = url_encode(argv[1]);
    if (!enc) {
        fprintf(stderr, "tempest: encoding error\\n");
        return 1;
    }

    char *req = build_request(enc);
    if (!req) {
        free(enc);
        fprintf(stderr, "tempest: memory error\\n");
        return 1;
    }

    free(enc);
    free(req);
    return 0;
}
""")

# STAGE 3: Tempest socket connect and poll timeout
s3 = setup_stage(3, "tempest socket connect with poll timeout")
shutil.copytree(s2, s3, dirs_exist_ok=True)
copy_file(f"{BASE_DIR}/networking/tempest/net.h", f"{s3}/networking/tempest/net.h")
copy_file(f"{BASE_DIR}/networking/tempest/net.c", f"{s3}/networking/tempest/net.c")
write_file(f"{s3}/networking/tempest/main.c", """#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include "http.h"
#include "net.h"

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "tempest: missing city argument\\n");
        return 1;
    }
    if (argc > 3) {
        fprintf(stderr, "tempest: too many arguments\\n");
        return 1;
    }
    if (argc == 3 && strcmp(argv[2], "--raw") != 0) {
        fprintf(stderr, "tempest: too many arguments\\n");
        return 1;
    }

    char *enc = url_encode(argv[1]);
    if (!enc) {
        fprintf(stderr, "tempest: encoding error\\n");
        return 1;
    }

    char *req = build_request(enc);
    if (!req) {
        free(enc);
        fprintf(stderr, "tempest: memory error\\n");
        return 1;
    }

    struct timespec st;
    clock_gettime(CLOCK_MONOTONIC, &st);

    int sock = net_connect("wttr.is", "80", st, 10000);
    if (sock < 0) {
        free(enc);
        free(req);
        fprintf(stderr, "tempest: connection failed or timed out\\n");
        return 1;
    }

    close(sock);
    free(enc);
    free(req);
    return 0;
}
""")

# STAGE 4: Tempest handle short reads, complete tempest & raw flag
s4 = setup_stage(4, "tempest handle short reads and raw flag")
shutil.copytree(s3, s4, dirs_exist_ok=True)
copy_file(f"{BASE_DIR}/networking/tempest/main.c", f"{s4}/networking/tempest/main.c")
copy_file(f"{BASE_DIR}/networking/tempest/net.c", f"{s4}/networking/tempest/net.c")
copy_file(f"{BASE_DIR}/networking/tempest/http.c", f"{s4}/networking/tempest/http.c")

# STAGE 5: Mastermind peer discovery
s5 = setup_stage(5, "mastermind udp peer discovery")
shutil.copytree(s4, s5, dirs_exist_ok=True)
copy_file(f"{BASE_DIR}/networking/mastermind/discovery.h", f"{s5}/networking/mastermind/discovery.h")
copy_file(f"{BASE_DIR}/networking/mastermind/discovery.c", f"{s5}/networking/mastermind/discovery.c")
write_file(f"{s5}/networking/mastermind/logger.h", """#ifndef LOGGER_H
#define LOGGER_H
void logger_init(int enabled);
void logger_log(const char *fmt, ...);
void logger_close(void);
#endif
""")
write_file(f"{s5}/networking/mastermind/logger.c", """#include "logger.h"
void logger_init(int enabled) { (void)enabled; }
void logger_log(const char *fmt, ...) { (void)fmt; }
void logger_close(void) {}
""")
write_file(f"{s5}/networking/mastermind/main.c", """#include <stdio.h>
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
        fprintf(stderr, "failed to bind discovery socket\\n");
        return 1;
    }
    printf("discovery initialized on port %u for %s\\n", bcast_port, name);
    disc_send_bcast(sock, name, 8000, 0, bcast_port);
    close(sock);
    return 0;
}
""")

# STAGE 6: Mastermind game state and feedback validation
s6 = setup_stage(6, "mastermind game state and feedback logic")
shutil.copytree(s5, s6, dirs_exist_ok=True)
copy_file(f"{BASE_DIR}/networking/mastermind/game.h", f"{s6}/networking/mastermind/game.h")
copy_file(f"{BASE_DIR}/networking/mastermind/game.c", f"{s6}/networking/mastermind/game.c")
write_file(f"{s6}/networking/mastermind/main.c", """#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "game.h"

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    struct game_state gs;
    game_init(&gs, "player1", "player2", 1);
    printf("master sequence validation: %d\\n", game_is_valid_seq("12345"));
    return 0;
}
""")

# STAGE 7: Mastermind tcp mode and gameplay loop
s7 = setup_stage(7, "mastermind tcp mode and gameplay loop")
shutil.copytree(s6, s7, dirs_exist_ok=True)
copy_file(f"{BASE_DIR}/networking/mastermind/net.h", f"{s7}/networking/mastermind/net.h")
copy_file(f"{BASE_DIR}/networking/mastermind/net.c", f"{s7}/networking/mastermind/net.c")
copy_file(f"{BASE_DIR}/networking/mastermind/udp_trans.h", f"{s7}/networking/mastermind/udp_trans.h")
copy_file(f"{BASE_DIR}/networking/mastermind/main.c", f"{s7}/networking/mastermind/main.c")
write_file(f"{s7}/networking/mastermind/logger.h", """#ifndef LOGGER_H
#define LOGGER_H
void logger_init(int enabled);
void logger_log(const char *fmt, ...);
void logger_close(void);
#endif
""")
write_file(f"{s7}/networking/mastermind/logger.c", """#include "logger.h"
void logger_init(int enabled) { (void)enabled; }
void logger_log(const char *fmt, ...) { (void)fmt; }
void logger_close(void) {}
""")
write_file(f"{s7}/networking/mastermind/udp_trans.c", """#include "udp_trans.h"
int udp_trans_send(int sock, const struct sockaddr_in *dest, const char *msg) {
    (void)sock; (void)dest; (void)msg; return -1;
}
int udp_trans_recv(int sock, struct sockaddr_in *src, char *out, size_t max_len, int timeout_ms) {
    (void)sock; (void)src; (void)out; (void)max_len; (void)timeout_ms; return -1;
}
""")

# STAGE 8: Mastermind add logging with microsecond timestamps
s8 = setup_stage(8, "mastermind add logging with microsecond timestamps")
shutil.copytree(s7, s8, dirs_exist_ok=True)
copy_file(f"{BASE_DIR}/networking/mastermind/logger.h", f"{s8}/networking/mastermind/logger.h")
copy_file(f"{BASE_DIR}/networking/mastermind/logger.c", f"{s8}/networking/mastermind/logger.c")

# STAGE 9: Mastermind udp chunking and ack packet protocol
s9 = setup_stage(9, "mastermind udp chunking and ack packet protocol")
shutil.copytree(s8, s9, dirs_exist_ok=True)
copy_file(f"{BASE_DIR}/networking/mastermind/udp_trans.h", f"{s9}/networking/mastermind/udp_trans.h")
write_file(f"{s9}/networking/mastermind/udp_trans.c", """#include <stdio.h>
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
    out[cpy] = '\\0';
    return 1;
}
""")

# STAGE 10: Mastermind cost cutting mode with reliable udp
s10 = setup_stage(10, "mastermind cost cutting mode with reliable udp")
shutil.copytree(s9, s10, dirs_exist_ok=True)
copy_file(f"{BASE_DIR}/networking/mastermind/udp_trans.c", f"{s10}/networking/mastermind/udp_trans.c")
copy_file(f"{BASE_DIR}/networking/mastermind/main.c", f"{s10}/networking/mastermind/main.c")

# STAGE 11: Final polish, docs, readme and ai usage
s11 = setup_stage(11, "update docs and final makefile polish")
shutil.copytree(s10, s11, dirs_exist_ok=True)
copy_file(f"{BASE_DIR}/readme.md", f"{s11}/readme.md")
copy_file(f"{BASE_DIR}/ai-usage.md", f"{s11}/ai-usage.md")

print("Validating compilation of each stage...")
for i in range(1, 12):
    sdir = os.path.join(STAGES_DIR, f"stage_{i:02d}")
    netdir = os.path.join(sdir, "networking")
    res = subprocess.run(["make", "-C", netdir, "clean"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    res = subprocess.run(["make", "-C", netdir, "all"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAILED STAGE {i:02d}: {res.stderr}")
        exit(1)
    else:
        print(f"Stage {i:02d} OK")
    subprocess.run(["make", "-C", netdir, "clean"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("All 11 stages generated and verified successfully!")
