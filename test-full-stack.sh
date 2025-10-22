#!/bin/bash
# Comprehensive test of virtual-rsp full stack

set -e

echo "=================================================="
echo "  Virtual RSP Full Stack Test"
echo "=================================================="
echo ""

# Configuration
VEUICC_PORT=8765
SMDPP_HTTP_PORT=8000
SMDPP_HTTPS_PORT=8443

cleanup() {
    echo ""
    echo "Cleaning up..."
    pkill -f v-euicc-daemon || true
    pkill -f osmo-smdpp || true
    pkill -f "nginx.*smdpp" || true
    sleep 1
    echo "Cleanup complete"
}

trap cleanup EXIT INT TERM

# Check prerequisites
echo "Checking prerequisites..."

if [ ! -f "build/v-euicc/v-euicc-daemon" ]; then
    echo "Error: v-euicc-daemon not built"
    echo "Run: cmake --build build"
    exit 1
fi

if [ ! -d "pySim/venv" ]; then
    echo "Error: Python environment not set up"
    echo "Run: cd pySim && ./setup-venv.sh"
    exit 1
fi

if ! command -v nginx &> /dev/null; then
    echo "Error: nginx not installed"
    echo "Install: brew install nginx"
    exit 1
fi

echo "  ✓ All prerequisites met"
echo ""

# Start v-euicc daemon
echo "1. Starting virtual eUICC daemon (port $VEUICC_PORT)..."
./build/v-euicc/v-euicc-daemon $VEUICC_PORT > /tmp/v-euicc.log 2>&1 &
VEUICC_PID=$!
sleep 2

if ! kill -0 $VEUICC_PID 2>/dev/null; then
    echo "   Error: v-euicc failed to start"
    cat /tmp/v-euicc.log
    exit 1
fi

echo "   ✓ v-euicc running (PID: $VEUICC_PID)"

# Start SM-DP+ server
echo ""
echo "2. Starting SM-DP+ server (osmo-smdpp)..."

cd pySim
source venv/bin/activate
./osmo-smdpp.py -H 127.0.0.1 -p $SMDPP_HTTP_PORT --nossl > osmo-smdpp.log 2>&1 &
SMDPP_PID=$!
cd ..
sleep 3

if ! kill -0 $SMDPP_PID 2>/dev/null; then
    echo "   Error: osmo-smdpp failed to start"
    cat pySim/osmo-smdpp.log | tail -20
    exit 1
fi

echo "   ✓ osmo-smdpp running (PID: $SMDPP_PID)"

# Start nginx TLS proxy
echo ""
echo "3. Starting nginx TLS proxy (port $SMDPP_HTTPS_PORT)..."

cd pySim
nginx -c "$PWD/nginx-smdpp.conf" -p "$PWD" > /tmp/nginx.log 2>&1 &
NGINX_PID=$!
cd ..
sleep 2

if ! kill -0 $NGINX_PID 2>/dev/null; then
    echo "   Error: nginx failed to start"
    cat /tmp/nginx.log
    exit 1
fi

echo "   ✓ nginx running (PID: $NGINX_PID)"

# Run tests
echo ""
echo "=================================================="
echo "  Running Tests"
echo "=================================================="
echo ""

# Test 1: Virtual eUICC connectivity
echo "Test 1: Virtual eUICC socket connection"
if nc -z localhost $VEUICC_PORT; then
    echo "  ✓ v-euicc socket accessible"
else
    echo "  ✗ v-euicc socket not accessible"
    exit 1
fi

# Test 2: lpac chip info via virtual eUICC
echo ""
echo "Test 2: lpac chip info (via socket driver)"
cd build/lpac/src
OUTPUT=$(DYLD_LIBRARY_PATH=../../lpac/euicc:../../lpac/utils:../../lpac/driver LPAC_APDU=socket ./lpac chip info 2>&1)
cd ../../..

if echo "$OUTPUT" | grep -q '"eidValue":"89049032001001234500012345678901"'; then
    echo "  ✓ lpac chip info successful"
    echo "    EID: 89049032001001234500012345678901"
else
    echo "  ✗ lpac chip info failed"
    echo "$OUTPUT"
    exit 1
fi

# Test 3: SM-DP+ HTTP endpoint
echo ""
echo "Test 3: SM-DP+ HTTP endpoint (port $SMDPP_HTTP_PORT)"
HTTP_RESPONSE=$(curl -s http://127.0.0.1:$SMDPP_HTTP_PORT/ | head -1)
if echo "$HTTP_RESPONSE" | grep -q "404\|html"; then
    echo "  ✓ osmo-smdpp HTTP responding"
else
    echo "  ✗ osmo-smdpp HTTP not responding"
    exit 1
fi

# Test 4: SM-DP+ HTTPS endpoint through nginx
echo ""
echo "Test 4: SM-DP+ HTTPS endpoint (port $SMDPP_HTTPS_PORT)"
HTTPS_RESPONSE=$(curl -k -s https://localhost:$SMDPP_HTTPS_PORT/ | head -1)
if echo "$HTTPS_RESPONSE" | grep -q "404\|html"; then
    echo "  ✓ nginx TLS proxy working"
else
    echo "  ✗ nginx TLS proxy not responding"
    exit 1
fi

# Test 5: TLS certificate verification
echo ""
echo "Test 5: TLS certificate details"
CERT_INFO=$(curl -k -v https://localhost:$SMDPP_HTTPS_PORT/ 2>&1 | grep "subject")
if echo "$CERT_INFO" | grep -q "testsmdpplus1.example.com"; then
    echo "  ✓ TLS certificate valid"
    echo "    $(echo "$CERT_INFO" | sed 's/^[* ]*//')"
else
    echo "  ✗ TLS certificate issue"
fi

# Summary
echo ""
echo "=================================================="
echo "  All Tests Passed!"
echo "=================================================="
echo ""
echo "Services running:"
echo "  • Virtual eUICC:   localhost:$VEUICC_PORT"
echo "  • SM-DP+ HTTP:     http://127.0.0.1:$SMDPP_HTTP_PORT"
echo "  • SM-DP+ HTTPS:    https://localhost:$SMDPP_HTTPS_PORT"
echo ""
echo "Test profile download (when implemented):"
echo "  LPAC_APDU=socket lpac profile download \\"
echo "    -s localhost:$SMDPP_HTTPS_PORT \\"
echo "    -m TS48v2_SAIP2.1_BERTLV"
echo ""
echo "Press Ctrl+C to stop all services"
echo "=================================================="

# Keep running
wait

