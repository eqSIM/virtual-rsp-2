/*
 * Unit tests for ML-KEM-768 keypair generation and decapsulation
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#ifdef ENABLE_PQC
#include <oqs/oqs.h>

// External function declarations (from crypto.c)
extern int generate_mlkem_keypair(uint8_t **pk, uint32_t *pk_len,
                                  uint8_t **sk, uint32_t *sk_len);
extern int mlkem_decapsulate(const uint8_t *ciphertext, uint32_t ct_len,
                             const uint8_t *secret_key, uint32_t sk_len,
                             uint8_t *shared_secret, uint32_t *ss_len);

void test_mlkem_keypair_generation() {
    printf("TEST: ML-KEM-768 keypair generation...\n");
    
    uint8_t *pk = NULL;
    uint32_t pk_len = 0;
    uint8_t *sk = NULL;
    uint32_t sk_len = 0;
    
    int result = generate_mlkem_keypair(&pk, &pk_len, &sk, &sk_len);
    
    assert(result == 0);
    assert(pk != NULL);
    assert(sk != NULL);
    assert(pk_len == 1184);  // ML-KEM-768 public key size
    assert(sk_len == 2400);  // ML-KEM-768 secret key size
    
    // Verify keys are not all zeros
    int pk_nonzero = 0, sk_nonzero = 0;
    for (uint32_t i = 0; i < pk_len; i++) {
        if (pk[i] != 0) pk_nonzero = 1;
    }
    for (uint32_t i = 0; i < sk_len; i++) {
        if (sk[i] != 0) sk_nonzero = 1;
    }
    assert(pk_nonzero);
    assert(sk_nonzero);
    
    free(pk);
    free(sk);
    
    printf("  ✓ PASSED: Keypair generated with correct sizes\n");
}

void test_mlkem_encaps_decaps() {
    printf("TEST: ML-KEM-768 encapsulation/decapsulation...\n");
    
    // Generate keypair
    uint8_t *pk = NULL;
    uint32_t pk_len = 0;
    uint8_t *sk = NULL;
    uint32_t sk_len = 0;
    
    int result = generate_mlkem_keypair(&pk, &pk_len, &sk, &sk_len);
    assert(result == 0);
    
    // Encapsulate using liboqs directly
    OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768);
    assert(kem != NULL);
    
    uint8_t *ciphertext = malloc(kem->length_ciphertext);
    uint8_t shared_secret_encaps[32];
    
    result = OQS_KEM_encaps(kem, ciphertext, shared_secret_encaps, pk);
    assert(result == OQS_SUCCESS);
    
    // Decapsulate using our function
    uint8_t shared_secret_decaps[32];
    uint32_t ss_len = 32;
    
    result = mlkem_decapsulate(ciphertext, kem->length_ciphertext,
                               sk, sk_len,
                               shared_secret_decaps, &ss_len);
    assert(result == 0);
    assert(ss_len == 32);
    
    // Verify shared secrets match
    assert(memcmp(shared_secret_encaps, shared_secret_decaps, 32) == 0);
    
    free(pk);
    free(sk);
    free(ciphertext);
    OQS_KEM_free(kem);
    
    printf("  ✓ PASSED: Encapsulation and decapsulation produce matching shared secrets\n");
}

void test_mlkem_invalid_inputs() {
    printf("TEST: ML-KEM-768 error handling...\n");
    
    uint8_t *pk = NULL, *sk = NULL;
    uint32_t pk_len = 0, sk_len = 0;
    uint8_t ss[32];
    uint32_t ss_len = 32;
    uint8_t ct[1088];
    
    // Test NULL inputs to keypair generation
    assert(generate_mlkem_keypair(NULL, &pk_len, &sk, &sk_len) == -1);
    assert(generate_mlkem_keypair(&pk, NULL, &sk, &sk_len) == -1);
    
    // Test NULL inputs to decapsulation
    assert(mlkem_decapsulate(NULL, 1088, sk, 2400, ss, &ss_len) == -1);
    assert(mlkem_decapsulate(ct, 1088, NULL, 2400, ss, &ss_len) == -1);
    assert(mlkem_decapsulate(ct, 1088, sk, 2400, NULL, &ss_len) == -1);
    
    printf("  ✓ PASSED: Error handling works correctly\n");
}

int main() {
    printf("\n╔═══════════════════════════════════════════╗\n");
    printf("║  ML-KEM-768 Unit Tests                    ║\n");
    printf("╚═══════════════════════════════════════════╝\n\n");
    
    test_mlkem_keypair_generation();
    test_mlkem_encaps_decaps();
    test_mlkem_invalid_inputs();
    
    printf("\n✓ All ML-KEM tests passed!\n\n");
    return 0;
}

#else
int main() {
    printf("PQC support not enabled (ENABLE_PQC not defined)\n");
    return 0;
}
#endif

