#!/bin/bash

# Quick test script for lpac commands against v-euicc daemon
# This tests the eUICC commands without a full profile download

set -e

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}=========================================================================="
echo "Quick lpac Command Test (chip info + profile list)"
echo -e "==========================================================================${NC}"

# Cleanup any existing processes
pkill -f v-euicc-daemon 2>/dev/null || true
sleep 1

# Start v-euicc daemon
echo -e "\n${YELLOW}Starting v-euicc daemon on port 8765...${NC}"
./build/v-euicc/v-euicc-daemon 8765 > /tmp/v-euicc-quick-test.log 2>&1 &
V_EUICC_PID=$!
sleep 2

if ! ps -p $V_EUICC_PID > /dev/null; then
    echo -e "${RED}❌ Failed to start v-euicc daemon${NC}"
    exit 1
fi

echo -e "${GREEN}✅ v-euicc daemon started (PID: $V_EUICC_PID)${NC}"

# Set environment for lpac
export DYLD_LIBRARY_PATH=build/lpac/euicc:build/lpac/utils:build/lpac/driver
export LPAC_APDU=socket

# Run chip info
echo -e "\n${CYAN}=========================================================================="
echo "Test 1: lpac chip info"
echo -e "==========================================================================${NC}"
cd build/lpac/src
./lpac chip info -i 123456789012345
cd ../../..

# Run profile list
echo -e "\n${CYAN}=========================================================================="
echo "Test 2: lpac profile list"
echo -e "==========================================================================${NC}"
cd build/lpac/src
./lpac profile list -i 123456789012345
cd ../../..

# Show logs
echo -e "\n${CYAN}=========================================================================="
echo "v-euicc Daemon Logs:"
echo -e "==========================================================================${NC}"
cat /tmp/v-euicc-quick-test.log

# Cleanup
echo -e "\n${YELLOW}Cleaning up...${NC}"
kill $V_EUICC_PID 2>/dev/null || true
echo -e "${GREEN}✅ Test complete${NC}"
