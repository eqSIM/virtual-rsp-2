#include "euicc_state.h"
#include <openssl/evp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

void euicc_state_init(struct euicc_state *state) {
    memset(state, 0, sizeof(struct euicc_state));
    
    // Hardcoded test EID (32 hex characters)
    strcpy(state->eid, "89049032001001234500012345678901");
    
    // Default addresses
    strcpy(state->default_smdp, "");  // Empty by default
    strcpy(state->root_smds, "testrootsmds.gsma.com");
    
    state->logic_channel = -1;
    state->aid_len = 0;
    state->transaction_id_len = 0;
    
    // Initialize random seed for challenge generation
    srand((unsigned int)time(NULL));
    
    // Initialize certificate pointers
    state->euicc_cert = NULL;
    state->eum_cert = NULL;
    state->euicc_private_key = NULL;
    
    // Initialize segment buffer
    state->segment_buffer = NULL;
    state->segment_buffer_len = 0;
    state->segment_buffer_capacity = 0;
    
    // Initialize download session
    state->bpp_commands_received = 0;
    state->notification_seq_number = 1;  // Start from 1
    memset(state->matching_id, 0, sizeof(state->matching_id));
    
    // Initialize ECKA session keys
    state->euicc_otpk = NULL;
    state->euicc_otpk_len = 0;
    state->euicc_otsk = NULL;
    state->euicc_otsk_len = 0;
    state->smdp_otpk = NULL;
    state->smdp_otpk_len = 0;
    memset(state->session_key_enc, 0, sizeof(state->session_key_enc));
    memset(state->session_key_mac, 0, sizeof(state->session_key_mac));
    state->session_keys_derived = 0;

    // Initialize profile storage
    state->bound_profile_package = NULL;
    state->bound_profile_package_len = 0;
    state->bound_profile_package_capacity = 0;

    state->installed_profiles = NULL;
    state->installed_profiles_len = 0;
    state->installed_profiles_capacity = 0;
    
    // Initialize profile metadata list
    state->profiles = NULL;
}

void euicc_state_reset(struct euicc_state *state) {
    state->logic_channel = -1;
    state->aid_len = 0;
    state->transaction_id_len = 0;
    memset(state->aid, 0, sizeof(state->aid));
    memset(state->euicc_challenge, 0, sizeof(state->euicc_challenge));
    memset(state->server_challenge, 0, sizeof(state->server_challenge));
    memset(state->transaction_id, 0, sizeof(state->transaction_id));
    
    // Free segment buffer
    free(state->segment_buffer);
    state->segment_buffer = NULL;
    state->segment_buffer_len = 0;
    state->segment_buffer_capacity = 0;
    
    // Free OpenSSL private key
    if (state->euicc_private_key_len > 0 && state->euicc_private_key) {
        EVP_PKEY_free((EVP_PKEY*)state->euicc_private_key);
        state->euicc_private_key = NULL;
        state->euicc_private_key_len = 0;
    }
    
    // Free certificates
    free(state->euicc_cert);
    free(state->eum_cert);
    state->euicc_cert = NULL;
    state->eum_cert = NULL;
    state->euicc_cert_len = 0;
    state->eum_cert_len = 0;
    
    // Free ECKA session keys
    free(state->euicc_otpk);
    free(state->euicc_otsk);
    free(state->smdp_otpk);
    state->euicc_otpk = NULL;
    state->euicc_otpk_len = 0;
    state->euicc_otsk = NULL;
    state->euicc_otsk_len = 0;
    state->smdp_otpk = NULL;
    state->smdp_otpk_len = 0;
    memset(state->session_key_enc, 0, sizeof(state->session_key_enc));
    memset(state->session_key_mac, 0, sizeof(state->session_key_mac));
    state->session_keys_derived = 0;

    // Free profile storage
    free(state->bound_profile_package);
    free(state->installed_profiles);
    state->bound_profile_package = NULL;
    state->bound_profile_package_len = 0;
    state->bound_profile_package_capacity = 0;
    state->installed_profiles = NULL;
    state->installed_profiles_len = 0;
    state->installed_profiles_capacity = 0;
    
    // Free profile metadata list
    struct profile_metadata *profile = state->profiles;
    while (profile) {
        struct profile_metadata *next = profile->next;
        free(profile->profile_data);
        free(profile);
        profile = next;
    }
    state->profiles = NULL;
}

// Certificate loading moved to cert_loader.c

