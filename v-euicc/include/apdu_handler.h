#pragma once

#include "euicc_state.h"
#include <stdint.h>

// Handle APDU connect request
int apdu_handle_connect(struct euicc_state *state);

// Handle APDU disconnect request
int apdu_handle_disconnect(struct euicc_state *state);

// Handle logic channel open request
// Returns channel ID on success, -1 on error
int apdu_handle_logic_channel_open(struct euicc_state *state, const uint8_t *aid, uint32_t aid_len);

// Handle logic channel close request
int apdu_handle_logic_channel_close(struct euicc_state *state, uint8_t channel);

// Handle APDU transmit request
// Returns 0 on success with response data, -1 on error
int apdu_handle_transmit(struct euicc_state *state, uint8_t **response, uint32_t *response_len,
                        const uint8_t *command, uint32_t command_len);

