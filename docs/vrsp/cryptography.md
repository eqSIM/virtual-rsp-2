# Cryptographic Operations & Technical Flow

## Overview

This document provides a detailed technical explanation of the complete SGP.22 v2.5 profile download and installation process, including all cryptographic operations, certificate handling, and data flows.

## Architecture Components

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│    LPA      │◄───────►│   v-euicc    │◄───────►│   SM-DP+    │
│   (lpac)    │  ES10x  │   (eUICC)    │  ES9+   │ (osmo-smdpp)│
└─────────────┘         └──────────────┘         └─────────────┘
```

---

## Certificate Infrastructure

### eUICC Certificate Chain

The eUICC uses a certificate hierarchy for authentication:

```
GSMA Root CA (Root of Trust)
    └── EUM (eUICC Manufacturer)
        └── CERT.EUICC.ECDSA (Device Certificate)
            └── SK.EUICC.ECDSA (Private Key in eUICC)
```

**Certificate Details:**
- **Algorithm**: ECDSA with NIST P-256 curve (secp256r1)
- **CERT.EUICC.ECDSA**:
  - Subject: CN=EID_89049032001001234500012345678901
  - Contains: Public Key (PK.EUICC.ECDSA)
  - Validity: Set by EUM
  - Extensions: EID, Certificate Profile OID

- **CERT.EUM.ECDSA**:
  - Issuer certificate from manufacturer
  - Validates the eUICC certificate

### SM-DP+ Certificate Chain

```
GSMA Root CA
    └── CERT.DPauth.ECDSA (Authentication Certificate)
    └── CERT.DPpb.ECDSA (Profile Binding Certificate)
```

---

## Mutual Authentication Flow

### Phase 1: InitiateAuthentication (ES9+)

**LPA → SM-DP+**

```
POST https://testsmdpplus1.example.com:8443/gsma/rsp2/es9plus/initiateAuthentication

Request:
{
  "euiccChallenge": "<base64-encoded 16-byte random>",
  "euiccInfo1": "<base64-encoded EUICCInfo1>",
  "smdpAddress": "testsmdpplus1.example.com"
}

Response:
{
  "transactionId": "<unique session ID>",
  "serverSigned1": { ... },
  "serverSignature1": "<ECDSA signature>",
  "euiccCiPKIdToBeUsed": "3c45e5f009d02c75ecf3d7fb0b63fd317cde2c4e",
  "serverCertificate": "<base64 CERT.DPauth.ECDSA>"
}
```

**Purpose**: SM-DP+ proves its identity and provides a challenge.

### Phase 2: AuthenticateServer (ES10b)

**LPA → eUICC**

The eUICC performs the following verification:

```c
// 1. Verify SM-DP+ certificate chain
verify_certificate_chain(CERT_DPauth_ECDSA, CERT_GSMA_ROOT);

// 2. Verify serverSignature1 over serverSigned1
ecdsa_verify(PK_DPauth_ECDSA, serverSignature1, serverSigned1);

// 3. Check euiccChallenge matches our challenge
assert(serverSigned1.euiccChallenge == our_challenge);

// 4. Generate response signature
euiccSigned1 = {
    transactionId,
    serverAddress,
    serverChallenge,
    euiccInfo2  // Contains EID, capabilities, cert PKIDs
};

// 5. Sign with eUICC private key
euiccSignature1 = ecdsa_sign(SK_EUICC_ECDSA, euiccSigned1);
```

**Signature Format** (TR-03111):
```
Raw signature = R || S (64 bytes total)
- R: 32 bytes (x-coordinate of signature point)
- S: 32 bytes (signature scalar)
```

### Phase 3: AuthenticateClient (ES9+)

**LPA → SM-DP+**

SM-DP+ verifies eUICC signature and certificate chain.

---

## Session Key Derivation

### PrepareDownload (ES10b)

**eUICC Operations:**

```c
// 1. Generate ephemeral ECKA key pair
(otPK_EUICC_ECKA, otSK_EUICC_ECKA) = generate_ec_keypair(NIST_P256);

// 2. Store private key for session key derivation
state->euicc_otsk = otSK_EUICC_ECKA;  // 32 bytes
state->euicc_otpk = otPK_EUICC_ECKA;  // 65 bytes (04||X||Y)

// 3. Sign response
euiccSigned2 = {
    transactionId,
    euiccOtpk: otPK_EUICC_ECKA,
    hashCC: SHA256(confirmationCode || transactionId)  // if CC required
};
euiccSignature2 = ecdsa_sign(SK_EUICC_ECDSA, euiccSigned2);
```

**Key Format:**
```
Uncompressed EC Point:
  0x04 || X-coordinate (32 bytes) || Y-coordinate (32 bytes)
  Total: 65 bytes
```

### GetBoundProfilePackage (ES9+)

**SM-DP+ Operations:**

```python
# 1. Verify euiccSignature2
verify_signature(PK_EUICC_ECDSA, euiccSignature2, euiccSigned2 || smdpSignature2)

# 2. Extract eUICC's public key
euicc_otpk = euiccSigned2.euiccOtpk

# 3. Generate SM-DP+ ephemeral key pair
(otPK_DP_ECKA, otSK_DP_ECKA) = generate_ec_keypair(NIST_P256)

# 4. Derive shared secret using ECDH
shared_secret = ECDH(otSK_DP_ECKA, euicc_otpk)

# 5. Derive session keys (SGP.22 Annex G)
def derive_keys(shared_secret, key_type, key_len, host_id, eid):
    counter = 0x00000001
    hash_input = counter || shared_secret || key_type || key_len || host_id || eid
    hash_output = SHA256(hash_input)
    
    KEK = hash_output[0:16]   # Key Encryption Key
    KM = hash_output[16:32]   # Key for MAC
    return (KEK, KM)

(s_enc, s_mac) = derive_keys(shared_secret, 0x88, 16, host_id, eid)
```

### InitialiseSecureChannel (ES8+)

**eUICC Operations:**

```c
// 1. Extract SM-DP+ public key from BF23
smdp_otpk = extract_field(BF23, 0x5F49);  // 65 bytes

// 2. Derive session keys using ECDH
shared_secret = ecdh_derive(state->euicc_otsk, smdp_otpk);

// 3. KDF (SGP.22 Annex G)
// Same algorithm as SM-DP+
(session_key_enc, session_key_mac) = derive_keys(shared_secret, ...);
```

---

## BPP Processing

### BoundProfilePackage Structure

```
BF36 (BoundProfilePackage) {
    BF23 (InitialiseSecureChannelRequest) {
        82: remoteOpId = 0x01 (installBoundProfilePackage)
        80: transactionId
        A6: controlRefTemplate (CRT)
        5F49: smdpOtpk (otPK.DP.ECKA, 65 bytes)
        5F37: smdpSignature
    }
    A0 (firstSequenceOf87) {
        87: encrypted ConfigureISDP command
        99: MAC
    }
    A1 (sequenceOf88) {
        88: MAC-only StoreMetadata
        99: MAC
    }
    A2 (secondSequenceOf87) {  // Optional, if PPK included
        87: encrypted ReplaceSessionKeys
        99: MAC
    }
    A3 (sequenceOf86) {
        86: encrypted profile element 1
        99: MAC
        86: encrypted profile element 2
        99: MAC
        ...
    }
}
```

### Command Processing

1. **A0 (ConfigureISDP)**:
   - Decrypt with KEK, verify MAC with KM
   - Configure ISD-P applet parameters

2. **A1 / 0x88 (StoreMetadata)**:
   - MAC-only protection (no encryption)
   - Store profile metadata
   - Verify Profile Policy Rules (PPR)

3. **A2 (ReplaceSessionKeys)** (if present):
   - Decrypt with KEK, verify MAC
   - Update session keys with Profile Protection Keys (PPK)

4. **A3 / 0x86 (LoadProfileElements)**:
   - Multiple encrypted profile elements
   - Decrypt each 0x86 TLV with current KEK
   - Verify MAC for each element
   - Install profile files

---

## ProfileInstallationResult

**Structure (BF37):**

```
BF37 (ProfileInstallationResult) {
    BF27 (ProfileInstallationResultData) {
        80: transactionId (16 bytes)
        BF2F (NotificationMetadata) {
            80: seqNumber
            81: profileManagementOperation
            0C: notificationAddress
        }
        06: smdpOid (SM-DP+ OID)
        A2 (finalResult) {
            A0 (successResult) {
                30 (SEQUENCE) {
                    4F: aid (ISD-P AID, 16 bytes)
                    04: simaResponse (90 00 = success)
                }
            }
        }
    }
    5F37: euiccSignPIR (ECDSA signature, 64 bytes)
}
```

---

## Cryptographic Operation Summary

### Operations Performed

1. **ECDSA Signatures**: 3+
   - AuthenticateServer response (euiccSignature1)
   - PrepareDownload response (euiccSignature2)
   - ProfileInstallationResult (euiccSignPIR)

2. **ECDH Key Agreements**: 1
   - Derive shared secret from otSK.EUICC.ECKA × otPK.DP.ECKA

3. **KDF Derivations**: 1
   - Derive KEK and KM from shared secret

4. **Certificate Verifications**: 4+
   - CERT.DPauth.ECDSA chain
   - CERT.DPpb.ECDSA chain
   - CERT.EUICC.ECDSA chain
   - CERT.EUM.ECDSA

5. **AES Operations**: 15+
   - AES-CMAC for MAC verification (each BPP command)
   - AES-CBC for decryption (encrypted commands)

### Security Properties

- **Mutual Authentication**: Both eUICC and SM-DP+ prove identity
- **Forward Secrecy**: Ephemeral ECKA keys ensure each session is unique
- **Integrity**: ECDSA signatures and AES-CMAC protect all data
- **Confidentiality**: Profile encrypted with session-specific keys
- **Replay Protection**: Transaction IDs and challenges prevent replay

---

## References

- **[GSMA eSIM Specification](https://www.gsma.com/solutions-and-impact/technologies/esim/esim-specification/)**: SGP.22 v2.5 RSP Technical Specification
- **TR-03111**: ECDSA Signature Format
- **GlobalPlatform Card Spec v2.3**: Secure Channel Protocol
- **NIST P-256**: secp256r1 elliptic curve parameters
