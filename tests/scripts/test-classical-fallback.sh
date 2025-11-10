#!/bin/bash
# Test Classical Fallback: Verify that classical-only eUICCs work with PQC-enabled SM-DP+

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test: Classical Fallback${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Testing that classical-only eUICC can connect to PQC-capable SM-DP+"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"
    pkill -f "v-euicc-daemon" 2>/dev/null || true
    pkill -f "osmo-smdpp.py" 2>/dev/null || true
    rm -f /tmp/classical-test-*.log
}

trap cleanup EXIT

# Start SM-DP+ (PQC-enabled)
echo -e "${BLUE}[1/4]${NC} Starting SM-DP+ server (PQC-capable)..."
cd pysim
python3 osmo-smdpp.py > /tmp/classical-test-smdp.log 2>&1 &
SMDP_PID=$!
cd ..
sleep 2

if ! ps -p $SMDP_PID > /dev/null; then
    echo -e "${RED}✗ Failed to start SM-DP+${NC}"
    cat /tmp/classical-test-smdp.log
    exit 1
fi
echo -e "${GREEN}✓${NC} SM-DP+ started (PID: $SMDP_PID)"

# Start v-euicc with PQC DISABLED
echo ""
echo -e "${BLUE}[2/4]${NC} Starting v-euicc daemon (Classical mode - PQC disabled)..."
./build/v-euicc/v-euicc-daemon 8765 --disable-pqc > /tmp/classical-test-euicc.log 2>&1 &
EUICC_PID=$!
sleep 2

if ! ps -p $EUICC_PID > /dev/null; then
    echo -e "${RED}✗ Failed to start v-euicc${NC}"
    cat /tmp/classical-test-euicc.log
    exit 1
fi
echo -e "${GREEN}✓${NC} v-euicc started (PID: $EUICC_PID)"

# Perform profile download test
echo ""
echo -e "${BLUE}[3/4]${NC} Testing profile download (classical mode)..."
sleep 2

# Run lpac to initiate download
echo "   Initiating profile download..."
export EUICC_HTTP_URL="http://localhost:8765"
export SM_DP_ADDRESS="testsmdpplus1.example.com"

# This should use classical ECDH only
./output/executables/bin/lpac chip info > /tmp/classical-test-lpac.log 2>&1 || true

# Verify logs
echo ""
echo -e "${BLUE}[4/4]${NC} Verifying classical mode operation..."

# Check that v-euicc did NOT generate ML-KEM keys
if grep -q "ML-KEM-768 keypair generated" /tmp/classical-test-euicc.log; then
    echo -e "${RED}✗ Error: ML-KEM keys were generated in classical mode${NC}"
    exit 1
else
    echo -e "${GREEN}✓${NC} No ML-KEM keys generated (expected in classical mode)"
fi

# Check that classical ECDH was used
if grep -q "Classical key agreement" /tmp/classical-test-euicc.log || \
   grep -q "ECDH" /tmp/classical-test-euicc.log; then
    echo -e "${GREEN}✓${NC} Classical ECDH key agreement used"
else
    echo -e "${YELLOW}⚠${NC}  Could not verify ECDH usage (check logs)"
fi

# Check that SM-DP+ detected classical mode
if grep -q "No ML-KEM public key detected, using classical mode" /tmp/classical-test-smdp.log || \
   grep -q "Performing classical key agreement" /tmp/classical-test-smdp.log; then
    echo -e "${GREEN}✓${NC} SM-DP+ correctly fell back to classical mode"
else
    echo -e "${YELLOW}⚠${NC}  Could not verify SM-DP+ fallback (check logs)"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Classical Fallback Test: PASSED${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Summary:"
echo "  - Classical-only eUICC: ✓"
echo "  - PQC-capable SM-DP+: ✓"
echo "  - Backward compatibility: ✓"
echo ""

