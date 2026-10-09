#include <stdio.h>
#include <string.h>
#include <ctype.h>
#include "game.h"

void game_init(struct game_state *gs, const char *my_name, const char *peer_name, int is_mm)
{
    memset(gs, 0, sizeof(*gs));
    strncpy(gs->my_name, my_name, 31);
    strncpy(gs->peer_name, peer_name, 31);
    gs->is_mastermind = is_mm;
    strcpy(gs->master, "*****");
    for (int i = 0; i < 12; i++) {
        strcpy(gs->attempts[i], "*****");
        strcpy(gs->feedbacks[i], "*****");
    }
    gs->round = 0;
}

int game_is_valid_seq(const char *seq)
{
    if (!seq) return 0;
    if (strlen(seq) != 5) return 0;
    for (int i = 0; i < 5; i++) {
        if (!isdigit((unsigned char)seq[i])) return 0;
    }
    return 1;
}

int game_is_valid_fb(const char *fb)
{
    if (!fb) return 0;
    if (strlen(fb) != 5) return 0;
    for (int i = 0; i < 5; i++) {
        char c = fb[i];
        if (c != 'x' && c != 'o' && c != '-') return 0;
    }
    return 1;
}

void game_calc_feedback(const char *attempt, const char *master, int *nx, int *no, int *nd)
{
    int x = 0;
    int o = 0;
    int ma[5] = {0};
    int mm[5] = {0};

    for (int i = 0; i < 5; i++) {
        if (attempt[i] == master[i]) {
            x++;
            ma[i] = 1;
            mm[i] = 1;
        }
    }

    for (int i = 0; i < 5; i++) {
        if (ma[i]) continue;
        for (int j = 0; j < 5; j++) {
            if (!mm[j] && attempt[i] == master[j]) {
                o++;
                mm[j] = 1;
                break;
            }
        }
    }

    *nx = x;
    *no = o;
    *nd = 5 - x - o;
}

int game_check_fairness(const char *attempt, const char *master, const char *fb)
{
    int ex = 0, eo = 0, ed = 0;
    game_calc_feedback(attempt, master, &ex, &eo, &ed);

    int ax = 0, ao = 0, ad = 0;
    for (int i = 0; i < 5; i++) {
        if (fb[i] == 'x') ax++;
        else if (fb[i] == 'o') ao++;
        else if (fb[i] == '-') ad++;
    }

    return (ax == ex && ao == eo && ad == ed);
}

void game_render(const struct game_state *gs)
{
    printf("\033[H\033[J");
    printf("%s vs %s (%s)\n\n", gs->my_name, gs->peer_name,
           gs->is_mastermind ? "Mastermind" : "Codebreaker");

    for (int i = 0; i < 12; i++) {
        printf("%s  ", gs->attempts[i]);
        for (int j = 0; j < 5; j++) {
            char c = gs->feedbacks[i][j];
            if (c == 'x') {
                printf("\033[32mx\033[0m");
            } else if (c == 'o') {
                printf("\033[33mo\033[0m");
            } else if (c == '-') {
                printf("\033[31m-\033[0m");
            } else {
                putchar(c);
            }
        }
        printf("\n");
    }

    printf("-----\n");
    printf("%s\n\n", gs->master);
    printf("Round: %d/12 | Attempts remaining: %d\n\n", gs->round, 12 - gs->round);
    fflush(stdout);
}
