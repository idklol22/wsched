#ifndef LOGGER_H
#define LOGGER_H
void logger_init(int enabled);
void logger_log(const char *fmt, ...);
void logger_close(void);
#endif
