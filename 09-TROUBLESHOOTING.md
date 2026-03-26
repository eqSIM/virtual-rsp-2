# Troubleshooting Guide

**[← Previous: Demo Script](08-DEMO-SCRIPT.md)** | **[Index](README.md)**

---

## Table of Contents
1. [Connection Issues](#1-connection-issues)
2. [GUI Issues](#2-gui-issues)
3. [Data Integrity Issues](#3-data-integrity-issues)
4. [Building Issues](#4-building-issues)
5. [Advanced Debugging](#5-advanced-debugging)

---

This document covers common issues and their solutions when working with the Virtual RSP system.

## 1. Connection Issues

### "euicc_init failed" or "Refused" in LPA
- **Cause**: The `v-euicc-daemon` is not running or is on a different port.
- **Solution**: Run `./teardown.sh` and then ensure the daemon is started with `./build/v-euicc/v-euicc-daemon 8765`.

### "HTTP status code error" during download
- **Cause**: The `nginx` proxy or `osmo-smdpp` server is down.
- **Solution**: Check the status bar in the GUI. If using CLI, check if processes are running: `pgrep -la "osmo-smdpp\|nginx"`.

### "Could not connect to testsmdpplus1.example.com"
- **Cause**: Missing `/etc/hosts` entry.
- **Solution**: Run `sudo ./add-hosts-entry.sh`.

## 2. GUI Issues

### Dialogs or Alerts are "invisible" (Blank White/Black)
- **Cause**: Operating system Dark Mode interference with PySide6 default styling.
- **Solution**: The GUIs have been updated with global stylesheets to force visibility. Ensure you are using the latest version of `mno/main.py` and `gui/main.py`.

### "Address already in use"
- **Cause**: Stale processes from a previous run are still holding the ports (8000, 8443, or 8765).
- **Solution**: Run `./teardown.sh`. This script will forcefully kill all project-related processes.

## 3. Data Integrity Issues

### Profile list is empty after successful download
- **Cause**: v-euicc state reset or daemon restart. The virtual eSIM stores profiles in memory.
- **Solution**: Profiles are also persisted to `data/profiles.json`. If they don't show up, check if that file contains the profile entries. Ensure the daemon wasn't restarted mid-session.

### "Error listing sessions"
- **Cause**: The SM-DP+ server is not responding to the MNO REST API.
- **Solution**: Check `data/smdp.log` for Python tracebacks. Ensure you are using the virtual environment with all dependencies installed.

## 4. Building Issues

### "lpac drivers not found"
- **Cause**: `lpac` expects drivers to be in a specific relative path.
- **Solution**: The CMake build should handle this, but if it fails, manually create a symlink:
  ```bash
  cd build/lpac/src && ln -s ../driver driver
  ```

### "OpenSSL headers not found"
- **Cause**: OpenSSL is installed in a non-standard path (common on macOS with Homebrew).
- **Solution**: Tell CMake where OpenSSL is:
  ```bash
  cmake -B build -DOPENSSL_ROOT_DIR=$(brew --prefix openssl)
  cmake --build build
  ```

### "Python module not found" when running GUIs
- **Cause**: Python dependencies not installed in the virtual environment.
- **Solution**:
  ```bash
  source pysim/venv/bin/activate
  pip install -r requirements-mno.txt -r requirements-gui.txt
  ```

## 5. Advanced Debugging

### Inspecting Live APDU Traffic
Monitor the `v-euicc` daemon logs in real-time:
```bash
tail -f data/veuicc.log
```

Look for lines like:
- `APDU: CLA=81 INS=E2 ...`: Incoming APDU command.
- `ES10x command tag: BF38`: Decoded ES10x command type.
- `ECDSA signature generated`: Cryptographic operation completed.

### Checking SM-DP+ Session State
Query the active sessions via curl:
```bash
curl -s http://127.0.0.1:8000/mno/sessions | jq
```

If this returns hundreds of sessions, your SM-DP+ is using persistent storage and has accumulated stale sessions. Restart with the `-m` flag:
```bash
cd pysim
python3 osmo-smdpp.py -H 127.0.0.1 -p 8000 --nossl -c generated -m
```

### Verifying Profile Installation
Check the contents of `data/profiles.json`:
```bash
cat data/profiles.json | jq
```

You should see an array of profiles with ICCIDs, states, and matching IDs.

### Manual Profile Download Test
For low-level debugging, run the profile download manually:
```bash
export LPAC_APDU=socket
export LPAC_APDU_SOCKET_HOST=127.0.0.1
export LPAC_APDU_SOCKET_PORT=8765
export DYLD_LIBRARY_PATH=./build/lpac/euicc:./build/lpac/utils:./build/lpac/driver

./build/lpac/src/lpac profile download -s testsmdpplus1.example.com:8443 -m TS48v5_SAIP2.3_BERTLV_SUCI
```

Watch for JSON output with `"type":"progress"` and `"type":"lpa"`.

---

**[← Previous: Demo Script](08-DEMO-SCRIPT.md)** | **[Index](README.md)**
