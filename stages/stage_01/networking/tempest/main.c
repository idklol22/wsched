#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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
    return 0;
}
