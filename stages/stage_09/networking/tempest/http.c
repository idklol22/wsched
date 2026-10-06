#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "http.h"

char *url_encode(const char *s)
{
    if (!s) return NULL;
    size_t len = strlen(s);
    char *out = malloc(len * 3 + 1);
    if (!out) return NULL;
    char *p = out;
    for (size_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)s[i];
        if (isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~') {
            *p++ = c;
        } else {
            sprintf(p, "%%%02X", c);
            p += 3;
        }
    }
    *p = '\0';
    return out;
}

char *build_request(const char *enc)
{
    char *buf = malloc(2048);
    if (!buf) return NULL;
    snprintf(buf, 2048,
        "GET /%s?0T HTTP/1.1\r\n"
        "Host: wttr.is\r\n"
        "User-Agent: curl/8.0.0\r\n"
        "Accept: */*\r\n"
        "Connection: close\r\n\r\n",
        enc);
    return buf;
}

int parse_response(const char *resp, int *status, const char **body)
{
    if (!resp) return -1;
    int code = 0;
    if (sscanf(resp, "HTTP/%*s %d", &code) != 1) return -1;
    *status = code;
    const char *sep = strstr(resp, "\r\n\r\n");
    if (sep) {
        *body = sep + 4;
    } else {
        sep = strstr(resp, "\n\n");
        if (sep) *body = sep + 2;
        else *body = resp;
    }
    return 0;
}
