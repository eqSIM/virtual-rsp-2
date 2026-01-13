# Detailed Technical Demo Walkthrough

**[← Previous: MNO Console](07-GUI-MNO-CONSOLE.md)** | **[Index](README.md)** | **[Next: Troubleshooting →](09-TROUBLESHOOTING.md)**

---

## Table of Contents
1. [What this script does](#what-this-script-does)
2. [Running the Demo](#running-the-demo)
3. [Walkthrough of Parts](#walkthrough-of-parts)
4. [Log Interpretation](#log-interpretation)

---

The `demo-detailed.sh` script is designed to provide a deep look into the cryptographic and protocol details of the eSIM Remote SIM Provisioning flow.

## What this script does

Unlike the GUIs, which abstract away the complexity, this script:
1.  Cleans up any running services.
2.  Starts the entire stack (`v-euicc`, `osmo-smdpp`, `nginx`).
3.  Performs a complete profile download.
4.  **Extracts and explains** the binary data at each step.

## Walkthrough of Parts

### Part 1: eUICC Certificates and Capabilities
- **Inspection**: Uses `openssl` to parse the DER certificates stored in `v-euicc/certs/`.
- **EID**: Displays the eUICC Identifier.
- **Info2**: Uses `lpac chip info` to show the virtual chip's memory, firmware version, and supported CI (Certificate Issuer) keys.

### Part 2: Mutual Authentication Flow
Shows the three-way handshake between LPA, eUICC, and SM-DP+:
- **Phase 1 (initiateAuthentication)**: Requesting the server challenge.
- **Phase 2 (AuthenticateServer)**: Captures the `v-euicc` log showing the **real ECDSA signature** generation (64 bytes in TR-03111 format).
- **Phase 3 (AuthenticateClient)**: Verifies that the SM-DP+ successfully validated the eUICC's signature and certificate chain.

### Part 3: Profile Download Preparation
- **PrepareDownload**: Captures the generation of the ephemeral ECKA key pair (`otPK.EUICC.ECKA`). This is the foundation for the secure channel encryption.

### Part 4: BPP Download & Installation
Detailed breakdown of the Bound Profile Package commands:
- **BF23**: Key agreement and session key derivation (KEK and KM).
- **A0**: Configure ISD-P.
- **A1/88**: Store Metadata.
- **86**: Transmission of encrypted profile segments.
- **A3**: Final installation trigger.

### Part 5: Installation Result
- **Confirmation**: Checks the eUICC logs for the "Profile Successfully Installed" message.
- **Metadata**: Displays the ICCID and Profile Name of the newly installed virtual SIM.

## Running the Demo

```bash
# Use defaults (testsmdpplus1.example.com:8443)
./demo-detailed.sh

# Specify custom SM-DP+ and profile
./demo-detailed.sh testsmdpplus1.example.com:8443 TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE

# Show help and available profiles
./demo-detailed.sh --help
```

The script will:
1. Automatically clean up any existing processes.
2. Start all required services.
3. Run a complete profile download with detailed console output.
4. Save raw logs to `/tmp/` for post-mortem analysis.

## Log Interpretation

The script redirects output to `/tmp/detailed-*.log`. You can inspect these files for the raw protocol data:

### Log Files
- **`/tmp/detailed-euicc.log`**: Complete APDU command processing, crypto operations, and BER-TLV parsing.
- **`/tmp/detailed-smdpp.log`**: SM-DP+ API handling, certificate validation, and session key derivation.
- **`/tmp/detailed-lpac.log`**: The raw JSON output from the LPA client showing each ES9+ and ES10b step.

### Key Log Patterns to Look For

**v-euicc logs**:
```
[v-euicc] AuthenticateServer: Real ECDSA signature generated (64 bytes)
[v-euicc] Session keys derived successfully (KEK: 16 bytes, KM: 16 bytes)
[v-euicc] Created profile metadata: ICCID=..., Name=...
```

**osmo-smdpp logs**:
```
Rx serverSigned1: {'transactionId': ..., 'euiccChallenge': ...}
ECDSA signature verification succeeded
Profile Installation Final Result: success
```

**lpac logs**:
```json
{"type":"progress","payload":{"code":0,"message":"es10b_authenticate_server","data":"..."}}
{"type":"lpa","payload":{"code":0,"message":"success","data":...}}
```

---

**[← Previous: MNO Console](07-GUI-MNO-CONSOLE.md)** | **[Index](README.md)** | **[Next: Troubleshooting →](09-TROUBLESHOOTING.md)**
