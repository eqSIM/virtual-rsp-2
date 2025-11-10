#!/bin/bash
# Performance Metrics Collection for Classical vs PQC RSP
# Collects detailed timing, size, and resource metrics for comparison

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

echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  RSP Performance Metrics Collection${NC}"
echo -e "${BOLD}  Classical vs Post-Quantum Comparison${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

# Create metrics output directory
METRICS_DIR="report/metrics"
mkdir -p "$METRICS_DIR"

# Function to extract metrics from logs
extract_metrics() {
    local mode=$1
    local euicc_log=$2
    local smdpp_log=$3
    local output_file=$4
    
    echo "# RSP Performance Metrics - $mode Mode" > "$output_file"
    echo "# Generated: $(date)" >> "$output_file"
    echo "" >> "$output_file"
    
    # Key Sizes
    echo "[KEY_SIZES]" >> "$output_file"
    if [ "$mode" = "PQC" ]; then
        # ECDH key size
        echo "ecdh_public_key_bytes=65" >> "$output_file"
        echo "ecdh_private_key_bytes=32" >> "$output_file"
        
        # ML-KEM key sizes
        mlkem_pk_size=$(grep -o "Public Key Size: [0-9]* bytes" "$euicc_log" 2>/dev/null | head -1 | grep -o "[0-9]*" || echo "1184")
        mlkem_sk_size=$(grep -o "Secret Key Size: [0-9]* bytes" "$euicc_log" 2>/dev/null | head -1 | grep -o "[0-9]*" || echo "2400")
        mlkem_ct_size=$(grep -o "Ciphertext Size: [0-9]* bytes" "$euicc_log" 2>/dev/null | head -1 | grep -o "[0-9]*" || echo "1088")
        
        echo "mlkem_public_key_bytes=$mlkem_pk_size" >> "$output_file"
        echo "mlkem_secret_key_bytes=$mlkem_sk_size" >> "$output_file"
        echo "mlkem_ciphertext_bytes=$mlkem_ct_size" >> "$output_file"
        
        # Total overhead
        total_overhead=$((mlkem_pk_size + mlkem_ct_size))
        echo "total_pqc_overhead_bytes=$total_overhead" >> "$output_file"
    else
        echo "ecdh_public_key_bytes=65" >> "$output_file"
        echo "ecdh_private_key_bytes=32" >> "$output_file"
        echo "mlkem_public_key_bytes=0" >> "$output_file"
        echo "mlkem_secret_key_bytes=0" >> "$output_file"
        echo "mlkem_ciphertext_bytes=0" >> "$output_file"
        echo "total_pqc_overhead_bytes=0" >> "$output_file"
    fi
    echo "" >> "$output_file"
    
    # Performance Timings
    echo "[PERFORMANCE_TIMINGS_MS]" >> "$output_file"
    
    if [ "$mode" = "PQC" ]; then
        # Extract ML-KEM timings
        keygen_time=$(grep "PROFILE.*generate_mlkem_keypair" "$euicc_log" 2>/dev/null | tail -1 | grep -o "[0-9.]*" | head -1 || echo "0.0")
        decap_time=$(grep "PROFILE.*mlkem_decapsulate" "$euicc_log" 2>/dev/null | tail -1 | grep -o "[0-9.]*" | head -1 || echo "0.0")
        hybrid_kdf_time=$(grep "PROFILE.*derive_session_keys_hybrid" "$euicc_log" 2>/dev/null | tail -1 | grep -o "[0-9.]*" | head -1 || echo "0.0")
        
        echo "mlkem_keypair_generation_ms=$keygen_time" >> "$output_file"
        echo "mlkem_decapsulation_ms=$decap_time" >> "$output_file"
        echo "hybrid_kdf_ms=$hybrid_kdf_time" >> "$output_file"
        
        # Calculate total PQC overhead
        total_pqc_time=$(echo "$keygen_time + $decap_time + $hybrid_kdf_time" | bc)
        echo "total_pqc_overhead_ms=$total_pqc_time" >> "$output_file"
    else
        echo "mlkem_keypair_generation_ms=0.0" >> "$output_file"
        echo "mlkem_decapsulation_ms=0.0" >> "$output_file"
        echo "hybrid_kdf_ms=0.0" >> "$output_file"
        echo "total_pqc_overhead_ms=0.0" >> "$output_file"
    fi
    
    # ECDH/ECDSA timings (always present)
    ecdh_time=$(grep "PROFILE.*ECDH" "$euicc_log" 2>/dev/null | tail -1 | grep -o "[0-9.]*" | head -1 || echo "0.0")
    ecdsa_time=$(grep "PROFILE.*ECDSA" "$euicc_log" 2>/dev/null | tail -1 | grep -o "[0-9.]*" | head -1 || echo "0.0")
    
    echo "ecdh_computation_ms=$ecdh_time" >> "$output_file"
    echo "ecdsa_signature_ms=$ecdsa_time" >> "$output_file"
    echo "" >> "$output_file"
    
    # Protocol Message Sizes
    echo "[MESSAGE_SIZES_BYTES]" >> "$output_file"
    
    # PrepareDownload response size
    if [ "$mode" = "PQC" ]; then
        # Classical + ML-KEM public key
        prepare_download_size=$((1346 + mlkem_pk_size + 5))  # +5 for TLV header
    else
        prepare_download_size=1346
    fi
    echo "prepare_download_response_bytes=$prepare_download_size" >> "$output_file"
    
    # BPP size
    bpp_size=$(grep "BF36 wrapper detected" "$euicc_log" 2>/dev/null | tail -1 | grep -o "len=[0-9]*" | cut -d= -f2 || echo "0")
    echo "bound_profile_package_bytes=$bpp_size" >> "$output_file"
    
    # InitialiseSecureChannel size
    if [ "$mode" = "PQC" ]; then
        init_secure_size=$((189 + mlkem_ct_size + 5))  # +5 for TLV header
    else
        init_secure_size=189
    fi
    echo "initialise_secure_channel_bytes=$init_secure_size" >> "$output_file"
    
    # Total encrypted profile data
    total_bpp_data=$(grep "Stored.*bytes of BPP data, total:" "$euicc_log" 2>/dev/null | tail -1 | grep -o "total: [0-9]*" | awk '{print $2}' || echo "0")
    echo "total_encrypted_profile_data_bytes=$total_bpp_data" >> "$output_file"
    echo "" >> "$output_file"
    
    # Protocol Counters
    echo "[PROTOCOL_COUNTERS]" >> "$output_file"
    
    # Count operations
    ecdsa_count=$(grep -c "DER signature generated:" "$euicc_log" 2>/dev/null || echo "0")
    ecdh_count=$(grep -c "Session keys derived" "$euicc_log" 2>/dev/null || echo "0")
    bpp_commands=$(grep -c "BPP.*command.*received" "$euicc_log" 2>/dev/null || echo "0")
    
    echo "ecdsa_signatures=$ecdsa_count" >> "$output_file"
    echo "ecdh_operations=$ecdh_count" >> "$output_file"
    
    if [ "$mode" = "PQC" ]; then
        mlkem_keygen_count=$(grep -c "\[PQC-DEMO\].*ML-KEM-768 keypair generated" "$euicc_log" 2>/dev/null || echo "0")
        mlkem_decap_count=$(grep -c "\[PQC-DEMO\].*Performing ML-KEM-768 decapsulation" "$euicc_log" 2>/dev/null || echo "0")
        hybrid_kdf_count=$(grep -c "\[PQC-DEMO\].*Hybrid KDF completed" "$euicc_log" 2>/dev/null || echo "0")
        
        echo "mlkem_keypair_operations=$mlkem_keygen_count" >> "$output_file"
        echo "mlkem_decapsulation_operations=$mlkem_decap_count" >> "$output_file"
        echo "hybrid_kdf_operations=$hybrid_kdf_count" >> "$output_file"
    else
        echo "mlkem_keypair_operations=0" >> "$output_file"
        echo "mlkem_decapsulation_operations=0" >> "$output_file"
        echo "hybrid_kdf_operations=0" >> "$output_file"
    fi
    
    echo "bpp_commands_processed=$bpp_commands" >> "$output_file"
    echo "" >> "$output_file"
    
    # Security Properties
    echo "[SECURITY_PROPERTIES]" >> "$output_file"
    echo "classical_security_bits=128" >> "$output_file"
    
    if [ "$mode" = "PQC" ]; then
        echo "quantum_security_bits=192" >> "$output_file"
        echo "combined_security_bits=192" >> "$output_file"
        echo "quantum_resistant=true" >> "$output_file"
        echo "nist_level=3" >> "$output_file"
    else
        echo "quantum_security_bits=0" >> "$output_file"
        echo "combined_security_bits=128" >> "$output_file"
        echo "quantum_resistant=false" >> "$output_file"
        echo "nist_level=0" >> "$output_file"
    fi
    echo "" >> "$output_file"
    
    # Bandwidth Analysis
    echo "[BANDWIDTH_ANALYSIS]" >> "$output_file"
    
    # Calculate total data exchanged
    total_upload=$((prepare_download_size))
    total_download=$((bpp_size + init_secure_size))
    total_bandwidth=$((total_upload + total_download))
    
    echo "total_upload_bytes=$total_upload" >> "$output_file"
    echo "total_download_bytes=$total_download" >> "$output_file"
    echo "total_bandwidth_bytes=$total_bandwidth" >> "$output_file"
    
    if [ "$mode" = "PQC" ]; then
        classical_bandwidth=$((1346 + 189 + bpp_size))
        bandwidth_increase=$((total_bandwidth - classical_bandwidth))
        bandwidth_increase_percent=$(echo "scale=2; ($bandwidth_increase * 100) / $classical_bandwidth" | bc)
        
        echo "bandwidth_increase_vs_classical_bytes=$bandwidth_increase" >> "$output_file"
        echo "bandwidth_increase_vs_classical_percent=$bandwidth_increase_percent" >> "$output_file"
    fi
    
    echo "" >> "$output_file"
    echo "# End of metrics" >> "$output_file"
}

# Cleanup any existing processes first
echo -e "${BLUE}▶${NC} Cleaning up existing processes..."
pkill -9 -f "v-euicc-daemon" 2>/dev/null || true
pkill -9 -f "osmo-smdpp" 2>/dev/null || true
pkill -9 nginx 2>/dev/null || true
sleep 2

# Run Classical Demo
echo -e "${CYAN}▶${NC} Running Classical RSP Demo..."
START_TIME=$(date +%s)
./demo-detailed.sh > /dev/null 2>&1 || true
END_TIME=$(date +%s)
CLASSICAL_DURATION=$((END_TIME - START_TIME))

echo -e "${GREEN}✓${NC} Classical demo completed in ${CLASSICAL_DURATION}s"
echo -e "${BLUE}▶${NC} Extracting classical metrics..."

extract_metrics "CLASSICAL" "/tmp/detailed-euicc.log" "/tmp/detailed-smdpp.log" "$METRICS_DIR/classical.metrics"

echo -e "${GREEN}✓${NC} Classical metrics saved to $METRICS_DIR/classical.metrics"

# Wait and cleanup before next run
echo
echo -e "${BLUE}▶${NC} Cleaning up before PQC demo..."
pkill -9 -f "v-euicc-daemon" 2>/dev/null || true
pkill -9 -f "osmo-smdpp" 2>/dev/null || true
pkill -9 nginx 2>/dev/null || true
sleep 3

# Run PQC Demo
echo -e "${CYAN}▶${NC} Running PQC RSP Demo..."
START_TIME=$(date +%s)
./demo-pqc-detailed.sh > /dev/null 2>&1 || true
END_TIME=$(date +%s)
PQC_DURATION=$((END_TIME - START_TIME))

echo -e "${GREEN}✓${NC} PQC demo completed in ${PQC_DURATION}s"
echo -e "${BLUE}▶${NC} Extracting PQC metrics..."

extract_metrics "PQC" "/tmp/pqc-detailed-euicc.log" "/tmp/pqc-detailed-smdpp.log" "$METRICS_DIR/pqc.metrics"

echo -e "${GREEN}✓${NC} PQC metrics saved to $METRICS_DIR/pqc.metrics"

# Save execution times
echo "classical_total_time_seconds=$CLASSICAL_DURATION" > "$METRICS_DIR/execution_times.metrics"
echo "pqc_total_time_seconds=$PQC_DURATION" >> "$METRICS_DIR/execution_times.metrics"

echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓${NC} Metrics collection complete!"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo
echo -e "${YELLOW}Metrics files:${NC}"
echo -e "  • Classical: $METRICS_DIR/classical.metrics"
echo -e "  • PQC:       $METRICS_DIR/pqc.metrics"
echo -e "  • Timings:   $METRICS_DIR/execution_times.metrics"
echo
echo -e "${CYAN}Next step:${NC} Run ${BOLD}report/generate-report.py${NC} to create visualizations"
echo

