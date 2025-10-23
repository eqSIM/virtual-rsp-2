#!/bin/bash
# Demo script: Show eUICC Info -> Download Profile -> Show Profile List
# This demonstrates a complete profile installation workflow

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
SMDP_ADDRESS="${1:-testsmdpplus1.example.com:8443}"
MATCHING_ID="${2:-TS48V2-SAIP2-1-BERTLV-UNIQUE}"

# Show usage if --help
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Usage: $0 [SMDP_ADDRESS] [MATCHING_ID]"
    echo
    echo "Examples:"
    echo "  $0                                              # Use defaults"
    echo "  $0 testsmdpplus1.example.com:8443 TS48V3-SAIP2-1-BERTLV-UNIQUE"
    echo "  $0 testsmdpplus1.example.com:8443 TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE"
    echo
    echo "Available profiles in pysim/smdpp-data/upp/:"
    ls -1 pysim/smdpp-data/upp/*.der 2>/dev/null | xargs -n1 basename | grep UNIQUE | sed 's/\.der$//' | sed 's/^/  - /'
    exit 0
fi

echo -e "${BOLD}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  Virtual eUICC - Profile Installation Demo (SGP.22 v2.5)     ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════════════════╝${NC}"
echo

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
    
    # Kill background processes
    if [ ! -z "$EUICC_PID" ]; then
        kill $EUICC_PID 2>/dev/null || true
    fi
    if [ ! -z "$SMDPP_PID" ]; then
        kill $SMDPP_PID 2>/dev/null || true
    fi
    if [ ! -z "$NGINX_PID" ]; then
        kill $NGINX_PID 2>/dev/null || true
    fi
    
    # Clean up log files
    rm -f /tmp/demo-euicc.log /tmp/demo-smdpp.log /tmp/demo-lpac.log /tmp/demo-nginx.log
    
    echo -e "${GREEN}✓${NC} Cleanup complete"
}

trap cleanup EXIT

# Kill any existing instances
echo -e "${BLUE}▶${NC}  Cleaning up any existing instances..."
pkill -9 -f "v-euicc-daemon 8765" 2>/dev/null || true
pkill -9 -f "osmo-smdpp" 2>/dev/null || true
pkill -9 nginx 2>/dev/null || true
lsof -ti:8765 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:8443 | xargs kill -9 2>/dev/null || true
sleep 2

# Start v-euicc daemon
echo -e "${BLUE}▶${NC}  Starting v-euicc daemon..."
./build/v-euicc/v-euicc-daemon 8765 > /tmp/demo-euicc.log 2>&1 &
EUICC_PID=$!
sleep 2

if ! kill -0 $EUICC_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Failed to start v-euicc daemon"
    exit 1
fi
echo -e "${GREEN}✓${NC} v-euicc daemon started (PID: $EUICC_PID)"

# Add hosts entry for SM-DP+
echo -e "${BLUE}▶${NC}  Configuring /etc/hosts..."
if ! grep -q "testsmdpplus1.example.com" /etc/hosts; then
    echo "127.0.0.1 testsmdpplus1.example.com" | sudo tee -a /etc/hosts > /dev/null
    echo -e "${GREEN}✓${NC} Added testsmdpplus1.example.com to /etc/hosts"
else
    echo -e "${GREEN}✓${NC} testsmdpplus1.example.com already in /etc/hosts"
fi

# Start osmo-smdpp
echo -e "${BLUE}▶${NC}  Starting SM-DP+ server..."
cd pysim

# Check if klein is installed
if ! python3 -c "import klein" 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC}  Installing Python dependencies..."
    pip3 install -q klein twisted cryptography pycryptodome pyscard pyOpenSSL || {
        echo -e "${RED}✗${NC} Failed to install dependencies"
        echo -e "${YELLOW}💡 Try: pip3 install klein twisted cryptography pycryptodome pyscard pyOpenSSL${NC}"
        exit 1
    }
fi

# Start SM-DP+ without SSL (nginx will handle HTTPS)
./osmo-smdpp.py -H 127.0.0.1 -p 8000 --nossl -c generated > /tmp/demo-smdpp.log 2>&1 &
SMDPP_PID=$!

# Start nginx for HTTPS proxy
nginx -c "$PWD/nginx-smdpp.conf" -p "$PWD" > /tmp/demo-nginx.log 2>&1 &
NGINX_PID=$!

cd ..
sleep 4

if ! kill -0 $SMDPP_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Failed to start SM-DP+ server"
    echo -e "${YELLOW}Check log: /tmp/demo-smdpp.log${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} SM-DP+ server started (PID: $SMDPP_PID)"

if ! kill -0 $NGINX_PID 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC}  nginx failed to start"
else
    echo -e "${GREEN}✓${NC} nginx HTTPS proxy started (PID: $NGINX_PID)"
fi

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  STEP 1: Get eUICC Information${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

# lpac binary location and environment
LPAC="./build/lpac/src/lpac"
export DYLD_LIBRARY_PATH=./build/lpac/euicc:./build/lpac/utils:./build/lpac/driver
export LPAC_APDU=socket
export LPAC_APDU_SOCKET_HOST=127.0.0.1
export LPAC_APDU_SOCKET_PORT=8765

# Get eUICC Info
echo -e "${BLUE}→${NC} Retrieving eUICC information..."
CHIP_INFO=$($LPAC chip info 2>&1)

# Check if command succeeded
if echo "$CHIP_INFO" | grep -q '"code":0'; then
    EID=$(echo "$CHIP_INFO" | jq -r '.payload.data.eidValue' 2>/dev/null || echo "")
    echo -e "${GREEN}✓${NC} ${BOLD}EID:${NC} $EID"
    echo
    
    # Display eUICC capabilities
    echo "$CHIP_INFO" | jq -r '.payload.data.EUICCInfo2 | 
        "  Profile Version:        \(.profileVersion)",
        "  SVN:                    \(.svn)", 
        "  Firmware Version:       \(.euiccFirmwareVer)",
        "  Free NV Memory:         \(.extCardResource.freeNonVolatileMemory) bytes",
        "  Installed Profiles:     \(.extCardResource.installedApplication)"' 2>/dev/null || echo -e "${YELLOW}  Could not parse info${NC}"
else
    echo -e "${RED}✗${NC} Failed to retrieve eUICC information"
    exit 1
fi

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  STEP 2: Download and Install Profile${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

echo -e "${BLUE}→${NC} SM-DP+ Address: ${BOLD}$SMDP_ADDRESS${NC}"
echo -e "${BLUE}→${NC} Matching ID:    ${BOLD}$MATCHING_ID${NC}"
echo

echo -e "${BLUE}→${NC} Starting profile download..."
DOWNLOAD_OUTPUT=$($LPAC profile download -s "$SMDP_ADDRESS" -m "$MATCHING_ID" 2>&1 | tee /tmp/demo-lpac.log)

# Check if download succeeded
if echo "$DOWNLOAD_OUTPUT" | grep -q '"code":0,"message":"success"'; then
    echo -e "${GREEN}✓${NC} ${BOLD}Profile installation successful!${NC}"
    
    # Extract profile metadata
    METADATA=$(echo "$DOWNLOAD_OUTPUT" | grep "es8p_meatadata_parse" | jq -r '.payload.data' 2>/dev/null || echo "")
    
    if [ ! -z "$METADATA" ]; then
        echo
        echo -e "${BOLD}Profile Details:${NC}"
        echo "$METADATA" | jq -r '
            "  ICCID:                  \(.iccid)",
            "  Profile Name:           \(.profileName)",
            "  Service Provider:       \(.serviceProviderName)"' 2>/dev/null || true
    fi
else
    echo -e "${RED}✗${NC} Profile installation failed"
    echo
    echo -e "${YELLOW}Last few lines of output:${NC}"
    echo "$DOWNLOAD_OUTPUT" | tail -5
    exit 1
fi

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  STEP 3: List Installed Profiles${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

echo -e "${BLUE}→${NC} Retrieving profile list..."
PROFILE_LIST=$($LPAC profile list 2>/dev/null)

if echo "$PROFILE_LIST" | grep -q "profileName"; then
    echo -e "${GREEN}✓${NC} Profiles found:"
    echo
    
    # Parse and display profiles
    echo "$PROFILE_LIST" | jq -r '.payload[] | 
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "  ICCID:              \(.iccid)",
        "  Profile Name:       \(.profileName)",
        "  Provider:           \(.serviceProviderName // "N/A")",
        "  State:              \(.profileState)",
        "  Profile Class:      \(.profileClass // "operational")",
        ""' 2>/dev/null || echo -e "${YELLOW}  Could not parse profile list${NC}"
else
    echo -e "${YELLOW}⚠${NC}  No profiles found or could not retrieve list"
fi

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Summary${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo
echo -e "${GREEN}✓${NC} eUICC Information:      ${GREEN}Retrieved${NC}"
echo -e "${GREEN}✓${NC} Profile Download:       ${GREEN}Successful${NC}"
echo -e "${GREEN}✓${NC} Profile Installation:   ${GREEN}Completed${NC}"
echo -e "${GREEN}✓${NC} Profile List:           ${GREEN}Displayed${NC}"

echo
echo -e "${BOLD}${GREEN}🎉 Demo completed successfully!${NC}"
echo
echo -e "${YELLOW}💡 Log files:${NC}"
echo -e "   v-euicc:  /tmp/demo-euicc.log"
echo -e "   SM-DP+:   /tmp/demo-smdpp.log"
echo -e "   lpac:     /tmp/demo-lpac.log"
echo
