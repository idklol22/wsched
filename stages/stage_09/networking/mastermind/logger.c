#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <sys/time.h>
#include <time.h>
#include "logger.h"

static FILE *log_fp = NULL;

int logger_init(int enable)
{
    if (!enable) {
        log_fp = NULL;
        return 0;
    }
    log_fp = fopen("log.txt", "a");
    if (!log_fp) return -1;
    return 0;
}

void logger_log(const char *fmt, ...)
{
    if (!log_fp) return;

    char time_buffer[30];
    struct timeval tv;
    time_t curtime;

    gettimeofday(&tv, NULL);
    curtime = tv.tv_sec;

    strftime(time_buffer, 30, "%Y-%m-%d %H:%M:%S", localtime(&curtime));
    fprintf(log_fp, "[%s.%06ld] [LOG] ", time_buffer, tv.tv_usec);

    va_list ap;
    va_start(ap, fmt);
    vfprintf(log_fp, fmt, ap);
    va_end(ap);

    fprintf(log_fp, "\n");
    fflush(log_fp);
}

void logger_close(void)
{
    if (log_fp) {
        fclose(log_fp);
        log_fp = NULL;
    }
}
