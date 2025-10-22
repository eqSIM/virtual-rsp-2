#include "protocol.h"
#include <euicc/hexutil.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int protocol_parse_request(const char *json_str, char **func, uint8_t **param, uint32_t *param_len) {
    cJSON *jroot = NULL;
    cJSON *jtype = NULL;
    cJSON *jpayload = NULL;
    cJSON *jfunc = NULL;
    cJSON *jparam = NULL;
    int ret = -1;

    *func = NULL;
    *param = NULL;
    *param_len = 0;

    jroot = cJSON_Parse(json_str);
    if (!jroot) {
        goto cleanup;
    }

    jtype = cJSON_GetObjectItem(jroot, "type");
    if (!jtype || !cJSON_IsString(jtype) || strcmp(jtype->valuestring, "apdu") != 0) {
        goto cleanup;
    }

    jpayload = cJSON_GetObjectItem(jroot, "payload");
    if (!jpayload || !cJSON_IsObject(jpayload)) {
        goto cleanup;
    }

    jfunc = cJSON_GetObjectItem(jpayload, "func");
    if (!jfunc || !cJSON_IsString(jfunc)) {
        goto cleanup;
    }

    *func = strdup(jfunc->valuestring);
    if (!*func) {
        goto cleanup;
    }

    jparam = cJSON_GetObjectItem(jpayload, "param");
    if (jparam && cJSON_IsString(jparam)) {
        const char *param_hex = jparam->valuestring;
        *param_len = strlen(param_hex) / 2;
        if (*param_len > 0) {
            *param = malloc(*param_len);
            if (!*param) {
                goto cleanup;
            }
            if (euicc_hexutil_hex2bin_r(*param, *param_len, param_hex, strlen(param_hex)) < 0) {
                goto cleanup;
            }
        }
    }

    ret = 0;

cleanup:
    if (ret != 0) {
        free(*func);
        free(*param);
        *func = NULL;
        *param = NULL;
        *param_len = 0;
    }
    cJSON_Delete(jroot);
    return ret;
}

char *protocol_generate_response(int ecode, const uint8_t *data, uint32_t data_len) {
    cJSON *jroot = NULL;
    cJSON *jpayload = NULL;
    char *data_hex = NULL;
    char *result = NULL;

    jroot = cJSON_CreateObject();
    if (!jroot) {
        return NULL;
    }

    if (!cJSON_AddStringToObject(jroot, "type", "apdu")) {
        goto cleanup;
    }

    jpayload = cJSON_CreateObject();
    if (!jpayload) {
        goto cleanup;
    }

    if (!cJSON_AddNumberToObject(jpayload, "ecode", ecode)) {
        goto cleanup;
    }

    if (data && data_len > 0) {
        data_hex = malloc((2 * data_len) + 1);
        if (!data_hex) {
            goto cleanup;
        }
        if (euicc_hexutil_bin2hex(data_hex, (2 * data_len) + 1, data, data_len) < 0) {
            goto cleanup;
        }
        if (!cJSON_AddStringToObject(jpayload, "data", data_hex)) {
            goto cleanup;
        }
    }

    if (!cJSON_AddItemToObject(jroot, "payload", jpayload)) {
        jpayload = NULL; // Ownership transferred, don't delete in cleanup
        goto cleanup;
    }

    result = cJSON_PrintUnformatted(jroot);

cleanup:
    free(data_hex);
    cJSON_Delete(jroot);
    if (jpayload && !result) {
        cJSON_Delete(jpayload);
    }
    return result;
}

void protocol_free_request(char *func, uint8_t *param) {
    free(func);
    free(param);
}

