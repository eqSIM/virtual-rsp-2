#!/bin/bash
cd "$(dirname "$0")"

echo "=== MNO Management Console ==="

# Teardown existing processes first
echo "Tearing down existing processes..."
./teardown.sh 2>/dev/null || true

sleep 1

# Use existing venv or create one
if [ ! -d "pysim/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv pysim/venv
fi

source pysim/venv/bin/activate

# Ensure dependencies are installed
echo "Checking dependencies..."
pip install -q PySide6 requests asn1tools cryptography klein twisted

# Start backend services
echo "Starting v-euicc daemon..."
./build/v-euicc/v-euicc-daemon 8765 > data/veuicc.log 2>&1 &
VEUICC_PID=$!
echo "  v-euicc started (PID: $VEUICC_PID)"

sleep 1

echo "Starting SM-DP+ server..."
# Clear stale session database to avoid accumulation
rm -f pysim/sm-dp-sessions-NIST* 2>/dev/null
rm -f pysim/sm-dp-sessions-BRP* 2>/dev/null
cd pysim
# Use in-memory sessions (-m) for clean state each run
python3 osmo-smdpp.py -H 127.0.0.1 -p 8000 --nossl -c generated -m > ../data/smdp.log 2>&1 &
SMDP_PID=$!
echo "  SM-DP+ started (PID: $SMDP_PID) [in-memory sessions]"
cd ..

sleep 2

echo "Starting nginx (TLS proxy)..."
# Ensure log directory exists
mkdir -p data
# nginx runs as daemon by default, redirect all output and run in background
(nginx -c "$(pwd)/pysim/nginx-smdpp.conf" -p "$(pwd)/pysim" >> data/nginx.log 2>&1 &)
sleep 1
if pgrep -f "nginx.*nginx-smdpp" > /dev/null; then
    echo "  nginx started successfully"
else
    echo "  Warning: nginx may not have started (check data/nginx.log)"
fi

sleep 1

echo ""
echo "All services started. Launching MNO Management Console..."
echo ""

# Run the GUI
python3 -m mno.main

# Cleanup on exit
echo ""
echo "Shutting down services..."
./teardown.sh 2>/dev/null || true
echo "Done."
