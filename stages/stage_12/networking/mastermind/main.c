#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <poll.h>
#include <time.h>
#include <arpa/inet.h>
#include "discovery.h"
#include "game.h"
#include "net.h"
#include "udp_trans.h"
#include "logger.h"

static void wait_for_enter(void)
{
    char buf[64];
    if (!fgets(buf, sizeof(buf), stdin)) return;
}

static void read_line(char *buf, size_t sz)
{
    if (!fgets(buf, sz, stdin)) {
        buf[0] = '\0';
        return;
    }
    size_t len = strlen(buf);
    while (len > 0 && (buf[len - 1] == '\n' || buf[len - 1] == '\r')) {
        buf[--len] = '\0';
    }
}

static void play_game_tcp(int sock, const char *my_name, const char *peer_name, int is_mm)
{
    struct game_state gs;
    game_init(&gs, my_name, peer_name, is_mm);

    char buf[128];

    if (is_mm) {
        printf("\033[H\033[J");
        printf("You are Mastermind! Enter 5-digit master sequence: ");
        while (1) {
            read_line(buf, sizeof(buf));
            if (game_is_valid_seq(buf)) {
                strncpy(gs.master, buf, 5);
                gs.master[5] = '\0';
                break;
            }
            printf("Invalid sequence. Must be exactly 5 digits (0-9): ");
        }
    }

    game_render(&gs);

    while (gs.round < 12) {
        if (!is_mm) {
            printf("Enter attempt (5 digits): ");
            while (1) {
                read_line(buf, sizeof(buf));
                if (game_is_valid_seq(buf)) {
                    strncpy(gs.attempts[gs.round], buf, 5);
                    gs.attempts[gs.round][5] = '\0';
                    break;
                }
                printf("Invalid attempt. Enter 5 digits: ");
            }

            char msg[64];
            snprintf(msg, sizeof(msg), "ATTEMPT %s", gs.attempts[gs.round]);
            if (net_tcp_send_line(sock, msg) < 0) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            game_render(&gs);
            printf("Waiting for %s's feedback...\n", peer_name);

            if (net_tcp_recv_line(sock, msg, sizeof(msg)) <= 0) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            char fb[16];
            if (sscanf(msg, "FEEDBACK %15s", fb) != 1 || !game_is_valid_fb(fb)) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            strncpy(gs.feedbacks[gs.round], fb, 5);
            gs.feedbacks[gs.round][5] = '\0';
            gs.round++;
            game_render(&gs);

            if (strcmp(fb, "xxxxx") == 0 || gs.round == 12) {
                if (net_tcp_recv_line(sock, msg, sizeof(msg)) <= 0) {
                    printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                    wait_for_enter();
                    return;
                }
                char secret[16];
                if (sscanf(msg, "OVER %15s", secret) == 1 && game_is_valid_seq(secret)) {
                    strncpy(gs.master, secret, 5);
                    gs.master[5] = '\0';
                    game_render(&gs);
                }
                if (strcmp(fb, "xxxxx") == 0) {
                    printf("Congratulations! You broke the code in %d attempts!\n", gs.round);
                } else {
                    printf("Game over! You ran out of attempts.\n");
                }
                printf("\nPress enter to go home.\n");
                wait_for_enter();
                return;
            }
        } else {
            printf("Waiting for %s's attempt...\n", peer_name);
            char msg[64];
            if (net_tcp_recv_line(sock, msg, sizeof(msg)) <= 0) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            char att[16];
            if (sscanf(msg, "ATTEMPT %15s", att) != 1 || !game_is_valid_seq(att)) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            strncpy(gs.attempts[gs.round], att, 5);
            gs.attempts[gs.round][5] = '\0';
            game_render(&gs);

            printf("Enter feedback for %s (5 chars of x, o, -): ", att);
            while (1) {
                read_line(buf, sizeof(buf));
                if (!game_is_valid_fb(buf)) {
                    printf("Invalid feedback format. Use 5 chars of 'x', 'o', '-': ");
                    continue;
                }
                if (!game_check_fairness(att, gs.master, buf)) {
                    int ex = 0, eo = 0, ed = 0;
                    game_calc_feedback(att, gs.master, &ex, &eo, &ed);
                    printf("Unfair feedback! Expected %d 'x', %d 'o', %d '-'. Enter fair feedback: ",
                           ex, eo, ed);
                    continue;
                }
                strncpy(gs.feedbacks[gs.round], buf, 5);
                gs.feedbacks[gs.round][5] = '\0';
                break;
            }

            snprintf(msg, sizeof(msg), "FEEDBACK %s", gs.feedbacks[gs.round]);
            if (net_tcp_send_line(sock, msg) < 0) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            gs.round++;
            game_render(&gs);

            if (strcmp(gs.feedbacks[gs.round - 1], "xxxxx") == 0 || gs.round == 12) {
                snprintf(msg, sizeof(msg), "OVER %s", gs.master);
                net_tcp_send_line(sock, msg);
                if (strcmp(gs.feedbacks[gs.round - 1], "xxxxx") == 0) {
                    printf("%s guessed your code in %d attempts!\n", peer_name, gs.round);
                } else {
                    printf("You won! %s failed to guess your code.\n", peer_name);
                }
                printf("\nPress enter to go home.\n");
                wait_for_enter();
                return;
            }
        }
    }
}

static void play_game_udp(int sock, const struct sockaddr_in *peer_addr,
                          const char *my_name, const char *peer_name, int is_mm)
{
    struct game_state gs;
    game_init(&gs, my_name, peer_name, is_mm);

    char buf[128];

    if (is_mm) {
        printf("\033[H\033[J");
        printf("You are Mastermind! Enter 5-digit master sequence: ");
        while (1) {
            read_line(buf, sizeof(buf));
            if (game_is_valid_seq(buf)) {
                strncpy(gs.master, buf, 5);
                gs.master[5] = '\0';
                break;
            }
            printf("Invalid sequence. Must be exactly 5 digits (0-9): ");
        }
    }

    game_render(&gs);

    while (gs.round < 12) {
        if (!is_mm) {
            printf("Enter attempt (5 digits): ");
            while (1) {
                read_line(buf, sizeof(buf));
                if (game_is_valid_seq(buf)) {
                    strncpy(gs.attempts[gs.round], buf, 5);
                    gs.attempts[gs.round][5] = '\0';
                    break;
                }
                printf("Invalid attempt. Enter 5 digits: ");
            }

            char msg[64];
            snprintf(msg, sizeof(msg), "ATTEMPT %s", gs.attempts[gs.round]);
            if (udp_trans_send(sock, peer_addr, msg) < 0) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            game_render(&gs);
            printf("Waiting for %s's feedback...\n", peer_name);

            struct sockaddr_in from;
            if (udp_trans_recv(sock, &from, msg, sizeof(msg), 15000) <= 0) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            char fb[16];
            if (sscanf(msg, "FEEDBACK %15s", fb) != 1 || !game_is_valid_fb(fb)) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            strncpy(gs.feedbacks[gs.round], fb, 5);
            gs.feedbacks[gs.round][5] = '\0';
            gs.round++;
            game_render(&gs);

            if (strcmp(fb, "xxxxx") == 0 || gs.round == 12) {
                if (udp_trans_recv(sock, &from, msg, sizeof(msg), 15000) <= 0) {
                    printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                    wait_for_enter();
                    return;
                }
                char secret[16];
                if (sscanf(msg, "OVER %15s", secret) == 1 && game_is_valid_seq(secret)) {
                    strncpy(gs.master, secret, 5);
                    gs.master[5] = '\0';
                    game_render(&gs);
                }
                if (strcmp(fb, "xxxxx") == 0) {
                    printf("Congratulations! You broke the code in %d attempts!\n", gs.round);
                } else {
                    printf("Game over! You ran out of attempts.\n");
                }
                printf("\nPress enter to go home.\n");
                wait_for_enter();
                return;
            }
        } else {
            printf("Waiting for %s's attempt...\n", peer_name);
            char msg[64];
            struct sockaddr_in from;
            if (udp_trans_recv(sock, &from, msg, sizeof(msg), 15000) <= 0) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            char att[16];
            if (sscanf(msg, "ATTEMPT %15s", att) != 1 || !game_is_valid_seq(att)) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            strncpy(gs.attempts[gs.round], att, 5);
            gs.attempts[gs.round][5] = '\0';
            game_render(&gs);

            printf("Enter feedback for %s (5 chars of x, o, -): ", att);
            while (1) {
                read_line(buf, sizeof(buf));
                if (!game_is_valid_fb(buf)) {
                    printf("Invalid feedback format. Use 5 chars of 'x', 'o', '-': ");
                    continue;
                }
                if (!game_check_fairness(att, gs.master, buf)) {
                    int ex = 0, eo = 0, ed = 0;
                    game_calc_feedback(att, gs.master, &ex, &eo, &ed);
                    printf("Unfair feedback! Expected %d 'x', %d 'o', %d '-'. Enter fair feedback: ",
                           ex, eo, ed);
                    continue;
                }
                strncpy(gs.feedbacks[gs.round], buf, 5);
                gs.feedbacks[gs.round][5] = '\0';
                break;
            }

            snprintf(msg, sizeof(msg), "FEEDBACK %s", gs.feedbacks[gs.round]);
            if (udp_trans_send(sock, peer_addr, msg) < 0) {
                printf("\n%s disconnected. Press enter to go home.\n", peer_name);
                wait_for_enter();
                return;
            }

            gs.round++;
            game_render(&gs);

            if (strcmp(gs.feedbacks[gs.round - 1], "xxxxx") == 0 || gs.round == 12) {
                snprintf(msg, sizeof(msg), "OVER %s", gs.master);
                udp_trans_send(sock, peer_addr, msg);
                if (strcmp(gs.feedbacks[gs.round - 1], "xxxxx") == 0) {
                    printf("%s guessed your code in %d attempts!\n", peer_name, gs.round);
                } else {
                    printf("You won! %s failed to guess your code.\n", peer_name);
                }
                printf("\nPress enter to go home.\n");
                wait_for_enter();
                return;
            }
        }
    }
}

int main(int argc, char **argv)
{
    int cost_cutting = 0;
    int enable_log = 0;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--cost-cutting") == 0) {
            cost_cutting = 1;
        } else if (strcmp(argv[i], "--log") == 0) {
            enable_log = 1;
        }
    }

    logger_init(enable_log);
    logger_log("mastermind started, cost_cutting=%d, log=%d", cost_cutting, enable_log);

    char my_name[32] = {0};
    printf("Enter your name: ");
    read_line(my_name, sizeof(my_name));
    if (strlen(my_name) == 0) {
        strcpy(my_name, "Player");
    }

    uint16_t my_port = 0;
    int tcp_listen_fd = -1;
    int udp_game_fd = -1;

    if (!cost_cutting) {
        tcp_listen_fd = net_create_tcp_listener(&my_port);
        if (tcp_listen_fd < 0) {
            fprintf(stderr, "failed to create tcp listen socket\n");
            return 1;
        }
    } else {
        udp_game_fd = net_create_udp_socket(&my_port);
        if (udp_game_fd < 0) {
            fprintf(stderr, "failed to create udp game socket\n");
            return 1;
        }
    }

    int bcast_sock = disc_init_sock(DISC_PORT);
    if (bcast_sock < 0) {
        fprintf(stderr, "failed to create discovery broadcast socket\n");
        return 1;
    }

    time_t last_bcast = 0;
    disc_clear();
    disc_render();

    while (1) {
        time_t now = time(NULL);
        if (now - last_bcast >= 2) {
            disc_send_bcast(bcast_sock, my_name, my_port, cost_cutting, DISC_PORT);
            last_bcast = now;
            disc_render();
        }

        struct pollfd pfds[4];
        int pcount = 0;

        pfds[pcount].fd = STDIN_FILENO;
        pfds[pcount].events = POLLIN;
        pfds[pcount].revents = 0;
        int idx_stdin = pcount++;

        pfds[pcount].fd = bcast_sock;
        pfds[pcount].events = POLLIN;
        pfds[pcount].revents = 0;
        int idx_bcast = pcount++;

        int idx_tcp = -1;
        if (tcp_listen_fd >= 0) {
            pfds[pcount].fd = tcp_listen_fd;
            pfds[pcount].events = POLLIN;
            pfds[pcount].revents = 0;
            idx_tcp = pcount++;
        }

        int idx_udp = -1;
        if (udp_game_fd >= 0) {
            pfds[pcount].fd = udp_game_fd;
            pfds[pcount].events = POLLIN;
            pfds[pcount].revents = 0;
            idx_udp = pcount++;
        }

        int pr = poll(pfds, pcount, 500);
        if (pr < 0) continue;

        if (pr == 0) {
            disc_render();
            continue;
        }

        if (pfds[idx_bcast].revents & POLLIN) {
            if (disc_recv_pkt(bcast_sock, my_name, my_port)) {
                disc_render();
            }
        }

        if (idx_tcp >= 0 && (pfds[idx_tcp].revents & POLLIN)) {
            struct sockaddr_in peer_addr;
            socklen_t plen = sizeof(peer_addr);
            int csock = accept(tcp_listen_fd, (struct sockaddr *)&peer_addr, &plen);
            if (csock >= 0) {
                char line[64];
                if (net_tcp_recv_line(csock, line, sizeof(line)) > 0) {
                    char peer_name[32] = {0};
                    if (sscanf(line, "CHALLENGE %31s", peer_name) == 1) {
                        char pip[INET_ADDRSTRLEN];
                        inet_ntop(AF_INET, &peer_addr.sin_addr, pip, sizeof(pip));
                        printf("\nChallenge from %s (%s:%u). Accept? (yes/no): ",
                               peer_name, pip, ntohs(peer_addr.sin_port));
                        char ans[32];
                        read_line(ans, sizeof(ans));
                        if (strcmp(ans, "yes") == 0) {
                            net_tcp_send_line(csock, "ACCEPT");
                            play_game_tcp(csock, my_name, peer_name, 0);
                            close(csock);
                            disc_clear();
                            disc_render();
                            continue;
                        } else {
                            net_tcp_send_line(csock, "REJECT");
                            close(csock);
                            disc_render();
                            continue;
                        }
                    }
                }
                close(csock);
            }
        }

        if (idx_udp >= 0 && (pfds[idx_udp].revents & POLLIN)) {
            struct sockaddr_in peer_addr;
            char line[64];
            int r = udp_trans_recv(udp_game_fd, &peer_addr, line, sizeof(line), 500);
            if (r > 0) {
                char peer_name[32] = {0};
                if (sscanf(line, "CHALLENGE %31s", peer_name) == 1) {
                    char pip[INET_ADDRSTRLEN];
                    inet_ntop(AF_INET, &peer_addr.sin_addr, pip, sizeof(pip));
                    printf("\nChallenge from %s (%s:%u). Accept? (yes/no): ",
                           peer_name, pip, ntohs(peer_addr.sin_port));
                    char ans[32];
                    read_line(ans, sizeof(ans));
                    if (strcmp(ans, "yes") == 0) {
                        udp_trans_send(udp_game_fd, &peer_addr, "ACCEPT");
                        play_game_udp(udp_game_fd, &peer_addr, my_name, peer_name, 0);
                        disc_clear();
                        disc_render();
                        continue;
                    } else {
                        udp_trans_send(udp_game_fd, &peer_addr, "REJECT");
                        disc_render();
                        continue;
                    }
                }
            }
        }

        if (pfds[idx_stdin].revents & POLLIN) {
            char cmd[64];
            read_line(cmd, sizeof(cmd));
            int target_id = 0;
            if (sscanf(cmd, "challenge %d", &target_id) == 1) {
                struct peer_entry *p = disc_find_peer(target_id);
                if (!p) {
                    printf("Player with ID %d not found.\n> ", target_id);
                    fflush(stdout);
                    continue;
                }

                if (!cost_cutting) {
                    int sock = net_tcp_connect(p->ip, p->port);
                    if (sock < 0) {
                        printf("Failed to connect to %s (%s:%u).\n> ", p->name, p->ip, p->port);
                        fflush(stdout);
                        continue;
                    }
                    char msg[64];
                    snprintf(msg, sizeof(msg), "CHALLENGE %s", my_name);
                    net_tcp_send_line(sock, msg);
                    printf("Challenge sent to %s. Waiting for reply...\n", p->name);
                    char resp[64];
                    if (net_tcp_recv_line(sock, resp, sizeof(resp)) > 0) {
                        if (strcmp(resp, "ACCEPT") == 0) {
                            play_game_tcp(sock, my_name, p->name, 1);
                            close(sock);
                            disc_clear();
                            disc_render();
                            continue;
                        } else {
                            printf("Challenge rejected by %s.\n> ", p->name);
                            close(sock);
                            fflush(stdout);
                            continue;
                        }
                    }
                    close(sock);
                } else {
                    struct sockaddr_in dest;
                    memset(&dest, 0, sizeof(dest));
                    dest.sin_family = AF_INET;
                    dest.sin_port = htons(p->port);
                    inet_pton(AF_INET, p->ip, &dest.sin_addr);

                    char msg[64];
                    snprintf(msg, sizeof(msg), "CHALLENGE %s", my_name);
                    if (udp_trans_send(udp_game_fd, &dest, msg) < 0) {
                        printf("Failed to send challenge to %s.\n> ", p->name);
                        fflush(stdout);
                        continue;
                    }
                    printf("Challenge sent to %s. Waiting for reply...\n", p->name);
                    char resp[64];
                    struct sockaddr_in from;
                    if (udp_trans_recv(udp_game_fd, &from, resp, sizeof(resp), 15000) > 0) {
                        if (strcmp(resp, "ACCEPT") == 0) {
                            play_game_udp(udp_game_fd, &dest, my_name, p->name, 1);
                            disc_clear();
                            disc_render();
                            continue;
                        } else {
                            printf("Challenge rejected by %s.\n> ", p->name);
                            fflush(stdout);
                            continue;
                        }
                    }
                }
            } else if (strcmp(cmd, "quit") == 0 || strcmp(cmd, "exit") == 0) {
                break;
            } else if (strlen(cmd) > 0) {
                printf("Unknown command. Use: challenge <ID>\n> ");
                fflush(stdout);
            } else {
                printf("> ");
                fflush(stdout);
            }
        }
    }

    if (tcp_listen_fd >= 0) close(tcp_listen_fd);
    if (udp_game_fd >= 0) close(udp_game_fd);
    if (bcast_sock >= 0) close(bcast_sock);
    logger_close();
    return 0;
}
