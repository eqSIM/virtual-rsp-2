#!/bin/bash
# Complete Performance Analysis: Collect Real Metrics and Generate Visualizations
# One-command solution for Classical vs PQC comparison

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${BOLD}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     RSP Performance Analysis: Classical vs PQC-Enabled       ║${NC}"
echo -e "${BOLD}║     Complete Automated Metrics Collection & Visualization    ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo

# Step 1: Collect real metrics from live demos
echo -e "${BOLD}═══ Step 1/2: Collecting Real Metrics ═══${NC}"
echo
./report/collect-real-metrics.sh

echo
echo -e "${BOLD}═══ Step 2/2: Generating Visualizations ═══${NC}"
echo
./report/generate-visualizations.py

echo
echo -e "${BOLD}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                  Analysis Complete! ✓                        ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo
echo -e "${GREEN}${BOLD}All outputs generated:${NC}"
echo
echo -e "${YELLOW}📊 Data Files:${NC}"
echo -e "   • report/output/summary.csv              ${DIM}(Key metrics table)${NC}"
echo -e "   • report/output/detailed_metrics.csv     ${DIM}(Complete data)${NC}"
echo -e "   • report/output/metrics_comparison.json  ${DIM}(Structured data)${NC}"
echo
echo -e "${YELLOW}📈 Visualizations:${NC}"
echo -e "   • report/output/chart_key_sizes.png      ${DIM}(Key size comparison)${NC}"
echo -e "   • report/output/chart_performance.png    ${DIM}(PQC overhead)${NC}"
echo -e "   • report/output/chart_message_sizes.png  ${DIM}(Protocol messages)${NC}"
echo -e "   • report/output/chart_bandwidth.png      ${DIM}(Bandwidth distribution)${NC}"
echo -e "   • report/output/chart_security.png       ${DIM}(Security levels)${NC}"
echo -e "   • report/output/chart_operations.png     ${DIM}(Crypto operations)${NC}"
echo
echo -e "${CYAN}💡 View images with:${NC} open report/output/chart_*.png"
echo -e "${CYAN}💡 View CSV with:${NC} cat report/output/summary.csv"
echo -e "${CYAN}💡 View JSON with:${NC} cat report/output/metrics_comparison.json | jq ."
echo

