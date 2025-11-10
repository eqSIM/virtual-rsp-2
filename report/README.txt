RSP PERFORMANCE METRICS & VISUALIZATION SYSTEM
==============================================

This system automatically collects performance metrics and generates
comparisons between Classical and PQC-enabled RSP implementations.

OUTPUTS:
--------
- CSV files (tabular data for spreadsheets)
- JSON files (structured data for tools)
- PNG charts (automatic visualizations)

USAGE:
------
1. Collect metrics (runs both demos):
   ./report/collect-metrics.sh

2. Generate outputs (CSV, JSON, PNG):
   ./report/generate-visualizations.py

OUTPUTS LOCATION:
-----------------
- Raw metrics:  report/metrics/
- Final outputs: report/output/

OUTPUT FILES:
-------------
- summary.csv              - Key metrics comparison table
- detailed_metrics.csv     - All metrics in tabular format
- metrics_comparison.json  - Complete structured data
- chart_key_sizes.png      - Key size comparison
- chart_performance.png    - PQC overhead timings
- chart_message_sizes.png  - Protocol message sizes
- chart_bandwidth.png      - Bandwidth distribution
- chart_security.png       - Security level comparison
- chart_operations.png     - Cryptographic operations count

METRICS TRACKED:
----------------
Key Sizes:
  - ECDH keys (public/private)
  - ML-KEM-768 keys (public/secret/ciphertext)
  - Total PQC overhead

Performance:
  - ML-KEM keypair generation time
  - ML-KEM decapsulation time
  - Hybrid KDF computation time
  - Total PQC overhead time

Message Sizes:
  - PrepareDownload response
  - BoundProfilePackage
  - InitialiseSecureChannel
  - Total encrypted profile data

Bandwidth:
  - Upload bytes
  - Download bytes
  - Total bandwidth
  - Increase vs classical (bytes & %)

Security:
  - Classical security level (bits)
  - Quantum security level (bits)
  - Combined security level
  - Quantum resistance (true/false)
  - NIST security level

Protocol Counters:
  - ECDSA signatures
  - ECDH operations
  - ML-KEM keypair operations
  - ML-KEM decapsulation operations
  - Hybrid KDF operations
  - BPP commands processed

REQUIREMENTS:
-------------
- Python 3.6+
- matplotlib (for chart generation): pip3 install matplotlib
  (Optional: system will work without it, just no PNG charts)

NOTES:
------
- Each metrics collection run takes ~40-60 seconds
- Classical demo runs first, then PQC demo
- All processes are automatically started and cleaned up
- Logs are saved to /tmp/detailed-*.log and /tmp/pqc-detailed-*.log

