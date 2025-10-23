# GSMA SGP.22 v2.5 — Profile Download and Installation (Sections 3.1.3–3.1.6)

## Overview
This document outlines the **Profile Download and Installation** process within the GSMA Remote SIM Provisioning (RSP) architecture, detailing the mutual authentication, eligibility checks, user consent flow, confirmation handling, profile installation, and lifecycle management at the SM-DP+.

---

## 3.1.3 Profile Download and Installation

### Start Conditions
Depending on the method used:
- **Activation Code (Option a):**
  - End user has an Activation Code per Section 4.1.
  - LPAd supports manual input and QR scanning.
- **SM-DS (Option b):**
  - LPAd retrieves SM-DP+ Address and EventID from SM-DS.
- **Default SM-DP+ (Option c):**
  - LPAd retrieves Default SM-DP+ Address via `ES10a.GetEuiccConfiguredAddresses`.

### Preconditions
- Mutual authentication (Section 3.1.2) between LPAd, eUICC, and SM-DP+ must be completed.
- `CERT.DPauth.ECDSA` must match the OID from the Activation Code if applicable.
- LPAd builds `ctxParams1` with `MatchingID`:
  - `Activation Code Token` (Option a)
  - `EventID` (Option b)
  - Missing (Option c)

### Main Procedure
1. LPAd parses Activation Code and extracts required parameters.
2. Execute Common Mutual Authentication with SM-DP+ (`ES9+` interface).
3. SM-DP+ performs:
   - Validation of `MatchingID` and `EID`.
   - Checks for pending Profile in `Released` or `Downloaded` state.
   - Enforces download attempt limits.
   - Executes **eligibility checks** (Annex F).
4. Optionally notify Operator via `ES2+.HandleDownloadProgressInfo`.
5. If eligible, SM-DP+:
   - Generates `smdpSigned2` = `{TransactionID, ConfirmationCodeRequiredFlag, [bppEuiccOtpk]}`.
   - Signs with `SK.DPpb.ECDSA`.
6. SM-DP+ returns:
   ```
   TransactionID,
   ProfileMetadata,
   smdpSigned2,
   smdpSignature2,
   CERT.DPpb.ECDSA
   ```
7. LPAd evaluates Profile Metadata:
   - Requests RAT via `ES10b.GetRAT`.
   - Retrieves installed profiles via `ES10b.GetProfilesInfo`.
   - Checks PPR (Profile Policy Rules) against Rules Authorization Table.
8. LPAd collects **End User consent**:
   - If PPRs require strong consent, show descriptive confirmation.
   - If Confirmation Code required, hash as:
     ```
     HashedCode = SHA256(SHA256(ConfirmationCode) | TransactionID)
     ```
   - If rejected or timed out → proceed to Sub-procedure **Download Rejection**.
9. If accepted → proceed to Sub-procedure **Download Confirmation**.

---

## 3.1.3.1 Sub-procedure: Download Rejection

### Trigger Conditions
Triggered by:
- User rejection, timeout, or postponed response.
- Invalid or mismatched ProfileMetadata.
- Unsupported PPR.
- Download failure or metadata inconsistency.

### Sequence Summary
1. LPAd calls:
   ```
   ES10b.CancelSession(TransactionID, reason)
   ```
2. eUICC signs:
   - `euiccCancelSessionSigned = {TransactionID, reason}`
   - Signature with `SK.EUICC.ECDSA`.
3. LPAd calls:
   ```
   ES9+.CancelSession(TransactionID, euiccCancelSessionSigned, euiccCancelSessionSignature)
   ```
4. SM-DP+ verifies signature and matching OID.
5. SM-DP+ sets Profile state to `Error` and, if SM-DS used, deletes Event.
6. Operator notified via `ES2+.HandleDownloadProgressInfo`.
7. Procedure stops with ‘Executed-Success’.

---

## 3.1.3.2 Sub-procedure: Download Confirmation

### Start Condition
User accepts profile download.

### Procedure Steps
1. LPAd calls:
   ```
   ES10b.PrepareDownload(smdpSigned2, smdpSignature2, CERT.DPpb.ECDSA, [HashedCode])
   ```
2. eUICC verifies:
   - Certificate validity (`CERT.DPpb.ECDSA` and `CERT.DPauth.ECDSA` owner consistency).
   - Signature correctness.
   - TransactionID match.
   - Presence of Hashed Confirmation Code if required.
3. eUICC generates new or reuses `otPK.EUICC.ECKA` key pair.
4. Returns:
   ```
   euiccSigned2, euiccSignature2
   ```
5. LPAd calls:
   ```
   ES9+.GetBoundProfilePackage(euiccSigned2, euiccSignature2)
   ```
6. SM-DP+ verifies eUICC signature.
7. If Confirmation Code required:
   - Recomputes expected hash:
     ```
     ExpectedHash = SHA256(StoredHashedCode | TransactionID)
     ```
   - Compares with received hash.
   - Updates retry counter; aborts if exceeded.
8. SM-DP+ generates:
   - One-time key pair `(otPK.DP.ECKA, otSK.DP.ECKA)`
   - Session Keys using CRT, `otPK.EUICC.ECKA`, and `otSK.DP.ECKA` (Annex G)
   - Bound Profile Package (BPP)
9. Optionally notifies Operator (`ES2+.HandleDownloadProgressInfo`).
10. Returns to LPAd:
    ```
    TransactionID, Bound Profile Package
    ```
11. LPAd verifies metadata, confirms consistency with earlier data.
12. If mismatch or new consent needed → may trigger rejection.
13. If approved → continue to **Profile Installation**.

---

## 3.1.3.3 Sub-procedure: Profile Installation

### Purpose
Transfers and installs the Bound Profile Package (BPP) onto the eUICC.

### Steps
1. LPAd transfers `ES8+.InitialiseSecureChannel` through segmented calls to:
   ```
   ES10b.LoadBoundProfilePackage
   ```
   - Includes CRT, `otPK.DP.ECKA`, `smdpSign2`.
2. eUICC verifies and generates Session Keys.
3. LPAd sends:
   - `ES8+.ConfigureISDP`
   - `ES8+.StoreMetadata` (verifies PPRs)
   - `ES8+.ReplaceSessionKeys` (if PPK included)
   - `ES8+.LoadProfileElements`
4. eUICC installs all elements and produces:
   ```
   ProfileInstallationResult = {ProfileInstallationResultData, EuiccSignPIR}
   ```
5. LPAd reports via:
   ```
   ES9+.HandleNotification(ProfileInstallationResult)
   ```
6. SM-DP+ acknowledges and updates state to `Installed` or `Error`.
7. SM-DP+ optionally notifies Operator via `ES2+.HandleDownloadProgressInfo`.
8. If SM-DS used, delete event (Section 3.6.3).
9. LPAd calls:
   ```
   ES10b.RemoveNotificationFromList
   ```
10. eUICC deletes the Profile Installation Result.

---

## 3.1.4 Limitation for Profile Installation
Multiple profiles may be installed depending on available non-volatile memory.

---

## 3.1.5 Error Handling
During download:
- LPAd must not initiate a new download if an RSP session is active.
- eUICC discards session state on:
  - Profile switch
  - Memory reset
  - Power loss or card removal
- LPAd retries after communication failure.
- eUICC returns `6A 88` for unrecognized BPP tags, or `69 85` for invalid commands.

---

## 3.1.6 Profile Lifecycle at SM-DP+

| State | Description |
|--------|--------------|
| **Available** | Profile exists in SM-DP+ inventory. |
| **Allocated** | Reserved for download (no EID linked). |
| **Linked** | Reserved and linked to EID. |
| **Confirmed** | Reserved with Matching ID and optional Confirmation Code. |
| **Released** | Ready for download and installation after operator configuration. |
| **Downloaded** | Bound Profile Package delivered to LPAd. |
| **Installed** | Profile successfully installed on eUICC. |

---

## References
- GSMA Official Document **SGP.22 – RSP Technical Specification v2.5**, Pages 59–77.  
- Sections referenced: 3.1.2–3.1.6, 4.5.2.2, 2.5.4–2.5.6, Annex F, Annex G.
