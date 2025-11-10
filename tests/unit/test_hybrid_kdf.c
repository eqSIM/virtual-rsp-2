/*
 * Unit tests for hybrid key derivation function
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#ifdef ENABLE_PQC

// External function declarations
extern int derive_session_keys_hybrid(const uint8_t *Z_ec, uint32_t z_ec_len,
                                     const uint8_t *Z_kem, uint32_t z_kem_len,
                                     uint8_t *kek_out, uint8_t *km_out);

extern int derive_session_keys_ecka(const uint8_t *euicc_otsk, uint32_t euicc_otsk_len,
                                   const uint8_t *smdp_otpk, uint32_t smdp_otpk_len,
                                   uint8_t *session_key_enc, uint8_t *session_key_mac);

void test_hybrid_kdf_basic() {
    printf("TEST: Hybrid KDF with deterministic inputs...\n");
    
    // Deterministic test vectors
    uint8_t Z_ec[32];
    uint8_t Z_kem[32];
    memset(Z_ec, 0xAA, 32);
    memset(Z_kem, 0x55, 32);
    
    uint8_t kek[16], km[16];
    
    int result = derive_session_keys_hybrid(Z_ec, 32, Z_kem, 32, kek, km);
    assert(result == 0);
    
    // Verify keys are not all zeros
    int kek_nonzero = 0, km_nonzero = 0;
    for (int i = 0; i < 16; i++) {
        if (kek[i] != 0) kek_nonzero = 1;
        if (km[i] != 0) km_nonzero = 1;
    }
    assert(kek_nonzero);
    assert(km_nonzero);
    
    // Verify KEK and KM are different
    assert(memcmp(kek, km, 16) != 0);
    
    printf("  ✓ PASSED: Hybrid KDF produces non-zero, distinct keys\n");
}

void test_hybrid_kdf_deterministic() {
    printf("TEST: Hybrid KDF produces consistent output...\n");
    
    uint8_t Z_ec[32];
    uint8_t Z_kem[32];
    memset(Z_ec, 0x01, 32);
    memset(Z_kem, 0x02, 32);
    
    uint8_t kek1[16], km1[16];
    uint8_t kek2[16], km2[16];
    
    // Derive keys twice with same inputs
    int result1 = derive_session_keys_hybrid(Z_ec, 32, Z_kem, 32, kek1, km1);
    int result2 = derive_session_keys_hybrid(Z_ec, 32, Z_kem, 32, kek2, km2);
    
    assert(result1 == 0);
    assert(result2 == 0);
    
    // Verify consistency
    assert(memcmp(kek1, kek2, 16) == 0);
    assert(memcmp(km1, km2, 16) == 0);
    
    printf("  ✓ PASSED: Hybrid KDF is deterministic\n");
}

void test_hybrid_kdf_different_inputs() {
    printf("TEST: Hybrid KDF produces different outputs for different inputs...\n");
    
    uint8_t Z_ec1[32], Z_kem1[32];
    uint8_t Z_ec2[32], Z_kem2[32];
    
    memset(Z_ec1, 0x01, 32);
    memset(Z_kem1, 0x02, 32);
    memset(Z_ec2, 0x03, 32);
    memset(Z_kem2, 0x04, 32);
    
    uint8_t kek1[16], km1[16];
    uint8_t kek2[16], km2[16];
    
    int result1 = derive_session_keys_hybrid(Z_ec1, 32, Z_kem1, 32, kek1, km1);
    int result2 = derive_session_keys_hybrid(Z_ec2, 32, Z_kem2, 32, kek2, km2);
    
    assert(result1 == 0);
    assert(result2 == 0);
    
    // Keys should be different
    assert(memcmp(kek1, kek2, 16) != 0);
    assert(memcmp(km1, km2, 16) != 0);
    
    printf("  ✓ PASSED: Different inputs produce different keys\n");
}

void test_hybrid_kdf_domain_separation() {
    printf("TEST: Hybrid KDF domain separation (EC vs KEM)...\n");
    
    // Use same secret for both EC and KEM
    uint8_t Z_same[32];
    memset(Z_same, 0xFF, 32);
    
    uint8_t kek1[16], km1[16];
    uint8_t kek2[16], km2[16];
    
    // First: EC=0xFF, KEM=0x00
    uint8_t Z_zero[32];
    memset(Z_zero, 0x00, 32);
    int result1 = derive_session_keys_hybrid(Z_same, 32, Z_zero, 32, kek1, km1);
    
    // Second: EC=0x00, KEM=0xFF
    int result2 = derive_session_keys_hybrid(Z_zero, 32, Z_same, 32, kek2, km2);
    
    assert(result1 == 0);
    assert(result2 == 0);
    
    // Should produce different results due to domain separation
    assert(memcmp(kek1, kek2, 16) != 0);
    assert(memcmp(km1, km2, 16) != 0);
    
    printf("  ✓ PASSED: Domain separation prevents input confusion\n");
}

void test_hybrid_kdf_error_handling() {
    printf("TEST: Hybrid KDF error handling...\n");
    
    uint8_t Z_ec[32], Z_kem[32];
    uint8_t kek[16], km[16];
    memset(Z_ec, 0x01, 32);
    memset(Z_kem, 0x02, 32);
    
    // Test NULL inputs
    assert(derive_session_keys_hybrid(NULL, 32, Z_kem, 32, kek, km) == -1);
    assert(derive_session_keys_hybrid(Z_ec, 32, NULL, 32, kek, km) == -1);
    assert(derive_session_keys_hybrid(Z_ec, 32, Z_kem, 32, NULL, km) == -1);
    assert(derive_session_keys_hybrid(Z_ec, 32, Z_kem, 32, kek, NULL) == -1);
    
    // Test wrong sizes
    assert(derive_session_keys_hybrid(Z_ec, 16, Z_kem, 32, kek, km) == -1);
    assert(derive_session_keys_hybrid(Z_ec, 32, Z_kem, 16, kek, km) == -1);
    
    printf("  ✓ PASSED: Error handling works correctly\n");
}

int main() {
    printf("\n╔═══════════════════════════════════════════╗\n");
    printf("║  Hybrid KDF Unit Tests                    ║\n");
    printf("╚═══════════════════════════════════════════╝\n\n");
    
    test_hybrid_kdf_basic();
    test_hybrid_kdf_deterministic();
    test_hybrid_kdf_different_inputs();
    test_hybrid_kdf_domain_separation();
    test_hybrid_kdf_error_handling();
    
    printf("\n✓ All Hybrid KDF tests passed!\n\n");
    return 0;
}

#else
int main() {
    printf("PQC support not enabled (ENABLE_PQC not defined)\n");
    return 0;
}
#endif

