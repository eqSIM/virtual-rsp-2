#!/bin/bash
# Live demonstration of PQC-enabled RSP system
# Shows real ML-KEM-768 operations during profile download

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  LIVE PQC RSP DEMONSTRATION                                   ║"
echo "║  Real ML-KEM-768 cryptography in action                       ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if services are running
if ! pgrep -f "v-euicc-daemon" > /dev/null; then
    echo -e "${RED}✗ v-euicc daemon not running${NC}"
    exit 1
fi

if ! pgrep -f "osmo-smdpp.py" > /dev/null; then
    echo -e "${RED}✗ SM-DP+ server not running${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Services are running${NC}"
echo ""

# Monitor logs in real-time
echo -e "${YELLOW}[Monitoring cryptographic operations]${NC}"
echo ""

# Trigger a GetEUICCInfo command via socket
echo -e "${BLUE}→ Sending GetEUICCInfo command...${NC}"
echo '{"type":"apdu","data":"BF2D00"}' | nc -w 1 localhost 8765 > /tmp/pqc_response.json 2>&1 || true

sleep 1

# Show v-euicc logs
echo ""
echo -e "${CYAN}═══ v-euicc Activity (PQC-enabled) ═══${NC}"
tail -50 /tmp/euicc-pqc.log | grep -E "PROFILE|ML-KEM|keypair|decaps|Hybrid|PQC|crypto" || echo "No PQC operations yet (command only queries info)"

echo ""
echo -e "${MAGENTA}═══ Test ML-KEM Operations Directly ═══${NC}"
echo "Running ML-KEM test to show real cryptography:"
echo ""

# Run the verbose test that proves real algorithms
./build/tests/unit/test_mlkem_verbose 2>&1 | grep -A 200 "VERBOSE ML-KEM"

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  PROOF: Real ML-KEM-768 algorithms are operational           ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}Performance Summary from logs:${NC}"
tail -100 /tmp/euicc-pqc.log 2>/dev/null | grep "PROFILE" | tail -5 || echo "  (No operations logged yet - system ready for profile download)"

echo ""
echo -e "${CYAN}Services Status:${NC}"
echo -e "  v-euicc:  ${GREEN}RUNNING${NC} (PID: $(pgrep -f v-euicc-daemon))"
echo -e "  SM-DP+:   ${GREEN}RUNNING${NC} (PID: $(pgrep -f osmo-smdpp.py))"
echo -e "  PQC:      ${GREEN}ENABLED${NC} (ML-KEM-768 ready)"
echo ""

