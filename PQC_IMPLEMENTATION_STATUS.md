# PQC Migration Implementation Status

## Branch: pqc-migration-1

## Overview
Implementation of Post-Quantum Cryptography (PQC) support for the Virtual RSP testbed, focusing on hybrid key exchange (ECDH + ML-KEM-768) for SGP.22 ES8+ protocol.

## ✅ Completed Implementation (Phase 1-3)

### Phase 1: Setup and Dependencies
- ✅ **liboqs Installation**: Version 0.14.0 installed via Homebrew
- ✅ **CMake Integration**: Added ENABLE_PQC option with conditional linking
- ✅ **Build System**: Successfully compiles with PQC support
- ✅ **Test Infrastructure**: Created `tests/` directory structure

### Phase 2: Core Crypto Extensions (v-euicc)
- ✅ **State Management**:
  - Added `pqc_capabilities_t` structure
  - Extended `euicc_state` with ML-KEM key storage
  - Proper initialization and cleanup in `euicc_state.c`

- ✅ **Crypto Primitives** (`v-euicc/src/crypto.c`):
  - `generate_mlkem_keypair()`: ML-KEM-768 keypair generation (1184B pk, 2400B sk)
  - `mlkem_decapsulate()`: ML-KEM-768 decapsulation
  - `derive_session_keys_hybrid()`: Nested KDF (NIST SP 800-56C style)
    - Domain separation: "ECDH-P256" and "ML-KEM-768" labels
    - Conservative composition: Hash each secret independently
    - Compatible with SGP.22 Annex G format

- ✅ **Unit Tests** (`tests/unit/`):
  - `test_mlkem.c`: ML-KEM keypair generation and encaps/decaps tests
  - `test_hybrid_kdf.c`: Hybrid KDF correctness and security tests

### Phase 3: Protocol Extensions (APDU Handler)
- ✅ **PrepareDownload Enhancement** (BF21):
  - Generates ML-KEM-768 keypair alongside ECDH keypair
  - Includes ML-KEM public key in response (tag 0x5F4A)
  - Sets `hybrid_mode_active` flag
  - Graceful fallback to classical mode on error

- ✅ **InitialiseSecureChannel Enhancement** (BF23):
  - Parses ML-KEM ciphertext (tag 0x5F4B)
  - Performs ECDH computation to get Z_ec
  - Performs ML-KEM decapsulation to get Z_kem
  - Derives session keys using hybrid KDF
  - Securely erases ML-KEM private key after use
  - Falls back to classical ECDH if ciphertext not present

- ✅ **Buffer Capacity Update**:
  - Increased segment buffer headroom to 4096 bytes
  - Handles ML-KEM ciphertext (1088 bytes) + overhead

### Phase 6: Demo and Verification
- ✅ **PQC Demo Script** (`tests/scripts/demo-pqc-detailed.sh`):
  - Verifies PQC support in v-euicc daemon
  - Demonstrates ML-KEM keypair generation
  - Shows hybrid mode activation
  - Includes detailed logging and analysis
  - Documents current limitations (SM-DP+ not yet implemented)

## 🚧 Remaining Implementation (Phase 4-7)

### Phase 4: SM-DP+ Server Integration
- ⏳ **Python Hybrid Key Agreement** (`pysim/hybrid_ka.py`):
  - Create HybridKeyAgreement class
  - Implement ML-KEM encapsulation using liboqs-python
  - Implement hybrid KDF matching v-euicc implementation

- ⏳ **SM-DP+ Modifications** (`pysim/osmo-smdpp.py`):
  - Parse ML-KEM public key from PrepareDownload (tag 0x5F4A)
  - Generate ML-KEM ciphertext via encapsulation
  - Include ciphertext in InitialiseSecureChannel (tag 0x5F4B)
  - Graceful fallback to classical mode

- ⏳ **Python Dependencies**:
  - Add `liboqs-python` to `requirements.txt`
  - Verify installation

### Phase 5: Integration Testing
- ⏳ **Test Scripts** (`tests/scripts/`):
  - `test-classical-fallback.sh`: Verify backward compatibility
  - `test-hybrid-mode.sh`: End-to-end hybrid test
  - `test-interop.sh`: Test all 4 mode combinations

- ⏳ **Integration Tests** (`tests/integration/test_protocol_flow.c`):
  - Mock APDU communication
  - Verify session key matching

### Phase 6: Performance Profiling
- ⏳ **Timing Instrumentation**:
  - Add `ENABLE_PROFILING` compile flag
  - Profile ML-KEM operations
  - Profile hybrid KDF
  - Compare classical vs hybrid performance

### Phase 7: Documentation
- ⏳ **README Updates**:
  - Build instructions for PQC support
  - Performance comparison table
  - Known limitations

- ⏳ **Validation Script** (`tests/scripts/validate-pqc.sh`):
  - Comprehensive test suite runner
  - Performance report generation

## Technical Details

### Key Sizes
| Component | Classical (ECDH) | Hybrid (ECDH + ML-KEM-768) |
|-----------|------------------|----------------------------|
| eUICC Public Key | 65 bytes | 65 + 1184 = 1249 bytes |
| eUICC Secret Key | 32 bytes | 32 + 2400 = 2432 bytes |
| SM-DP+ Public Key | 65 bytes | 65 + 0 = 65 bytes |
| SM-DP+ Ciphertext | 0 bytes | 1088 bytes |
| Shared Secret | 32 bytes | 32 + 32 = 64 bytes (combined) |
| Session Keys | 32 bytes (16+16) | 32 bytes (16+16) |

### Protocol Tags
| Tag | Description | Size |
|-----|-------------|------|
| 0x5F49 | euiccOtpk (ECDH public key) | 65 bytes |
| 0x5F4A | euiccOtpkKEM (ML-KEM public key) | 1184 bytes |
| 0x5F4B | smdpCiphertextKEM (ML-KEM ciphertext) | 1088 bytes |

### Security Properties
- **Hybrid Security**: Secure if EITHER ECDH OR ML-KEM is secure
- **SNDL Protection**: ML-KEM provides quantum resistance
- **Forward Secrecy**: ECDH provides classical forward secrecy
- **Domain Separation**: Independent key extraction prevents protocol confusion

## Building and Testing

### Build with PQC Support
```bash
cd /Users/jhurykevinlastre/Documents/projects/virtual-rsp
rm -rf build && mkdir build && cd build
cmake .. -DENABLE_PQC=ON
make v-euicc-daemon
```

### Run PQC Demo
```bash
cd /Users/jhurykevinlastre/Documents/projects/virtual-rsp
./tests/scripts/demo-pqc-detailed.sh
```

### Current Behavior
- v-euicc generates ML-KEM-768 keypair ✓
- v-euicc includes ML-KEM public key in PrepareDownload ✓
- SM-DP+ (classical) ignores ML-KEM public key
- v-euicc falls back to classical ECDH
- Profile download succeeds with classical crypto ✓

### Expected Behavior (After Phase 4 Complete)
- v-euicc generates ML-KEM-768 keypair ✓
- v-euicc includes ML-KEM public key in PrepareDownload ✓
- SM-DP+ encapsulates ML-KEM ciphertext
- SM-DP+ includes ciphertext in InitialiseSecureChannel
- v-euicc decapsulates and derives hybrid session keys
- Profile download succeeds with hybrid crypto ✓

## Next Steps

1. **Immediate** (to complete full hybrid mode):
   - Implement `pysim/hybrid_ka.py`
   - Install `liboqs-python`: `pip install liboqs-python`
   - Modify `pysim/osmo-smdpp.py` to use hybrid_ka

2. **Testing**:
   - Create test scripts for various scenarios
   - Run integration tests
   - Verify session key matching

3. **Validation**:
   - Performance benchmarking
   - Memory profiling with valgrind
   - Security audit of key handling

## Known Limitations

### Phase 1 Scope
- **No signature migration**: Still using classical ECDSA (deferred per GSMA phased approach)
- **No certificate chain updates**: Using classical certificates
- **Test-only implementation**: Not production-ready
- **No ES9+ TLS modifications**: Focus on ES8+ only

### Technical Constraints
- **Increased message size**: ~42% larger (per GSMA projections)
- **Memory overhead**: ~37× for key storage (mitigated by immediate deletion)
- **Segmentation required**: ML-KEM ciphertext requires 5+ APDU segments

## References
- GSMA PQ.03: "Post-Quantum Cryptography: Migration Guidelines for Consumer eSIM"
- SGP.22 v2.5: Remote Provisioning Architecture for Embedded UICC Technical Specification
- NIST FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard
- liboqs documentation: https://github.com/open-quantum-safe/liboqs

## Notes
- This is a research prototype demonstrating PQC feasibility
- Phase 1 implements key exchange only (per GSMA phased migration)
- Backward compatibility maintained throughout
- Classical mode works without PQC dependencies

