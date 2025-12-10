#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <cjson-ext/cJSON_ex.h>
#include <driver.h>
#include <euicc/hexutil.h>
#include <euicc/interface.h>
#include <lpac/utils.h>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
typedef int socklen_t;
#else
#include <arpa/inet.h>
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

#define ENV_SOCKET_HOST APDU_ENV_NAME(SOCKET, HOST)
#define ENV_SOCKET_PORT APDU_ENV_NAME(SOCKET, PORT)

struct socket_userdata {
    int sockfd;
    char read_buffer[8192];
    size_t read_buffer_len;
};

#ifdef _WIN32
static void socket_cleanup() { WSACleanup(); }

static int socket_init() {
    WSADATA wsa_data;
    return WSAStartup(MAKEWORD(2, 2), &wsa_data);
}
#else
static void socket_cleanup() {}
static int socket_init() { return 0; }
#endif

static int socket_connect_to_server(const char *host, const char *port) {
    struct addrinfo hints, *servinfo, *p;
    int sockfd;

    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    if (getaddrinfo(host, port, &hints, &servinfo) != 0) {
        fprintf(stderr, "getaddrinfo failed\n");
        return -1;
    }

    for (p = servinfo; p != NULL; p = p->ai_next) {
        sockfd = socket(p->ai_family, p->ai_socktype, p->ai_protocol);
        if (sockfd == -1) {
            continue;
        }

        if (connect(sockfd, p->ai_addr, p->ai_addrlen) == -1) {
#ifdef _WIN32
            closesocket(sockfd);
#else
            close(sockfd);
#endif
            continue;
        }

        break;
    }

    freeaddrinfo(servinfo);

    if (p == NULL) {
        fprintf(stderr, "Failed to connect to %s:%s\n", host, port);
        return -1;
    }

    return sockfd;
}

static int socket_send_line(int sockfd, const char *line) {
    size_t len = strlen(line);
    size_t total_sent = 0;

    while (total_sent < len) {
        int sent = send(sockfd, line + total_sent, len - total_sent, 0);
        if (sent <= 0) {
            return -1;
        }
        total_sent += sent;
    }

    // Send newline
    if (send(sockfd, "\n", 1, 0) <= 0) {
        return -1;
    }

    return 0;
}

static int socket_recv_line(struct socket_userdata *userdata, char **line) {
    while (1) {
        // Check if we have a complete line in buffer
        char *newline = memchr(userdata->read_buffer, '\n', userdata->read_buffer_len);
        if (newline) {
            size_t line_len = newline - userdata->read_buffer;
            *line = malloc(line_len + 1);
            if (!*line) {
                return -1;
            }
            memcpy(*line, userdata->read_buffer, line_len);
            (*line)[line_len] = '\0';

            // Remove line from buffer
            memmove(userdata->read_buffer, newline + 1, userdata->read_buffer_len - line_len - 1);
            userdata->read_buffer_len -= line_len + 1;

            return 0;
        }

        // Need to read more data
        if (userdata->read_buffer_len >= sizeof(userdata->read_buffer)) {
            fprintf(stderr, "Socket read buffer overflow\n");
            return -1;
        }

        int received = recv(userdata->sockfd, userdata->read_buffer + userdata->read_buffer_len,
                           sizeof(userdata->read_buffer) - userdata->read_buffer_len, 0);
        if (received <= 0) {
            fprintf(stderr, "Socket connection closed or error\n");
            return -1;
        }

        userdata->read_buffer_len += received;
    }
}

static int json_request(struct socket_userdata *userdata, const char *func, const uint8_t *param, unsigned param_len) {
    char *param_hex = NULL;
    cJSON *jroot = NULL;
    cJSON *jpayload = NULL;
    char *jstr = NULL;
    int result = -1;

    if (param && param_len) {
        param_hex = malloc((2 * param_len) + 1);
        if (param_hex == NULL) {
            return -1;
        }
        if (euicc_hexutil_bin2hex(param_hex, (2 * param_len) + 1, param, param_len) < 0) {
            free(param_hex);
            return -1;
        }
    }

    jpayload = cJSON_CreateObject();
    if (jpayload == NULL) {
        free(param_hex);
        return -1;
    }
    
    if (cJSON_AddStringToObject(jpayload, "func", func) == NULL) {
        cJSON_Delete(jpayload);
        free(param_hex);
        return -1;
    }
    
    if (param_hex) {
        if (cJSON_AddStringToObject(jpayload, "param", param_hex) == NULL) {
            cJSON_Delete(jpayload);
            free(param_hex);
            return -1;
        }
    } else {
        if (cJSON_AddNullToObject(jpayload, "param") == NULL) {
            cJSON_Delete(jpayload);
            return -1;
        }
    }

    jroot = cJSON_CreateObject();
    if (jroot == NULL) {
        cJSON_Delete(jpayload);
        free(param_hex);
        return -1;
    }
    
    if (cJSON_AddStringToObject(jroot, "type", "apdu") == NULL) {
        cJSON_Delete(jpayload);
        cJSON_Delete(jroot);
        free(param_hex);
        return -1;
    }
    
    if (cJSON_AddItemToObject(jroot, "payload", jpayload) == 0) {
        cJSON_Delete(jpayload);
        cJSON_Delete(jroot);
        free(param_hex);
        return -1;
    }

    jstr = cJSON_PrintUnformatted(jroot);
    cJSON_Delete(jroot);
    free(param_hex);

    if (jstr == NULL) {
        return -1;
    }

    result = socket_send_line(userdata->sockfd, jstr);
    cJSON_free(jstr);
    
    return result;
}

static int json_response(struct socket_userdata *userdata, int *ecode, uint8_t **data, uint32_t *data_len) {
    int fret = 0;
    _cleanup_free_ char *data_json = NULL;
    _cleanup_cjson_ cJSON *data_jroot = NULL;
    cJSON *data_payload;
    cJSON *jtmp;

    if (data) {
        *data = NULL;
    }

    if (socket_recv_line(userdata, &data_json) < 0) {
        return -1;
    }

    data_jroot = cJSON_Parse(data_json);
    if (data_jroot == NULL) {
        return -1;
    }

    jtmp = cJSON_GetObjectItem(data_jroot, "type");
    if (!jtmp) {
        goto err;
    }
    if (!cJSON_IsString(jtmp)) {
        goto err;
    }
    if (strcmp("apdu", jtmp->valuestring) != 0) {
        goto err;
    }

    data_payload = cJSON_GetObjectItem(data_jroot, "payload");
    if (!data_payload) {
        goto err;
    }
    if (!cJSON_IsObject(data_payload)) {
        goto err;
    }

    jtmp = cJSON_GetObjectItem(data_payload, "ecode");
    if (!jtmp) {
        goto err;
    }
    if (!cJSON_IsNumber(jtmp)) {
        goto err;
    }
    *ecode = jtmp->valueint;

    jtmp = cJSON_GetObjectItem(data_payload, "data");
    if (jtmp && cJSON_IsString(jtmp) && data && data_len) {
        *data_len = strlen(jtmp->valuestring) / 2;
        *data = malloc(*data_len);
        if (!*data) {
            goto err;
        }
        if (euicc_hexutil_hex2bin_r(*data, *data_len, jtmp->valuestring, strlen(jtmp->valuestring)) < 0) {
            goto err;
        }
    }

    fret = 0;
    goto exit;

err:
    fret = -1;
    if (data != NULL) {
        free(*data);
        *data = NULL;
    }
    if (data_len != NULL) {
        *data_len = 0;
    }
    *ecode = -1;
exit:
    return fret;
}

static int apdu_interface_connect(struct euicc_ctx *ctx) {
    struct socket_userdata *userdata = ctx->apdu.interface->userdata;
    int ecode;

    const char *host = getenv_or_default(ENV_SOCKET_HOST, "127.0.0.1");
    const char *port = getenv_or_default(ENV_SOCKET_PORT, "8765");

    if (socket_init() != 0) {
        fprintf(stderr, "[lpac-socket] Socket initialization failed\n");
        return -1;
    }

    userdata->sockfd = socket_connect_to_server(host, port);
    if (userdata->sockfd < 0) {
        fprintf(stderr, "[lpac-socket] Failed to connect to server\n");
        return -1;
    }

    userdata->read_buffer_len = 0;

    fprintf(stderr, "[lpac-socket] Sending connect request\n");
    if (json_request(userdata, "connect", NULL, 0)) {
        fprintf(stderr, "[lpac-socket] Failed to send connect request\n");
        return -1;
    }

    fprintf(stderr, "[lpac-socket] Waiting for connect response\n");
    if (json_response(userdata, &ecode, NULL, NULL)) {
        fprintf(stderr, "[lpac-socket] Failed to read connect response\n");
        return -1;
    }

    fprintf(stderr, "[lpac-socket] connect() returning ecode=%d\n", ecode);
    return ecode;
}

static void apdu_interface_disconnect(struct euicc_ctx *ctx) {
    struct socket_userdata *userdata = ctx->apdu.interface->userdata;
    int ecode;

    json_request(userdata, "disconnect", NULL, 0);
    json_response(userdata, &ecode, NULL, NULL);

    if (userdata->sockfd >= 0) {
#ifdef _WIN32
        closesocket(userdata->sockfd);
#else
        close(userdata->sockfd);
#endif
        userdata->sockfd = -1;
    }

    socket_cleanup();
}

static int apdu_interface_logic_channel_open(struct euicc_ctx *ctx, const uint8_t *aid, uint8_t aid_len) {
    struct socket_userdata *userdata = ctx->apdu.interface->userdata;
    int ecode;

    fprintf(stderr, "[lpac-socket] Sending logic_channel_open request\n");
    if (json_request(userdata, "logic_channel_open", aid, aid_len)) {
        fprintf(stderr, "[lpac-socket] Failed to send logic_channel_open request\n");
        return -1;
    }

    fprintf(stderr, "[lpac-socket] Waiting for logic_channel_open response\n");
    if (json_response(userdata, &ecode, NULL, NULL)) {
        fprintf(stderr, "[lpac-socket] Failed to read logic_channel_open response\n");
        return -1;
    }

    fprintf(stderr, "[lpac-socket] logic_channel_open() returning ecode=%d\n", ecode);
    return ecode;
}

static void apdu_interface_logic_channel_close(struct euicc_ctx *ctx, uint8_t channel) {
    struct socket_userdata *userdata = ctx->apdu.interface->userdata;
    int ecode;

    json_request(userdata, "logic_channel_close", &channel, sizeof(channel));
    json_response(userdata, &ecode, NULL, NULL);
}

static int apdu_interface_transmit(struct euicc_ctx *ctx, uint8_t **rx, uint32_t *rx_len, const uint8_t *tx,
                                   uint32_t tx_len) {
    struct socket_userdata *userdata = ctx->apdu.interface->userdata;
    int ecode;

    if (json_request(userdata, "transmit", tx, tx_len)) {
        return -1;
    }

    if (json_response(userdata, &ecode, rx, rx_len)) {
        return -1;
    }

    return ecode;
}

static int libapduinterface_init(struct euicc_apdu_interface *ifstruct) {
    struct socket_userdata *userdata = malloc(sizeof(struct socket_userdata));
    if (!userdata) {
        return -1;
    }

    memset(userdata, 0, sizeof(struct socket_userdata));
    userdata->sockfd = -1;

    ifstruct->connect = apdu_interface_connect;
    ifstruct->disconnect = apdu_interface_disconnect;
    ifstruct->logic_channel_open = apdu_interface_logic_channel_open;
    ifstruct->logic_channel_close = apdu_interface_logic_channel_close;
    ifstruct->transmit = apdu_interface_transmit;
    ifstruct->userdata = userdata;

    return 0;
}

static void libapduinterface_fini(struct euicc_apdu_interface *ifstruct) {
    free(ifstruct->userdata);
}

DRIVER_INTERFACE = {
    .type = DRIVER_APDU,
    .name = "socket",
    .init = (int (*)(void *))libapduinterface_init,
    .main = NULL,
    .fini = (void (*)(void *))libapduinterface_fini,
};

