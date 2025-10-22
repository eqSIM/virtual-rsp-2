/*
 * Comprehensive Colored Logging Service for Virtual RSP
 * Provides consistent logging across all components with distinct colors
 */

#ifndef LOGGING_H
#define LOGGING_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <stdarg.h>

// ANSI Color Codes
#define LOG_COLOR_RESET       "\033[0m"
#define LOG_COLOR_BLACK       "\033[30m"
#define LOG_COLOR_RED         "\033[31m"
#define LOG_COLOR_GREEN       "\033[32m"
#define LOG_COLOR_YELLOW      "\033[33m"
#define LOG_COLOR_BLUE        "\033[34m"
#define LOG_COLOR_MAGENTA     "\033[35m"
#define LOG_COLOR_CYAN        "\033[36m"
#define LOG_COLOR_WHITE       "\033[37m"
#define LOG_COLOR_BOLD        "\033[1m"
#define LOG_COLOR_DIM         "\033[2m"

// Component-specific colors
#define LOG_COLOR_V_EUICC     LOG_COLOR_CYAN
#define LOG_COLOR_OSMO_SMDPP  LOG_COLOR_GREEN
#define LOG_COLOR_LPAC        LOG_COLOR_YELLOW
#define LOG_COLOR_NGINX       LOG_COLOR_MAGENTA
#define LOG_COLOR_TEST        LOG_COLOR_BLUE
#define LOG_COLOR_ERROR       LOG_COLOR_RED
#define LOG_COLOR_SUCCESS     LOG_COLOR_GREEN LOG_COLOR_BOLD

// Log levels
typedef enum {
    LOG_LEVEL_DEBUG = 0,
    LOG_LEVEL_INFO = 1,
    LOG_LEVEL_WARN = 2,
    LOG_LEVEL_ERROR = 3,
    LOG_LEVEL_CRITICAL = 4
} log_level_t;

// Current log level (can be set at runtime)
extern log_level_t current_log_level;

// Initialize logging (call once at startup)
void logging_init(log_level_t level);

// Component names
#define LOG_COMPONENT_V_EUICC    "v-euicc"
#define LOG_COMPONENT_OSMO_SMDPP "osmo-smdpp"
#define LOG_COMPONENT_LPAC       "lpac"
#define LOG_COMPONENT_NGINX      "nginx"
#define LOG_COMPONENT_TEST       "test"

// Function to get current timestamp
static inline void get_timestamp(char *buffer, size_t size) {
    time_t now = time(NULL);
    struct tm *tm_info = localtime(&now);
    strftime(buffer, size, "%H:%M:%S", tm_info);
}

// Main logging function
static inline void log_message(log_level_t level, const char *component,
                              const char *color, const char *level_str,
                              const char *format, ...) {
    if (level < current_log_level) {
        return;
    }

    char timestamp[20];
    get_timestamp(timestamp, sizeof(timestamp));

    // Get PID for process identification
    pid_t pid = getpid();

    // Print timestamp, component, and level with color
    fprintf(stderr, "%s[%s] %s%-12s%s %-8s [%d] ",
            LOG_COLOR_DIM, timestamp, color, component, LOG_COLOR_RESET,
            level_str, pid);

    // Print the actual message
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);

    fprintf(stderr, "%s\n", LOG_COLOR_RESET);
}

// Convenience macros for different log levels
#define LOG_DEBUG(component, color, ...) \
    log_message(LOG_LEVEL_DEBUG, component, color, "DEBUG", __VA_ARGS__)

#define LOG_INFO(component, color, ...) \
    log_message(LOG_LEVEL_INFO, component, color, "INFO", __VA_ARGS__)

#define LOG_WARN(component, color, ...) \
    log_message(LOG_LEVEL_WARN, component, color, "WARN", __VA_ARGS__)

#define LOG_ERROR(component, color, ...) \
    log_message(LOG_LEVEL_ERROR, component, color, "ERROR", __VA_ARGS__)

#define LOG_CRITICAL(component, color, ...) \
    log_message(LOG_LEVEL_CRITICAL, component, color, "CRITICAL", __VA_ARGS__)

// Component-specific logging macros
#define LOG_V_EUICC_DEBUG(...)   LOG_DEBUG(LOG_COMPONENT_V_EUICC, LOG_COLOR_V_EUICC, __VA_ARGS__)
#define LOG_V_EUICC_INFO(...)    LOG_INFO(LOG_COMPONENT_V_EUICC, LOG_COLOR_V_EUICC, __VA_ARGS__)
#define LOG_V_EUICC_WARN(...)    LOG_WARN(LOG_COMPONENT_V_EUICC, LOG_COLOR_V_EUICC, __VA_ARGS__)
#define LOG_V_EUICC_ERROR(...)   LOG_ERROR(LOG_COMPONENT_V_EUICC, LOG_COLOR_V_EUICC, __VA_ARGS__)

#define LOG_OSMO_SMDPP_DEBUG(...)   LOG_DEBUG(LOG_COMPONENT_OSMO_SMDPP, LOG_COLOR_OSMO_SMDPP, __VA_ARGS__)
#define LOG_OSMO_SMDPP_INFO(...)    LOG_INFO(LOG_COMPONENT_OSMO_SMDPP, LOG_COLOR_OSMO_SMDPP, __VA_ARGS__)
#define LOG_OSMO_SMDPP_WARN(...)    LOG_WARN(LOG_COMPONENT_OSMO_SMDPP, LOG_COLOR_OSMO_SMDPP, __VA_ARGS__)
#define LOG_OSMO_SMDPP_ERROR(...)   LOG_ERROR(LOG_COMPONENT_OSMO_SMDPP, LOG_COLOR_OSMO_SMDPP, __VA_ARGS__)

#define LOG_LPAC_DEBUG(...)   LOG_DEBUG(LOG_COMPONENT_LPAC, LOG_COLOR_LPAC, __VA_ARGS__)
#define LOG_LPAC_INFO(...)    LOG_INFO(LOG_COMPONENT_LPAC, LOG_COLOR_LPAC, __VA_ARGS__)
#define LOG_LPAC_WARN(...)    LOG_WARN(LOG_COMPONENT_LPAC, LOG_COLOR_LPAC, __VA_ARGS__)
#define LOG_LPAC_ERROR(...)   LOG_ERROR(LOG_COMPONENT_LPAC, LOG_COLOR_LPAC, __VA_ARGS__)

#define LOG_NGINX_DEBUG(...)   LOG_DEBUG(LOG_COMPONENT_NGINX, LOG_COLOR_NGINX, __VA_ARGS__)
#define LOG_NGINX_INFO(...)    LOG_INFO(LOG_COMPONENT_NGINX, LOG_COLOR_NGINX, __VA_ARGS__)
#define LOG_NGINX_WARN(...)    LOG_WARN(LOG_COMPONENT_NGINX, LOG_COLOR_NGINX, __VA_ARGS__)
#define LOG_NGINX_ERROR(...)   LOG_ERROR(LOG_COMPONENT_NGINX, LOG_COLOR_NGINX, __VA_ARGS__)

#define LOG_TEST_DEBUG(...)   LOG_DEBUG(LOG_COMPONENT_TEST, LOG_COLOR_TEST, __VA_ARGS__)
#define LOG_TEST_INFO(...)    LOG_INFO(LOG_COMPONENT_TEST, LOG_COLOR_TEST, __VA_ARGS__)
#define LOG_TEST_WARN(...)    LOG_WARN(LOG_COMPONENT_TEST, LOG_COLOR_TEST, __VA_ARGS__)
#define LOG_TEST_ERROR(...)   LOG_ERROR(LOG_COMPONENT_TEST, LOG_COLOR_TEST, __VA_ARGS__)
#define LOG_TEST_SUCCESS(...) LOG_INFO(LOG_COMPONENT_TEST, LOG_COLOR_SUCCESS, __VA_ARGS__)

// Hex dump utility for debugging
static inline void log_hex_dump(const char *component, const char *color,
                               const char *prefix, const uint8_t *data, size_t len) {
    if (LOG_LEVEL_DEBUG < current_log_level) {
        return;
    }

    char timestamp[20];
    get_timestamp(timestamp, sizeof(timestamp));
    pid_t pid = getpid();

    fprintf(stderr, "%s[%s] %s%-12s%s %-8s [%d] %s (%zu bytes):\n",
            LOG_COLOR_DIM, timestamp, color, component, LOG_COLOR_RESET,
            "DEBUG", pid, prefix, len);

    for (size_t i = 0; i < len; i++) {
        if (i % 16 == 0) {
            fprintf(stderr, "%s[%s] %s%-12s%s %-8s [%d]   ",
                    LOG_COLOR_DIM, timestamp, color, component, LOG_COLOR_RESET,
                    "DEBUG", pid);
        }
        fprintf(stderr, "%s%02x", (i % 16 == 0) ? "" : " ", data[i]);
        if ((i + 1) % 16 == 0 || i == len - 1) {
            fprintf(stderr, "%s\n", LOG_COLOR_RESET);
        }
    }
}

#define LOG_V_EUICC_HEX_DUMP(prefix, data, len) \
    log_hex_dump(LOG_COMPONENT_V_EUICC, LOG_COLOR_V_EUICC, prefix, data, len)

#define LOG_OSMO_SMDPP_HEX_DUMP(prefix, data, len) \
    log_hex_dump(LOG_COMPONENT_OSMO_SMDPP, LOG_COLOR_OSMO_SMDPP, prefix, data, len)

#endif /* LOGGING_H */
