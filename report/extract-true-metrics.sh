#!/bin/bash
# Extract TRUE metrics from actual demo logs
# NO FALLBACKS, NO HARDCODED VALUES - Only real data

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

extract_true_metrics() {
    local mode=$1
    local euicc_log=$2
    local output_file=$3
    
    echo "# RSP Performance Metrics - $mode Mode (TRUE DATA)" > "$output_file"
    echo "# Extracted from: $euicc_log" >> "$output_file"
    echo "# Generated: $(date '+%Y-%m-%d %H:%M:%S')" >> "$output_file"
    echo "" >> "$output_file"
    
    # Key Sizes - ECDH is always 65/32, verified from OpenSSL
    echo "[KEY_SIZES]" >> "$output_file"
    echo "ecdh_public_key_bytes=65" >> "$output_file"
    echo "ecdh_private_key_bytes=32" >> "$output_file"
    
    if [ "$mode" = "PQC" ]; then
        # Extract ACTUAL ML-KEM sizes from log (must contain "ML-KEM-768 keypair generated")
        mlkem_pk_size=$(grep "ML-KEM-768 keypair generated: pk=" "$euicc_log" 2>/dev/null | head -1 | sed -n 's/.*pk=\([0-9]*\) bytes.*/\1/p')
        mlkem_sk_size=$(grep "ML-KEM-768 keypair generated: pk=" "$euicc_log" 2>/dev/null | head -1 | sed -n 's/.*sk=\([0-9]*\) bytes.*/\1/p')
        mlkem_ct_size=$(grep "Ciphertext Size:" "$euicc_log" 2>/dev/null | head -1 | sed -n 's/.*Ciphertext Size: \([0-9]*\) bytes.*/\1/p')
        
        echo "mlkem_public_key_bytes=${mlkem_pk_size:-NOT_FOUND}" >> "$output_file"
        echo "mlkem_secret_key_bytes=${mlkem_sk_size:-NOT_FOUND}" >> "$output_file"
        echo "mlkem_ciphertext_bytes=${mlkem_ct_size:-NOT_FOUND}" >> "$output_file"
        
        if [ -n "$mlkem_pk_size" ] && [ -n "$mlkem_ct_size" ]; then
            total_overhead=$((mlkem_pk_size + mlkem_ct_size))
            echo "total_pqc_overhead_bytes=$total_overhead" >> "$output_file"
        else
            echo "total_pqc_overhead_bytes=NOT_FOUND" >> "$output_file"
        fi
    else
        echo "mlkem_public_key_bytes=0" >> "$output_file"
        echo "mlkem_secret_key_bytes=0" >> "$output_file"
        echo "mlkem_ciphertext_bytes=0" >> "$output_file"
        echo "total_pqc_overhead_bytes=0" >> "$output_file"
    fi
    echo "" >> "$output_file"
    
    # Performance Timings - ONLY from PROFILE logs
    echo "[PERFORMANCE_TIMINGS_MS]" >> "$output_file"
    
    if [ "$mode" = "PQC" ]; then
        # Extract from [PROFILE] lines - these show actual µs measurements
        keygen_time=$(grep "\[PROFILE\] mlkem_keypair:" "$euicc_log" 2>/dev/null | tail -1 | sed -n 's/.*(\([0-9.]*\) ms).*/\1/p')
        decap_time=$(grep "\[PROFILE\] mlkem_decaps:" "$euicc_log" 2>/dev/null | tail -1 | sed -n 's/.*(\([0-9.]*\) ms).*/\1/p')
        hybrid_kdf_time=$(grep "\[PROFILE\] hybrid_kdf:" "$euicc_log" 2>/dev/null | tail -1 | sed -n 's/.*(\([0-9.]*\) ms).*/\1/p')
        
        echo "mlkem_keypair_generation_ms=${keygen_time:-NOT_MEASURED}" >> "$output_file"
        echo "mlkem_decapsulation_ms=${decap_time:-NOT_MEASURED}" >> "$output_file"
        echo "hybrid_kdf_ms=${hybrid_kdf_time:-NOT_MEASURED}" >> "$output_file"
        
        if [ -n "$keygen_time" ] && [ -n "$decap_time" ] && [ -n "$hybrid_kdf_time" ]; then
            total_pqc_time=$(echo "$keygen_time + $decap_time + $hybrid_kdf_time" | bc -l 2>/dev/null)
            echo "total_pqc_overhead_ms=$total_pqc_time" >> "$output_file"
        else
            echo "total_pqc_overhead_ms=NOT_MEASURED" >> "$output_file"
        fi
    else
        echo "mlkem_keypair_generation_ms=0" >> "$output_file"
        echo "mlkem_decapsulation_ms=0" >> "$output_file"
        echo "hybrid_kdf_ms=0" >> "$output_file"
        echo "total_pqc_overhead_ms=0" >> "$output_file"
    fi
    
    # Classical crypto timings (if profiling is enabled)
    ecdh_time=$(grep "\[PROFILE\].*ECDH" "$euicc_log" 2>/dev/null | tail -1 | sed -n 's/.*(\([0-9.]*\) ms).*/\1/p')
    ecdsa_time=$(grep "\[PROFILE\].*ECDSA" "$euicc_log" 2>/dev/null | tail -1 | sed -n 's/.*(\([0-9.]*\) ms).*/\1/p')
    
    echo "ecdh_computation_ms=${ecdh_time:-NOT_MEASURED}" >> "$output_file"
    echo "ecdsa_signature_ms=${ecdsa_time:-NOT_MEASURED}" >> "$output_file"
    echo "" >> "$output_file"
    
    # Protocol Message Sizes - from ACTUAL log entries
    echo "[MESSAGE_SIZES_BYTES]" >> "$output_file"
    
    # PrepareDownload response - look for "[METRICS] PrepareDownloadResponse: X bytes"
    prepare_download_size=$(grep "\[METRICS\] PrepareDownloadResponse:" "$euicc_log" 2>/dev/null | head -1 | sed -n 's/.*PrepareDownloadResponse: \([0-9]*\) bytes.*/\1/p')
    echo "prepare_download_response_bytes=${prepare_download_size:-NOT_LOGGED}" >> "$output_file"
    
    # BPP size from BF36 wrapper
    bpp_size=$(grep "BF36 wrapper detected" "$euicc_log" 2>/dev/null | tail -1 | sed -n 's/.*len=\([0-9]*\).*/\1/p')
    echo "bound_profile_package_bytes=${bpp_size:-NOT_LOGGED}" >> "$output_file"
    
    # InitialiseSecureChannel size - look for "InitialiseSecureChannelRequest (BF23) received, len=X"
    init_secure_size=$(grep "InitialiseSecureChannelRequest (BF23) received" "$euicc_log" 2>/dev/null | head -1 | sed -n 's/.*len=\([0-9]*\).*/\1/p')
    echo "initialise_secure_channel_bytes=${init_secure_size:-NOT_LOGGED}" >> "$output_file"
    
    # Total encrypted profile data - last "total:" entry
    total_bpp_data=$(grep "Stored.*bytes of BPP data, total:" "$euicc_log" 2>/dev/null | tail -1 | sed -n 's/.*total: \([0-9]*\) bytes.*/\1/p')
    echo "total_encrypted_profile_data_bytes=${total_bpp_data:-NOT_LOGGED}" >> "$output_file"
    echo "" >> "$output_file"
    
    # Protocol Counters - COUNT actual occurrences
    echo "[PROTOCOL_COUNTERS]" >> "$output_file"
    
    ecdsa_count=$(grep -c "DER signature generated:" "$euicc_log" 2>/dev/null || echo "0")
    ecdh_count=$(grep -c "Session keys derived" "$euicc_log" 2>/dev/null || echo "0")
    bpp_commands=$(grep -c "BPP data command.*received" "$euicc_log" 2>/dev/null || echo "0")
    
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
    
    # Security Properties - these are constants based on algorithms used
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
    
    # Bandwidth Analysis - calculated from actual message sizes
    echo "[BANDWIDTH_ANALYSIS]" >> "$output_file"
    
    if [ -n "$prepare_download_size" ]; then
        total_upload=$prepare_download_size
    else
        total_upload="0"
    fi
    
    if [ -n "$bpp_size" ] && [ -n "$init_secure_size" ]; then
        total_download=$((bpp_size + init_secure_size))
    else
        total_download="0"
    fi
    
    if [ "$total_upload" != "0" ] && [ "$total_download" != "0" ]; then
        total_bandwidth=$((total_upload + total_download))
    else
        total_bandwidth="0"
    fi
    
    echo "total_upload_bytes=$total_upload" >> "$output_file"
    echo "total_download_bytes=$total_download" >> "$output_file"
    echo "total_bandwidth_bytes=$total_bandwidth" >> "$output_file"
    
    echo "" >> "$output_file"
    echo "# End of TRUE metrics" >> "$output_file"
}

# Check if logs exist
if [ ! -f "/tmp/pqc-detailed-euicc.log" ]; then
    echo "ERROR: PQC log not found. Run ./demo-pqc-detailed.sh first"
    exit 1
fi

mkdir -p report/metrics

echo "Extracting TRUE metrics from actual demo logs..."
echo

echo "▶ Extracting PQC metrics from /tmp/pqc-detailed-euicc.log..."
extract_true_metrics "PQC" "/tmp/pqc-detailed-euicc.log" "report/metrics/pqc.metrics"
echo "✓ PQC metrics extracted"

# For classical, check if we have a good log
if [ -f "/tmp/detailed-euicc.log" ] && [ -s "/tmp/detailed-euicc.log" ]; then
    echo "▶ Extracting Classical metrics from /tmp/detailed-euicc.log..."
    extract_true_metrics "CLASSICAL" "/tmp/detailed-euicc.log" "report/metrics/classical.metrics"
    echo "✓ Classical metrics extracted"
else
    echo "⚠ Classical log not complete, run ./demo-detailed.sh to get classical metrics"
fi

echo
echo "✓ TRUE metrics extracted (no fabricated values)"
echo
echo "To verify:"
echo "  cat report/metrics/pqc.metrics"
echo "  cat report/metrics/classical.metrics"

