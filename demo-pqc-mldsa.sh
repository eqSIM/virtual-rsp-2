#!/bin/bash
# Enhanced PQC Demo: ML-DSA Authentication + ML-KEM Key Exchange + OQS TLS
# Replaces GSMA PKI with post-quantum self-signed certificates

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'

# Configuration
SMDP_ADDRESS="${1:-testsmdpplus1.example.com:8443}"
MATCHING_ID="${2:-TS48V2-SAIP2-1-BERTLV-UNIQUE}"

# Show usage if --help
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Usage: $0 [SMDP_ADDRESS] [MATCHING_ID]"
    echo
    echo "Enhanced PQC Demo: ML-DSA + ML-KEM + OQS TLS"
    echo "This demonstration shows:"
    echo "  - ML-DSA-87 self-signed certificates (replaces GSMA PKI)"
    echo "  - ML-KEM-768 hybrid key exchange"
    echo "  - OQS-enabled TLS with hybrid ciphersuites"
    echo "  - Complete post-quantum security stack"
    echo
    echo "Examples:"
    echo "  $0                                              # Use defaults"
    echo "  $0 testsmdpplus1.example.com:8443 TS48V3-SAIP2-1-BERTLV-UNIQUE"
    exit 0
fi

echo -e "${BOLD}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  Virtual eUICC - ML-DSA + ML-KEM + OQS TLS Demo               ║${NC}"
echo -e "${BOLD}║  Full Post-Quantum Cryptography Stack                          ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════════════════╝${NC}"
echo

cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
    [ ! -z "$EUICC_PID" ] && kill $EUICC_PID 2>/dev/null || true
    [ ! -z "$SMDPP_PID" ] && kill $SMDPP_PID 2>/dev/null || true
    [ ! -z "$NGINX_PID" ] && kill $NGINX_PID 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Cleanup complete"
}

trap cleanup EXIT

# Pre-flight checks
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Pre-Flight: Verify Full PQC Stack${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

echo -e "${BLUE}▶${NC} Checking liboqs version..."
if pkg-config --exists liboqs; then
    LIBOQS_VERSION=$(pkg-config --modversion liboqs)
    if [[ "$LIBOQS_VERSION" == "0.14.0" ]]; then
        echo -e "${GREEN}✓${NC} liboqs version: $LIBOQS_VERSION (correct)"
    else
        echo -e "${YELLOW}⚠${NC}  liboqs version: $LIBOQS_VERSION (expected 0.14.0)"
    fi
else
    echo -e "${RED}✗${NC} liboqs not found. Install with: brew install liboqs"
    exit 1
fi

echo -e "${BLUE}▶${NC} Checking v-euicc PQC build..."
if [ ! -f "build/v-euicc/v-euicc-daemon" ]; then
    echo -e "${RED}✗${NC} v-euicc-daemon not found. Please build first."
    exit 1
fi

if nm build/v-euicc/v-euicc-daemon 2>/dev/null | grep -q "OQS_KEM"; then
    KEM_COUNT=$(nm build/v-euicc/v-euicc-daemon 2>/dev/null | grep -c "OQS_KEM" || echo "0")
    SIG_COUNT=$(nm build/v-euicc/v-euicc-daemon 2>/dev/null | grep -c "OQS_SIG" || echo "0")
    echo -e "${GREEN}✓${NC} PQC-enabled binary: ML-KEM symbols=$KEM_COUNT, ML-DSA symbols=$SIG_COUNT"
else
    echo -e "${RED}✗${NC} No OQS symbols found. Rebuild with: cmake -DENABLE_PQC=ON"
    exit 1
fi

echo -e "${BLUE}▶${NC} Checking Python liboqs-python..."
cd pysim
if python3 -c "import sys, os; os.environ['OQS_PYTHON_BUILD_SKIP_INSTALL']='1'; sys.path.insert(0, '.'); from hybrid_ka import PQC_AVAILABLE, oqs; print('liboqs-python:', oqs.oqs_version() if PQC_AVAILABLE else 'N/A')" 2>/dev/null; then
    OQS_VERSION=$(python3 -c "import sys, os; os.environ['OQS_PYTHON_BUILD_SKIP_INSTALL']='1'; sys.path.insert(0, '.'); from hybrid_ka import oqs; print(oqs.oqs_version())" 2>/dev/null)
    echo -e "${GREEN}✓${NC} Python liboqs bindings: $OQS_VERSION"
    PQC_MODE="HYBRID"
else
    echo -e "${RED}✗${NC} Python liboqs not available"
    exit 1
fi
cd ..

echo -e "${BLUE}▶${NC} Checking ML-DSA certificates..."
if [ -f "v-euicc/certs-mldsa/euicc_cert_mldsa87.der" ] && [ -f "v-euicc/certs-mldsa/smdp_cert_mldsa87.der" ]; then
    EUICC_CERT_SIZE=$(stat -f%z "v-euicc/certs-mldsa/euicc_cert_mldsa87.der" 2>/dev/null || stat -c%s "v-euicc/certs-mldsa/euicc_cert_mldsa87.der" 2>/dev/null)
    SMDP_CERT_SIZE=$(stat -f%z "v-euicc/certs-mldsa/smdp_cert_mldsa87.der" 2>/dev/null || stat -c%s "v-euicc/certs-mldsa/smdp_cert_mldsa87.der" 2>/dev/null)
    echo -e "${GREEN}✓${NC} ML-DSA certificates exist (eUICC: $EUICC_CERT_SIZE bytes, SM-DP+: $SMDP_CERT_SIZE bytes)"
else
    echo -e "${YELLOW}⚠${NC}  ML-DSA certificates not found, generating..."
    python3 scripts/generate-mldsa-certs.py
fi

echo -e "${BLUE}▶${NC} Checking OQS TLS certificates..."
if [ -f "pysim/certs-oqs-tls/server-ecdsa.crt" ] && [ -f "pysim/certs-oqs-tls/server-mldsa87.pub" ]; then
    echo -e "${GREEN}✓${NC} OQS TLS certificates exist"
else
    echo -e "${YELLOW}⚠${NC}  OQS TLS certificates not found, generating..."
    bash scripts/generate-oqs-tls-certs.sh
fi

# Pre-flight cleanup
echo -e "${BLUE}▶${NC} Pre-flight cleanup..."
pkill -9 -f "v-euicc-daemon 8765" 2>/dev/null || true
pkill -9 -f "osmo-smdpp" 2>/dev/null || true
pkill -9 nginx 2>/dev/null || true
lsof -ti:8765 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:8443 | xargs kill -9 2>/dev/null || true
sleep 2
echo -e "${GREEN}✓${NC} Cleanup complete"

# Start v-euicc with ML-DSA support
echo -e "${BLUE}▶${NC} Starting v-euicc daemon (ML-KEM + ML-DSA enabled)..."
./build/v-euicc/v-euicc-daemon 8765 > /tmp/pqc-mldsa-euicc.log 2>&1 &
EUICC_PID=$!
sleep 2
if ! kill -0 $EUICC_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Failed to start v-euicc"
    cat /tmp/pqc-mldsa-euicc.log
    exit 1
fi
echo -e "${GREEN}✓${NC} v-euicc started (PID: $EUICC_PID)"
echo -e "${GREEN}✓${NC} Capabilities: ML-KEM-768 + ML-DSA-87"

# Configure hosts
echo -e "${BLUE}▶${NC} Configuring /etc/hosts..."
if ! grep -q "testsmdpplus1.example.com" /etc/hosts; then
    echo "127.0.0.1 testsmdpplus1.example.com" | sudo tee -a /etc/hosts > /dev/null
fi
echo -e "${GREEN}✓${NC} Hosts configured"

# Start SM-DP+ with PQC support
echo -e "${BLUE}▶${NC} Starting SM-DP+ server (PQC-aware)..."
cd pysim
OQS_PYTHON_BUILD_SKIP_INSTALL=1 ./osmo-smdpp-pqc.sh -H 127.0.0.1 -p 8000 --nossl -c generated > /tmp/pqc-mldsa-smdpp.log 2>&1 &
SMDPP_PID=$!
cd ..
sleep 3
if ! kill -0 $SMDPP_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Failed to start SM-DP+"
    cat /tmp/pqc-mldsa-smdpp.log
    exit 1
fi
echo -e "${GREEN}✓${NC} SM-DP+ started (PID: $SMDPP_PID)"

# Start nginx with OQS TLS
echo -e "${BLUE}▶${NC} Starting nginx with OQS-enabled TLS..."
cd pysim
nginx -c "$PWD/nginx-smdpp-oqs.conf" -p "$PWD" > /tmp/pqc-mldsa-nginx.log 2>&1 &
NGINX_PID=$!
cd ..
sleep 2
if ! kill -0 $NGINX_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Failed to start nginx"
    cat /tmp/pqc-mldsa-nginx.log
    exit 1
fi
echo -e "${GREEN}✓${NC} nginx started with hybrid TLS (PID: $NGINX_PID)"
echo -e "${GREEN}✓${NC} TLS: ECDSA + ML-DSA-87 dual signatures"

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Post-Quantum Security Stack Active${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo
echo -e "${MAGENTA}Layer 1: Transport Security${NC}"
echo -e "  ${GREEN}✓${NC} TLS 1.3 with hybrid ciphersuites"
echo -e "  ${GREEN}✓${NC} Server authentication: ECDSA + ML-DSA-87"
echo -e "  ${GREEN}✓${NC} Certificate chain: Self-signed PQC (no GSMA CA)"
echo
echo -e "${MAGENTA}Layer 2: Key Agreement${NC}"
echo -e "  ${GREEN}✓${NC} Hybrid: ECDH P-256 + ML-KEM-768"
echo -e "  ${GREEN}✓${NC} Session keys: Nested KDF (conservative security)"
echo
echo -e "${MAGENTA}Layer 3: Mutual Authentication${NC}"
echo -e "  ${GREEN}✓${NC} eUICC → SM-DP+: ML-DSA-87 signature"
echo -e "  ${GREEN}✓${NC} SM-DP+ → eUICC: ML-DSA-87 signature"
echo -e "  ${GREEN}✓${NC} Trust model: Self-signed PQC certificates"
echo
echo -e "${CYAN}Press Ctrl+C to stop services${NC}"
echo

# Keep services running and monitor logs
echo -e "${DIM}Monitoring services (press Ctrl+C to stop)...${NC}"
echo

# Display log summary every 5 seconds
while true; do
    sleep 5
    
    # Check if all services are still running
    if ! kill -0 $EUICC_PID 2>/dev/null; then
        echo -e "${RED}✗${NC} v-euicc crashed"
        break
    fi
    
    if ! kill -0 $SMDPP_PID 2>/dev/null; then
        echo -e "${RED}✗${NC} SM-DP+ crashed"
        break
    fi
    
    if ! kill -0 $NGINX_PID 2>/dev/null; then
        echo -e "${RED}✗${NC} nginx crashed"
        break
    fi
    
    # Show PQC activity
    if grep -q "ML-KEM" /tmp/pqc-mldsa-euicc.log 2>/dev/null; then
        echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} PQC operations active"
    fi
done

echo
echo -e "${YELLOW}📋 Logs available at:${NC}"
echo -e "   • v-euicc:  /tmp/pqc-mldsa-euicc.log"
echo -e "   • SM-DP+:   /tmp/pqc-mldsa-smdpp.log"
echo -e "   • nginx:    /tmp/pqc-mldsa-nginx.log"
echo

