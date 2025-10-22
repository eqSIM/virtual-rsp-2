#!/bin/bash
# Test script for virtual eUICC integration

set -e

echo "=== Virtual eUICC Test Script ==="
echo ""

# Build directory paths
BUILD_DIR="build"
LPAC_BIN="$BUILD_DIR/lpac/src/lpac"
DAEMON_BIN="$BUILD_DIR/v-euicc/v-euicc-daemon"

# Check if binaries exist
if [ ! -f "$LPAC_BIN" ]; then
    echo "Error: lpac binary not found. Run 'cmake --build build' first."
    exit 1
fi

if [ ! -f "$DAEMON_BIN" ]; then
    echo "Error: v-euicc-daemon binary not found. Run 'cmake --build build' first."
    exit 1
fi

# Start daemon
echo "1. Starting virtual eUICC daemon on port 8765..."
$DAEMON_BIN 8765 > /tmp/v-euicc-daemon.log 2>&1 &
DAEMON_PID=$!
echo "   Daemon started (PID: $DAEMON_PID)"
sleep 2

# Test connection
echo ""
echo "2. Testing socket connection..."
if ! nc -z localhost 8765; then
    echo "   Error: Cannot connect to daemon"
    kill $DAEMON_PID 2>/dev/null || true
    exit 1
fi
echo "   Connection successful"

# Run lpac chip info
echo ""
echo "3. Running 'lpac chip info' with socket driver..."
cd "$BUILD_DIR/lpac/src"

# Create driver symlinks if needed
if [ ! -d "driver" ]; then
    mkdir -p driver
    for driver in ../../../lpac/driver/driver_*.dylib; do
        ln -sf "$driver" driver/
    done
fi

# Run lpac
DYLD_LIBRARY_PATH=../../lpac/euicc:../../lpac/utils:../../lpac/driver \
LPAC_APDU=socket \
./lpac chip info

echo ""
echo "4. Stopping daemon..."
kill $DAEMON_PID 2>/dev/null || true
wait $DAEMON_PID 2>/dev/null || true
echo "   Daemon stopped"

echo ""
echo "=== Test completed successfully! ==="

