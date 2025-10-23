#!/bin/bash
# Interactive Profile Selection and Installation Demo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'

echo -e "${BOLD}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║        Virtual eUICC - Profile Selection Menu                ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════════════════╝${NC}"
echo

# Get available profiles
PROFILE_DIR="pysim/smdpp-data/upp"
echo -e "${CYAN}📋 Available Test Profiles:${NC}"
echo

# List unique profiles (remove duplicates with different extensions)
PROFILES=($(ls -1 "$PROFILE_DIR"/*.der | xargs -n1 basename | grep -E "UNIQUE\.der$" | sed 's/\.der$//' | sort))

# Display menu
i=1
for profile in "${PROFILES[@]}"; do
    # Determine profile type
    TYPE=""
    if [[ $profile == *"TS48V1"* ]]; then
        TYPE="${DIM}[Test Spec 48 v1]${NC}"
    elif [[ $profile == *"TS48V2"* ]]; then
        TYPE="${DIM}[Test Spec 48 v2]${NC}"
    elif [[ $profile == *"TS48V3"* ]]; then
        TYPE="${DIM}[Test Spec 48 v3]${NC}"
    elif [[ $profile == *"TS48V4"* ]]; then
        TYPE="${DIM}[Test Spec 48 v4]${NC}"
    elif [[ $profile == *"TS48V5"* ]]; then
        TYPE="${DIM}[Test Spec 48 v5]${NC}"
    fi
    
    # Highlight features
    FEATURES=""
    [[ $profile == *"BERTLV"* ]] && FEATURES="${FEATURES}${GREEN}BER-TLV${NC} "
    [[ $profile == *"NOBERTLV"* ]] && FEATURES="${FEATURES}${YELLOW}No BER-TLV${NC} "
    [[ $profile == *"SAIP2"* ]] && FEATURES="${FEATURES}${BLUE}SAIP2${NC} "
    [[ $profile == *"SUCI"* ]] && FEATURES="${FEATURES}${MAGENTA}SUCI${NC} "
    
    printf "%2d) ${BOLD}%-45s${NC} %s %s\n" $i "$profile" "$TYPE" "$FEATURES"
    ((i++))
done

echo
echo -e "${YELLOW}Special options:${NC}"
echo -e " 0) ${BOLD}Custom Matching ID${NC} (enter manually)"
echo -e " q) Quit"
echo

# Get user selection
read -p "$(echo -e ${CYAN}Select profile number [1-${#PROFILES[@]}]:${NC} )" selection

# Handle quit
if [[ "$selection" == "q" ]] || [[ "$selection" == "Q" ]]; then
    echo -e "${YELLOW}Cancelled.${NC}"
    exit 0
fi

# Handle custom matching ID
if [[ "$selection" == "0" ]]; then
    echo
    read -p "$(echo -e ${CYAN}Enter custom Matching ID:${NC} )" MATCHING_ID
    if [ -z "$MATCHING_ID" ]; then
        echo -e "${RED}✗${NC} Matching ID cannot be empty"
        exit 1
    fi
else
    # Validate selection
    if ! [[ "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -lt 1 ] || [ "$selection" -gt "${#PROFILES[@]}" ]; then
        echo -e "${RED}✗${NC} Invalid selection"
        exit 1
    fi
    
    # Get selected profile
    MATCHING_ID="${PROFILES[$((selection-1))]}"
fi

echo
echo -e "${GREEN}✓${NC} Selected profile: ${BOLD}$MATCHING_ID${NC}"
echo

# Ask for demo type
echo -e "${CYAN}Select demo type:${NC}"
echo "  1) Quick demo (simple overview)"
echo "  2) Detailed demo (full crypto details)"
echo
read -p "$(echo -e ${CYAN}Choice [1-2]:${NC} )" demo_type

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Starting Profile Installation${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo
echo -e "  ${YELLOW}SM-DP+ Address:${NC} testsmdpplus1.example.com:8443"
echo -e "  ${YELLOW}Matching ID:${NC}    $MATCHING_ID"
echo

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
    [ ! -z "$EUICC_PID" ] && kill $EUICC_PID 2>/dev/null || true
    [ ! -z "$SMDPP_PID" ] && kill $SMDPP_PID 2>/dev/null || true
    [ ! -z "$NGINX_PID" ] && kill $NGINX_PID 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Cleanup complete"
}

trap cleanup EXIT

# Pre-flight cleanup
pkill -9 -f "v-euicc-daemon 8765" 2>/dev/null || true
pkill -9 -f "osmo-smdpp" 2>/dev/null || true
pkill -9 nginx 2>/dev/null || true
lsof -ti:8765 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:8443 | xargs kill -9 2>/dev/null || true
sleep 2

# Start services
echo -e "${BLUE}▶${NC} Starting v-euicc daemon..."
./build/v-euicc/v-euicc-daemon 8765 > /tmp/menu-euicc.log 2>&1 &
EUICC_PID=$!
sleep 2

if ! grep -q "testsmdpplus1.example.com" /etc/hosts; then
    echo "127.0.0.1 testsmdpplus1.example.com" | sudo tee -a /etc/hosts > /dev/null
fi

echo -e "${BLUE}▶${NC} Starting SM-DP+ server..."
cd pysim
./osmo-smdpp.py -H 127.0.0.1 -p 8000 --nossl -c generated > /tmp/menu-smdpp.log 2>&1 &
SMDPP_PID=$!
nginx -c "$PWD/nginx-smdpp.conf" -p "$PWD" > /tmp/menu-nginx.log 2>&1 &
NGINX_PID=$!
cd ..
sleep 4

# Setup lpac
LPAC="./build/lpac/src/lpac"
export DYLD_LIBRARY_PATH=./build/lpac/euicc:./build/lpac/utils:./build/lpac/driver
export LPAC_APDU=socket
export LPAC_APDU_SOCKET_HOST=127.0.0.1
export LPAC_APDU_SOCKET_PORT=8765

# Get eUICC info
echo -e "${CYAN}→${NC} Getting eUICC information..."
CHIP_INFO=$($LPAC chip info 2>&1)
if echo "$CHIP_INFO" | grep -q '"code":0'; then
    EID=$(echo "$CHIP_INFO" | jq -r '.payload.data.eidValue' 2>/dev/null)
    echo -e "${GREEN}✓${NC} EID: $EID"
fi

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Downloading Profile${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

# Download profile
if [[ "$demo_type" == "2" ]]; then
    # Detailed demo - show crypto operations
    echo -e "${CYAN}→${NC} Starting detailed profile download..."
    $LPAC profile download -s "testsmdpplus1.example.com:8443" -m "$MATCHING_ID" > /tmp/menu-lpac.log 2>&1 &
    DOWNLOAD_PID=$!
    
    sleep 3
    
    # Show authentication
    echo -e "${CYAN}→${NC} ${BOLD}Authentication Phase${NC}"
    if grep -q "AuthenticateServer: Real ECDSA signature generated" /tmp/menu-euicc.log; then
        SIG_SIZE=$(grep "AuthenticateServer: Real ECDSA signature generated" /tmp/menu-euicc.log | tail -1 | grep -o '[0-9]* bytes' | awk '{print $1}')
        echo -e "   ${GREEN}✓${NC} ECDSA signature: $SIG_SIZE bytes (NIST P-256)"
    fi
    
    sleep 2
    
    # Show key generation
    echo
    echo -e "${CYAN}→${NC} ${BOLD}Key Generation${NC}"
    if grep -q "Generated valid euiccOtpk:" /tmp/menu-euicc.log; then
        echo -e "   ${GREEN}✓${NC} Ephemeral key pair generated (otPK/otSK.EUICC.ECKA)"
    fi
    
    sleep 2
    
    # Show session keys
    echo
    echo -e "${CYAN}→${NC} ${BOLD}Session Keys${NC}"
    if grep -q "Session keys derived successfully" /tmp/menu-euicc.log; then
        echo -e "   ${GREEN}✓${NC} ECDH + KDF: KEK (16 bytes) + KM (16 bytes)"
    fi
    
    wait $DOWNLOAD_PID 2>/dev/null || true
    
    # Show BPP processing
    echo
    echo -e "${CYAN}→${NC} ${BOLD}BPP Processing${NC}"
    BPP_COUNT=$(grep -c "BPP.*command.*received" /tmp/menu-euicc.log 2>/dev/null || echo "0")
    echo -e "   ${GREEN}✓${NC} Processed $BPP_COUNT BPP commands"
    
    TOTAL_DATA=$(grep "Stored.*bytes of BPP data, total:" /tmp/menu-euicc.log | tail -1 | grep -o 'total: [0-9]*' | awk '{print $2}')
    if [ ! -z "$TOTAL_DATA" ]; then
        echo -e "   ${GREEN}✓${NC} Profile data: $TOTAL_DATA bytes"
    fi
else
    # Quick demo
    echo -e "${CYAN}→${NC} Downloading and installing..."
    DOWNLOAD_OUTPUT=$($LPAC profile download -s "testsmdpplus1.example.com:8443" -m "$MATCHING_ID" 2>&1 | tee /tmp/menu-lpac.log)
fi

# Check result
echo
if grep -q "Created profile metadata:" /tmp/menu-euicc.log; then
    PROFILE_INFO=$(grep "Created profile metadata:" /tmp/menu-euicc.log | tail -1)
    ICCID=$(echo "$PROFILE_INFO" | grep -o 'ICCID=[^,]*' | cut -d= -f2)
    PROF_NAME=$(echo "$PROFILE_INFO" | grep -o 'Name=.*' | cut -d= -f2)
    
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}${BOLD}  ✓ Profile Installation Successful!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
    echo -e "   ${YELLOW}ICCID:${NC}             $ICCID"
    echo -e "   ${YELLOW}Profile Name:${NC}      $PROF_NAME"
    echo -e "   ${YELLOW}Matching ID:${NC}       $MATCHING_ID"
    echo -e "   ${YELLOW}State:${NC}             Disabled (default)"
else
    echo -e "${RED}✗${NC} Profile installation failed"
    echo -e "${YELLOW}Check logs:${NC} /tmp/menu-euicc.log, /tmp/menu-lpac.log"
fi

echo
echo -e "${YELLOW}📋 Logs available at:${NC}"
echo -e "   • v-euicc:  /tmp/menu-euicc.log"
echo -e "   • SM-DP+:   /tmp/menu-smdpp.log"
echo -e "   • lpac:     /tmp/menu-lpac.log"
echo
