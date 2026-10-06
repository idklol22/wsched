#ifndef GAME_H
#define GAME_H

struct game_state {
    char my_name[32];
    char peer_name[32];
    int is_mastermind;
    char master[6];
    char attempts[12][6];
    char feedbacks[12][6];
    int round;
};

void game_init(struct game_state *gs, const char *my_name, const char *peer_name, int is_mm);
int game_is_valid_seq(const char *seq);
int game_is_valid_fb(const char *fb);
void game_calc_feedback(const char *attempt, const char *master, int *nx, int *no, int *nd);
int game_check_fairness(const char *attempt, const char *master, const char *fb);
void game_render(const struct game_state *gs);

#endif
