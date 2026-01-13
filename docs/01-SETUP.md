# Setup & Configuration

**[← Back to Index](README.md)** | **[Next: Architecture →](02-ARCHITECTURE.md)**

---

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Building the Project](#2-building-the-project)
3. [Python Environment Setup](#3-python-environment-setup)
4. [Network Configuration](#4-network-configuration)
5. [Certificate Generation](#5-certificate-generation)
6. [Running the System](#6-running-the-system)
7. [Environment Variables](#7-environment-variables)

---

This guide provides step-by-step instructions to get the Virtual RSP environment up and running on your local machine.

## 1. Prerequisites

Ensure you have the following installed:

- **CMake** (3.23 or higher)
- **Python 3.11+**
- **nginx** (used as a TLS reverse proxy for SM-DP+)
- **OpenSSL** (3.0+ recommended)
- **C compiler** (GCC or Clang)

### Installation on macOS
```bash
brew install cmake python nginx openssl
```

### Installation on Ubuntu/Debian
```bash
sudo apt update
sudo apt install cmake python3 python3-venv nginx openssl build-essential
```

## 2. Building the Project

The project uses CMake to build both the `lpac` client and the `v-euicc-daemon`.

```bash
# From the project root
cmake -B build
cmake --build build
```

### Build Artifacts
This will produce:
- **`build/lpac/src/lpac`**: The Local Profile Assistant client.
  - Includes the custom socket driver for communicating with `v-euicc`.
  - Shared libraries in `build/lpac/euicc`, `build/lpac/utils`, `build/lpac/driver`.
- **`build/v-euicc/v-euicc-daemon`**: The virtual eUICC server.
  - Implements all ES10x APDU commands.
  - Linked against OpenSSL for ECDSA cryptography.

### Build Verification
To verify the build was successful:

```bash
# Check lpac binary
./build/lpac/src/lpac --help

# Check v-euicc binary
./build/v-euicc/v-euicc-daemon --help
```

### Troubleshooting Build Issues
- **"OpenSSL not found"**: On macOS with Homebrew, specify the path:
  ```bash
  cmake -B build -DOPENSSL_ROOT_DIR=$(brew --prefix openssl)
  cmake --build build
  ```
- **"Driver not found" error**: The CMake build should create the necessary symlinks, but if it fails, manually run:
  ```bash
  cd build/lpac/src && ln -s ../driver driver
  ```

## 3. Python Environment Setup

The SM-DP+ server and the GUI applications require several Python dependencies. It is recommended to use a virtual environment.

```bash
# Create and activate virtual environment
python3 -m venv pysim/venv
source pysim/venv/bin/activate

# Install dependencies for SM-DP+ and GUIs
pip install -r requirements-mno.txt
pip install -r requirements-gui.txt
```

## 4. Network Configuration

### Hosts File Entry
The SM-DP+ server is configured to use the hostname `testsmdpplus1.example.com`. You must add an entry to your `/etc/hosts` file.

```bash
# Run the helper script (requires sudo)
./add-hosts-entry.sh
```

Or manually add:
```text
127.0.0.1  testsmdpplus1.example.com
```

## 5. Certificate Generation

The RSP flow requires valid SGP.22 test certificates. A script is provided to generate a complete chain (CI, EUM, eUICC, SM-DP+).

```bash
source pysim/venv/bin/activate
cd pysim
python3 contrib/generate_smdpp_certs.py
cd ..
```

This creates the `pysim/smdpp-data/generated` directory containing all necessary keys and certificates.

## 6. Running the System

### Option A: Using Launcher Scripts (Recommended)
Two scripts are provided to automatically handle service teardown, startup, and GUI launching.

- **Developer GUI**: `./run-gui.sh`
- **MNO Management Console**: `./run-mno.sh`

### Option B: Manual Startup
If you need to run services separately for debugging:

1.  **Start v-euicc-daemon**:
    ```bash
    ./build/v-euicc/v-euicc-daemon 8765
    ```
2.  **Start SM-DP+ Server**:
    ```bash
    cd pysim
    source venv/bin/activate
    python3 osmo-smdpp.py -H 127.0.0.1 -p 8000 --nossl -c generated -m
    ```
3.  **Start nginx Proxy**:
    ```bash
    nginx -c $(pwd)/pysim/nginx-smdpp.conf -p $(pwd)/pysim
    ```

## 7. Environment Variables

When running `lpac` manually, you must configure it to use the socket driver to talk to the virtual eUICC:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `LPAC_APDU` | APDU driver to use | `socket` |
| `LPAC_APDU_SOCKET_HOST` | v-euicc host | `127.0.0.1` |
| `LPAC_APDU_SOCKET_PORT` | v-euicc port | `8765` |
| `DYLD_LIBRARY_PATH` | Path to lpac shared libs (macOS) | `./build/lpac/euicc:./build/lpac/utils:./build/lpac/driver` |
| `LD_LIBRARY_PATH` | Path to lpac shared libs (Linux) | Same as above |

### Example: Manual Command
```bash
export LPAC_APDU=socket
export LPAC_APDU_SOCKET_HOST=127.0.0.1
export LPAC_APDU_SOCKET_PORT=8765
export DYLD_LIBRARY_PATH=./build/lpac/euicc:./build/lpac/utils:./build/lpac/driver

./build/lpac/src/lpac chip info
./build/lpac/src/lpac profile list
```

---

**[← Back to Index](README.md)** | **[Next: Architecture →](02-ARCHITECTURE.md)**
