# Virtual RSP

Software-based GSMA SGP.22 eSIM Remote SIM Provisioning stack. Simulates eSIM profile download and lifecycle management without physical hardware.

## Components

| Component | Role |
|---|---|
| **v-euicc** | Virtual eUICC daemon (ECDSA-P256 crypto) |
| **lpac** | Local Profile Assistant (LPA client) |
| **osmo-smdpp** | SM-DP+ profile server |
| **nginx** | TLS reverse proxy |

```
lpac <──socket──> v-euicc-daemon <──HTTPS/ES9+──> nginx <──> osmo-smdpp
```

## Getting Started (fresh clone)

```bash
# 1. One-time system setup (needs sudo password)
sudo apt install cmake gcc nginx swig libssl-dev python3-venv   # skip if already installed
echo '127.0.0.1 testsmdpplus1.example.com' | sudo tee -a /etc/hosts

# 2. Run everything
./test-all.sh
```

That's it. `test-all.sh` handles the rest:
- Builds C components (lpac + v-euicc-daemon)
- Creates Python venv and installs all packages
- Generates SGP.26 test certificates
- Syncs CI PKID between certs and C source, rebuilds if needed
- Starts all services (v-euicc-daemon, osmo-smdpp, nginx)
- Runs the SGP.22 test suite (chip info, mutual auth, profile download)
- Tears down all processes on exit

If any system packages are missing, the script tells you exactly what to install.

### Re-running

```bash
./test-all.sh                # full run (build + setup + test)
./test-all.sh --skip-build   # reuse existing build artifacts
./test-all.sh --skip-setup   # reuse existing venv + certs too
./test-all.sh --tests-only   # fastest re-run (skip build AND setup)
```

## Manual Setup (if needed)

```bash
# Build
cmake -B build -DLPAC_WITH_APDU_PCSC=OFF -DCMAKE_C_FLAGS="-Wno-deprecated-declarations" .
cmake --build build -j$(nproc)

# Python venv
python3 -m venv pysim/venv
source pysim/venv/bin/activate
pip install -r pysim/requirements.txt
pip install klein requests

# Generate certs
cd pysim && python3 contrib/generate_smdpp_certs.py && cd ..

# Hosts entry
echo "127.0.0.1 testsmdpplus1.example.com" | sudo tee -a /etc/hosts

# Start services
./build/v-euicc/v-euicc-daemon 8765 &
source pysim/venv/bin/activate
cd pysim && python3 osmo-smdpp.py -H 127.0.0.1 -p 8000 --nossl -c generated &
nginx -c $PWD/pysim/nginx-smdpp.conf -p $PWD/pysim &

# Test
LPAC_APDU=socket ./build/lpac/src/lpac chip info
LPAC_APDU=socket ./build/lpac/src/lpac profile discovery -s testsmdpplus1.example.com:8443
```

## License

See component directories for licensing.
