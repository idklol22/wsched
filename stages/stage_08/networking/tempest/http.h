#ifndef HTTP_H
#define HTTP_H

char *url_encode(const char *s);
char *build_request(const char *enc);
int parse_response(const char *resp, int *status, const char **body);

#endif
