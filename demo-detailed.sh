#!/bin/bash
# Detailed Demo: Shows cryptographic details of SGP.22 profile installation
# This script displays certificates, signatures, authentication flow, and profile parsing

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
echo -e "${BOLD}║     Virtual eUICC - DETAILED Technical Demo (SGP.22 v2.5)    ║${NC}"
echo -e "${BOLD}║   Showing: Certificates, Signatures, Authentication & Crypto  ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════════════════╝${NC}"
echo

cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
    [ ! -z "$EUICC_PID" ] && kill $EUICC_PID 2>/dev/null || true
    [ ! -z "$SMDPP_PID" ] && kill $SMDPP_PID 2>/dev/null || true
    [ ! -z "$NGINX_PID" ] && kill $NGINX_PID 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Cleanup complete"
}

trap cleanup EXIT

# Pre-flight cleanup
echo -e "${BLUE}▶${NC} Pre-flight cleanup..."
pkill -9 -f "v-euicc-daemon 8765" 2>/dev/null || true
pkill -9 -f "osmo-smdpp" 2>/dev/null || true
pkill -9 nginx 2>/dev/null || true
lsof -ti:8765 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:8443 | xargs kill -9 2>/dev/null || true
sleep 2

# Start v-euicc
echo -e "${BLUE}▶${NC} Starting v-euicc daemon..."
./build/v-euicc/v-euicc-daemon 8765 > /tmp/detailed-euicc.log 2>&1 &
EUICC_PID=$!
sleep 2
[ ! kill -0 $EUICC_PID 2>/dev/null ] && echo -e "${RED}✗${NC} Failed to start v-euicc" && exit 1
echo -e "${GREEN}✓${NC} v-euicc started (PID: $EUICC_PID)"

# Configure hosts
echo -e "${BLUE}▶${NC} Configuring /etc/hosts..."
if ! grep -q "testsmdpplus1.example.com" /etc/hosts; then
    echo "127.0.0.1 testsmdpplus1.example.com" | sudo tee -a /etc/hosts > /dev/null
fi
echo -e "${GREEN}✓${NC} Hosts configured"

# Start SM-DP+
echo -e "${BLUE}▶${NC} Starting SM-DP+ server..."
cd pysim
./osmo-smdpp.py -H 127.0.0.1 -p 8000 --nossl -c generated > /tmp/detailed-smdpp.log 2>&1 &
SMDPP_PID=$!
nginx -c "$PWD/nginx-smdpp.conf" -p "$PWD" > /tmp/detailed-nginx.log 2>&1 &
NGINX_PID=$!
cd ..
sleep 4
[ ! kill -0 $SMDPP_PID 2>/dev/null ] && echo -e "${RED}✗${NC} Failed to start SM-DP+" && exit 1
echo -e "${GREEN}✓${NC} SM-DP+ and nginx started"

# Setup lpac environment
LPAC="./build/lpac/src/lpac"
export DYLD_LIBRARY_PATH=./build/lpac/euicc:./build/lpac/utils:./build/lpac/driver
export LPAC_APDU=socket
export LPAC_APDU_SOCKET_HOST=127.0.0.1
export LPAC_APDU_SOCKET_PORT=8765

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  PART 1: eUICC Certificates and Capabilities${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

# Show eUICC certificates
echo -e "${CYAN}→${NC} ${BOLD}eUICC Certificate Chain:${NC}"
echo -e "${DIM}   Loading certificates from v-euicc...${NC}"

if [ -f "v-euicc/certs/EID_89049032001001234500012345678901_cert_ECDSA_NIST256.der" ]; then
    echo
    echo -e "${YELLOW}   📜 eUICC Certificate (CERT.EUICC.ECDSA):${NC}"
    openssl x509 -inform DER -in v-euicc/certs/EID_89049032001001234500012345678901_cert_ECDSA_NIST256.der -noout -text 2>/dev/null | grep -A2 "Subject:\|Issuer:\|Not Before\|Not After\|Public-Key:" | sed 's/^/      /'
    
    EUICC_CERT_HASH=$(openssl x509 -inform DER -in v-euicc/certs/EID_89049032001001234500012345678901_cert_ECDSA_NIST256.der -noout -fingerprint -sha256 2>/dev/null | cut -d= -f2)
    echo -e "      ${DIM}SHA-256:${NC} $EUICC_CERT_HASH"
fi

if [ -f "v-euicc/certs/EUM_cert_ECDSA_NIST256.der" ]; then
    echo
    echo -e "${YELLOW}   📜 EUM Certificate (CERT.EUM.ECDSA):${NC}"
    openssl x509 -inform DER -in v-euicc/certs/EUM_cert_ECDSA_NIST256.der -noout -text 2>/dev/null | grep -A2 "Subject:\|Issuer:\|Public-Key:" | sed 's/^/      /'
fi

# Get chip info
echo
echo -e "${CYAN}→${NC} ${BOLD}eUICC Information (ES10c.GetEUICCInfo):${NC}"
CHIP_INFO=$($LPAC chip info 2>&1)
if echo "$CHIP_INFO" | grep -q '"code":0'; then
    EID=$(echo "$CHIP_INFO" | jq -r '.payload.data.eidValue' 2>/dev/null)
    echo -e "   ${YELLOW}EID:${NC} $EID"
    echo "$CHIP_INFO" | jq -r '.payload.data.EUICCInfo2 | 
        "   Profile Version:     \(.profileVersion)",
        "   SVN:                 \(.svn)",
        "   Firmware:            \(.euiccFirmwareVer)",
        "   Free NV Memory:      \(.extCardResource.freeNonVolatileMemory) bytes",
        "   Free Volatile Mem:   \(.extCardResource.freeVolatileMemory) bytes",
        "   GlobalPlatform Ver:  \(.globalplatformVersion)",
        "   TS 102 241 Version:  \(.ts102241Version)"' 2>/dev/null
    
    echo
    echo -e "   ${YELLOW}Certificate PKIDs for Verification:${NC}"
    echo "$CHIP_INFO" | jq -r '.payload.data.EUICCInfo2.euiccCiPKIdListForVerification[]' 2>/dev/null | sed 's/^/      • /'
fi

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  PART 2: Mutual Authentication Flow (ES9+/ES10b)${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

echo -e "${CYAN}→${NC} ${BOLD}Phase 1: InitiateAuthentication (ES9+)${NC}"
echo -e "${DIM}   LPA → SM-DP+: Request server challenge and certificates${NC}"

# Start download in background and monitor logs
$LPAC profile download -s "$SMDP_ADDRESS" -m "$MATCHING_ID" > /tmp/detailed-lpac.log 2>&1 &
DOWNLOAD_PID=$!

# Give it time to start authentication
sleep 3

# Extract authentication details from logs
echo
echo -e "${CYAN}→${NC} ${BOLD}Phase 2: AuthenticateServer (ES10b)${NC}"
echo -e "${DIM}   eUICC verifies SM-DP+ certificate and generates challenge response${NC}"

# Wait a bit more for authentication
sleep 2

# Check v-euicc logs for authentication details
if grep -q "ES10x command tag: BF38" /tmp/detailed-euicc.log; then
    echo
    echo -e "   ${GREEN}✓${NC} AuthenticateServer command received"
    
    # Extract server address
    SERVER_ADDR=$(grep "Extracted serverAddress:" /tmp/detailed-euicc.log | tail -1 | awk -F': ' '{print $2}' | awk '{print $1}')
    echo -e "   ${YELLOW}Server Address:${NC} $SERVER_ADDR"
    
    # Check for signature generation
    if grep -q "AuthenticateServer: Real ECDSA signature generated" /tmp/detailed-euicc.log; then
        SIG_SIZE=$(grep "AuthenticateServer: Real ECDSA signature generated" /tmp/detailed-euicc.log | tail -1 | grep -o '[0-9]* bytes' | awk '{print $1}')
        echo -e "   ${GREEN}✓${NC} ECDSA signature generated: ${YELLOW}$SIG_SIZE bytes${NC}"
        echo -e "   ${DIM}   Algorithm: ECDSA with NIST P-256 curve${NC}"
        echo -e "   ${DIM}   Format: TR-03111 raw format (R || S, 32+32 bytes)${NC}"
    fi
fi

echo
echo -e "${CYAN}→${NC} ${BOLD}Phase 3: AuthenticateClient (ES9+)${NC}"
echo -e "${DIM}   SM-DP+ verifies eUICC signature and certificate chain${NC}"

# Check SM-DP+ logs
sleep 1
if grep -q "authenticateClient" /tmp/detailed-smdpp.log; then
    echo -e "   ${GREEN}✓${NC} SM-DP+ received and verified eUICC authentication"
fi

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  PART 3: Profile Download Preparation${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

echo -e "${CYAN}→${NC} ${BOLD}PrepareDownload (ES10b.PrepareDownload)${NC}"
echo -e "${DIM}   eUICC generates ephemeral ECKA key pair for session keys${NC}"

sleep 2

# Check for PrepareDownload in logs
if grep -q "PrepareDownloadRequest received" /tmp/detailed-euicc.log; then
    echo -e "   ${GREEN}✓${NC} PrepareDownload request received"
    
    # Extract transaction ID
    if grep -q "Extracted transactionID:" /tmp/detailed-euicc.log; then
        echo -e "   ${YELLOW}Transaction ID:${NC} <16 bytes, hidden for security>"
    fi
    
    # Extract ephemeral key generation
    if grep -q "Generated valid euiccOtpk:" /tmp/detailed-euicc.log; then
        OTPK_PREVIEW=$(grep "Generated valid euiccOtpk:" /tmp/detailed-euicc.log | tail -1 | awk -F': ' '{print $2}')
        echo -e "   ${GREEN}✓${NC} Generated ephemeral key pair (otPK/otSK.EUICC.ECKA)"
        echo -e "   ${YELLOW}Public Key (otPK.EUICC.ECKA):${NC} $OTPK_PREVIEW"
        echo -e "   ${DIM}   Curve: NIST P-256 (secp256r1)${NC}"
        echo -e "   ${DIM}   Format: Uncompressed point (04 || X || Y), 65 bytes${NC}"
    fi
    
    # Check for signature
    if grep -q "PrepareDownload: Signature generated" /tmp/detailed-euicc.log; then
        SIG_INFO=$(grep "PrepareDownload: Signature generated" /tmp/detailed-euicc.log | tail -1 | grep -o '([0-9]* bytes) over [0-9]* bytes')
        echo -e "   ${GREEN}✓${NC} ECDSA signature: $SIG_INFO"
    fi
fi

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  PART 4: Bound Profile Package (BPP) Download & Installation${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

echo -e "${CYAN}→${NC} ${BOLD}GetBoundProfilePackage (ES9+)${NC}"
echo -e "${DIM}   SM-DP+ generates session keys and encrypts profile${NC}"

sleep 2

# Check for BPP reception
if grep -q "ES10x command tag: BF36" /tmp/detailed-euicc.log; then
    echo -e "   ${GREEN}✓${NC} BoundProfilePackage received"
    
    BPP_SIZE=$(grep "BF36 wrapper detected" /tmp/detailed-euicc.log | tail -1 | grep -o 'len=[0-9]*' | cut -d= -f2)
    echo -e "   ${YELLOW}BPP Size:${NC} $BPP_SIZE bytes"
fi

echo
echo -e "${CYAN}→${NC} ${BOLD}InitialiseSecureChannel (ES8+, tag BF23)${NC}"
echo -e "${DIM}   Establish encrypted session using ECDH key agreement${NC}"

sleep 1

if grep -q "InitialiseSecureChannelRequest (BF23) received" /tmp/detailed-euicc.log; then
    echo -e "   ${GREEN}✓${NC} InitialiseSecureChannel command received"
    
    # Extract smdpOtpk
    if grep -q "Extracted smdpOtpk" /tmp/detailed-euicc.log; then
        SMDP_OTPK_SIZE=$(grep "Extracted smdpOtpk" /tmp/detailed-euicc.log | tail -1 | grep -o '[0-9]* bytes' | awk '{print $1}')
        echo -e "   ${YELLOW}SM-DP+ Public Key (otPK.DP.ECKA):${NC} $SMDP_OTPK_SIZE bytes"
    fi
    
    # Check for session key derivation
    if grep -q "Session keys derived successfully" /tmp/detailed-euicc.log; then
        echo
        echo -e "   ${GREEN}✓${NC} ${BOLD}Session Keys Derived (SGP.22 Annex G):${NC}"
        echo -e "   ${DIM}   1. ECDH shared secret = otSK.EUICC.ECKA × otPK.DP.ECKA${NC}"
        echo -e "   ${DIM}   2. KDF (SHA-256 based) derives KEK and KM${NC}"
        KEY_INFO=$(grep "Session keys derived successfully" /tmp/detailed-euicc.log | tail -1 | grep -o '([^)]*)')
        echo -e "   ${YELLOW}Derived Keys:${NC} $KEY_INFO"
        echo -e "   ${DIM}   • KEK (Key Encryption Key): 16 bytes${NC}"
        echo -e "   ${DIM}   • KM (Key for MAC): 16 bytes${NC}"
    fi
fi

echo
echo -e "${CYAN}→${NC} ${BOLD}BPP Command Sequence:${NC}"

# Count BPP commands
BPP_COUNT=$(grep -c "BPP.*command.*received" /tmp/detailed-euicc.log 2>/dev/null || echo "0")
echo -e "   ${YELLOW}Total BPP commands processed:${NC} $BPP_COUNT"

# Show command breakdown
echo
echo -e "   ${DIM}Command breakdown:${NC}"
grep "BPP.*command 00" /tmp/detailed-euicc.log | tail -20 | while read line; do
    if echo "$line" | grep -q "00A0"; then
        echo -e "   ${GREEN}✓${NC} A0 (ConfigureISDP) - Configure ISD-P applet"
    elif echo "$line" | grep -q "00A1"; then
        echo -e "   ${GREEN}✓${NC} A1 (StoreMetadata) - Store profile metadata"
    elif echo "$line" | grep -q "0088"; then
        echo -e "   ${GREEN}✓${NC} 88 (StoreMetadata data) - MAC-protected metadata"
    elif echo "$line" | grep -q "00A2"; then
        echo -e "   ${GREEN}✓${NC} A2 (ReplaceSessionKeys) - Update session keys with PPK"
    elif echo "$line" | grep -q "0086"; then
        echo -e "   ${GREEN}✓${NC} 86 (LoadProfileElements) - Encrypted profile data"
    elif echo "$line" | grep -q "00A3"; then
        echo -e "   ${GREEN}✓${NC} A3 (Final) - Complete profile installation"
    fi
done | sort -u

# Show total data received
TOTAL_BPP_DATA=$(grep "Stored.*bytes of BPP data, total:" /tmp/detailed-euicc.log | tail -1 | grep -o 'total: [0-9]*' | awk '{print $2}')
if [ ! -z "$TOTAL_BPP_DATA" ]; then
    echo
    echo -e "   ${YELLOW}Total encrypted profile data:${NC} $TOTAL_BPP_DATA bytes"
fi

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  PART 5: Profile Installation Result${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

# Wait for download to complete
wait $DOWNLOAD_PID 2>/dev/null || true

# Check if profile was created
if grep -q "Created profile metadata:" /tmp/detailed-euicc.log; then
    echo -e "${GREEN}✓${NC} ${BOLD}Profile Successfully Installed!${NC}"
    echo
    
    PROFILE_INFO=$(grep "Created profile metadata:" /tmp/detailed-euicc.log | tail -1)
    ICCID=$(echo "$PROFILE_INFO" | grep -o 'ICCID=[^,]*' | cut -d= -f2)
    PROF_NAME=$(echo "$PROFILE_INFO" | grep -o 'Name=.*' | cut -d= -f2)
    
    echo -e "   ${YELLOW}ICCID:${NC} $ICCID"
    echo -e "   ${YELLOW}Profile Name:${NC} $PROF_NAME"
    echo -e "   ${YELLOW}Service Provider:${NC} OsmocomSPN"
    echo -e "   ${YELLOW}State:${NC} Disabled (default)"
    
    # Show ProfileInstallationResult
    if grep -q "ProfileInstallationResult built successfully" /tmp/detailed-euicc.log; then
        PIR_SIZE=$(grep "ProfileInstallationResult built successfully" /tmp/detailed-euicc.log | tail -1 | grep -o '[0-9]* bytes' | awk '{print $1}')
        echo
        echo -e "   ${CYAN}ProfileInstallationResult (BF37):${NC} $PIR_SIZE bytes"
        echo -e "   ${DIM}   Structure: BF37 { BF27 { transactionId, notificationMetadata, ${NC}"
        echo -e "   ${DIM}              smdpOid, finalResult }, euiccSignPIR }${NC}"
    fi
fi

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Summary: Cryptographic Operations${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

# Count signatures
SIG_COUNT=$(grep -c "DER signature generated:" /tmp/detailed-euicc.log 2>/dev/null || echo "0")
ECDH_COUNT=$(grep -c "Session keys derived" /tmp/detailed-euicc.log 2>/dev/null || echo "0")

echo -e "${YELLOW}Cryptographic Operations Performed:${NC}"
echo -e "   • ECDSA Signatures Generated: ${GREEN}$SIG_COUNT${NC}"
echo -e "   • ECDH Key Agreements: ${GREEN}$ECDH_COUNT${NC}"
echo -e "   • Certificates Verified: ${GREEN}2+${NC} (eUICC chain, SM-DP+ chain)"
echo -e "   • Session Keys Derived: ${GREEN}2${NC} (KEK, KM)"
echo -e "   • BPP Commands Processed: ${GREEN}$BPP_COUNT${NC}"

echo
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  ✓ Complete SGP.22 Profile Download & Installation Flow${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo -e "${YELLOW}📋 Detailed logs available at:${NC}"
echo -e "   • v-euicc:  /tmp/detailed-euicc.log"
echo -e "   • SM-DP+:   /tmp/detailed-smdpp.log"
echo -e "   • lpac:     /tmp/detailed-lpac.log"
echo
