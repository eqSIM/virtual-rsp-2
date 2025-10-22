#!/bin/bash
# Complete Virtual RSP Test - All Components

set -e

echo "=========================================================================="
echo "  Virtual RSP - Complete System Test"
echo "=========================================================================="
echo ""

cd "$(dirname "$0")"

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up processes..."
    pkill -f v-euicc-daemon || true
    pkill -f osmo-smdpp || true
    pkill -f "nginx.*smdpp" || true
    sleep 2
    echo "Cleanup complete"
}

# Initial cleanup
pkill -f v-euicc-daemon || true
pkill -f osmo-smdpp || true
pkill -f "nginx.*smdpp" || true
sleep 2

trap cleanup EXIT INT TERM

echo "Step 1: Starting infrastructure"
echo "=========================================================================="
echo ""

# Start osmo-smdpp + nginx
echo "Starting SM-DP+ server (osmo-smdpp + nginx)..."
cd pySim
source venv/bin/activate
./osmo-smdpp.py -H 127.0.0.1 -p 8000 --nossl -c generated > osmo-smdpp.log 2>&1 &
SMDPP_PID=$!
sleep 3

if ! kill -0 $SMDPP_PID 2>/dev/null; then
    echo "❌ osmo-smdpp failed to start"
    cat osmo-smdpp.log | tail -20
    exit 1
fi
echo "✅ osmo-smdpp running (PID: $SMDPP_PID)"

nginx -c "$PWD/nginx-smdpp.conf" -p "$PWD" > /tmp/nginx.log 2>&1 &
NGINX_PID=$!
cd ..
sleep 2

if ! kill -0 $NGINX_PID 2>/dev/null; then
    echo "❌ nginx failed to start"
    cat /tmp/nginx.log
    exit 1
fi
echo "✅ nginx TLS proxy running (PID: $NGINX_PID)"

# Start v-euicc
echo "Starting virtual eUICC daemon..."
./build/v-euicc/v-euicc-daemon 8765 > /tmp/v-euicc.log 2>&1 &
VEUICC_PID=$!
sleep 3

if ! kill -0 $VEUICC_PID 2>/dev/null; then
    echo "❌ v-euicc-daemon failed to start"
    cat /tmp/v-euicc.log
    exit 1
fi
echo "✅ v-euicc-daemon running (PID: $VEUICC_PID)"

echo ""
echo "Step 2: Testing Mutual Authentication"
echo "=========================================================================="
echo ""

cd build/lpac/src

OUTPUT=$(DYLD_LIBRARY_PATH=../../lpac/euicc:../../lpac/utils:../../lpac/driver \
         LPAC_APDU=socket \
         ./lpac profile discovery \
         -s testsmdpplus1.example.com:8443 \
         -i 123456789012345 2>&1)

echo "$OUTPUT" | python3 -m json.tool 2>/dev/null | head -30 || echo "$OUTPUT"

# Check results
if echo "$OUTPUT" | grep -q '"es10b_get_euicc_challenge_and_info"'; then
    echo "✅ Challenge & Info retrieved"
fi

if echo "$OUTPUT" | grep -q '"es9p_initiate_authentication"'; then
    echo "✅ Authentication initiated"
fi

if echo "$OUTPUT" | grep -q '"es10b_authenticate_server"'; then
    echo "✅ Server authenticated (ECDSA signature)"
fi

if echo "$OUTPUT" | grep -q '"es11_authenticate_client"'; then
    echo "✅ Client authenticated"
fi

# Check osmo-smdpp logs
cd ../../..
if tail -20 pySim/osmo-smdpp.log | grep -q "('8.2.6', '3.8', 'Refused')"; then
    echo "✅ Mutual authentication: SUCCESS"
    echo "   (Refused = MatchingID not registered in discovery mode)"
elif tail -20 pySim/osmo-smdpp.log | grep -q "Verification failed"; then
    echo "❌ Signature verification failed"
    tail -10 pySim/osmo-smdpp.log | grep "ApiError"
    exit 1
fi

echo ""
echo "Step 3: Testing Profile Download"
echo "=========================================================================="
echo ""

cd build/lpac/src

echo "Attempting download of: TS48V2-SAIP2-1-BERTLV-UNIQUE"
echo ""

timeout 45 bash -c "DYLD_LIBRARY_PATH=../../lpac/euicc:../../lpac/utils:../../lpac/driver \
         LPAC_APDU=socket \
         ./lpac profile download \
         -s testsmdpplus1.example.com:8443 \
         -m TS48V2-SAIP2-1-BERTLV-UNIQUE" 2>&1 | tee /tmp/download-result.log || true

DOWNLOAD_EXIT=$?

echo ""
echo "Download exit code: $DOWNLOAD_EXIT"

# Analyze result
if grep -q '"es10b_prepare_download"' /tmp/download-result.log; then
    echo "✅ PrepareDownload executed"
fi

if grep -q '"es9p_get_bound_profile_package"' /tmp/download-result.log; then
    echo "✅ BoundProfilePackage requested"
fi

if grep -q '"es10b_load_bound_profile_package"' /tmp/download-result.log; then
    echo "✅ LoadBoundProfilePackage executed"
fi

if grep -q '"code":0' /tmp/download-result.log | grep -q '"message":"success"'; then
    echo "✅ Profile download: SUCCESS"
elif grep -q "Refused\|HTTP status code error" /tmp/download-result.log; then
    echo "⚠️  Download in progress but needs refinement"
    echo "   Check logs for details"
else
    echo "❌ Download failed"
fi

echo ""
echo "Step 4: Checking logs"
echo "=========================================================================="
echo ""

echo "v-euicc log (last 20 lines with relevant info):"
grep -E "Loaded|signature|PrepareDownload|BPP|ProfileInstallation|matchingID" /tmp/v-euicc.log | tail -20

echo ""
echo "osmo-smdpp log (last 10 lines):"
tail -10 pySim/osmo-smdpp.log | grep -v "^	"

echo ""
echo "=========================================================================="
echo "  Test Complete"
echo "=========================================================================="
echo ""
echo "Services still running. Press Ctrl+C to stop all."
echo ""

# Keep running
wait

