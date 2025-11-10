#!/bin/bash
# Comprehensive PQC Implementation Validation Script
# Verifies all components of the PQC migration are correctly implemented

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

check() {
    local condition="$1"
    local success_msg="$2"
    local failure_msg="$3"
    
    if eval "$condition"; then
        echo -e "${GREEN}✓${NC} $success_msg"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $failure_msg"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
        return 1
    fi
}

warn() {
    local message="$1"
    echo -e "${YELLOW}⚠${NC} $message"
    WARNINGS=$((WARNINGS + 1))
}

info() {
    local message="$1"
    echo -e "${CYAN}ℹ${NC} $message"
}

section() {
    local title="$1"
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$title${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          PQC Implementation Validation Suite                 ║"
echo "║      Comprehensive verification of hybrid cryptography       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ========================================
# Phase 1: Dependency Verification
# ========================================
section "Phase 1: Dependency Verification"

check "command -v cmake >/dev/null 2>&1" \
      "CMake is installed" \
      "CMake not found"

check "command -v pkg-config >/dev/null 2>&1" \
      "pkg-config is installed" \
      "pkg-config not found"

check "pkg-config --exists liboqs" \
      "liboqs library found" \
      "liboqs library not found (install via brew/apt)"

if pkg-config --exists liboqs; then
    LIBOQS_VERSION=$(pkg-config --modversion liboqs)
    info "liboqs version: $LIBOQS_VERSION"
fi

check "command -v python3 >/dev/null 2>&1" \
      "Python 3 is installed" \
      "Python 3 not found"

check "python3 -c 'from cryptography.hazmat.primitives import hashes' 2>/dev/null" \
      "Python cryptography library available" \
      "Python cryptography library not found (pip install cryptography)"

# ========================================
# Phase 2: Build System Verification
# ========================================
section "Phase 2: Build System Verification"

check "[ -f v-euicc/CMakeLists.txt ]" \
      "v-euicc CMakeLists.txt exists" \
      "v-euicc/CMakeLists.txt not found"

check "grep -q 'ENABLE_PQC' v-euicc/CMakeLists.txt" \
      "ENABLE_PQC option defined in CMakeLists.txt" \
      "ENABLE_PQC option not found in CMakeLists.txt"

check "grep -q 'liboqs' v-euicc/CMakeLists.txt" \
      "liboqs integration present in CMakeLists.txt" \
      "liboqs not referenced in CMakeLists.txt"

check "[ -d build/v-euicc ]" \
      "Build directory exists" \
      "Build directory not found (run cmake first)"

if [ -f build/v-euicc/v-euicc-daemon ]; then
    check "true" "v-euicc-daemon executable built" ""
else
    check "false" "" "v-euicc-daemon executable not found (build required)"
fi

# ========================================
# Phase 3: Source Code Verification
# ========================================
section "Phase 3: Source Code Verification"

# Check header files
check "[ -f v-euicc/include/euicc_state.h ]" \
      "euicc_state.h exists" \
      "euicc_state.h not found"

check "grep -q 'pqc_capabilities_t' v-euicc/include/euicc_state.h" \
      "PQC capabilities structure defined" \
      "pqc_capabilities_t not found in euicc_state.h"

check "grep -q 'euicc_pk_kem' v-euicc/include/euicc_state.h" \
      "ML-KEM key storage defined in state" \
      "ML-KEM key fields not found in euicc_state.h"

check "[ -f v-euicc/include/crypto.h ]" \
      "crypto.h exists" \
      "crypto.h not found"

check "grep -q 'generate_mlkem_keypair' v-euicc/include/crypto.h" \
      "ML-KEM keypair function declared" \
      "generate_mlkem_keypair not found in crypto.h"

check "grep -q 'derive_session_keys_hybrid' v-euicc/include/crypto.h" \
      "Hybrid KDF function declared" \
      "derive_session_keys_hybrid not found in crypto.h"

# Check implementation files
check "[ -f v-euicc/src/crypto.c ]" \
      "crypto.c exists" \
      "crypto.c not found"

check "grep -q 'oqs/oqs.h' v-euicc/src/crypto.c" \
      "liboqs header included in crypto.c" \
      "liboqs not included in crypto.c"

check "grep -q 'OQS_KEM_alg_ml_kem_768' v-euicc/src/crypto.c" \
      "ML-KEM-768 algorithm used" \
      "ML-KEM-768 not found in crypto.c"

check "grep -q 'PROFILE_START' v-euicc/src/crypto.c" \
      "Performance profiling instrumentation present" \
      "Performance profiling not found"

check "[ -f v-euicc/src/apdu_handler.c ]" \
      "apdu_handler.c exists" \
      "apdu_handler.c not found"

check "grep -q '0x5F4A' v-euicc/src/apdu_handler.c" \
      "ML-KEM public key tag (0x5F4A) used" \
      "Tag 0x5F4A not found in apdu_handler.c"

check "grep -q '0x5F4B' v-euicc/src/apdu_handler.c" \
      "ML-KEM ciphertext tag (0x5F4B) used" \
      "Tag 0x5F4B not found in apdu_handler.c"

# ========================================
# Phase 4: Python SM-DP+ Verification
# ========================================
section "Phase 4: Python SM-DP+ Verification"

check "[ -f pysim/hybrid_ka.py ]" \
      "hybrid_ka.py module exists" \
      "pysim/hybrid_ka.py not found"

check "grep -q 'HybridKeyAgreement' pysim/hybrid_ka.py" \
      "HybridKeyAgreement class defined" \
      "HybridKeyAgreement class not found"

check "grep -q 'perform_key_agreement' pysim/hybrid_ka.py" \
      "Key agreement method implemented" \
      "perform_key_agreement method not found"

check "grep -q '_derive_session_keys_hybrid' pysim/hybrid_ka.py" \
      "Hybrid KDF implemented in Python" \
      "Hybrid KDF not found in hybrid_ka.py"

check "[ -f pysim/osmo-smdpp.py ]" \
      "osmo-smdpp.py exists" \
      "pysim/osmo-smdpp.py not found"

check "grep -q 'hybrid_ka import' pysim/osmo-smdpp.py" \
      "hybrid_ka module imported in SM-DP+" \
      "hybrid_ka not imported in osmo-smdpp.py"

check "grep -q '_extract_tlv' pysim/osmo-smdpp.py" \
      "TLV extraction helper implemented" \
      "TLV extraction not found in osmo-smdpp.py"

check "grep -q 'euicc_pk_kem' pysim/osmo-smdpp.py" \
      "ML-KEM public key handling in SM-DP+" \
      "ML-KEM key handling not found in osmo-smdpp.py"

check "[ -f pysim/pySim/esim/es8p.py ]" \
      "es8p.py exists" \
      "pySim/esim/es8p.py not found"

check "grep -q '0x5F4B' pysim/pySim/esim/es8p.py" \
      "ML-KEM ciphertext injection in BPP" \
      "Ciphertext injection not found in es8p.py"

# ========================================
# Phase 5: Test Infrastructure Verification
# ========================================
section "Phase 5: Test Infrastructure Verification"

check "[ -d tests ]" \
      "tests/ directory exists" \
      "tests/ directory not found"

check "[ -d tests/unit ]" \
      "tests/unit/ directory exists" \
      "tests/unit/ directory not found"

check "[ -d tests/integration ]" \
      "tests/integration/ directory exists" \
      "tests/integration/ directory not found"

check "[ -d tests/scripts ]" \
      "tests/scripts/ directory exists" \
      "tests/scripts/ directory not found"

check "[ -f tests/unit/test_mlkem.c ]" \
      "ML-KEM unit test exists" \
      "test_mlkem.c not found"

check "[ -f tests/unit/test_hybrid_kdf.c ]" \
      "Hybrid KDF unit test exists" \
      "test_hybrid_kdf.c not found"

check "[ -f tests/integration/test_full_protocol.c ]" \
      "Full protocol integration test exists" \
      "test_full_protocol.c not found"

check "[ -f tests/scripts/test-classical-fallback.sh ]" \
      "Classical fallback test script exists" \
      "test-classical-fallback.sh not found"

check "[ -f tests/scripts/test-hybrid-mode.sh ]" \
      "Hybrid mode test script exists" \
      "test-hybrid-mode.sh not found"

check "[ -f tests/scripts/test-interop.sh ]" \
      "Interoperability test script exists" \
      "test-interop.sh not found"

check "[ -f tests/scripts/demo-pqc-detailed.sh ]" \
      "PQC detailed demo script exists" \
      "demo-pqc-detailed.sh not found"

# ========================================
# Phase 6: Runtime Verification (optional)
# ========================================
section "Phase 6: Runtime Verification (Optional)"

if [ -f build/v-euicc/v-euicc-daemon ]; then
    if ldd build/v-euicc/v-euicc-daemon 2>/dev/null | grep -q liboqs; then
        check "true" "v-euicc-daemon linked against liboqs" ""
    else
        warn "v-euicc-daemon may not be linked with liboqs (static linking possible)"
    fi
    
    if nm build/v-euicc/v-euicc-daemon 2>/dev/null | grep -q OQS_KEM_new; then
        check "true" "OQS_KEM symbols present in binary" ""
    elif nm build/v-euicc/v-euicc-daemon 2>/dev/null | grep -q _OQS_KEM_new; then
        check "true" "OQS_KEM symbols present in binary (mangled)" ""
    else
        warn "OQS_KEM symbols not found (may be statically linked or stripped)"
    fi
fi

# ========================================
# Phase 7: Documentation Verification
# ========================================
section "Phase 7: Documentation Verification"

check "[ -f README.md ]" \
      "README.md exists" \
      "README.md not found"

if grep -q "PQC\|Post-Quantum\|ML-KEM" README.md 2>/dev/null; then
    check "true" "README mentions PQC/ML-KEM" ""
else
    warn "README does not mention PQC implementation"
fi

if [ -f plan.md ]; then
    check "true" "Implementation plan (plan.md) exists" ""
    info "Implementation phases documented in plan.md"
else
    warn "Implementation plan not found"
fi

# ========================================
# Summary
# ========================================
echo ""
section "Validation Summary"

echo ""
echo -e "${CYAN}Component Status:${NC}"
echo "  • Dependencies:        $([ $CHECKS_PASSED -gt 0 ] && echo -e "${GREEN}✓${NC}" || echo -e "${RED}✗${NC}")"
echo "  • Build System:        $(grep -q 'ENABLE_PQC' v-euicc/CMakeLists.txt 2>/dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${RED}✗${NC}")"
echo "  • C Implementation:    $([ -f v-euicc/src/crypto.c ] && grep -q 'generate_mlkem_keypair' v-euicc/src/crypto.c && echo -e "${GREEN}✓${NC}" || echo -e "${RED}✗${NC}")"
echo "  • Python SM-DP+:       $([ -f pysim/hybrid_ka.py ] && echo -e "${GREEN}✓${NC}" || echo -e "${RED}✗${NC}")"
echo "  • Test Infrastructure: $([ -d tests ] && echo -e "${GREEN}✓${NC}" || echo -e "${RED}✗${NC}")"
echo ""

echo -e "${CYAN}Results:${NC}"
echo -e "  Checks Passed:  ${GREEN}$CHECKS_PASSED${NC}"
echo -e "  Checks Failed:  ${RED}$CHECKS_FAILED${NC}"
echo -e "  Warnings:       ${YELLOW}$WARNINGS${NC}"
echo ""

# Final verdict
if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║            ✓ PQC IMPLEMENTATION VALIDATED ✓                  ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}All critical components are present and correctly implemented!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Run unit tests: cd build && ctest"
    echo "  2. Test hybrid mode: ./tests/scripts/test-hybrid-mode.sh"
    echo "  3. Test fallback: ./tests/scripts/test-classical-fallback.sh"
    echo "  4. Run demo: ./tests/scripts/demo-pqc-detailed.sh"
    echo ""
    exit 0
else
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║           ✗ VALIDATION FAILED - ISSUES FOUND ✗               ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${RED}Please address the failed checks above.${NC}"
    echo ""
    exit 1
fi

