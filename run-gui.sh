#!/bin/bash
# Virtual RSP Control Center - Quick Launch Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Virtual RSP Control Center - Launcher                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo

# Check if v-euicc is built
if [ ! -f "./build/v-euicc/v-euicc-daemon" ]; then
    echo -e "${RED}✗${NC} v-euicc not built"
    echo -e "${BLUE}▶${NC} Building v-euicc..."
    
    mkdir -p build
    cd build
    cmake .. > /dev/null 2>&1
    make > /dev/null 2>&1
    cd ..
    
    if [ -f "./build/v-euicc/v-euicc-daemon" ]; then
        echo -e "${GREEN}✓${NC} v-euicc built successfully"
    else
        echo -e "${RED}✗${NC} Failed to build v-euicc"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} v-euicc binary found"
fi

# Check if lpac is built
if [ ! -f "./build/lpac/src/lpac" ]; then
    echo -e "${RED}✗${NC} lpac not found at ./build/lpac/src/lpac"
    echo -e "  Please build lpac separately"
else
    echo -e "${GREEN}✓${NC} lpac binary found"
fi

# Check Python dependencies
if ! python3 -c "import PySide6" 2>/dev/null; then
    echo -e "${RED}✗${NC} PySide6 not installed"
    echo -e "${BLUE}▶${NC} Installing dependencies..."
    pip3 install -r requirements-gui.txt
else
    echo -e "${GREEN}✓${NC} PySide6 installed"
fi

# Create data directory
mkdir -p data

# Check /etc/hosts
if ! grep -q "testsmdpplus1.example.com" /etc/hosts; then
    echo -e "${BLUE}⚠${NC} SM-DP+ hostname not in /etc/hosts"
    echo -e "  You may need to add: 127.0.0.1 testsmdpplus1.example.com"
    echo -e "  Run: sudo ./add-hosts-entry.sh"
fi

echo
echo -e "${GREEN}✓${NC} Pre-flight checks complete"
echo -e "${BLUE}▶${NC} Launching GUI..."
echo

# Launch GUI
exec python3 gui/main.py

