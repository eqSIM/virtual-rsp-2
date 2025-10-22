#pragma once

#include "euicc_state.h"

// Load certificates from filesystem
// For Phase 1: Load generated SGP.26 certificates
// For Phase 2: Also load private keys for signing
int euicc_state_load_certificates(struct euicc_state *state, const char *cert_base_dir);

