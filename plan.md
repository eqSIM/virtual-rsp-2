# PQC Migration Guide for Virtual RSP Testbed
## Methodology-Focused Implementation Plan

---

## Executive Summary

Your current testbed successfully implements **SGP.22 Phase 2** (real crypto with ECDSA + ECKA). The PQC migration follows **GSMA's phased approach**: prioritize key exchange (ES8+) while deferring signature migration. This preserves your existing authentication infrastructure while addressing the immediate SNDL threat.

**Core Principle**: Minimize disruption by adding PQC as a **parallel capability**, not a replacement.

---

## Phase 0: Current State Analysis

### What You Have (✅ Working)

```
┌─────────────────────────────────────────────────────────┐
│  Current Testbed: Classical Cryptography (NIST P-256)  │
└─────────────────────────────────────────────────────────┘

ES10b.AuthenticateServer:
├─ eUICC generates ECDSA signature (64 bytes, TR-03111)
├─ Uses SK.EUICC.ECDSA from loaded certificate
└─ SM-DP+ verifies signature ✓

ES10b.PrepareDownload:
├─ eUICC generates ephemeral EC keypair (otPK/otSK.EUICC.ECKA)
├─ Public key: 65 bytes uncompressed (0x04 || X || Y)
└─ Stored in state for later use ✓

ES8+.InitialiseSecureChannel:
├─ Receives smdpOtpk from SM-DP+
├─ ECDH: Z = otSK.EUICC × otPK.DP
├─ KDF (Annex G): KEK || KM = SHA256(Z || counter)
└─ Session keys derived ✓

BPP Installation:
├─ Receives encrypted profile data
├─ Stores in bound_profile_package buffer
└─ Creates profile_metadata (ICCID, name, state) ✓
```

### What's Missing for PQC

1. **No hybrid key agreement** (only ECDH)
2. **No ML-KEM keypair generation**
3. **No ciphertext handling** (ML-KEM encapsulation/decapsulation)
4. **No capability negotiation** (eUICC can't advertise PQC support)
5. **No ASN.1 extensions** for hybrid structures

---

## Phase 1: Foundations (Week 1-2)

### 1.1 Dependency Integration

**Goal**: Add liboqs to your build system without breaking existing code.

**Methodology**:
- **Conservative approach**: Keep liboqs as optional dependency initially
- **Verification strategy**: Build with/without PQC support to ensure compatibility
- **Risk mitigation**: Use feature flags to isolate PQC code paths

**CMake Strategy** (`v-euicc/CMakeLists.txt`):
```cmake
option(ENABLE_PQC "Enable Post-Quantum Cryptography support" ON)

if(ENABLE_PQC)
    find_package(liboqs REQUIRED)
    target_compile_definitions(v-euicc-daemon PRIVATE ENABLE_PQC)
    target_link_libraries(v-euicc-daemon PRIVATE OQS::oqs)
endif()
```

**Why this works**:
- Existing code unaffected when `ENABLE_PQC=OFF`
- Clear separation of classical vs. hybrid code paths
- Easy rollback if integration issues arise

**Verification Test**:
```bash
# Test 1: Ensure classical mode still works
cmake -DENABLE_PQC=OFF .. && make
./demo.sh  # Should pass all existing tests

# Test 2: Verify PQC libraries link correctly
cmake -DENABLE_PQC=ON .. && make
ldd build/v-euicc/v-euicc-daemon | grep oqs  # Should show liboqs
```

### 1.2 Capability Negotiation Framework

**Goal**: Add infrastructure for eUICC to advertise PQC support before actual implementation.

**Methodology**:
- **Top-down design**: Define capability structure first, implement crypto later
- **Backward compatibility**: Classical-only eUICCs report no PQC capabilities
- **Future-proofing**: Extensible bit flags for multiple PQC algorithms

**Design Decision**: Where to add capabilities?

```
Option A: Extend EUICCInfo2 (ES10c.GetEUICCInfo)
  ✓ Already sent during mutual authentication
  ✓ SM-DP+ reads it before PrepareDownload
  ✗ Requires SGP.22 spec change (slow standardization)

Option B: Custom extension in AuthenticateServer response
  ✓ Minimal spec impact
  ✓ Vendor-specific extensions allowed in SGP.22
  ✗ Not standardized (research prototype only)

✅ Choose Option A for standards compliance
```

**Implementation Strategy** (in `apdu_handler.c`):
```c
// Conceptual structure - don't implement crypto yet
typedef struct {
    bool mlkem768_supported;    // Phase 1 target
    bool mlkem1024_supported;   // Higher security level
    bool mldsa_supported;       // Phase 2 (signatures)
    bool hybrid_only;           // Cannot do PQC-only mode
} pqc_capabilities_t;

// Add to euicc_state structure
struct euicc_state {
    // ... existing fields ...
    pqc_capabilities_t pqc_caps;  // ← New field
};
```

**Why separate capabilities from implementation**:
- Allows SM-DP+ to negotiate before generating keys
- Enables gradual rollout (advertise capability before full implementation)
- Facilitates testing (can mock capabilities)

---

## Phase 2: Hybrid Key Generation (Week 3-4)

### 2.1 Conceptual Model: Dual-Key Architecture

**Current (ECKA-only)**:
```
PrepareDownload:
  Input:  None
  Output: (otPK.EUICC.ECKA, otSK.EUICC.ECKA)
  
InitialiseSecureChannel:
  Input:  smdpOtpk (65 bytes)
  Derive: Z = otSK.EUICC × smdpOtpk
  Output: KEK || KM from Z
```

**Target (Hybrid)**:
```
PrepareDownload:
  Input:  None
  Output: (otPK_EC, otSK_EC)      ← Classical (existing)
          (pk_KEM, sk_KEM)        ← PQC (new)
  
InitialiseSecureChannel:
  Input:  smdpOtpk_EC (65 bytes)       ← Classical
          smdpCiphertext_KEM (1088 B)  ← PQC
  Derive: Z_EC = otSK_EC × smdpOtpk_EC
          Z_KEM = Decaps(ct, sk_KEM)
          Z = Z_EC || Z_KEM
  Output: KEK || KM from Z
```

**Security Rationale**:
- **Defense in depth**: Secure if *either* ECDH *or* ML-KEM is secure
- **SNDL protection**: Quantum adversary must break ML-KEM to recover past keys
- **Performance**: ECDH still provides forward secrecy against classical attackers

### 2.2 State Management Strategy

**Challenge**: Where to store ML-KEM keys?

Your `euicc_state` already has:
```c
uint8_t *euicc_otpk;   // ECDH public key (65 bytes)
uint8_t *euicc_otsk;   // ECDH private key (32 bytes)
```

**Design Decision**: Parallel storage vs. unified structure?

```
Option A: Separate fields (simple but cluttered)
  uint8_t *euicc_otpk_ec;
  uint8_t *euicc_otsk_ec;
  uint8_t *euicc_pk_kem;
  uint8_t *euicc_sk_kem;
  
Option B: Unified hybrid keypair structure
  typedef struct {
      uint8_t *ec_public;
      uint8_t *ec_private;
      uint8_t *kem_public;
      uint8_t *kem_private;
      bool is_hybrid;
  } hybrid_keypair_t;
  
  hybrid_keypair_t euicc_keypair;

✅ Choose Option B for maintainability
```

**Why unified structure**:
- Single source of truth for "hybrid mode" state
- Easier cleanup (free one struct vs. 4 pointers)
- Natural extension point for future algorithms

### 2.3 Key Generation Methodology

**Critical Decision**: When to generate ML-KEM keys?

```
Timing Option A: During PrepareDownload
  ✓ Matches existing ECKA key generation
  ✓ Keys available when building response
  ✗ Larger state overhead (hold both keypairs)

Timing Option B: Lazy generation (only if SM-DP+ requests hybrid)
  ✓ Saves resources if SM-DP+ doesn't support PQC
  ✗ Complicates PrepareDownload logic

✅ Choose Option A for simplicity
```

**Implementation Philosophy**: 

Replace your current `generate_ec_keypair()` call with:
```c
// Pseudocode - focus on methodology
hybrid_keypair_t* generate_hybrid_keypair(pqc_capabilities_t caps) {
    hybrid_keypair_t *keypair = allocate_keypair();
    
    // Classical part (always generate)
    keypair->ec = generate_ec_keypair_p256();
    
    // PQC part (conditional)
    if (caps.mlkem768_supported) {
        OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768);
        OQS_KEM_keypair(kem, keypair->kem_public, keypair->kem_private);
        keypair->is_hybrid = true;
    } else {
        keypair->is_hybrid = false;
    }
    
    return keypair;
}
```

**Why this layered approach**:
- Classical path unchanged (backward compatibility)
- PQC opt-in based on capabilities (gradual migration)
- Easy to test (mock `pqc_capabilities_t`)

### 2.4 Memory Management Considerations

**Challenge**: ML-KEM keys are large.

| Key Type | Size | Your Current Allocation |
|----------|------|-------------------------|
| ECDH public | 65 B | `malloc(65)` ✓ |
| ECDH private | 32 B | `malloc(32)` ✓ |
| **ML-KEM-768 public** | **1184 B** | **Not allocated** |
| **ML-KEM-768 private** | **2400 B** | **Not allocated** |

**Memory Strategy**:
```
Classical mode:    ~100 bytes per session
Hybrid mode:      ~3700 bytes per session
Increase:         37× larger!
```

**Risk Mitigation**:
1. **Allocate on demand**: Only when hybrid mode negotiated
2. **Zero and free immediately**: After `InitialiseSecureChannel` completes
3. **Monitor testbed memory**: Add logging for peak usage

**Secure Cleanup Pattern**:
```c
void free_hybrid_keypair(hybrid_keypair_t *keypair) {
    if (keypair->kem_private) {
        // CRITICAL: Zero before freeing (avoid memory disclosure)
        memset(keypair->kem_private, 0, 2400);
        free(keypair->kem_private);
    }
    // ... similar for other keys
}
```

---

## Phase 3: Protocol Message Extensions (Week 5-6)

### 3.1 ASN.1 Strategy

**Goal**: Extend SGP.22 structures to carry hybrid keys without breaking parsers.

**Backward Compatibility Principle**:
```
Classical parser reading hybrid message:
  ✓ Must successfully parse known fields
  ✗ Can ignore unknown PQC fields (ASN.1 extensibility)

Hybrid parser reading classical message:
  ✓ Must successfully parse
  ✓ Must detect absence of PQC fields
  ✓ Must fall back to classical mode
```

**Design Decision**: How to extend `PrepareDownloadResponse`?

Current structure (`rsp.asn`):
```asn1
PrepareDownloadResponseOk ::= SEQUENCE {
    euiccSigned2 EUICCSigned2,
    euiccSignature2 [APPLICATION 55] OCTET STRING
}

EUICCSigned2 ::= SEQUENCE {
    transactionId [0] TransactionId,
    euiccOtpk [APPLICATION 73] OCTET STRING,  -- 65 bytes ECDH
    hashCc Octet32 OPTIONAL
}
```

**Extension Strategy**:
```asn1
-- Option A: Add optional field (preserves backward compat)
EUICCSigned2-v3 ::= SEQUENCE {
    transactionId [0] TransactionId,
    euiccOtpk [APPLICATION 73] OCTET STRING,  -- Classical (required)
    euiccOtpkKEM [APPLICATION 74] OCTET STRING OPTIONAL,  -- PQC (optional)
    hashCc Octet32 OPTIONAL
}

-- Option B: Use CHOICE (breaks backward compat)
EUICCSigned2-v3 ::= SEQUENCE {
    transactionId [0] TransactionId,
    keyMaterial CHOICE {
        classical [APPLICATION 73] OCTET STRING,
        hybrid [APPLICATION 74] SEQUENCE {
            ecdhKey OCTET STRING,
            mlkemKey OCTET STRING
        }
    },
    hashCc Octet32 OPTIONAL
}

✅ Choose Option A (optional field)
```

**Rationale**:
- Optional field = graceful degradation
- Classical parsers skip unknown tags
- Hybrid parsers check for tag 74 presence

**Implementation Impact** (in `apdu_handler.c`):

You currently build `euiccSigned2` like this:
```c
// Current: Classical-only
uint8_t *otpk_tlv = NULL;
build_tlv(&otpk_tlv, &otpk_tlv_len, 0x5F49, euicc_otpk, 65);
memcpy(signed2_ptr, otpk_tlv, otpk_tlv_len);
```

**Hybrid extension**:
```c
// Step 1: Add classical key (always present)
build_tlv(&otpk_ec_tlv, 0x5F49, euicc_otpk_ec, 65);
memcpy(signed2_ptr, otpk_ec_tlv, ...);
signed2_ptr += ...;

// Step 2: Conditionally add PQC key
if (state->pqc_caps.mlkem768_supported) {
    build_tlv(&otpk_kem_tlv, 0x5F4A, euicc_pk_kem, 1184);
    memcpy(signed2_ptr, otpk_kem_tlv, ...);
    signed2_ptr += ...;
}
```

**Why this works**:
- Classical SM-DP+ reads tag 0x5F49, derives ECDH-only keys
- Hybrid SM-DP+ reads both tags, performs hybrid key agreement
- No protocol ambiguity

### 3.2 Wire Format Considerations

**Challenge**: How does SM-DP+ send ML-KEM ciphertext?

After eUICC sends `pk_KEM` in `PrepareDownload`, SM-DP+ must send back:
1. Classical: `smdpOtpk_EC` (65 bytes) 
2. Hybrid: `smdpOtpk_EC` (65 bytes) + `ciphertext` (1088 bytes)

**Protocol Flow Design**:
```
Current InitialiseSecureChannel:
  BF23 {
    smdpOtpk [APPLICATION 73] 65 bytes
    smdpSign [APPLICATION 55] 64 bytes
  }

Hybrid InitialiseSecureChannel:
  BF23 {
    smdpOtpk [APPLICATION 73] 65 bytes        ← Classical (unchanged)
    smdpCiphertextKEM [APPLICATION 75] 1088 bytes  ← PQC (new)
    smdpSign [APPLICATION 55] variable bytes  ← Signs both keys
  }
```

**APDU Segmentation Problem**:
- Your testbed handles segmentation in `apdu_handle_transmit()`
- Current buffer: 256 bytes per APDU
- ML-KEM ciphertext: 1088 bytes → **5 APDUs minimum**

**Solution Strategy**:
```
Option A: Extend segment_buffer (already implemented)
  ✓ Your code already handles multi-APDU commands
  ✓ No protocol changes needed
  ✗ Testing: Ensure buffer size adequate (1088 + overhead)

Option B: Compress ciphertext (academic optimization)
  ✗ No standard compression for ML-KEM
  ✗ Added complexity

✅ Reuse existing segmentation (Option A)
```

**Verification**:
```c
// In apdu_handle_transmit(), verify buffer capacity
if (new_len > state->segment_buffer_capacity) {
    uint32_t new_capacity = new_len + 2048;  // ← Increase headroom
    uint8_t *new_buffer = realloc(state->segment_buffer, new_capacity);
    // ...
}
```

---

## Phase 4: Key Derivation Logic (Week 7-8)

### 4.1 Cryptographic Composition

**Current KDF** (SGP.22 Annex G):
```c
// Input:  Z_EC (32 bytes from ECDH)
// Output: KEK (16 bytes), KM (16 bytes)

void derive_session_keys_ecka(const uint8_t *Z, ...) {
    uint8_t kdf_input[36] = {0};
    memcpy(kdf_input, Z, 32);
    
    // KEK = SHA256(Z || 0x00000001)[0:16]
    kdf_input[32..35] = {0x00, 0x00, 0x00, 0x01};
    SHA256(kdf_input, 36, kek_hash);
    memcpy(session_key_enc, kek_hash, 16);
    
    // KM = SHA256(Z || 0x00000002)[0:16]
    kdf_input[35] = 0x02;
    SHA256(kdf_input, 36, km_hash);
    memcpy(session_key_mac, km_hash, 16);
}
```

**Challenge**: How to combine two secrets (Z_EC and Z_KEM)?

**Cryptographic Design Decision**:
```
Option A: Concatenate then hash (simple)
  Z_hybrid = Z_EC || Z_KEM  (64 bytes)
  KEK || KM = KDF(Z_hybrid)
  
  ✓ Simple implementation
  ✓ Security proof straightforward
  ✗ Different from standard hybrid KEM constructions

Option B: XOR combination (Kyber reference)
  Z_hybrid = Z_EC ⊕ Z_KEM  (32 bytes)
  KEK || KM = KDF(Z_hybrid)
  
  ✓ Matches some hybrid KEM papers
  ✗ Requires equal-length secrets
  ✗ Less conservative (XOR can lose entropy)

Option C: Nested KDF (NIST SP 800-56C)
  K1 = KDF(Z_EC, "ECDH")
  K2 = KDF(Z_KEM, "MLKEM")
  KEK || KM = KDF(K1 || K2)
  
  ✓ Most conservative (each secret independently hashed)
  ✓ Matches NIST guidance
  ✗ Three hash operations (slight performance cost)

✅ Choose Option C for maximum security assurance
```

**Implementation Methodology**:

```c
// High-level structure - focus on methodology
int derive_session_keys_hybrid(
    const uint8_t *Z_ec,   uint32_t z_ec_len,      // 32 bytes
    const uint8_t *Z_kem,  uint32_t z_kem_len,     // 32 bytes
    uint8_t *kek_out,      uint8_t *km_out
) {
    // Step 1: Independent extraction
    uint8_t K_ec[32], K_kem[32];
    HKDF_Extract(Z_ec,  "ECDH-P256",   K_ec);
    HKDF_Extract(Z_kem, "ML-KEM-768",  K_kem);
    
    // Step 2: Combine intermediate keys
    uint8_t combined[64];
    memcpy(combined,      K_ec,  32);
    memcpy(combined + 32, K_kem, 32);
    
    // Step 3: Final KDF (SGP.22 Annex G format)
    uint8_t kdf_input[68];  // 64 + 4 for counter
    memcpy(kdf_input, combined, 64);
    
    // Derive KEK
    uint32_to_bytes(kdf_input + 64, 0x00000001);
    SHA256(kdf_input, 68, kek_out);
    
    // Derive KM
    uint32_to_bytes(kdf_input + 64, 0x00000002);
    SHA256(kdf_input, 68, km_out);
    
    // Step 4: Secure cleanup
    memset(K_ec,  0, 32);
    memset(K_kem, 0, 32);
    memset(combined, 0, 64);
    
    return 0;
}
```

**Security Rationale**:
1. **Domain separation**: "ECDH-P256" vs "ML-KEM-768" labels prevent cross-protocol attacks
2. **Conservative composition**: Hash each secret independently before combining
3. **Forward compatible**: Easy to swap KDF algorithm if SHA-256 becomes weak

### 4.2 Timing and Sequencing

**Critical Question**: When does key derivation happen?

Your current flow:
```
PrepareDownload (BF21):
  → Generate ECKA keypair
  → Store otSK in state
  → Return otPK to SM-DP+

[SM-DP+ generates its keys and sends BPP]

InitialiseSecureChannel (BF23):
  → Receive smdpOtpk
  → Derive Z = otSK × smdpOtpk      ← KEY DERIVATION HERE
  → KDF → KEK, KM
  → Store in state->session_key_enc/mac
```

**Hybrid timing**:
```
PrepareDownload (BF21):
  → Generate EC keypair (otPK_EC, otSK_EC)
  → Generate KEM keypair (pk_KEM, sk_KEM)
  → Store BOTH private keys in state
  → Return BOTH public keys to SM-DP+

InitialiseSecureChannel (BF23):
  → Receive smdpOtpk_EC + smdpCiphertext_KEM
  → Derive Z_EC = otSK_EC × smdpOtpk_EC
  → Decapsulate Z_KEM = Decaps(ct, sk_KEM)  ← NEW STEP
  → Hybrid KDF → KEK, KM
  → CRITICAL: Wipe sk_KEM after use
```

**Memory Management Strategy**:
```c
// In InitialiseSecureChannel handler
case 0xBF23: {
    // ... existing code ...
    
    // After deriving session keys:
    if (state->euicc_keypair.is_hybrid) {
        // Securely erase ML-KEM private key (no longer needed)
        memset(state->euicc_keypair.kem_private, 0, 2400);
        free(state->euicc_keypair.kem_private);
        state->euicc_keypair.kem_private = NULL;
        
        // Keep ECDH private key (might be reused? - check spec)
    }
    
    // Session keys now stored in state->session_key_enc/mac
    state->session_keys_derived = 1;
    break;
}
```

**Why immediate deletion**:
- ML-KEM keys are ephemeral (one-time use)
- Reduces attack surface (side-channel resistance)
- Frees 2.4 KB of memory

---

## Phase 5: SM-DP+ Server Integration (Week 9-10)

### 5.1 Architecture Decision

**Challenge**: Your SM-DP+ is `osmo-smdpp` (Python). How to add liboqs?

```
Option A: Python bindings (liboqs-python)
  ✓ Matches existing language (osmo-smdpp is Python)
  ✓ pip install liboqs-python (easy)
  ✗ Python performance overhead (less critical for server)

Option B: C extension module
  ✓ Maximum performance
  ✗ Complex build system
  ✗ Maintenance burden

Option C: Separate PQC service (microservice)
  ✓ Language-agnostic
  ✓ Scalable (multiple eUICC sessions)
  ✗ Added network complexity

✅ Choose Option A for rapid prototyping
```

**Integration Strategy** (in `pysim/osmo-smdpp.py`):

```python
# Minimal conceptual example
try:
    import oqs
    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False
    print("Warning: liboqs-python not found, falling back to classical crypto")

class HybridKeyAgreement:
    def __init__(self, euicc_capabilities):
        self.mode = "hybrid" if (PQC_AVAILABLE and 
                                 euicc_capabilities.get('mlkem768')) else "classical"
        if self.mode == "hybrid":
            self.kem = oqs.KeyEncapsulation("ML-KEM-768")
    
    def prepare_bpp(self, euicc_public_keys):
        # Classical ECDH (existing code)
        Z_ec = self.ecdh_agree(euicc_public_keys['ec'])
        
        # Hybrid addition
        if self.mode == "hybrid":
            ciphertext, Z_kem = self.kem.encap_secret(euicc_public_keys['kem'])
            Z_hybrid = self.combine_secrets(Z_ec, Z_kem)
            return {'ct': ciphertext, 'kek_km': self.kdf(Z_hybrid)}
        else:
            return {'kek_km': self.kdf(Z_ec)}
```

**Why gradual integration**:
- `PQC_AVAILABLE` flag allows testing without liboqs
- Fallback to classical maintains existing functionality
- Easy to A/B test (hybrid vs classical sessions)

### 5.2 Certificate and PKI Considerations

**Critical Issue**: Your current certs are generated by `pysim/smdpp-data/generated/`.

For hybrid mode, you need:
```
Classical (current):
  CERT.DPpb.ECDSA (SM-DP+ certificate)
  └─ Subject Public Key: ECDSA P-256

Hybrid (Phase 1 - defer to Phase 2):
  CERT.DPpb.ECDSA-MLKEM (composite certificate)
  ├─ Subject Public Key (Signing): ECDSA P-256
  └─ Subject Public Key (KEM): ML-KEM-768
```

**Interim Solution for Testbed**:
```
Phase 1 Migration: Keep certificates unchanged
  ✓ Signatures still use ECDSA (backward compatible)
  ✓ Focus on key agreement only (KEM not in certificate)
  ✓ Defer certificate migration to Phase 2

Rationale:
  - GSMA allows "phased transition" (key exchange first)
  - Certificate chain migration is complex (CI, EUM, etc.)
  - Your testbed can demonstrate hybrid KEM without cert changes
```

**Action Item**: Document limitation
```python
# In osmo-smdpp.py
"""
NOTE: Phase 1 implementation uses classical ECDSA certificates
for authentication, but hybrid ECKA+ML-KEM for session key agreement.
This is compliant with GSMA PQ.03 phased transition strategy.

Phase 2 (future): Migrate to ML-DSA signature certificates.
"""
```

---

## Phase 6: Testing Strategy (Week 11-12)

### 6.1 Test Pyramid

```
                    ┌─────────────────┐
                    │  End-to-End     │
                    │  (demo.sh)      │
                    └─────────────────┘
                    
              ┌───────────────────────────┐
              │   Integration Tests       │
              │  (eUICC ↔ SM-DP+)        │
              └───────────────────────────┘
              
        ┌─────────────────────────────────────┐
        │        Unit Tests                    │
        │  (crypto, ASN.1, state management)  │
        └─────────────────────────────────────┘
```

### 6.2 Unit Testing Methodology

**Goal**: Verify each component independently before integration.

**Test 1: ML-KEM Keypair Generation**
```c
// test_mlkem_keygen.c
void test_mlkem_keypair() {
    OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768);
    uint8_t *pk = malloc(kem->length_public_key);
    uint8_t *sk = malloc(kem->length_secret_key);
    
    assert(OQS_KEM_keypair(kem, pk, sk) == OQS_SUCCESS);
    assert(pk != NULL && sk != NULL);
    
    // Verify sizes
    assert(kem->length_public_key == 1184);
    assert(kem->length_secret_key == 2400);
    
    cleanup();
}
```

**Test 2: Hybrid KDF Correctness**
```c
void test_hybrid_kdf() {
    // Known test vectors (generate with reference implementation)
    uint8_t Z_ec[32] = {0x01, 0x02, ...};   // Deterministic ECDH secret
    uint8_t Z_kem[32] = {0xAA, 0xBB, ...};  // Deterministic KEM secret
    
    uint8_t kek[16], km[16];
    derive_session_keys_hybrid(Z_ec, 32, Z_kem, 32, kek, km);
    
    // Expected values from Python reference implementation
    uint8_t expected_kek[16] = {0x12, 0x34, ...};
    assert(memcmp(kek, expected_kek, 16) == 0);
}
```

**Test 3: ASN.1 Encoding/Decoding**
```c
void test_asn1_hybrid_encoding() {
    // Build hybrid EUICCSigned2
    uint8_t otpk_ec[65] = {...};
    uint8_t pk_kem[1184] = {...};
    
    uint8_t *encoded = NULL;
    uint32_t encoded_len = 0;
    build_euicc_signed2_hybrid(otpk_ec, pk_kem, &encoded, &encoded_len);
    
    // Verify structure
    assert(encoded[0] == 0x30);  // SEQUENCE tag
    // ... parse and verify each field
}
```

### 6.3 Integration Testing

**Test Scenario 1: Classical Fallback**
```bash
#!/bin/bash
# test_classical_fallback.sh

# Start eUICC with PQC disabled
./v-euicc-daemon 8765 --disable-pqc &

# Start classical SM-DP+
./osmo-smdpp.py --classical-only &

# Run profile download - should succeed with ECDH only
./lpac profile download -s testsmdpplus1.example.com:8443 -m TEST-PROFILE

# Verify: No ML-KEM keys in logs
grep "ML-KEM" /tmp/euicc.log && exit 1  # Should NOT find ML-KEM
echo "✓ Classical fallback successful"
```

**Test Scenario 2: Hybrid Mode**
```bash
# Start eUICC with PQC enabled
./v-euicc-daemon 8765 --enable-pqc &

# Start hybrid SM-DP+
./osmo-smdpp.py --hybrid &

# Run profile download
./lpac profile download -s testsmdpplus1.example.com:8443 -m TEST-HYBRID

# Verify: ML-KEM operations in logs
grep "ML-KEM keypair generated" /tmp/euicc.log || exit 1
grep "Session keys derived.*hybrid" /tmp/euicc.log || exit 1
echo "✓ Hybrid mode successful"
```

**Test Scenario 3: Performance Comparison**
```bash
# Benchmark classical vs hybrid
time ./lpac profile download -m TEST-CLASSICAL  # Baseline
time ./lpac profile download -m TEST-HYBRID     # Compare

# Measure payload size
tcpdump -i lo -w classical.pcap port 8443 &
./lpac profile download -m TEST-CLASSICAL
killall tcpdump

tcpdump -i lo -w hybrid.pcap port 8443 &
./lpac profile download -m TEST-HYBRID
killall tcpdump

# Analyze
capinfos classical.pcap hybrid.pcap
# Expected: Hybrid ~40-50% larger (per GSMA table)
```

### 6.4 Negative Testing

**Test Scenario 4: Decapsulation Failure Handling**
```c
void test_invalid_ciphertext() {
    // Simulate corrupted ciphertext
    uint8_t corrupt_ct[1088];
    memset(corrupt_ct, 0xFF, 1088);  // Invalid ciphertext
    
    int result = derive_session_keys_hybrid(Z_ec, 32, corrupt_ct, 1088, kek, km);
    assert(result == -1);  // Should fail gracefully
    
    // Verify: No partial state corruption
    assert(state->session_keys_derived == 0);
}
```

---

## Phase 7: Performance Profiling (Week 13)

### 7.1 Metrics Collection Strategy

**Key Performance Indicators (KPIs)**:

| Metric | Classical | Hybrid Target | Measurement Method |
|--------|-----------|---------------|---------------------|
| **Total Download Time** | 30-35s | <50s (+40%) | Wall-clock time (`time` command) |
| **Payload Size** | 38.3 KB | <55 KB (+42%) | pcap analysis (`capinfos`) |
| **APDU Count** | ~150 | <220 (+47%) | Log parsing (`grep "APDU:"`) |
| **CPU Usage (eUICC)** | Baseline | <+30% | `perf stat` or `time` |
| **Memory Peak** | 4 KB | <8 KB | `valgrind --tool=massif` |

### 7.2 Instrumentation Points

**Add timing logs without breaking protocol**:

```c
// In apdu_handler.c
#ifdef ENABLE_PROFILING
#define PROFILE_START(name) \
    struct timespec start_##name; \
    clock_gettime(CLOCK_MONOTONIC, &start_##name);

#define PROFILE_END(name) \
    struct timespec end_##name; \
    clock_gettime(CLOCK_MONOTONIC, &end_##name); \
    long elapsed_us = (end_##name.tv_sec - start_##name.tv_sec) * 1000000 + \
                      (end_##name.tv_nsec - start_##name.tv_nsec) / 1000; \
    fprintf(stderr, "[PROFILE] %s: %ld μs\n", #name, elapsed_us);
#else
#define PROFILE_START(name)
#define PROFILE_END(name)
#endif

// Usage in PrepareDownload
case 0xBF21: {
    PROFILE_START(mlkem_keygen);
    generate_hybrid_keypair(...);
    PROFILE_END(mlkem_keygen);
    
    PROFILE_START(signature_generation);
    ecdsa_sign(...);
    PROFILE_END(signature_generation);
}
```

**Why conditional compilation**:
- Production builds: No performance overhead
- Profiling builds: Detailed timing data
- Easy to enable/disable (`-DENABLE_PROFILING`)

### 7.3 Bottleneck Identification

**Expected bottlenecks**:

1. **ML-KEM Decapsulation** (in `InitialiseSecureChannel`)
   - Theoretical: ~0.5-1ms on modern CPU
   - Testbed: May be higher due to emulation
   - Mitigation: Profile with `perf record`

2. **APDU Segmentation** (in `apdu_handle_transmit`)
   - 1088-byte ciphertext → 5 APDUs
   - Each APDU: socket send/recv overhead
   - Mitigation: Batch sends (optimize at protocol level)

3. **ASN.1 Encoding** (in `build_tlv`)
   - Large TLVs (>1KB) require multi-pass encoding
   - Mitigation: Pre-allocate buffer size

**Profiling Example**:
```bash
# Run with profiling enabled
cmake -DENABLE_PROFILING=ON ..
make

# Execute profile download
./v-euicc-daemon 8765 > profile.log 2>&1 &
./lpac profile download ...

# Analyze profile.log
grep "[PROFILE]" profile.log | sort -k3 -n
# Expected output:
# [PROFILE] mlkem_keygen: 1234 μs
# [PROFILE] mlkem_decaps: 567 μs
# [PROFILE] signature_generation: 890 μs
```

---

## Phase 8: Documentation & Reproducibility (Week 14)

### 8.1 Research Artifact Package

**Goal**: Enable other researchers to reproduce your results.

**Deliverables**:
```
pqc-esim-testbed/
├── README.md              # High-level overview
├── INSTALL.md             # Dependency installation
├── BENCHMARK.md           # Performance reproduction steps
├── v-euicc/               # Your virtual eUICC code
├── pysim/                 # SM-DP+ server code
├── scripts/
│   ├── setup-deps.sh      # Install liboqs, openssl, etc.
│   ├── run-classical.sh   # Baseline test
│   ├── run-hybrid.sh      # PQC test
│   └── compare-results.sh # Generate comparison table
└── results/
    ├── classical.pcap     # Reference network trace
    ├── hybrid.pcap
    └── performance.csv    # Raw measurements
```

### 8.2 Reproducibility Checklist

**Docker Container Strategy** (recommended):
```dockerfile
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    cmake gcc liboqs-dev openssl python3-pip

# Copy testbed code
COPY . /testbed
WORKDIR /testbed

# Build
RUN ./scripts/setup-deps.sh
RUN cmake -DENABLE_PQC=ON . && make

# Default command: Run comparison
CMD ["./scripts/compare-results.sh"]
```

**Why Docker**:
- Eliminates "works on my machine" issues
- Captures exact dependency versions
- Easy for reviewers to run (`docker run pqc-esim-testbed`)

### 8.3 Measurement Reporting

**CSV Output Format** (for paper tables):
```csv
Mode,Download_Time_ms,Payload_Bytes,APDU_Count,CPU_ms,Memory_KB
classical,32500,39219,152,8450,4.2
hybrid,45800,54320,218,10520,7.8
```

**Automated Analysis Script**:
```python
# scripts/analyze-results.py
import pandas as pd

df = pd.read_csv('results/performance.csv')

# Calculate overhead
overhead = (df[df['Mode']=='hybrid'] / df[df['Mode']=='classical'] - 1) * 100

print(f"Payload overhead: {overhead['Payload_Bytes'].values[0]:.1f}%")
print(f"Time overhead: {overhead['Download_Time_ms'].values[0]:.1f}%")
# Expected: ~40-50% per GSMA PQ.03
```

---

## Phase 9: Validation Against GSMA Spec (Week 15)

### 9.1 Compliance Verification

**GSMA PQ.03 Requirements Checklist**:

| Requirement | Classical | Hybrid | Verification Method |
|-------------|-----------|--------|---------------------|
| **Backward Compatibility** | ✓ | Must maintain | Test with classical SM-DP+ |
| **Hybrid Key Exchange** | N/A | Must support | Wireshark inspection |
| **Graceful Degradation** | ✓ | Must support | Disable PQC, verify fallback |
| **Performance <50% overhead** | Baseline | Target | Benchmark comparison |
| **SNDL Protection** | ❌ | ✓ | Conceptual (cannot break ML-KEM) |

**Test Script**:
```bash
#!/bin/bash
# validate-gsma-compliance.sh

echo "=== GSMA PQ.03 Compliance Validation ==="

# Test 1: Backward Compatibility
echo "Test 1: Classical eUICC with Hybrid SM-DP+"
./v-euicc-daemon --classical &
./osmo-smdpp.py --hybrid &
./lpac profile download ... && echo "✓ PASS" || echo "✗ FAIL"

# Test 2: Hybrid Capability Negotiation
echo "Test 2: Hybrid eUICC capabilities advertised"
./lpac chip info | grep -q "mlkem768Support" && echo "✓ PASS" || echo "✗ FAIL"

# Test 3: Performance Overhead
echo "Test 3: Hybrid overhead <50%"
CLASSICAL_TIME=$(time_download classical)
HYBRID_TIME=$(time_download hybrid)
OVERHEAD=$(echo "scale=2; ($HYBRID_TIME - $CLASSICAL_TIME) / $CLASSICAL_TIME * 100" | bc)
[ $(echo "$OVERHEAD < 50" | bc) -eq 1 ] && echo "✓ PASS ($OVERHEAD%)" || echo "✗ FAIL ($OVERHEAD%)"
```

### 9.2 Known Limitations Documentation

**Document what your testbed does NOT implement**:

```markdown
# Testbed Limitations (Phase 1)

## Out of Scope:
1. **Signature Migration**: Still uses ECDSA (deferred to Phase 2 per GSMA)
2. **Certificate Chains**: No hybrid certificates (testbed uses classical certs)
3. **ES9+ TLS**: Not modified (focus on ES8+ only)
4. **Production PKI**: Uses test certificates, not GSMA-approved CI

## In Scope:
1. ✓ Hybrid ECKA+ML-KEM key agreement
2. ✓ Backward compatibility with classical eUICCs
3. ✓ Performance benchmarking vs. classical
4. ✓ Protocol message extensions (ASN.1)

## Justification:
Phase 1 prioritizes key exchange per GSMA "Phased Transition" strategy (Section 5.6.9.2).
This addresses immediate SNDL threat while deferring complex PKI migration.
```

---

## Success Criteria Summary

### Functional Requirements ✓
- [ ] eUICC generates hybrid EC + ML-KEM keypairs
- [ ] SM-DP+ encapsulates ML-KEM ciphertext
- [ ] Session keys derived from hybrid secrets
- [ ] Profile downloads complete successfully
- [ ] Classical fallback works without PQC libraries

### Performance Requirements ✓
- [ ] Payload size increase <50% (GSMA target: 42%)
- [ ] Download time increase <50% (GSMA target: 40%)
- [ ] Memory overhead <2× baseline
- [ ] No crashes under 100 concurrent downloads

### Research Quality ✓
- [ ] Reproducible via Docker container
- [ ] Performance data matches GSMA projections
- [ ] Clear documentation of limitations
- [ ] Comparison with classical baseline

---

## Risk Management

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **liboqs compatibility issues** | Medium | High | Test on multiple platforms early |
| **ASN.1 parsing bugs** | Medium | Medium | Extensive unit tests with known vectors |
| **Memory leaks (ML-KEM keys)** | Low | High | Valgrind every commit |
| **Performance worse than GSMA** | Low | Medium | Profile early, optimize bottlenecks |
| **Backward compat broken** | Low | Critical | Maintain classical test suite |

---

## Next Steps: Getting Started

**Week 1 Action Items**:
1. Fork your current working branch (`git checkout -b pqc-migration`)
2. Install liboqs (`sudo apt install liboqs-dev` on Ubuntu)
3. Add CMake PQC option (see Phase 1.1)
4. Write first unit test (ML-KEM keypair generation)
5. Run test: `./test_mlkem_keygen` (should compile and pass)

**Validation**: By end of Week 1, you should have:
- liboqs linked to v-euicc-daemon
- One passing unit test
- No regressions in classical mode

This proves your build system is ready for full migration.

---

**Focus**: Each phase builds on the previous. Don't skip ahead—validate each step before proceeding. 
