#ifndef LOGGER_H
#define LOGGER_H

int logger_init(int enable);
void logger_log(const char *fmt, ...);
void logger_close(void);

#endif
