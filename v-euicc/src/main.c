#include "apdu_handler.h"
#include "euicc_state.h"
#include "protocol.h"
#include "../logging.h"

#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
#else
#include <arpa/inet.h>
#include <netdb.h>
#include <sys/socket.h>
#endif

static volatile int keep_running = 1;

static void sigint_handler(int sig) {
    (void)sig;
    keep_running = 0;
}

static int create_server_socket(const char *port) {
    struct addrinfo hints, *servinfo, *p;
    int sockfd;
    int yes = 1;

    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_PASSIVE;

    if (getaddrinfo(NULL, port, &hints, &servinfo) != 0) {
        fprintf(stderr, "getaddrinfo failed\n");
        return -1;
    }

    for (p = servinfo; p != NULL; p = p->ai_next) {
        sockfd = socket(p->ai_family, p->ai_socktype, p->ai_protocol);
        if (sockfd == -1) {
            continue;
        }

        if (setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, (const char *)&yes, sizeof(yes)) == -1) {
            fprintf(stderr, "setsockopt failed\n");
#ifdef _WIN32
            closesocket(sockfd);
#else
            close(sockfd);
#endif
            continue;
        }

        if (bind(sockfd, p->ai_addr, p->ai_addrlen) == -1) {
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
        fprintf(stderr, "Failed to bind socket\n");
        return -1;
    }

    if (listen(sockfd, 5) == -1) {
        fprintf(stderr, "listen failed\n");
#ifdef _WIN32
        closesocket(sockfd);
#else
        close(sockfd);
#endif
        return -1;
    }

    return sockfd;
}

static int recv_line(int sockfd, char **line, char *buffer, size_t *buffer_len, size_t buffer_size) {
    while (1) {
        // Check for complete line
        char *newline = memchr(buffer, '\n', *buffer_len);
        if (newline) {
            size_t line_len = newline - buffer;
            *line = malloc(line_len + 1);
            if (!*line) {
                return -1;
            }
            memcpy(*line, buffer, line_len);
            (*line)[line_len] = '\0';

            // Remove line from buffer
            memmove(buffer, newline + 1, *buffer_len - line_len - 1);
            *buffer_len -= line_len + 1;

            return 0;
        }

        // Read more data
        if (*buffer_len >= buffer_size) {
            return -1;
        }

        int received = recv(sockfd, buffer + *buffer_len, buffer_size - *buffer_len, 0);
        if (received <= 0) {
            return -1;
        }

        *buffer_len += received;
    }
}

static int send_line(int sockfd, const char *line) {
    size_t len = strlen(line);
    size_t total_sent = 0;

    while (total_sent < len) {
        int sent = send(sockfd, line + total_sent, len - total_sent, 0);
        if (sent <= 0) {
            fprintf(stderr, "[v-euicc] send() failed: %s\n", strerror(errno));
            return -1;
        }
        total_sent += sent;
    }

    if (send(sockfd, "\n", 1, 0) <= 0) {
        fprintf(stderr, "[v-euicc] send() newline failed: %s\n", strerror(errno));
        return -1;
    }

    return 0;
}

static void handle_client(int client_fd) {
    struct euicc_state state;
    char recv_buffer[8192];
    size_t recv_buffer_len = 0;

    printf("Client connected\n");
    fflush(stdout);
    fprintf(stderr, "[v-euicc] Client connected, fd=%d\n", client_fd);

    while (keep_running) {
        char *request_line = NULL;
        char *func = NULL;
        uint8_t *param = NULL;
        uint32_t param_len = 0;
        int ecode = 0;
        uint8_t *response_data = NULL;
        uint32_t response_data_len = 0;
        char *response_json = NULL;

        // Receive request
        if (recv_line(client_fd, &request_line, recv_buffer, &recv_buffer_len, sizeof(recv_buffer)) < 0) {
            break;
        }

        // Parse request
        fprintf(stderr, "[v-euicc] Received request: %s\n", request_line);
        if (protocol_parse_request(request_line, &func, &param, &param_len) < 0) {
            fprintf(stderr, "[v-euicc] Failed to parse request\n");
            free(request_line);
            break;
        }

        fprintf(stderr, "[v-euicc] Parsed function: %s, param_len=%u\n", func, param_len);
        free(request_line);

        // Handle request
        if (strcmp(func, "connect") == 0) {
            fprintf(stderr, "[v-euicc] Handling connect request\n");
            ecode = apdu_handle_connect(&state);
            fprintf(stderr, "[v-euicc] connect returned ecode=%d\n", ecode);
        } else if (strcmp(func, "disconnect") == 0) {
            ecode = apdu_handle_disconnect(&state);
        } else if (strcmp(func, "logic_channel_open") == 0) {
            fprintf(stderr, "[v-euicc] Handling logic_channel_open request\n");
            ecode = apdu_handle_logic_channel_open(&state, param, param_len);
            fprintf(stderr, "[v-euicc] logic_channel_open returned ecode=%d\n", ecode);
        } else if (strcmp(func, "logic_channel_close") == 0) {
            if (param_len > 0) {
                ecode = apdu_handle_logic_channel_close(&state, param[0]);
            }
        } else if (strcmp(func, "transmit") == 0) {
            ecode = apdu_handle_transmit(&state, &response_data, &response_data_len, param, param_len);
        } else {
            fprintf(stderr, "Unknown function: %s\n", func);
            ecode = -1;
        }

        protocol_free_request(func, param);

        // Generate and send response
        response_json = protocol_generate_response(ecode, response_data, response_data_len);
        free(response_data);

        if (!response_json) {
            fprintf(stderr, "[v-euicc] Failed to generate response JSON\n");
            break;
        }

        fprintf(stderr, "[v-euicc] Sending response: %s\n", response_json);
        if (send_line(client_fd, response_json) < 0) {
            fprintf(stderr, "[v-euicc] Failed to send response\n");
            free(response_json);
            break;
        }
        
        // Flush to ensure data is sent immediately
        fflush(stdout);
        fflush(stderr);

        free(response_json);
        fprintf(stderr, "[v-euicc] Response sent successfully\n");

        // If disconnect, close connection
        if (func && strcmp(func, "disconnect") == 0) {
            break;
        }
    }

    printf("Client disconnected\n");
}

int main(int argc, char **argv) {
    int server_fd, client_fd;
    struct sockaddr_storage client_addr;
    socklen_t addr_size;
    const char *port = "8765";

#ifdef _WIN32
    WSADATA wsa_data;
    if (WSAStartup(MAKEWORD(2, 2), &wsa_data) != 0) {
        fprintf(stderr, "WSAStartup failed\n");
        return 1;
    }
#endif

    if (argc > 1) {
        port = argv[1];
    }

    signal(SIGINT, sigint_handler);

    // Initialize logging
    logging_init(LOG_LEVEL_INFO);
    LOG_V_EUICC_INFO("Virtual eUICC daemon starting on port %s", port);

    server_fd = create_server_socket(port);
    if (server_fd < 0) {
        return 1;
    }

    printf("Virtual eUICC daemon listening on port %s\n", port);
    fflush(stdout);
    fprintf(stderr, "[v-euicc] Server socket created, waiting for connections...\n");

    while (keep_running) {
        addr_size = sizeof(client_addr);
        fprintf(stderr, "[v-euicc] Waiting for accept()...\n");
        client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &addr_size);

        if (client_fd < 0) {
            if (errno == EINTR) {
                continue;
            }
            fprintf(stderr, "[v-euicc] accept failed: %s\n", strerror(errno));
            break;
        }

        fprintf(stderr, "[v-euicc] Connection accepted, client_fd=%d\n", client_fd);
        handle_client(client_fd);

#ifdef _WIN32
        closesocket(client_fd);
#else
        close(client_fd);
#endif
    }

#ifdef _WIN32
    closesocket(server_fd);
    WSACleanup();
#else
    close(server_fd);
#endif

    printf("Virtual eUICC daemon stopped\n");
    return 0;
}

