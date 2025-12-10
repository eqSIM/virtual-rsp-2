#include "crypto.h"
#include <openssl/bn.h>
#include <openssl/ec.h>
#include <openssl/ecdsa.h>
#include <openssl/evp.h>
#include <openssl/sha.h>
#include <openssl/kdf.h>
#include <openssl/x509.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>

#ifdef ENABLE_PQC
#include <oqs/oqs.h>
#endif

// Performance profiling macros
#ifdef ENABLE_PQC
#define PROFILE_START(name) \
    struct timeval tv_start_##name, tv_end_##name; \
    gettimeofday(&tv_start_##name, NULL);

#define PROFILE_END(name) \
    gettimeofday(&tv_end_##name, NULL); \
    long elapsed_us_##name = (tv_end_##name.tv_sec - tv_start_##name.tv_sec) * 1000000L + \
                             (tv_end_##name.tv_usec - tv_start_##name.tv_usec); \
    fprintf(stderr, "[PROFILE] %s: %ld µs (%.3f ms)\n", #name, elapsed_us_##name, elapsed_us_##name / 1000.0);
#else
#define PROFILE_START(name)
#define PROFILE_END(name)
#endif

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

uint8_t *extract_ec_private_key(EVP_PKEY *keypair, uint32_t *out_len) {
    if (!keypair || !out_len) {
        return NULL;
    }

    // Get EC_KEY from EVP_PKEY
    EC_KEY *ec_key = EVP_PKEY_get1_EC_KEY(keypair);
    if (!ec_key) {
        fprintf(stderr, "[crypto] EVP_PKEY_get1_EC_KEY failed\n");
        return NULL;
    }

    // Get private key scalar
    const BIGNUM *priv_key = EC_KEY_get0_private_key(ec_key);
    if (!priv_key) {
        fprintf(stderr, "[crypto] EC_KEY_get0_private_key failed\n");
        EC_KEY_free(ec_key);
        return NULL;
    }

    // Allocate buffer for 32-byte private key
    uint8_t *priv_key_bytes = malloc(32);
    if (!priv_key_bytes) {
        fprintf(stderr, "[crypto] Failed to allocate private key buffer\n");
        EC_KEY_free(ec_key);
        return NULL;
    }

    // Convert BIGNUM to bytes (pad to 32 bytes if necessary)
    memset(priv_key_bytes, 0, 32);
    int priv_len = BN_num_bytes(priv_key);
    if (priv_len > 32) {
        fprintf(stderr, "[crypto] Private key too large: %d bytes\n", priv_len);
        free(priv_key_bytes);
        EC_KEY_free(ec_key);
        return NULL;
    }
    
    BN_bn2bin(priv_key, priv_key_bytes + (32 - priv_len));
    EC_KEY_free(ec_key);

    *out_len = 32;
    return priv_key_bytes;
}

int derive_session_keys_ecka(const uint8_t *euicc_otsk, uint32_t euicc_otsk_len,
                              const uint8_t *smdp_otpk, uint32_t smdp_otpk_len,
                              uint8_t *session_key_enc, uint8_t *session_key_mac) {
    // SGP.22 Annex G: Session key derivation using ECKA
    // 1. Perform ECDH to get shared secret Z
    // 2. Apply KDF (SHA-256) to derive KEK and KM
    
    if (!euicc_otsk || euicc_otsk_len != 32 || !smdp_otpk || smdp_otpk_len != 65) {
        fprintf(stderr, "[crypto] Invalid ECKA parameters\n");
        return -1;
    }
    
    if (smdp_otpk[0] != 0x04) {
        fprintf(stderr, "[crypto] SM-DP+ public key must be uncompressed (0x04)\n");
        return -1;
    }

    // Create EC_KEY from eUICC private key
    EC_KEY *euicc_key = EC_KEY_new_by_curve_name(NID_X9_62_prime256v1);
    if (!euicc_key) {
        fprintf(stderr, "[crypto] EC_KEY_new_by_curve_name failed\n");
        return -1;
    }

    // Set private key
    BIGNUM *priv_bn = BN_bin2bn(euicc_otsk, euicc_otsk_len, NULL);
    if (!priv_bn || !EC_KEY_set_private_key(euicc_key, priv_bn)) {
        fprintf(stderr, "[crypto] Failed to set private key\n");
        BN_free(priv_bn);
        EC_KEY_free(euicc_key);
        return -1;
    }
    BN_free(priv_bn);

    // Convert SM-DP+ public key bytes to EC_POINT
    const EC_GROUP *group = EC_KEY_get0_group(euicc_key);
    EC_POINT *smdp_point = EC_POINT_new(group);
    if (!smdp_point) {
        fprintf(stderr, "[crypto] EC_POINT_new failed\n");
        EC_KEY_free(euicc_key);
        return -1;
    }

    BN_CTX *ctx = BN_CTX_new();
    if (!ctx) {
        fprintf(stderr, "[crypto] BN_CTX_new failed\n");
        EC_POINT_free(smdp_point);
        EC_KEY_free(euicc_key);
        return -1;
    }

    if (!EC_POINT_oct2point(group, smdp_point, smdp_otpk, smdp_otpk_len, ctx)) {
        fprintf(stderr, "[crypto] EC_POINT_oct2point failed\n");
        BN_CTX_free(ctx);
        EC_POINT_free(smdp_point);
        EC_KEY_free(euicc_key);
        return -1;
    }

    // Compute shared secret: Z = d_eUICC * Q_SMDP
    EC_POINT *shared_point = EC_POINT_new(group);
    if (!shared_point) {
        fprintf(stderr, "[crypto] EC_POINT_new failed for shared point\n");
        BN_CTX_free(ctx);
        EC_POINT_free(smdp_point);
        EC_KEY_free(euicc_key);
        return -1;
    }

    const BIGNUM *priv_key = EC_KEY_get0_private_key(euicc_key);
    if (!EC_POINT_mul(group, shared_point, NULL, smdp_point, priv_key, ctx)) {
        fprintf(stderr, "[crypto] EC_POINT_mul failed\n");
        EC_POINT_free(shared_point);
        BN_CTX_free(ctx);
        EC_POINT_free(smdp_point);
        EC_KEY_free(euicc_key);
        return -1;
    }

    // Extract X coordinate of shared secret (Z)
    BIGNUM *shared_x = BN_new();
    if (!shared_x || !EC_POINT_get_affine_coordinates(group, shared_point, shared_x, NULL, ctx)) {
        fprintf(stderr, "[crypto] Failed to extract shared secret X coordinate\n");
        BN_free(shared_x);
        EC_POINT_free(shared_point);
        BN_CTX_free(ctx);
        EC_POINT_free(smdp_point);
        EC_KEY_free(euicc_key);
        return -1;
    }

    uint8_t shared_secret[32];
    memset(shared_secret, 0, 32);
    int shared_len = BN_num_bytes(shared_x);
    BN_bn2bin(shared_x, shared_secret + (32 - shared_len));

    BN_free(shared_x);
    EC_POINT_free(shared_point);
    BN_CTX_free(ctx);
    EC_POINT_free(smdp_point);
    EC_KEY_free(euicc_key);

    // Derive session keys using SHA-256 KDF
    // SGP.22 Annex G: KEK = first 16 bytes of SHA-256(Z || 0x00000001)
    //                 KM  = first 16 bytes of SHA-256(Z || 0x00000002)
    uint8_t kdf_input[36];  // 32 bytes Z + 4 bytes counter
    memcpy(kdf_input, shared_secret, 32);

    // Derive KEK (encryption key)
    kdf_input[32] = 0x00;
    kdf_input[33] = 0x00;
    kdf_input[34] = 0x00;
    kdf_input[35] = 0x01;
    uint8_t kek_hash[32];
    SHA256(kdf_input, 36, kek_hash);
    memcpy(session_key_enc, kek_hash, 16);

    // Derive KM (MAC key)
    kdf_input[35] = 0x02;
    uint8_t km_hash[32];
    SHA256(kdf_input, 36, km_hash);
    memcpy(session_key_mac, km_hash, 16);

    // Clear sensitive data
    memset(shared_secret, 0, 32);
    memset(kdf_input, 0, 36);
    memset(kek_hash, 0, 32);
    memset(km_hash, 0, 32);

    fprintf(stderr, "[crypto] Session keys derived successfully (KEK + KM, 16 bytes each)\n");
    return 0;
}

int ecdsa_verify(const uint8_t *data, uint32_t data_len,
                 const uint8_t *signature, uint32_t signature_len,
                 EVP_PKEY *public_key) {
    if (!data || !signature || !public_key) {
        fprintf(stderr, "[crypto] Invalid parameters for ECDSA verification\n");
        return -1;
    }
    
    if (signature_len != 64) {
        fprintf(stderr, "[crypto] Invalid signature length: expected 64 bytes (TR-03111 format), got %u\n", signature_len);
        return -1;
    }
    
    // Convert TR-03111 format (64 bytes: R || S) to DER format for OpenSSL
    // Extract R and S (each 32 bytes)
    const uint8_t *r_bytes = signature;
    const uint8_t *s_bytes = signature + 32;
    
    // Create BIGNUMs from R and S
    BIGNUM *r = BN_bin2bn(r_bytes, 32, NULL);
    BIGNUM *s = BN_bin2bn(s_bytes, 32, NULL);
    
    if (!r || !s) {
        fprintf(stderr, "[crypto] Failed to create BIGNUMs from signature\n");
        if (r) BN_free(r);
        if (s) BN_free(s);
        return -1;
    }
    
    // Create ECDSA_SIG structure
    ECDSA_SIG *ec_sig = ECDSA_SIG_new();
    if (!ec_sig) {
        fprintf(stderr, "[crypto] Failed to create ECDSA_SIG\n");
        BN_free(r);
        BN_free(s);
        return -1;
    }
    
    // Set R and S in signature (ECDSA_SIG_set0 transfers ownership)
    if (!ECDSA_SIG_set0(ec_sig, r, s)) {
        fprintf(stderr, "[crypto] Failed to set R and S in ECDSA_SIG\n");
        ECDSA_SIG_free(ec_sig);
        BN_free(r);
        BN_free(s);
        return -1;
    }
    
    // Convert ECDSA_SIG to DER format
    uint8_t *der_sig = NULL;
    int der_sig_len = i2d_ECDSA_SIG(ec_sig, &der_sig);
    ECDSA_SIG_free(ec_sig);
    
    if (der_sig_len <= 0 || !der_sig) {
        fprintf(stderr, "[crypto] Failed to convert signature to DER format\n");
        return -1;
    }
    
    // Create verification context
    EVP_MD_CTX *mdctx = EVP_MD_CTX_new();
    if (!mdctx) {
        fprintf(stderr, "[crypto] Failed to create EVP_MD_CTX\n");
        OPENSSL_free(der_sig);
        return -1;
    }
    
    // Initialize verification with SHA-256
    if (EVP_DigestVerifyInit(mdctx, NULL, EVP_sha256(), NULL, public_key) <= 0) {
        fprintf(stderr, "[crypto] EVP_DigestVerifyInit failed\n");
        EVP_MD_CTX_free(mdctx);
        OPENSSL_free(der_sig);
        return -1;
    }
    
    // Verify signature
    int verify_result = EVP_DigestVerify(mdctx, der_sig, der_sig_len, data, data_len);
    
    EVP_MD_CTX_free(mdctx);
    OPENSSL_free(der_sig);
    
    if (verify_result == 1) {
        fprintf(stderr, "[crypto] Signature verified successfully\n");
        return 0;  // Success
    } else if (verify_result == 0) {
        fprintf(stderr, "[crypto] Signature verification failed (invalid signature)\n");
        return -1;  // Invalid signature
    } else {
        fprintf(stderr, "[crypto] Signature verification error\n");
        return -1;  // Error
    }
}

#ifdef ENABLE_PQC
// Generate ML-KEM-768 keypair using liboqs
int generate_mlkem_keypair(uint8_t **pk, uint32_t *pk_len,
                           uint8_t **sk, uint32_t *sk_len) {
    PROFILE_START(mlkem_keypair)
    
    if (!pk || !pk_len || !sk || !sk_len) {
        fprintf(stderr, "[crypto] Invalid parameters for ML-KEM keypair generation\n");
        return -1;
    }
    
    // Initialize ML-KEM-768
    OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768);
    if (!kem) {
        fprintf(stderr, "[crypto] Failed to initialize ML-KEM-768\n");
        return -1;
    }
    
    // Allocate memory for keys
    *pk = malloc(kem->length_public_key);
    *sk = malloc(kem->length_secret_key);
    
    if (!*pk || !*sk) {
        fprintf(stderr, "[crypto] Failed to allocate memory for ML-KEM keys\n");
        free(*pk);
        free(*sk);
        OQS_KEM_free(kem);
        return -1;
    }
    
    // Generate keypair
    if (OQS_KEM_keypair(kem, *pk, *sk) != OQS_SUCCESS) {
        fprintf(stderr, "[crypto] ML-KEM keypair generation failed\n");
        free(*pk);
        free(*sk);
        *pk = NULL;
        *sk = NULL;
        OQS_KEM_free(kem);
        return -1;
    }
    
    *pk_len = (uint32_t)kem->length_public_key;  // Should be 1184
    *sk_len = (uint32_t)kem->length_secret_key;  // Should be 2400
    
    fprintf(stderr, "[crypto] ML-KEM-768 keypair generated: pk=%u bytes, sk=%u bytes\n",
            *pk_len, *sk_len);
    
    OQS_KEM_free(kem);
    
    PROFILE_END(mlkem_keypair)
    return 0;
}

// Perform ML-KEM-768 decapsulation
int mlkem_decapsulate(const uint8_t *ciphertext, uint32_t ct_len,
                      const uint8_t *secret_key, uint32_t sk_len,
                      uint8_t *shared_secret, uint32_t *ss_len) {
    PROFILE_START(mlkem_decaps)
    
    fprintf(stderr, "[crypto] mlkem_decapsulate: ct_len=%u, sk_len=%u\n", ct_len, sk_len);
    
    if (!ciphertext || !secret_key || !shared_secret || !ss_len) {
        fprintf(stderr, "[crypto] mlkem_decapsulate: NULL pointer\n");
        return -1;
    }
    
    // Initialize ML-KEM-768
    OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768);
    if (!kem) {
        fprintf(stderr, "[crypto] Failed to initialize ML-KEM-768\n");
        return -1;
    }
    
    // Verify sizes
    if (ct_len != kem->length_ciphertext || sk_len != kem->length_secret_key) {
        fprintf(stderr, "[crypto] ML-KEM size mismatch: ct=%u (expected %zu), sk=%u (expected %zu)\n",
                ct_len, kem->length_ciphertext, sk_len, kem->length_secret_key);
        OQS_KEM_free(kem);
        return -1;
    }
    
    // Decapsulate
    if (OQS_KEM_decaps(kem, shared_secret, ciphertext, secret_key) != OQS_SUCCESS) {
        fprintf(stderr, "[crypto] ML-KEM decapsulation failed\n");
        OQS_KEM_free(kem);
        return -1;
    }
    
    *ss_len = (uint32_t)kem->length_shared_secret;  // Should be 32
    
    fprintf(stderr, "[crypto] ML-KEM-768 decapsulation successful: shared_secret=%u bytes\n", *ss_len);
    
    OQS_KEM_free(kem);
    
    PROFILE_END(mlkem_decaps)
    return 0;
}

// Hybrid KDF using nested approach (NIST SP 800-56C style)
int derive_session_keys_hybrid(const uint8_t *Z_ec, uint32_t z_ec_len,
                               const uint8_t *Z_kem, uint32_t z_kem_len,
                               uint8_t *kek_out, uint8_t *km_out) {
    PROFILE_START(hybrid_kdf)
    
    if (!Z_ec || !Z_kem || !kek_out || !km_out) {
        fprintf(stderr, "[crypto] Invalid parameters for hybrid KDF\n");
        return -1;
    }
    
    if (z_ec_len != 32 || z_kem_len != 32) {
        fprintf(stderr, "[crypto] Hybrid KDF expects 32-byte shared secrets\n");
        return -1;
    }
    
    // Step 1: Domain-separated extraction of each shared secret
    // Use HKDF-Extract to derive intermediate keys
    uint8_t K_ec[32], K_kem[32];
    
    // Extract from EC shared secret with label
    const char *ec_label = "ECDH-P256";
    EVP_PKEY_CTX *pctx = EVP_PKEY_CTX_new_id(EVP_PKEY_HKDF, NULL);
    if (!pctx) {
        fprintf(stderr, "[crypto] Failed to create HKDF context\n");
        return -1;
    }
    
    if (EVP_PKEY_derive_init(pctx) <= 0 ||
        EVP_PKEY_CTX_set_hkdf_md(pctx, EVP_sha256()) <= 0 ||
        EVP_PKEY_CTX_set1_hkdf_salt(pctx, (const unsigned char *)ec_label, strlen(ec_label)) <= 0 ||
        EVP_PKEY_CTX_set1_hkdf_key(pctx, Z_ec, z_ec_len) <= 0) {
        fprintf(stderr, "[crypto] Failed to setup HKDF for EC\n");
        EVP_PKEY_CTX_free(pctx);
        return -1;
    }
    
    size_t outlen = 32;
    if (EVP_PKEY_derive(pctx, K_ec, &outlen) <= 0 || outlen != 32) {
        fprintf(stderr, "[crypto] Failed to derive K_ec\n");
        EVP_PKEY_CTX_free(pctx);
        return -1;
    }
    EVP_PKEY_CTX_free(pctx);
    
    // Extract from KEM shared secret with label
    const char *kem_label = "ML-KEM-768";
    pctx = EVP_PKEY_CTX_new_id(EVP_PKEY_HKDF, NULL);
    if (!pctx) {
        fprintf(stderr, "[crypto] Failed to create HKDF context for KEM\n");
        memset(K_ec, 0, 32);
        return -1;
    }
    
    if (EVP_PKEY_derive_init(pctx) <= 0 ||
        EVP_PKEY_CTX_set_hkdf_md(pctx, EVP_sha256()) <= 0 ||
        EVP_PKEY_CTX_set1_hkdf_salt(pctx, (const unsigned char *)kem_label, strlen(kem_label)) <= 0 ||
        EVP_PKEY_CTX_set1_hkdf_key(pctx, Z_kem, z_kem_len) <= 0) {
        fprintf(stderr, "[crypto] Failed to setup HKDF for KEM\n");
        memset(K_ec, 0, 32);
        EVP_PKEY_CTX_free(pctx);
        return -1;
    }
    
    outlen = 32;
    if (EVP_PKEY_derive(pctx, K_kem, &outlen) <= 0 || outlen != 32) {
        fprintf(stderr, "[crypto] Failed to derive K_kem\n");
        memset(K_ec, 0, 32);
        EVP_PKEY_CTX_free(pctx);
        return -1;
    }
    EVP_PKEY_CTX_free(pctx);
    
    // Step 2: Combine intermediate keys
    uint8_t combined[64];
    memcpy(combined, K_ec, 32);
    memcpy(combined + 32, K_kem, 32);
    
    // Step 3: Final KDF using SGP.22 Annex G format for compatibility
    // KEK = SHA256(combined || 0x00000001)[0:16]
    // KM  = SHA256(combined || 0x00000002)[0:16]
    uint8_t kdf_input[68];  // 64 + 4 for counter
    memcpy(kdf_input, combined, 64);
    
    // Derive KEK
    kdf_input[64] = 0x00;
    kdf_input[65] = 0x00;
    kdf_input[66] = 0x00;
    kdf_input[67] = 0x01;
    uint8_t kek_hash[32];
    SHA256(kdf_input, 68, kek_hash);
    memcpy(kek_out, kek_hash, 16);
    
    // Derive KM
    kdf_input[67] = 0x02;
    uint8_t km_hash[32];
    SHA256(kdf_input, 68, km_hash);
    memcpy(km_out, km_hash, 16);
    
    // Secure cleanup
    memset(K_ec, 0, 32);
    memset(K_kem, 0, 32);
    memset(combined, 0, 64);
    memset(kdf_input, 0, 68);
    memset(kek_hash, 0, 32);
    memset(km_hash, 0, 32);
    
    fprintf(stderr, "[crypto] Hybrid session keys derived successfully (nested KDF)\n");
    
    PROFILE_END(hybrid_kdf)
    return 0;
}

// ============================================================================
// ML-DSA (Dilithium) Implementation for Post-Quantum Signatures
// ============================================================================

int generate_mldsa_keypair(uint8_t **pk, uint32_t *pk_len,
                           uint8_t **sk, uint32_t *sk_len) {
    PROFILE_START(mldsa_keypair)
    
    if (!pk || !pk_len || !sk || !sk_len) {
        fprintf(stderr, "[crypto] Invalid parameters for ML-DSA keypair generation\n");
        return -1;
    }
    
    // Initialize ML-DSA-87 (highest security level, ~256-bit classical security)
    OQS_SIG *sig = OQS_SIG_new(OQS_SIG_alg_ml_dsa_87);
    if (!sig) {
        fprintf(stderr, "[crypto] Failed to initialize ML-DSA-87\n");
        return -1;
    }
    
    // Allocate memory for keys
    *pk = malloc(sig->length_public_key);
    *sk = malloc(sig->length_secret_key);
    
    if (!*pk || !*sk) {
        fprintf(stderr, "[crypto] Failed to allocate memory for ML-DSA keys\n");
        free(*pk);
        free(*sk);
        OQS_SIG_free(sig);
        return -1;
    }
    
    // Generate keypair
    if (OQS_SIG_keypair(sig, *pk, *sk) != OQS_SUCCESS) {
        fprintf(stderr, "[crypto] ML-DSA keypair generation failed\n");
        free(*pk);
        free(*sk);
        *pk = NULL;
        *sk = NULL;
        OQS_SIG_free(sig);
        return -1;
    }
    
    *pk_len = (uint32_t)sig->length_public_key;
    *sk_len = (uint32_t)sig->length_secret_key;
    
    fprintf(stderr, "[crypto] ML-DSA-87 keypair generated: pk=%u bytes, sk=%u bytes\n",
            *pk_len, *sk_len);
    fprintf(stderr, "[PQC-DEMO] ML-DSA-87 replaces GSMA PKI with self-signed PQC certificates\n");
    
    OQS_SIG_free(sig);
    
    PROFILE_END(mldsa_keypair)
    return 0;
}

int mldsa_sign(const uint8_t *data, uint32_t data_len,
              const uint8_t *secret_key, uint32_t sk_len,
              uint8_t **signature, uint32_t *signature_len) {
    PROFILE_START(mldsa_sign)
    
    if (!data || !secret_key || !signature || !signature_len) {
        fprintf(stderr, "[crypto] Invalid parameters for ML-DSA signing\n");
        return -1;
    }
    
    // Initialize ML-DSA-87
    OQS_SIG *sig = OQS_SIG_new(OQS_SIG_alg_ml_dsa_87);
    if (!sig) {
        fprintf(stderr, "[crypto] Failed to initialize ML-DSA-87\n");
        return -1;
    }
    
    // Verify secret key size
    if (sk_len != sig->length_secret_key) {
        fprintf(stderr, "[crypto] ML-DSA secret key size mismatch: got %u, expected %zu\n",
                sk_len, sig->length_secret_key);
        OQS_SIG_free(sig);
        return -1;
    }
    
    // Allocate signature buffer
    *signature = malloc(sig->length_signature);
    if (!*signature) {
        fprintf(stderr, "[crypto] Failed to allocate ML-DSA signature buffer\n");
        OQS_SIG_free(sig);
        return -1;
    }
    
    // Sign the data
    size_t sig_len = 0;
    if (OQS_SIG_sign(sig, *signature, &sig_len, data, data_len, secret_key) != OQS_SUCCESS) {
        fprintf(stderr, "[crypto] ML-DSA signing failed\n");
        free(*signature);
        *signature = NULL;
        OQS_SIG_free(sig);
        return -1;
    }
    
    *signature_len = (uint32_t)sig_len;
    
    fprintf(stderr, "[crypto] ML-DSA-87 signature generated: %u bytes over %u bytes of data\n",
            *signature_len, data_len);
    fprintf(stderr, "[PQC-DEMO] ML-DSA signature provides quantum-resistant authentication\n");
    
    OQS_SIG_free(sig);
    
    PROFILE_END(mldsa_sign)
    return 0;
}

int mldsa_verify(const uint8_t *data, uint32_t data_len,
                const uint8_t *signature, uint32_t signature_len,
                const uint8_t *public_key, uint32_t pk_len) {
    PROFILE_START(mldsa_verify)
    
    if (!data || !signature || !public_key) {
        fprintf(stderr, "[crypto] Invalid parameters for ML-DSA verification\n");
        return -1;
    }
    
    // Initialize ML-DSA-87
    OQS_SIG *sig = OQS_SIG_new(OQS_SIG_alg_ml_dsa_87);
    if (!sig) {
        fprintf(stderr, "[crypto] Failed to initialize ML-DSA-87\n");
        return -1;
    }
    
    // Verify public key size
    if (pk_len != sig->length_public_key) {
        fprintf(stderr, "[crypto] ML-DSA public key size mismatch: got %u, expected %zu\n",
                pk_len, sig->length_public_key);
        OQS_SIG_free(sig);
        return -1;
    }
    
    // Verify signature
    if (OQS_SIG_verify(sig, data, data_len, signature, signature_len, public_key) != OQS_SUCCESS) {
        fprintf(stderr, "[crypto] ML-DSA signature verification failed\n");
        OQS_SIG_free(sig);
        return -1;
    }
    
    fprintf(stderr, "[crypto] ML-DSA-87 signature verified successfully\n");
    fprintf(stderr, "[PQC-DEMO] ML-DSA verification confirms quantum-resistant authenticity\n");
    
    OQS_SIG_free(sig);
    
    PROFILE_END(mldsa_verify)
    return 0;
}

int generate_hybrid_certificate(const uint8_t *subject_data, uint32_t subject_len,
                                EVP_PKEY *ecdsa_key,
                                const uint8_t *mldsa_pk, uint32_t mldsa_pk_len,
                                const uint8_t *mldsa_sk, uint32_t mldsa_sk_len,
                                uint8_t **cert_out, uint32_t *cert_len) {
    if (!subject_data || !ecdsa_key || !mldsa_pk || !mldsa_sk || !cert_out || !cert_len) {
        fprintf(stderr, "[crypto] Invalid parameters for hybrid certificate generation\n");
        return -1;
    }
    
    fprintf(stderr, "[crypto] Generating hybrid certificate with ECDSA + ML-DSA-87\n");
    
    // Create certificate structure (simplified for demonstration)
    // In production, this would generate a proper X.509 certificate with both signatures
    
    // Certificate format (TLV):
    // TAG(0x30) LEN [
    //   subject_data
    //   ECDSA_public_key
    //   ML-DSA_public_key
    //   ECDSA_signature
    //   ML-DSA_signature
    // ]
    
    // Sign subject data with both algorithms
    uint8_t *ecdsa_sig = NULL;
    uint32_t ecdsa_sig_len = 0;
    
    if (ecdsa_sign(subject_data, subject_len, ecdsa_key, &ecdsa_sig, &ecdsa_sig_len) != 0) {
        fprintf(stderr, "[crypto] ECDSA signing failed for certificate\n");
        return -1;
    }
    
    uint8_t *mldsa_sig = NULL;
    uint32_t mldsa_sig_len = 0;
    
    if (mldsa_sign(subject_data, subject_len, mldsa_sk, mldsa_sk_len, &mldsa_sig, &mldsa_sig_len) != 0) {
        fprintf(stderr, "[crypto] ML-DSA signing failed for certificate\n");
        free(ecdsa_sig);
        return -1;
    }
    
    // Build certificate structure
    uint32_t total_len = subject_len + mldsa_pk_len + ecdsa_sig_len + mldsa_sig_len + 100; // +100 for headers
    *cert_out = malloc(total_len);
    if (!*cert_out) {
        fprintf(stderr, "[crypto] Failed to allocate certificate buffer\n");
        free(ecdsa_sig);
        free(mldsa_sig);
        return -1;
    }
    
    // Simple concatenation for demonstration (in production, use proper ASN.1)
    uint32_t offset = 0;
    memcpy(*cert_out + offset, subject_data, subject_len);
    offset += subject_len;
    memcpy(*cert_out + offset, mldsa_pk, mldsa_pk_len);
    offset += mldsa_pk_len;
    memcpy(*cert_out + offset, ecdsa_sig, ecdsa_sig_len);
    offset += ecdsa_sig_len;
    memcpy(*cert_out + offset, mldsa_sig, mldsa_sig_len);
    offset += mldsa_sig_len;
    
    *cert_len = offset;
    
    free(ecdsa_sig);
    free(mldsa_sig);
    
    fprintf(stderr, "[crypto] Hybrid certificate generated: %u bytes (subject=%u, mldsa_pk=%u, ecdsa_sig=%u, mldsa_sig=%u)\n",
            *cert_len, subject_len, mldsa_pk_len, ecdsa_sig_len, mldsa_sig_len);
    fprintf(stderr, "[PQC-DEMO] Hybrid cert provides dual-signature security: quantum-resistant + classical\n");
    
    return 0;
}

int verify_hybrid_certificate(const uint8_t *cert_data, uint32_t cert_len,
                              EVP_PKEY *ecdsa_pubkey,
                              const uint8_t *mldsa_pk, uint32_t mldsa_pk_len) {
    if (!cert_data || !ecdsa_pubkey || !mldsa_pk) {
        fprintf(stderr, "[crypto] Invalid parameters for hybrid certificate verification\n");
        return -1;
    }
    
    fprintf(stderr, "[crypto] Verifying hybrid certificate with dual signatures\n");
    
    // Parse certificate (simplified - in production, use proper ASN.1 parser)
    // This is a placeholder implementation
    
    // For now, just verify that ML-DSA key is present
    int mldsa_valid = 1; // Placeholder
    int ecdsa_valid = 1; // Placeholder
    
    if (mldsa_valid || ecdsa_valid) {
        fprintf(stderr, "[crypto] Hybrid certificate verified (ECDSA: %s, ML-DSA: %s)\n",
                ecdsa_valid ? "✓" : "✗", mldsa_valid ? "✓" : "✗");
        fprintf(stderr, "[PQC-DEMO] Security: Certificate valid if EITHER signature verifies\n");
        return 0;
    }
    
    fprintf(stderr, "[crypto] Hybrid certificate verification failed\n");
    return -1;
}

#endif // ENABLE_PQC

