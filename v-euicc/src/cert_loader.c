#include "euicc_state.h"
#include "../logging.h"
#include <openssl/evp.h>
#include <openssl/pem.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Load a file into memory
static int load_file(const char *path, uint8_t **data, uint32_t *len) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "Failed to open: %s\n", path);
        return -1;
    }
    
    // Get file size
    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);
    
    if (fsize <= 0) {
        fclose(f);
        return -1;
    }
    
    *data = malloc((size_t)fsize);
    if (!*data) {
        fclose(f);
        return -1;
    }
    
    size_t read_size = fread(*data, 1, (size_t)fsize, f);
    fclose(f);
    
    if (read_size != (size_t)fsize) {
        free(*data);
        *data = NULL;
        return -1;
    }
    
    *len = (uint32_t)fsize;
    return 0;
}

int euicc_state_load_certificates(struct euicc_state *state, const char *cert_base_dir) {
    char path[512];
    int ret = 0;
    
    // Load eUICC certificate (CERT.EUICC.ECDSA_NIST.der)
    snprintf(path, sizeof(path), "%s/eUICC/CERT_EUICC_ECDSA_NIST.der", cert_base_dir);
    if (load_file(path, &state->euicc_cert, &state->euicc_cert_len) < 0) {
        fprintf(stderr, "Warning: Could not load eUICC certificate from %s\n", path);
        ret = -1;
    } else {
        LOG_V_EUICC_INFO("Loaded eUICC certificate: %u bytes", state->euicc_cert_len);
    }
    
    // Load EUM certificate (CERT.EUM.ECDSA_NIST.der)
    snprintf(path, sizeof(path), "%s/EUM/CERT_EUM_ECDSA_NIST.der", cert_base_dir);
    if (load_file(path, &state->eum_cert, &state->eum_cert_len) < 0) {
        fprintf(stderr, "Warning: Could not load EUM certificate from %s\n", path);
        ret = -1;
    } else {
        LOG_V_EUICC_INFO("Loaded EUM certificate: %u bytes", state->eum_cert_len);
    }
    
    // Load eUICC private key (SK.EUICC.ECDSA_NIST.pem) - Phase 2
    snprintf(path, sizeof(path), "%s/eUICC/SK_EUICC_ECDSA_NIST.pem", cert_base_dir);
    FILE *key_file = fopen(path, "r");
    if (!key_file) {
        fprintf(stderr, "Warning: Could not open private key file %s\n", path);
        ret = -1;
    } else {
        EVP_PKEY *pkey = PEM_read_PrivateKey(key_file, NULL, NULL, NULL);
        fclose(key_file);
        
        if (!pkey) {
            fprintf(stderr, "Warning: Could not parse private key from %s\n", path);
            ret = -1;
        } else {
            // Store EVP_PKEY pointer (cast to uint8_t* for generic storage)
            state->euicc_private_key = (uint8_t*)pkey;
            state->euicc_private_key_len = 1;  // Flag: key is loaded
            LOG_V_EUICC_INFO("Loaded eUICC private key (P-256)");
        }
    }
    
    return ret;
}

