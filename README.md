# Virtual Remote SIM Provisioning (Virtual RSP)

A complete software-based implementation of the GSMA SGP.22 eSIM Remote SIM Provisioning (RSP) stack. This project allows for the simulation of eSIM profile downloads and lifecycle management without physical hardware.

## 🚀 Quick Start

### 1. Build the Project
```bash
cmake -B build && cmake --build build
```

### 2. Configure Environment (One-time)
```bash
# Add hosts entry (requires sudo)
./add-hosts-entry.sh

# Setup Python venv
python3 -m venv pysim/venv
source pysim/venv/bin/activate
pip install -r requirements-mno.txt -r requirements-gui.txt

# Generate test certificates
cd pysim && python3 contrib/generate_smdpp_certs.py && cd ..
```

### 3. Run the Applications
Choose the interface that fits your role:

- **Developer**: `./run-gui.sh` (Full stack orchestration & debugging)
- **MNO Operator**: `./run-mno.sh` (Server metrics & profile warehousing)

---

## 📚 Documentation

For detailed technical documentation, please refer to the `docs/` directory:

1.  [**Setup & Configuration**](docs/01-SETUP.md) - Prerequisites and build guide.
2.  [**Architecture Overview**](docs/02-ARCHITECTURE.md) - How the components interact.
3.  [**SGP.22 RSP Flow**](docs/03-RSP-FLOW.md) - Step-by-step protocol walkthrough.
4.  [**v-euicc Internals**](docs/04-V-EUICC.md) - C implementation deep-dive.
5.  [**Modifications**](docs/05-MODIFICATIONS.md) - Changes to open-source components.
6.  [**RSP Control Center**](docs/06-GUI-CONTROL-CENTER.md) - Developer GUI walkthrough.
7.  [**MNO Management Console**](docs/07-GUI-MNO-CONSOLE.md) - Operator GUI walkthrough.
8.  [**Detailed Demo Script**](docs/08-DEMO-SCRIPT.md) - Walkthrough of `demo-detailed.sh`.
9.  [**Troubleshooting**](docs/09-TROUBLESHOOTING.md) - Solutions to common issues.

## 🛠️ Main Components

- **v-euicc**: Virtual eSIM daemon with real ECDSA-P256 cryptography.
- **lpac**: Local Profile Assistant client with a custom socket driver.
- **osmo-smdpp**: Extended SM-DP+ server with MNO management REST API.
- **nginx**: Secure TLS proxy for RSP HTTPS traffic.

## 📜 License

See component-specific directories for licensing information.
