#!/bin/bash
# Quick test: Generate visualizations from existing demo logs
# This doesn't re-run the demos, just extracts metrics from current logs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo "Testing visualization system with existing logs..."
echo

# Check if logs exist
if [ ! -f "/tmp/detailed-euicc.log" ]; then
    echo -e "${RED}✗${NC} Classical log not found. Run ./demo-detailed.sh first"
    exit 1
fi

if [ ! -f "/tmp/pqc-detailed-euicc.log" ]; then
    echo -e "${RED}✗${NC} PQC log not found. Run ./demo-pqc-detailed.sh first"
    exit 1
fi

# Create metrics directory
METRICS_DIR="report/metrics"
mkdir -p "$METRICS_DIR"

echo -e "${BLUE}▶${NC} Extracting metrics from existing logs..."

# Source the extract_metrics function from collect-metrics.sh
source report/collect-metrics.sh

# Extract metrics
extract_metrics "CLASSICAL" "/tmp/detailed-euicc.log" "/tmp/detailed-smdpp.log" "$METRICS_DIR/classical.metrics"
echo -e "${GREEN}✓${NC} Classical metrics extracted"

extract_metrics "PQC" "/tmp/pqc-detailed-euicc.log" "/tmp/pqc-detailed-smdpp.log" "$METRICS_DIR/pqc.metrics"
echo -e "${GREEN}✓${NC} PQC metrics extracted"

# Create dummy execution times
echo "classical_total_time_seconds=30" > "$METRICS_DIR/execution_times.metrics"
echo "pqc_total_time_seconds=31" >> "$METRICS_DIR/execution_times.metrics"

echo
echo -e "${BLUE}▶${NC} Generating visualizations..."
./report/generate-visualizations.py

echo
echo -e "${GREEN}✓${NC} Test complete!"

