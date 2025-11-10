#!/bin/bash
# Demo: Create sample metrics and generate visualizations
# This demonstrates the metrics system without running full demos

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  RSP Metrics System Demo${NC}"
echo -e "${BOLD}  Creating sample metrics and visualizations${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

# Create metrics directory
METRICS_DIR="report/metrics"
mkdir -p "$METRICS_DIR"

# Create Classical metrics
echo -e "${CYAN}▶${NC} Creating classical RSP metrics..."

cat > "$METRICS_DIR/classical.metrics" << 'EOF'
# RSP Performance Metrics - CLASSICAL Mode
# Generated: Demo

[KEY_SIZES]
ecdh_public_key_bytes=65
ecdh_private_key_bytes=32
mlkem_public_key_bytes=0
mlkem_secret_key_bytes=0
mlkem_ciphertext_bytes=0
total_pqc_overhead_bytes=0

[PERFORMANCE_TIMINGS_MS]
mlkem_keypair_generation_ms=0.0
mlkem_decapsulation_ms=0.0
hybrid_kdf_ms=0.0
total_pqc_overhead_ms=0.0
ecdh_computation_ms=0.085
ecdsa_signature_ms=0.120

[MESSAGE_SIZES_BYTES]
prepare_download_response_bytes=1346
bound_profile_package_bytes=189
initialise_secure_channel_bytes=189
total_encrypted_profile_data_bytes=1689

[PROTOCOL_COUNTERS]
ecdsa_signatures=3
ecdh_operations=1
mlkem_keypair_operations=0
mlkem_decapsulation_operations=0
hybrid_kdf_operations=0
bpp_commands_processed=18

[SECURITY_PROPERTIES]
classical_security_bits=128
quantum_security_bits=0
combined_security_bits=128
quantum_resistant=false
nist_level=0

[BANDWIDTH_ANALYSIS]
total_upload_bytes=1346
total_download_bytes=378
total_bandwidth_bytes=1724

# End of metrics
EOF

echo -e "${GREEN}✓${NC} Classical metrics created"

# Create PQC metrics
echo -e "${CYAN}▶${NC} Creating PQC RSP metrics..."

cat > "$METRICS_DIR/pqc.metrics" << 'EOF'
# RSP Performance Metrics - PQC Mode
# Generated: Demo

[KEY_SIZES]
ecdh_public_key_bytes=65
ecdh_private_key_bytes=32
mlkem_public_key_bytes=1184
mlkem_secret_key_bytes=2400
mlkem_ciphertext_bytes=1088
total_pqc_overhead_bytes=2272

[PERFORMANCE_TIMINGS_MS]
mlkem_keypair_generation_ms=0.089
mlkem_decapsulation_ms=0.078
hybrid_kdf_ms=0.012
total_pqc_overhead_ms=0.179
ecdh_computation_ms=0.085
ecdsa_signature_ms=0.120

[MESSAGE_SIZES_BYTES]
prepare_download_response_bytes=2535
bound_profile_package_bytes=1277
initialise_secure_channel_bytes=1277
total_encrypted_profile_data_bytes=1689

[PROTOCOL_COUNTERS]
ecdsa_signatures=3
ecdh_operations=1
mlkem_keypair_operations=1
mlkem_decapsulation_operations=1
hybrid_kdf_operations=1
bpp_commands_processed=18

[SECURITY_PROPERTIES]
classical_security_bits=128
quantum_security_bits=192
combined_security_bits=192
quantum_resistant=true
nist_level=3

[BANDWIDTH_ANALYSIS]
total_upload_bytes=2535
total_download_bytes=2554
total_bandwidth_bytes=5089
bandwidth_increase_vs_classical_bytes=3365
bandwidth_increase_vs_classical_percent=195.17

# End of metrics
EOF

echo -e "${GREEN}✓${NC} PQC metrics created"

# Create execution times
cat > "$METRICS_DIR/execution_times.metrics" << 'EOF'
classical_total_time_seconds=28
pqc_total_time_seconds=29
EOF

echo -e "${GREEN}✓${NC} Execution times created"
echo

# Generate visualizations
echo -e "${CYAN}▶${NC} Generating CSV, JSON, and PNG outputs..."
./report/generate-visualizations.py

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}✓ Demo complete!${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo
echo -e "${YELLOW}View outputs in:${NC} report/output/"
echo
echo -e "${CYAN}Files generated:${NC}"
ls -lh report/output/ 2>/dev/null | tail -n +2 | awk '{print "  • " $9 " (" $5 ")"}'
echo

