# Verify TRUE Metrics - No Fabrication

This document shows how to verify that all metrics come from actual demo runs with NO hardcoded values, NO fabricated delays, and NO simulated data.

## How to Verify

Run these commands to see the ACTUAL data in the logs:

### 1. PQC Key Sizes
```bash
# ML-KEM public/secret key sizes
grep "ML-KEM-768 keypair generated" /tmp/pqc-detailed-euicc.log
# Expected output: [crypto] ML-KEM-768 keypair generated: pk=1184 bytes, sk=2400 bytes

# ML-KEM ciphertext size
grep "Ciphertext Size:" /tmp/pqc-detailed-euicc.log
# Expected output: [PQC-DEMO]   Ciphertext Size: 1088 bytes (expected 1088)
```

### 2. Performance Timings
```bash
# All PROFILE measurements (real µs timings)
grep "\[PROFILE\]" /tmp/pqc-detailed-euicc.log
# Expected output:
# [PROFILE] mlkem_keypair: 662 µs (0.662 ms)
# [PROFILE] mlkem_decaps: 27 µs (0.027 ms)
# [PROFILE] hybrid_kdf: 83 µs (0.083 ms)
```

### 3. Protocol Operations Count
```bash
# Count ECDSA signatures
grep -c "DER signature generated:" /tmp/pqc-detailed-euicc.log
# Expected: 3

# Count ML-KEM operations
grep -c "\[PQC-DEMO\].*ML-KEM-768 keypair generated" /tmp/pqc-detailed-euicc.log
grep -c "\[PQC-DEMO\].*Performing ML-KEM-768 decapsulation" /tmp/pqc-detailed-euicc.log
grep -c "\[PQC-DEMO\].*Hybrid KDF completed" /tmp/pqc-detailed-euicc.log
# Expected: 1 for each

# Count BPP commands
grep -c "BPP data command.*received" /tmp/pqc-detailed-euicc.log
# Expected: 18
```

### 4. Message Sizes
```bash
# BPP (BoundProfilePackage) size
grep "BF36 wrapper detected" /tmp/pqc-detailed-euicc.log
# Expected output: [v-euicc] BF36 wrapper detected (len=1277), extracting inner BPP command

# Total encrypted profile data
grep "Stored.*bytes of BPP data, total:" /tmp/pqc-detailed-euicc.log | tail -1
# Expected: Stored 1689 bytes of BPP data, total: ...
```

## Extraction Script

The extraction is performed by `report/extract-true-metrics.sh`:
- ✅ Uses `grep` and `sed` to extract from logs
- ✅ No fallback to hardcoded values (shows "NOT_MEASURED" if missing)
- ✅ All calculations are from extracted values only
- ✅ Timestamps in output show when metrics were extracted

## Verify Extraction Commands

```bash
# Run the extraction
./report/extract-true-metrics.sh

# Check the extracted metrics
cat report/metrics/pqc.metrics

# Verify the header says "TRUE DATA"
head -3 report/metrics/pqc.metrics
# Should show:
# # RSP Performance Metrics - PQC Mode (TRUE DATA)
# # Extracted from: /tmp/pqc-detailed-euicc.log
# # Generated: [timestamp]
```

## What Gets Extracted

### From Log Lines
- **Key sizes**: Parsed from `[crypto] ML-KEM-768 keypair generated: pk=X bytes, sk=Y bytes`
- **Ciphertext size**: Parsed from `[PQC-DEMO]   Ciphertext Size: X bytes`
- **Timings**: Parsed from `[PROFILE] operation_name: X µs (Y ms)`
- **Counts**: Using `grep -c` to count actual occurrences
- **Message sizes**: Parsed from `BF36 wrapper detected (len=X)`

### NOT in Extraction Script
- ❌ No hardcoded fallback values
- ❌ No `sleep` commands
- ❌ No simulated delays
- ❌ No fabricated numbers
- ❌ No placeholder data

## Compare With Classical

For classical metrics, run:
```bash
# First run the classical demo
./demo-detailed.sh

# Then extract
./report/extract-true-metrics.sh

# Verify classical metrics
cat report/metrics/classical.metrics
```

## Re-run Full Analysis

To collect fresh TRUE metrics and regenerate visualizations:
```bash
# Option 1: Use existing demo logs
./report/extract-true-metrics.sh
./report/generate-visualizations.py

# Option 2: Run fresh demos and extract
./demo-pqc-detailed.sh  # Run PQC demo
./report/extract-true-metrics.sh
./report/generate-visualizations.py
```

## Verification Checklist

- [ ] Metrics file header says "TRUE DATA"
- [ ] Metrics file shows "Extracted from:" with log path
- [ ] All numeric values match grep output from logs
- [ ] No "0.0" placeholder values (should be "NOT_MEASURED" if missing)
- [ ] Performance timings are in microseconds precision (e.g., 0.662 not 1.0)
- [ ] Counts match actual grep -c results
- [ ] Timestamp shows recent generation time

## If You Find Fabricated Data

If you find any hardcoded values or fabricated numbers:
1. Check `report/extract-true-metrics.sh` for fallback values
2. Verify log file exists: `ls -lh /tmp/pqc-detailed-euicc.log`
3. Check log has content: `wc -l /tmp/pqc-detailed-euicc.log`
4. Run verification commands above to see raw log data
5. Report the issue with specific line numbers

## Notes

- Classical demo may not have PROFILE timing logs (depends on build configuration)
- Some message sizes may show "NOT_LOGGED" if not explicitly logged
- This is accurate - we report what's actually in the logs, nothing more

