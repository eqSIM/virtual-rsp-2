# Virtual eUICC Implementation Deep-Dive

**[← Previous: RSP Flow](03-RSP-FLOW.md)** | **[Index](README.md)** | **[Next: Modifications →](05-MODIFICATIONS.md)**

---

## Table of Contents
1. [Core Responsibilities](#core-responsibilities)
2. [TCP Server & Global State](#1-tcp-server--global-state-mainc)
3. [APDU Command Dispatch](#2-apdu-command-dispatch-apdu_handlerc)
4. [State Management](#3-state-management-euicc_stateh)
5. [Cryptographic Operations](#4-cryptographic-operations-cryptoc)
6. [Profile Installation Logic](#5-profile-installation-logic)
7. [Supported ES10x Tags](#6-supported-es10x-tags)
8. [Code Reference](#code-reference)

---

This document provides a technical walkthrough of the `v-euicc-daemon`, a custom C implementation that simulates an eSIM (eUICC) hardware module.

## Core Responsibilities

The `v-euicc-daemon` serves as a bridge between the high-level LPA software (`lpac`) and the low-level cryptographic operations required by the SGP.22 specification. It implements:
- A TCP server for APDU communication.
- A JSON-based protocol for command/response wrapping.
- A complete state machine for RSP sessions.
- Real ECDSA-P256 signing and verification using OpenSSL.

## 1. TCP Server & Global State (`main.c`)

The daemon starts a TCP server (default port 8765) and manages a `static struct euicc_state global_state`.

- **Persistence**: By using a global static state, the virtual eSIM maintains its memory (installed profiles, EID, etc.) even as the LPA connects and disconnects between different commands.
- **Client Handling**: Each incoming connection is handled by `handle_client()`, which parses JSON requests containing functions like `connect`, `transmit`, and `disconnect`.

## 2. APDU Command Dispatch (`apdu_handler.c`)

This is the largest component (2700+ lines), implementing the ES10x interface logic.

- **`apdu_handle_transmit`**: This is the main entry point for almost all RSP operations. It receives a raw APDU, extracts the ES10x command tag (e.g., `BF38` for `AuthenticateServer`), and routes it to the appropriate handler.
- **BER-TLV Encoding**: A custom `build_tlv` helper is used to manually construct the complex nested TLV (Tag-Length-Value) structures required by GSMA.
- **Segmentation**: Since APDUs have a limited size, the daemon implements command segmentation. Large payloads (like Bound Profile Packages) are accumulated in a `segment_buffer` across multiple `transmit` calls.

## 3. State Management (`euicc_state.h`)

The `euicc_state` structure is the "brain" of the virtual eSIM.

```c
struct euicc_state {
    char eid[33];                    // EID string
    // ... authentication state ...
    uint8_t *euicc_cert;             // CERT.EUICC.ECDSA
    EVP_PKEY *euicc_private_key;     // SK.EUICC.ECDSA
    // ... session keys (KEK, KM) ...
    struct profile_metadata *profiles; // Linked list of installed profiles
};
```

- **In-Memory Storage**: Currently, the eUICC state is stored in memory. While the GUI persists profiles to `profiles.json`, the daemon itself rebuilds its internal view from this file or maintains it while running.

## 4. Cryptographic Operations (`crypto.c`)

Integrated with OpenSSL 3.x to perform real cryptographic operations:

- **ECDSA Signatures**: Generates signatures for `AuthenticateServerResponse` and `PrepareDownloadResponse`.
- **Format Conversion**: Handles the conversion between OpenSSL's ASN.1 DER format and the raw 64-byte `R || S` format required by the eSIM protocol (SGP.22 / TR-03111).
- **ECDH Key Agreement**: Derives the shared secret used to generate session keys during the `InitialiseSecureChannel` (BF23) command.

## 5. Profile Installation Logic

When the daemon receives the final `A3` sequence of the Bound Profile Package:
1. It extracts the profile metadata (ICCID, Name, SPN).
2. It allocates a new `profile_metadata` structure.
3. It adds the profile to the `state->profiles` linked list.
4. It logs the successful installation, which is then captured by the GUI log viewers.

## 6. Supported ES10x Tags

The implementation currently supports:

### Information Retrieval
- **`BF2E`**: GetEuiccChallenge - Generate a random 16-byte challenge for authentication.
- **`BF20`**: GetEuiccInfo1 - Return basic eUICC information and supported CI keys.
- **`BF22`**: GetEuiccInfo2 - Return detailed eUICC capabilities, memory, and firmware version.
- **`BF3E`**: GetEuiccData - Retrieve eUICC configuration data.
- **`BF3C`**: EuiccConfiguredAddresses - Get default SM-DP+ and SM-DS addresses.

### Authentication
- **`BF38`**: AuthenticateServer - Process server authentication with ECDSA signature verification.

### Profile Download
- **`BF21`**: PrepareDownload - Generate ephemeral ECKA key pair for session encryption.
- **`BF23`**: InitialiseSecureChannel - Establish encrypted channel using ECDH.
- **`A0`**: ConfigureISDP - Configure ISD-P applet parameters.
- **`A1`**: StoreMetadata (sequenceOf88) - Store profile metadata with MAC protection.
- **`A2`**: ReplaceSessionKeys (secondSequenceOf87) - Update session keys with PPK.
- **`A3`**: LoadProfileElements (sequenceOf86) - Receive encrypted profile segments.

### Profile Management
- **`BF2D`**: GetProfilesInfo - List all installed profiles with their state.
- **`BF2F`**: EnableProfile / DisableProfile - Change profile activation state.
- **`BF31`**: DeleteProfile - Remove a profile from the eUICC.

### Session Management
- **`BF41`**: CancelSession - Abort an ongoing RSP session.

## Code Reference

Key files to examine:
- **`v-euicc/src/main.c`** (293 lines): TCP server, global state initialization.
- **`v-euicc/src/apdu_handler.c`** (2789 lines): Main APDU dispatcher, ES10x command handlers.
- **`v-euicc/src/euicc_state.c`**: State initialization and cleanup routines.
- **`v-euicc/src/crypto.c`**: ECDSA signing, ECDH key agreement, session key derivation.
- **`v-euicc/src/cert_loader.c`**: Loading X.509 certificates and private keys from DER/PEM files.
- **`v-euicc/include/euicc_state.h`**: Complete state structure definition.

---

**[← Previous: RSP Flow](03-RSP-FLOW.md)** | **[Index](README.md)** | **[Next: Modifications →](05-MODIFICATIONS.md)**
