#pragma once

#include <stdint.h>

// Forward declaration to avoid including OpenSSL headers in header
typedef struct evp_pkey_st EVP_PKEY;

// Sign data with eUICC private key using ECDSA
// Data is hashed with SHA-256 and then signed
// Returns DER-encoded signature suitable for SGP.22
// Signature must be freed by caller
int ecdsa_sign(const uint8_t *data, uint32_t data_len,
               EVP_PKEY *private_key,
               uint8_t **signature, uint32_t *signature_len);

// Generate a new EC key pair using P-256 curve
// Returns EVP_PKEY containing the key pair
// Key must be freed with EVP_PKEY_free()
EVP_PKEY *generate_ec_keypair(void);

// Extract public key from EVP_PKEY in uncompressed format (0x04 + X + Y)
// Returns 65-byte buffer (0x04 + 32-byte X + 32-byte Y)
// Buffer must be freed by caller
uint8_t *extract_ec_public_key_uncompressed(EVP_PKEY *keypair, uint32_t *out_len);




