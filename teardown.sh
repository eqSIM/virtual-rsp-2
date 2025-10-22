#!/bin/bash
# Virtual RSP - Teardown Script
# Clean up all running processes before starting tests

echo "======================================"
echo "  Virtual RSP - Teardown"
echo "======================================"

cd "$(dirname "$0")"

echo "Cleaning up running processes..."

# Kill v-euicc-daemon processes
if pgrep -f "v-euicc-daemon" > /dev/null; then
    echo "  - Stopping v-euicc-daemon processes..."
    pkill -f "v-euicc-daemon" || true
else
    echo "  - No v-euicc-daemon processes running"
fi

# Kill osmo-smdpp processes
if pgrep -f "osmo-smdpp" > /dev/null; then
    echo "  - Stopping osmo-smdpp processes..."
    pkill -f "osmo-smdpp" || true
else
    echo "  - No osmo-smdpp processes running"
fi

# Kill nginx processes with smdpp config
if pgrep -f "nginx.*smdpp" > /dev/null; then
    echo "  - Stopping nginx smdpp processes..."
    pkill -f "nginx.*smdpp" || true
else
    echo "  - No nginx smdpp processes running"
fi

# Wait a bit for processes to fully terminate
sleep 2

# Clean up temporary log files
echo "Cleaning up temporary files..."
rm -f /tmp/v-euicc-*.log /tmp/osmo-smdpp-*.log /tmp/nginx-*.log 2>/dev/null || true

echo "✅ Teardown complete"
echo ""
