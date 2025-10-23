#!/bin/bash

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}=========================================================================="
echo "Profile Installation and Listing Test"
echo -e "==========================================================================${NC}"

# Step 1: Run test-all.sh to install profile
echo -e "\n${YELLOW}Step 1: Running test-all.sh to install profile...${NC}"
./test-all.sh

# Step 2: Check if profile was installed (stored in memory)
echo -e "\n${YELLOW}Step 2: Checking profile installation status...${NC}"
if grep -q "Created profile metadata" /tmp/v-euicc-test-all.log 2>/dev/null; then
    echo -e "${GREEN}✅ Profile metadata created during download${NC}"
else
    echo -e "${RED}⚠️  Profile metadata not found in logs${NC}"
fi

# Step 3: Cleanup from test-all.sh
echo -e "\n${YELLOW}Step 3: Cleaning up test-all.sh processes...${NC}"
pkill -f v-euicc-daemon 2>/dev/null || true
pkill -f osmo-smdpp.py 2>/dev/null || true
pkill -f log_monitor.py 2>/dev/null || true
sleep 2
echo -e "${GREEN}✅ Cleanup complete${NC}"

# Step 4: Start v-euicc daemon
echo -e "\n${YELLOW}Step 4: Starting v-euicc daemon and socket...${NC}"
echo "Starting v-euicc daemon on port 8765..."
./build/v-euicc/v-euicc-daemon 8765 > /tmp/v-euicc-profile-test.log 2>&1 &
V_EUICC_PID=$!
sleep 2

# Check if v-euicc started successfully
if ps -p $V_EUICC_PID > /dev/null; then
    echo -e "${GREEN}✅ v-euicc daemon started (PID: $V_EUICC_PID)${NC}"
else
    echo -e "${RED}❌ Failed to start v-euicc daemon${NC}"
    exit 1
fi

# Set environment for lpac
export DYLD_LIBRARY_PATH=build/lpac/euicc:build/lpac/utils:build/lpac/driver
export LPAC_APDU=socket

# Step 5: Run lpac chip info
echo -e "\n${YELLOW}Step 5a: Running lpac chip info...${NC}"
echo -e "${CYAN}Command: lpac chip info${NC}"
echo "---"
cd build/lpac/src
./lpac chip info -i 123456789012345 || true
cd ../../..

# Step 5b: Run lpac profile list
echo -e "\n${YELLOW}Step 5b: Running lpac profile list...${NC}"
echo -e "${CYAN}Command: lpac profile list${NC}"
echo "---"
cd build/lpac/src
PROFILE_LIST_OUTPUT=$(./lpac profile list -i 123456789012345 2>&1)
echo "$PROFILE_LIST_OUTPUT"
cd ../../..

# Parse profile list output
if echo "$PROFILE_LIST_OUTPUT" | grep -q '"code":0'; then
    echo -e "\n${GREEN}✅ Profile list command succeeded${NC}"
    
    # Check if any profiles are listed
    PROFILE_COUNT=$(echo "$PROFILE_LIST_OUTPUT" | grep -o '"iccid"' | wc -l)
    if [ "$PROFILE_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✅ Found $PROFILE_COUNT profile(s) in the list${NC}"
    else
        echo -e "${YELLOW}⚠️  No profiles found in the list${NC}"
        echo -e "${YELLOW}   Note: Profiles are currently stored in memory only${NC}"
        echo -e "${YELLOW}   A fresh v-euicc daemon has no profile history${NC}"
    fi
else
    echo -e "${RED}❌ Profile list command failed${NC}"
fi

# Show v-euicc logs
echo -e "\n${CYAN}=========================================================================="
echo "v-euicc Daemon Logs (last 30 lines):"
echo -e "==========================================================================${NC}"
tail -30 /tmp/v-euicc-profile-test.log

# Cleanup
echo -e "\n${YELLOW}Cleaning up...${NC}"
kill $V_EUICC_PID 2>/dev/null || true
sleep 1
echo -e "${GREEN}✅ Test complete${NC}"

echo -e "\n${CYAN}=========================================================================="
echo "Summary:"
echo -e "==========================================================================${NC}"
echo "• Profile download: Tested via test-all.sh"
echo "• v-euicc daemon: Started successfully"
echo "• lpac chip info: Executed"
echo "• lpac profile list: Executed"
echo ""
echo -e "${YELLOW}NOTE: Profiles are currently stored in memory only.${NC}"
echo -e "${YELLOW}      To see installed profiles, they must be persisted to disk.${NC}"
echo -e "${YELLOW}      This is the next TODO item.${NC}"
