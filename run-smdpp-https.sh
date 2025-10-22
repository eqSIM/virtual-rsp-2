#!/bin/bash
# Start osmo-smdpp with nginx TLS proxy

set -e

echo "=== Starting osmo-smdpp with HTTPS ==="
echo ""

# Kill any existing instances
echo "Cleaning up any existing processes..."
pkill -f osmo-smdpp.py || true
pkill -f "nginx.*smdpp" || true
sleep 1

cd pySim

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Error: Python virtual environment not found"
    echo "Run: ./pySim/setup-venv.sh first"
    exit 1
fi

# Check if certificates exist
if [ ! -f "smdpp-data/generated/DPtls/CERT_S_SM_DP_TLS_NIST.pem" ]; then
    echo "Error: Certificates not found"
    echo "Certificates should be in smdpp-data/generated/"
    exit 1
fi

# Check if hosts entry exists
if ! grep -q "testsmdpplus1.example.com" /etc/hosts 2>/dev/null; then
    echo "Warning: testsmdpplus1.example.com not in /etc/hosts"
    echo "Run: ./add-hosts-entry.sh (requires sudo)"
    echo "Continuing anyway (can use localhost:8443)..."
    echo ""
fi

# Start osmo-smdpp on HTTP (without SSL, nginx handles TLS)
echo "1. Starting osmo-smdpp on http://127.0.0.1:8000"
source venv/bin/activate
./osmo-smdpp.py -H 127.0.0.1 -p 8000 --nossl -c generated -v > osmo-smdpp.log 2>&1 &
SMDPP_PID=$!
echo "   PID: $SMDPP_PID"

sleep 3

# Check if osmo-smdpp started
if ! kill -0 $SMDPP_PID 2>/dev/null; then
    echo "Error: osmo-smdpp failed to start"
    cat osmo-smdpp.log
    exit 1
fi

echo "   Status: Running"

# Start nginx TLS proxy
echo ""
echo "2. Starting nginx TLS proxy on https://localhost:8443"

if ! command -v nginx &> /dev/null; then
    echo "Error: nginx not found"
    echo "Install with: brew install nginx"
    kill $SMDPP_PID
    exit 1
fi

nginx -c "$PWD/nginx-smdpp.conf" -p "$PWD" > nginx-startup.log 2>&1 &
NGINX_PID=$!
echo "   PID: $NGINX_PID"

sleep 2

# Check if nginx started
if ! kill -0 $NGINX_PID 2>/dev/null; then
    echo "Error: nginx failed to start"
    cat nginx-error.log 2>/dev/null || cat nginx-startup.log
    kill $SMDPP_PID
    exit 1
fi

echo "   Status: Running"

echo ""
echo "======================================"
echo "SM-DP+ Server Ready!"
echo "======================================"
echo ""
echo "Access URLs:"
echo "  HTTPS: https://testsmdpplus1.example.com:8443"
echo "  HTTPS: https://localhost:8443"
echo "  HTTP:  http://127.0.0.1:8000 (internal only)"
echo ""
echo "Test with:"
echo "  curl -k https://localhost:8443/gsma/rsp2/es9plus/initiateAuthentication"
echo ""
echo "Logs:"
echo "  osmo-smdpp: pySim/osmo-smdpp.log"
echo "  nginx:      pySim/nginx-error.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo "======================================"
echo ""

# Cleanup handler
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $SMDPP_PID 2>/dev/null || true
    kill $NGINX_PID 2>/dev/null || true
    sleep 1
    pkill -f "nginx.*smdpp" || true
    echo "Stopped"
    exit 0
}

trap cleanup INT TERM

# Wait for processes
wait

