# Modifications to Open-Source Components

**[← Previous: v-euicc Internals](04-V-EUICC.md)** | **[Index](README.md)** | **[Next: Dev GUI →](06-GUI-CONTROL-CENTER.md)**

---

## Table of Contents
1. [lpac (Local Profile Assistant)](#1-lpac-local-profile-assistant)
2. [osmo-smdpp (SM-DP+ Server)](#2-osmo-smdpp-sm-dp-server)
3. [pySim Libraries](#3-pysim-libraries)

---

This project leverages several open-source tools. To achieve end-to-end Virtual RSP functionality, we have made specific modifications to `lpac` and `osmo-smdpp`.

## 1. lpac (Local Profile Assistant)

The core change to `lpac` is the addition of a **Socket APDU Driver**.

### Socket Driver Implementation
- **File**: `lpac/driver/apdu/socket.c`
- **Purpose**: Allows `lpac` to communicate with the virtual eSIM over a network socket instead of using physical smart card readers (PC/SC) or AT commands.
- **Protocol**: It uses the same JSON-over-TCP protocol as lpac's `stdio` driver, following the schema in `lpac/docs/backends/stdio-schema.json`.

### Request Format
```json
{
  "func": "transmit",
  "param": "<hex_encoded_apdu>"
}
```

### Response Format
```json
{
  "code": 0,
  "data": "<hex_encoded_response>"
}
```

### Environment Variables Added
- `LPAC_APDU_SOCKET_HOST`: Hostname or IP address of the v-euicc daemon (default: `127.0.0.1`).
- `LPAC_APDU_SOCKET_PORT`: TCP port (default: `8765`).

### Integration
The socket driver is automatically compiled as part of the standard lpac build. To use it, simply set `LPAC_APDU=socket`.

## 2. osmo-smdpp (SM-DP+ Server)

We extended the SM-DP+ server from the `pySim` project with administrative and monitoring features.

### MNO Management REST API
- **File**: `pysim/osmo-smdpp.py` (lines 945-1028)
- **Purpose**: Provides RESTful endpoints for MNO operators to manage the SM-DP+ server remotely.

**Endpoints Added**:

| Method | Endpoint | Description | Response |
|:-------|:---------|:------------|:---------|
| `GET` | `/mno/profiles` | Lists all `.der` profile packages | JSON array of `{matching_id, size, modified}` |
| `POST` | `/mno/profiles` | Upload new profile package | 200 OK or error |
| `DELETE` | `/mno/profiles/<id>` | Delete profile by matching ID | 200 OK or 404 |
| `GET` | `/mno/sessions` | Active RSP sessions | JSON array of `{transaction_id, eid, matching_id, started_at}` |
| `GET` | `/mno/downloads` | Download history log | JSON array of download records |
| `GET` | `/mno/stats` | Dashboard statistics | JSON object with counts and success rate |

### Persistence & History
- **`DownloadHistoryStore`** (lines 152-197): A new class that persists every profile download event to `pysim/smdpp-data/download_history.json`.

**Tracked Data**:
- Transaction ID (unique per RSP session)
- EID of the requesting device
- Profile ICCID and Matching ID
- Download status (`bpp_sent`, `success`, `failed`)
- Timestamp (ISO 8601 format)
- Final installation result (from handleNotification)

**Hooks**:
- `getBoundProfilePackage()` (line 811): Records when a BPP is sent.
- `handleNotification()` (line 857, 864): Updates the record with the final result.

### Session Management Improvements
- Added `--in-memory` (`-m`) flag to use ephemeral session storage.
- **Why**: Prevents stale sessions from accumulating across server restarts during development.
- **Implementation**: Passes `in_memory=True` to `RspSessionStore` constructor (line 483).

## 3. pySim Libraries

### ASN.1 OID Decoding Fix
- **Location**: `pysim/osmo-smdpp.py` (lines 31-108)
- **Issue**: The `asn1tools` library has a known bug when decoding OBJECT IDENTIFIERs with large second arcs (e.g., `2.999.10`).
- **Fix**: Implemented a custom `fixed_decode_object_identifier()` function that correctly applies the ASN.1 rules for arc splitting.
- **Impact**: Required for GSMA test certificates which use custom OIDs.

### Session Tracking Enhancement
- **Change**: Modified `RspSessionState` to store the device's EID as soon as authentication completes.
- **Location**: `pysim/osmo-smdpp.py` (line 680-681)
- **Benefit**: Enables the MNO Console to display real-time session information with device identification.

```python
# Extract EID from eUICC certificate
ss.eid = ss.euicc_cert.subject.get_attributes_for_oid(
    x509.oid.NameOID.SERIAL_NUMBER
)[0].value
```

---

**[← Previous: v-euicc Internals](04-V-EUICC.md)** | **[Index](README.md)** | **[Next: Dev GUI →](06-GUI-CONTROL-CENTER.md)**
