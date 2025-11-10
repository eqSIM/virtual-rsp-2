#!/usr/bin/env python3
"""
RSP Performance Visualization Generator
Generates CSV, JSON, and PNG charts comparing Classical vs PQC RSP
"""

import json
import csv
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not available, skipping chart generation")
    print("Install with: pip3 install matplotlib")

SCRIPT_DIR = Path(__file__).parent
METRICS_DIR = SCRIPT_DIR / "metrics"
OUTPUT_DIR = SCRIPT_DIR / "output"

def parse_metrics_file(filepath):
    """Parse a metrics file into a dictionary"""
    metrics = {}
    current_section = None
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                metrics[current_section] = {}
            elif '=' in line and current_section:
                key, value = line.split('=', 1)
                # Handle empty values
                if not value or value.strip() == '':
                    value = 0
                # Try to convert to appropriate type
                try:
                    if '.' in str(value):
                        value = float(value)
                    elif str(value).lower() in ('true', 'false'):
                        value = str(value).lower() == 'true'
                    else:
                        value = int(value)
                except (ValueError, AttributeError):
                    value = 0  # Default to 0 for numeric fields
                metrics[current_section][key] = value
    
    return metrics

def export_to_json(classical_metrics, pqc_metrics, exec_times):
    """Export metrics to JSON format"""
    output = {
        "metadata": {
            "generated": datetime.now().isoformat(),
            "version": "1.0",
            "description": "RSP Performance Comparison: Classical vs Post-Quantum"
        },
        "classical": classical_metrics,
        "pqc": pqc_metrics,
        "execution_times": exec_times,
        "comparison": {}
    }
    
    # Add comparison calculations
    if "KEY_SIZES" in classical_metrics and "KEY_SIZES" in pqc_metrics:
        pqc_overhead = pqc_metrics["KEY_SIZES"].get("total_pqc_overhead_bytes", 0)
        output["comparison"]["additional_key_material_bytes"] = pqc_overhead
    
    if "PERFORMANCE_TIMINGS_MS" in pqc_metrics:
        total_pqc_time = pqc_metrics["PERFORMANCE_TIMINGS_MS"].get("total_pqc_overhead_ms", 0)
        output["comparison"]["additional_computation_time_ms"] = total_pqc_time
    
    if "BANDWIDTH_ANALYSIS" in classical_metrics and "BANDWIDTH_ANALYSIS" in pqc_metrics:
        classical_bw = classical_metrics["BANDWIDTH_ANALYSIS"].get("total_bandwidth_bytes", 0)
        pqc_bw = pqc_metrics["BANDWIDTH_ANALYSIS"].get("total_bandwidth_bytes", 0)
        increase = pqc_bw - classical_bw
        increase_pct = (increase / classical_bw * 100) if classical_bw > 0 else 0
        output["comparison"]["bandwidth_increase_bytes"] = increase
        output["comparison"]["bandwidth_increase_percent"] = round(increase_pct, 2)
    
    output_file = OUTPUT_DIR / "metrics_comparison.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✓ JSON exported: {output_file}")
    return output

def export_to_csv(classical_metrics, pqc_metrics, exec_times):
    """Export metrics to CSV format"""
    
    # Summary CSV
    summary_file = OUTPUT_DIR / "summary.csv"
    with open(summary_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Classical", "PQC", "Difference", "Unit"])
        
        # Key sizes
        if "KEY_SIZES" in classical_metrics and "KEY_SIZES" in pqc_metrics:
            writer.writerow(["ECDH Public Key", 65, 65, 0, "bytes"])
            mlkem_pk = pqc_metrics["KEY_SIZES"].get("mlkem_public_key_bytes", 0)
            writer.writerow(["ML-KEM Public Key", 0, mlkem_pk, mlkem_pk, "bytes"])
            mlkem_ct = pqc_metrics["KEY_SIZES"].get("mlkem_ciphertext_bytes", 0)
            writer.writerow(["ML-KEM Ciphertext", 0, mlkem_ct, mlkem_ct, "bytes"])
            total_overhead = pqc_metrics["KEY_SIZES"].get("total_pqc_overhead_bytes", 0)
            writer.writerow(["Total PQC Overhead", 0, total_overhead, total_overhead, "bytes"])
        
        writer.writerow([])  # Empty row
        
        # Performance timings
        if "PERFORMANCE_TIMINGS_MS" in pqc_metrics:
            keygen = pqc_metrics["PERFORMANCE_TIMINGS_MS"].get("mlkem_keypair_generation_ms", 0)
            writer.writerow(["ML-KEM Keypair Gen", 0, keygen, keygen, "ms"])
            decap = pqc_metrics["PERFORMANCE_TIMINGS_MS"].get("mlkem_decapsulation_ms", 0)
            writer.writerow(["ML-KEM Decapsulation", 0, decap, decap, "ms"])
            hybrid_kdf = pqc_metrics["PERFORMANCE_TIMINGS_MS"].get("hybrid_kdf_ms", 0)
            writer.writerow(["Hybrid KDF", 0, hybrid_kdf, hybrid_kdf, "ms"])
            total_pqc = pqc_metrics["PERFORMANCE_TIMINGS_MS"].get("total_pqc_overhead_ms", 0)
            writer.writerow(["Total PQC Overhead", 0, total_pqc, total_pqc, "ms"])
        
        writer.writerow([])
        
        # Bandwidth
        if "BANDWIDTH_ANALYSIS" in classical_metrics and "BANDWIDTH_ANALYSIS" in pqc_metrics:
            classical_bw = classical_metrics["BANDWIDTH_ANALYSIS"].get("total_bandwidth_bytes", 0)
            pqc_bw = pqc_metrics["BANDWIDTH_ANALYSIS"].get("total_bandwidth_bytes", 0)
            diff = pqc_bw - classical_bw
            writer.writerow(["Total Bandwidth", classical_bw, pqc_bw, diff, "bytes"])
        
        writer.writerow([])
        
        # Security
        writer.writerow(["Classical Security", 128, 128, 0, "bits"])
        writer.writerow(["Quantum Security", 0, 192, 192, "bits"])
        writer.writerow(["Quantum Resistant", "No", "Yes", "-", "-"])
    
    print(f"✓ CSV exported: {summary_file}")
    
    # Detailed CSV with all metrics
    detailed_file = OUTPUT_DIR / "detailed_metrics.csv"
    with open(detailed_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Section", "Metric", "Classical", "PQC"])
        
        all_sections = set(classical_metrics.keys()) | set(pqc_metrics.keys())
        for section in sorted(all_sections):
            classical_section = classical_metrics.get(section, {})
            pqc_section = pqc_metrics.get(section, {})
            
            all_keys = set(classical_section.keys()) | set(pqc_section.keys())
            for key in sorted(all_keys):
                classical_val = classical_section.get(key, "N/A")
                pqc_val = pqc_section.get(key, "N/A")
                writer.writerow([section, key, classical_val, pqc_val])
    
    print(f"✓ CSV exported: {detailed_file}")

def generate_charts(classical_metrics, pqc_metrics, exec_times):
    """Generate visualization charts as PNG files"""
    if not HAS_MATPLOTLIB:
        print("⚠ Skipping chart generation (matplotlib not available)")
        return
    
    # Set style
    plt.style.use('seaborn-v0_8-darkgrid')
    colors = {'classical': '#3498db', 'pqc': '#e74c3c', 'overhead': '#f39c12'}
    
    # Chart 1: Key Sizes Comparison
    fig, ax = plt.subplots(figsize=(12, 6))
    
    categories = ['ECDH Keys', 'ML-KEM Public Key', 'ML-KEM Ciphertext', 'Total Overhead']
    classical_sizes = [65, 0, 0, 0]
    pqc_sizes = [
        65,
        pqc_metrics["KEY_SIZES"].get("mlkem_public_key_bytes", 0),
        pqc_metrics["KEY_SIZES"].get("mlkem_ciphertext_bytes", 0),
        pqc_metrics["KEY_SIZES"].get("total_pqc_overhead_bytes", 0)
    ]
    
    x = np.arange(len(categories))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, classical_sizes, width, label='Classical', color=colors['classical'])
    bars2 = ax.bar(x + width/2, pqc_sizes, width, label='PQC', color=colors['pqc'])
    
    ax.set_xlabel('Key Type', fontsize=12, fontweight='bold')
    ax.set_ylabel('Size (bytes)', fontsize=12, fontweight='bold')
    ax.set_title('Key Sizes: Classical vs PQC RSP', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=15, ha='right')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}',
                       ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "chart_key_sizes.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ Chart generated: {output_file}")
    
    # Chart 2: Performance Overhead
    fig, ax = plt.subplots(figsize=(10, 6))
    
    operations = ['ML-KEM\nKeypair', 'ML-KEM\nDecaps', 'Hybrid\nKDF', 'Total PQC\nOverhead']
    timings = [
        float(pqc_metrics["PERFORMANCE_TIMINGS_MS"].get("mlkem_keypair_generation_ms", 0)),
        float(pqc_metrics["PERFORMANCE_TIMINGS_MS"].get("mlkem_decapsulation_ms", 0)),
        float(pqc_metrics["PERFORMANCE_TIMINGS_MS"].get("hybrid_kdf_ms", 0)),
        float(pqc_metrics["PERFORMANCE_TIMINGS_MS"].get("total_pqc_overhead_ms", 0))
    ]
    
    x_pos = np.arange(len(operations))
    bars = ax.bar(x_pos, timings, color=colors['overhead'], edgecolor='black', linewidth=1.5)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(operations)
    
    ax.set_ylabel('Time (milliseconds)', fontsize=12, fontweight='bold')
    ax.set_title('PQC Operations Performance Overhead', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.3f} ms',
               ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # Add reference line at 1ms
    ax.axhline(y=1.0, color='green', linestyle='--', linewidth=2, alpha=0.7, label='1ms threshold')
    ax.legend()
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "chart_performance.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ Chart generated: {output_file}")
    
    # Chart 3: Message Sizes
    fig, ax = plt.subplots(figsize=(12, 6))
    
    messages = ['PrepareDownload\nResponse', 'BoundProfile\nPackage', 'InitialiseSecure\nChannel']
    classical_msg = [
        classical_metrics["MESSAGE_SIZES_BYTES"].get("prepare_download_response_bytes", 0),
        classical_metrics["MESSAGE_SIZES_BYTES"].get("bound_profile_package_bytes", 0),
        classical_metrics["MESSAGE_SIZES_BYTES"].get("initialise_secure_channel_bytes", 0)
    ]
    pqc_msg = [
        pqc_metrics["MESSAGE_SIZES_BYTES"].get("prepare_download_response_bytes", 0),
        pqc_metrics["MESSAGE_SIZES_BYTES"].get("bound_profile_package_bytes", 0),
        pqc_metrics["MESSAGE_SIZES_BYTES"].get("initialise_secure_channel_bytes", 0)
    ]
    
    x = np.arange(len(messages))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, classical_msg, width, label='Classical', color=colors['classical'])
    bars2 = ax.bar(x + width/2, pqc_msg, width, label='PQC', color=colors['pqc'])
    
    ax.set_xlabel('Message Type', fontsize=12, fontweight='bold')
    ax.set_ylabel('Size (bytes)', fontsize=12, fontweight='bold')
    ax.set_title('Protocol Message Sizes: Classical vs PQC', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(messages)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}',
                       ha='center', va='bottom', fontsize=9, rotation=90)
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "chart_message_sizes.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ Chart generated: {output_file}")
    
    # Chart 4: Bandwidth Comparison (Bar chart instead of pie)
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Get bandwidth data
    classical_bw = classical_metrics["BANDWIDTH_ANALYSIS"].get("total_bandwidth_bytes", 0)
    pqc_bw = pqc_metrics["BANDWIDTH_ANALYSIS"].get("total_bandwidth_bytes", 0)
    
    classical_prep = classical_metrics["MESSAGE_SIZES_BYTES"].get("prepare_download_response_bytes", 0)
    classical_bpp = classical_metrics["MESSAGE_SIZES_BYTES"].get("bound_profile_package_bytes", 0)
    classical_init = classical_metrics["MESSAGE_SIZES_BYTES"].get("initialise_secure_channel_bytes", 0)
    
    pqc_prep = pqc_metrics["MESSAGE_SIZES_BYTES"].get("prepare_download_response_bytes", 0)
    pqc_bpp = pqc_metrics["MESSAGE_SIZES_BYTES"].get("bound_profile_package_bytes", 0)
    pqc_init = pqc_metrics["MESSAGE_SIZES_BYTES"].get("initialise_secure_channel_bytes", 0)
    
    categories = ['PrepareDownload', 'BPP', 'InitSecure', 'Total']
    classical_values = [classical_prep, classical_bpp, classical_init, classical_bw]
    pqc_values = [pqc_prep, pqc_bpp, pqc_init, pqc_bw]
    
    x = np.arange(len(categories))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, classical_values, width, label='Classical', color=colors['classical'])
    bars2 = ax.bar(x + width/2, pqc_values, width, label='PQC', color=colors['pqc'])
    
    ax.set_xlabel('Component', fontsize=12, fontweight='bold')
    ax.set_ylabel('Size (bytes)', fontsize=12, fontweight='bold')
    ax.set_title('Bandwidth Comparison: Classical vs PQC', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}',
                       ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "chart_bandwidth.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ Chart generated: {output_file}")
    
    # Chart 5: Security Level Comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    
    categories = ['Classical\nSecurity', 'Quantum\nSecurity', 'Combined\nSecurity']
    classical_sec = [128, 0, 128]
    pqc_sec = [128, 192, 192]
    
    x = np.arange(len(categories))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, classical_sec, width, label='Classical RSP', color=colors['classical'])
    bars2 = ax.bar(x + width/2, pqc_sec, width, label='PQC RSP', color=colors['pqc'])
    
    ax.set_ylabel('Security Level (bits)', fontsize=12, fontweight='bold')
    ax.set_title('Security Levels: Classical vs PQC RSP', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, 220)
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)} bits',
                       ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # Add quantum resistance indicator
    ax.text(2.5, 210, 'Quantum\nResistant ✓', ha='center', 
           bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8),
           fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "chart_security.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ Chart generated: {output_file}")
    
    # Chart 6: Scalability Analysis (Operations per protocol execution)
    fig, ax = plt.subplots(figsize=(12, 6))
    
    operations_list = ['ECDSA\nSignatures', 'ECDH\nOperations', 'ML-KEM\nKeypairs', 
                      'ML-KEM\nDecaps', 'Hybrid\nKDF']
    
    classical_ops = [
        classical_metrics["PROTOCOL_COUNTERS"].get("ecdsa_signatures", 0),
        classical_metrics["PROTOCOL_COUNTERS"].get("ecdh_operations", 0),
        0, 0, 0
    ]
    
    pqc_ops = [
        pqc_metrics["PROTOCOL_COUNTERS"].get("ecdsa_signatures", 0),
        pqc_metrics["PROTOCOL_COUNTERS"].get("ecdh_operations", 0),
        pqc_metrics["PROTOCOL_COUNTERS"].get("mlkem_keypair_operations", 0),
        pqc_metrics["PROTOCOL_COUNTERS"].get("mlkem_decapsulation_operations", 0),
        pqc_metrics["PROTOCOL_COUNTERS"].get("hybrid_kdf_operations", 0)
    ]
    
    x = np.arange(len(operations_list))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, classical_ops, width, label='Classical', color=colors['classical'])
    bars2 = ax.bar(x + width/2, pqc_ops, width, label='PQC', color=colors['pqc'])
    
    ax.set_xlabel('Operation Type', fontsize=12, fontweight='bold')
    ax.set_ylabel('Count per Protocol Execution', fontsize=12, fontweight='bold')
    ax.set_title('Cryptographic Operations: Classical vs PQC RSP', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(operations_list)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}',
                       ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    output_file = OUTPUT_DIR / "chart_operations.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ Chart generated: {output_file}")

def main():
    print("═" * 65)
    print("  RSP Performance Visualization Generator")
    print("  Classical vs Post-Quantum Comparison")
    print("═" * 65)
    print()
    
    # Check if metrics exist
    classical_file = METRICS_DIR / "classical.metrics"
    pqc_file = METRICS_DIR / "pqc.metrics"
    exec_times_file = METRICS_DIR / "execution_times.metrics"
    
    if not classical_file.exists() or not pqc_file.exists():
        print("✗ Metrics files not found!")
        print(f"  Expected: {classical_file}")
        print(f"  Expected: {pqc_file}")
        print()
        print("  Run './report/collect-metrics.sh' first to collect metrics")
        sys.exit(1)
    
    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Parse metrics
    print("▶ Parsing metrics files...")
    classical_metrics = parse_metrics_file(classical_file)
    pqc_metrics = parse_metrics_file(pqc_file)
    
    exec_times = {}
    if exec_times_file.exists():
        with open(exec_times_file, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=')
                    exec_times[key] = int(value)
    
    print("✓ Metrics parsed")
    print()
    
    # Export to JSON
    print("▶ Generating JSON export...")
    export_to_json(classical_metrics, pqc_metrics, exec_times)
    print()
    
    # Export to CSV
    print("▶ Generating CSV exports...")
    export_to_csv(classical_metrics, pqc_metrics, exec_times)
    print()
    
    # Generate charts
    print("▶ Generating visualization charts...")
    generate_charts(classical_metrics, pqc_metrics, exec_times)
    print()
    
    print("═" * 65)
    print("✓ All outputs generated successfully!")
    print("═" * 65)
    print()
    print("Output directory:", OUTPUT_DIR)
    print()
    print("Generated files:")
    for file in sorted(OUTPUT_DIR.glob("*")):
        size = file.stat().st_size
        print(f"  • {file.name} ({size:,} bytes)")
    print()

if __name__ == "__main__":
    main()

