/*
 * Logging Service Implementation
 */

#include "logging.h"

// Global log level variable
log_level_t current_log_level = LOG_LEVEL_INFO;

void logging_init(log_level_t level) {
    current_log_level = level;
}
