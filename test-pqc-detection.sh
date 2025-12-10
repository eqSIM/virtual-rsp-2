#!/bin/bash
# Quick test to see why PQC falls back to classical mode

set -e

cd "$(dirname "$0")"

echo "=== Testing PQC Detection ==="
echo

# Cleanup
pkill -9 -f "v-euicc-daemon\|osmo-smdpp\|nginx" 2>/dev/null || true
sleep 1
rm -f /tmp/pqc-test-*.log

# Start v-euicc
echo "[1/3] Starting v-euicc..."
./build/v-euicc/v-euicc-daemon 8765 > /tmp/pqc-test-euicc.log 2>&1 &
EUICC_PID=$!
sleep 2

# Start SM-DP+
echo "[2/3] Starting SM-DP+..."
cd pysim
OQS_PYTHON_BUILD_SKIP_INSTALL=1 ./osmo-smdpp-pqc.sh -H 127.0.0.1 -p 8000 --nossl -c generated > /tmp/pqc-test-smdpp.log 2>&1 &
SMDPP_PID=$!
cd ..
sleep 3

# Trigger a profile download attempt (this will call PrepareDownload)
echo "[3/3] Triggering PrepareDownload..."
cd build/lpac/src
DYLD_LIBRARY_PATH=../../lpac/euicc:../../lpac/utils:../../lpac/driver \
LPAC_APDU=socket \
LPAC_APDU_SOCKET_HOST=127.0.0.1 \
LPAC_APDU_SOCKET_PORT=8765 \
timeout 10 ./lpac profile download -s "testsmdpplus1.example.com:8000" -m "TS48V2-SAIP2-1-BERTLV-UNIQUE" 2>&1 | head -20 || true
cd ../..

sleep 2

echo
echo "=== v-euicc Debug Output ==="
grep -E "PQC-DEBUG|Generating ML-KEM|mlkem768_supported|ENABLE_PQC|ML-KEM.*keypair|5F4A|hybrid|classical" /tmp/pqc-test-euicc.log | head -20

echo
echo "=== SM-DP+ Debug Output ==="
grep -E "PQC-DEBUG|ML-KEM|5F4A|hybrid|classical" /tmp/pqc-test-smdpp.log | head -20

# Cleanup
kill $EUICC_PID $SMDPP_PID 2>/dev/null || true

