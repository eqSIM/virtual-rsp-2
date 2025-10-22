#include "crypto.h"
#include <openssl/bn.h>
#include <openssl/ec.h>
#include <openssl/ecdsa.h>
#include <openssl/evp.h>
#include <openssl/sha.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int ecdsa_sign(const uint8_t *data, uint32_t data_len,
               EVP_PKEY *private_key,
               uint8_t **signature, uint32_t *signature_len) {
    
    if (!private_key || !data || !signature || !signature_len) {
        return -1;
    }
    
    *signature = NULL;
    *signature_len = 0;
    
    // Create signing context
    EVP_MD_CTX *mdctx = EVP_MD_CTX_new();
    if (!mdctx) {
        fprintf(stderr, "[crypto] Failed to create EVP_MD_CTX\n");
        return -1;
    }
    
    // Initialize signing operation with SHA-256
    if (EVP_DigestSignInit(mdctx, NULL, EVP_sha256(), NULL, private_key) <= 0) {
        fprintf(stderr, "[crypto] EVP_DigestSignInit failed\n");
        EVP_MD_CTX_free(mdctx);
        return -1;
    }
    
    // Get DER signature length
    size_t der_sig_len = 0;
    if (EVP_DigestSign(mdctx, NULL, &der_sig_len, data, data_len) <= 0) {
        fprintf(stderr, "[crypto] EVP_DigestSign (get length) failed\n");
        EVP_MD_CTX_free(mdctx);
        return -1;
    }
    
    // Allocate buffer for DER signature
    uint8_t *der_signature = malloc(der_sig_len);
    if (!der_signature) {
        fprintf(stderr, "[crypto] Failed to allocate DER signature buffer\n");
        EVP_MD_CTX_free(mdctx);
        return -1;
    }
    
    // Generate DER signature
    if (EVP_DigestSign(mdctx, der_signature, &der_sig_len, data, data_len) <= 0) {
        fprintf(stderr, "[crypto] EVP_DigestSign (generate) failed\n");
        free(der_signature);
        EVP_MD_CTX_free(mdctx);
        return -1;
    }
    
    EVP_MD_CTX_free(mdctx);
    
    fprintf(stderr, "[crypto] DER signature generated: %zu bytes\n", der_sig_len);
    
    // Convert DER to raw format (TR-03111: 64 bytes = 32-byte R + 32-byte S)
    // Parse DER SEQUENCE to extract R and S
    ECDSA_SIG *ec_sig = NULL;
    const uint8_t *der_ptr = der_signature;
    ec_sig = d2i_ECDSA_SIG(NULL, &der_ptr, (long)der_sig_len);
    free(der_signature);
    
    if (!ec_sig) {
        fprintf(stderr, "[crypto] Failed to parse DER signature\n");
        return -1;
    }
    
    const BIGNUM *r, *s;
    ECDSA_SIG_get0(ec_sig, &r, &s);
    
    // Convert to raw 64-byte format (32 bytes R + 32 bytes S)
    *signature = malloc(64);
    if (!*signature) {
        ECDSA_SIG_free(ec_sig);
        return -1;
    }
    
    memset(*signature, 0, 64);
    
    // Extract R (pad to 32 bytes)
    int r_len = BN_num_bytes(r);
    BN_bn2bin(r, *signature + (32 - r_len));
    
    // Extract S (pad to 32 bytes)
    int s_len = BN_num_bytes(s);
    BN_bn2bin(s, *signature + 32 + (32 - s_len));
    
    *signature_len = 64;
    ECDSA_SIG_free(ec_sig);
    
    fprintf(stderr, "[crypto] Converted to TR-03111 raw format: 64 bytes (R=%d, S=%d)\n", r_len, s_len);

    return 0;
}

EVP_PKEY *generate_ec_keypair(void) {
    EVP_PKEY_CTX *pctx = NULL;
    EVP_PKEY *pkey = NULL;

    // Create context for key generation
    pctx = EVP_PKEY_CTX_new_id(EVP_PKEY_EC, NULL);
    if (!pctx) {
        fprintf(stderr, "[crypto] Failed to create EVP_PKEY_CTX\n");
        return NULL;
    }

    // Initialize key generation
    if (EVP_PKEY_keygen_init(pctx) <= 0) {
        fprintf(stderr, "[crypto] EVP_PKEY_keygen_init failed\n");
        EVP_PKEY_CTX_free(pctx);
        return NULL;
    }

    // Set curve to P-256 (secp256r1)
    if (EVP_PKEY_CTX_set_ec_paramgen_curve_nid(pctx, NID_X9_62_prime256v1) <= 0) {
        fprintf(stderr, "[crypto] EVP_PKEY_CTX_set_ec_paramgen_curve_nid failed\n");
        EVP_PKEY_CTX_free(pctx);
        return NULL;
    }

    // Generate key pair
    if (EVP_PKEY_keygen(pctx, &pkey) <= 0) {
        fprintf(stderr, "[crypto] EVP_PKEY_keygen failed\n");
        EVP_PKEY_CTX_free(pctx);
        return NULL;
    }

    EVP_PKEY_CTX_free(pctx);
    return pkey;
}

uint8_t *extract_ec_public_key_uncompressed(EVP_PKEY *keypair, uint32_t *out_len) {
    if (!keypair || !out_len) {
        return NULL;
    }

    // Get EC_KEY from EVP_PKEY
    EC_KEY *ec_key = EVP_PKEY_get1_EC_KEY(keypair);
    if (!ec_key) {
        fprintf(stderr, "[crypto] EVP_PKEY_get1_EC_KEY failed\n");
        return NULL;
    }

    // Get public key point
    const EC_POINT *pub_key = EC_KEY_get0_public_key(ec_key);
    if (!pub_key) {
        fprintf(stderr, "[crypto] EC_KEY_get0_public_key failed\n");
        EC_KEY_free(ec_key);
        return NULL;
    }

    // Get curve group
    const EC_GROUP *group = EC_KEY_get0_group(ec_key);
    if (!group) {
        fprintf(stderr, "[crypto] EC_KEY_get0_group failed\n");
        EC_KEY_free(ec_key);
        return NULL;
    }

    // Allocate buffer for uncompressed public key (0x04 + X + Y = 65 bytes)
    uint8_t *pub_key_bytes = malloc(65);
    if (!pub_key_bytes) {
        fprintf(stderr, "[crypto] Failed to allocate public key buffer\n");
        EC_KEY_free(ec_key);
        return NULL;
    }

    // Convert point to uncompressed format
    BN_CTX *ctx = BN_CTX_new();
    if (!ctx) {
        fprintf(stderr, "[crypto] BN_CTX_new failed\n");
        free(pub_key_bytes);
        EC_KEY_free(ec_key);
        return NULL;
    }

    size_t pub_key_len = EC_POINT_point2oct(group, pub_key, POINT_CONVERSION_UNCOMPRESSED,
                                           pub_key_bytes, 65, ctx);
    if (pub_key_len != 65) {
        fprintf(stderr, "[crypto] EC_POINT_point2oct failed or wrong length: %zu\n", pub_key_len);
        free(pub_key_bytes);
        BN_CTX_free(ctx);
        EC_KEY_free(ec_key);
        return NULL;
    }

    BN_CTX_free(ctx);
    EC_KEY_free(ec_key);

    *out_len = 65;
    return pub_key_bytes;
}

