#pragma once

#include <cjson/cJSON.h>
#include <stdint.h>

// Parse incoming JSON APDU request
// Returns 0 on success, -1 on error
int protocol_parse_request(const char *json_str, char **func, uint8_t **param, uint32_t *param_len);

// Generate JSON APDU response
// Returns JSON string that must be freed by caller, or NULL on error
char *protocol_generate_response(int ecode, const uint8_t *data, uint32_t data_len);

// Free memory allocated by protocol_parse_request
void protocol_free_request(char *func, uint8_t *param);

