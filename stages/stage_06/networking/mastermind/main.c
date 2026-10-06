#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "game.h"

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    struct game_state gs;
    game_init(&gs, "player1", "player2", 1);
    printf("master sequence validation: %d\n", game_is_valid_seq("12345"));
    return 0;
}
