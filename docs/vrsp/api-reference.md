# API Reference

Complete API reference for Virtual RSP components including ES9+, ES10b, and internal interfaces.

## ES9+ API (SM-DP+ ↔ LPA)

### Authentication Endpoints

#### initiateAuthentication

**HTTP Method**: `POST`

**URL**: `/gsma/rsp2/es9plus/initiateAuthentication`

**Purpose**: Initiate mutual authentication and establish session

**Request Body**:
```json
{
    "transactionId": "string (optional)",
    "euiccChallenge": "base64-encoded-16-bytes",
    "euiccInfo2": "base64-encoded-euicc-info"
}
```

**Response Body**:
```json
{
    "transactionId": "string",
    "serverSigned1": "base64-encoded-server-signed-data",
    "serverSignature1": "base64-encoded-signature",
    "serverCertificate": "base64-encoded-cert-chain"
}
```

**Error Responses**:
```json
{
    "errorCode": "8.2",
    "subjectCode": "3.8",
    "errorMessage": "Refused"
}
```

#### authenticateClient

**HTTP Method**: `POST`

**URL**: `/gsma/rsp2/es9plus/authenticateClient`

**Purpose**: Complete mutual authentication with client verification

**Request Body**:
```json
{
    "transactionId": "string",
    "authenticateServerResponse": "base64-encoded-client-response",
    "euiccSignature1": "base64-encoded-client-signature"
}
```

**Response Body**:
```json
{
    "transactionId": "string",
    "serverSigned2": "base64-encoded-server-signed-data",
    "serverSignature2": "base64-encoded-signature"
}
```

### Profile Management Endpoints

#### getBoundProfilePackage

**HTTP Method**: `POST`

**URL**: `/gsma/rsp2/es9plus/getBoundProfilePackage`

**Purpose**: Retrieve encrypted profile package for installation

**Request Body**:
```json
{
    "transactionId": "string",
    "prepareDownloadResponse": "base64-encoded-prepare-download-response"
}
```

**Response Body**:
```json
{
    "transactionId": "string",
    "boundProfilePackage": "base64-encoded-bpp-data"
}
```

#### handleNotification

**HTTP Method**: `POST`

**URL**: `/gsma/rsp2/es9plus/handleNotification`

**Purpose**: Handle profile installation notifications

**Request Body**:
```json
{
    "pendingNotification": "base64-encoded-notification-data"
}
```

**Response**: HTTP 204 (No Content)

#### cancelSession

**HTTP Method**: `POST`

**URL**: `/gsma/rsp2/es9plus/cancelSession`

**Purpose**: Cancel active session and clean up resources

**Request Body**:
```json
{
    "transactionId": "string",
    "cancelSessionResponseOk": {
        "transactionId": "string",
        "smdpOid": "string",
        "reason": "integer"
    },
    "euiccCancelSessionSignature": "base64-encoded-signature"
}
```

**Response**: HTTP 200

## ES10b Commands (LPA ↔ eUICC)

### APDU Command Format

**ES10b commands use extended APDU format**:
```c
CLA | INS | P1 | P2 | LC | DATA | LE
```

**Common Values**:
- **CLA**: `0x81` (extended length)
- **INS**: `0xE2` (ES10x commands)
- **P1/P2**: Command-specific
- **LC**: Data length (2 bytes for extended)
- **DATA**: ES10x command data
- **LE**: Expected response length

### Command Reference

#### AuthenticateServerRequest (0xBF38)

**Purpose**: Send server authentication data to eUICC

**APDU Data Structure**:
```c
BF38 LEN [
    serverSigned1 TLV,
    serverSignature1 TLV,
    serverCertificate TLV
]
```

**Response**: `9000` (success) or error code

#### AuthenticateServerResponse (0xBF38)

**Purpose**: Return client authentication data to LPA

**APDU Data Structure**:
```c
BF38 LEN [
    euiccSigned1 TLV,
    euiccSignature1 TLV
]
```

#### PrepareDownloadRequest (0xBF21)

**Purpose**: Prepare eUICC for profile download

**APDU Data Structure**:
```c
BF21 LEN [
    smdpSigned2 TLV,
    smdpSignature2 TLV,
    hashCc TLV (optional),
    smdpCertificate TLV
]
```

**Response**: `9000` (success) or error code

#### InitialiseSecureChannelRequest (0xBF23)

**Purpose**: Establish secure channel for profile installation

**APDU Data Structure**:
```c
BF23 LEN [
    transactionId TLV,
    hostId TLV,
    smdpOtpk TLV,
    euiccOtpk TLV
]
```

**Response**: `9000` (success) or error code

#### Profile Data Commands (0xA0, 0xA1, 0xA2, 0xA3)

**Purpose**: Transfer encrypted profile data segments

**APDU Data Structure**:
```c
// A0 (ConfigureISDP):
A0 LEN [encrypted_configureISDP_data]

// A1 (StoreMetadata):
A1 LEN [MACed_metadata_data]

// A2 (ReplaceSessionKeys):
A2 LEN [encrypted_session_keys_data]

// A3 (Profile Data):
A3 LEN [encrypted_profile_package_data]
```

**Response**: `9000` (success) or error code

#### CancelSessionRequest (0xBF41)

**Purpose**: Cancel active session

**APDU Data Structure**:
```c
BF41 LEN [
    transactionId TLV,
    smdpOid TLV,
    reason TLV
]
```

**Response**: `9000` (success) or error code

## Data Structures

### ASN.1 Definitions

#### TransactionId
```asn1
TransactionId ::= OCTET STRING (SIZE(16))
```

#### EuiccInfo2
```asn1
EuiccInfo2 ::= SEQUENCE {
    profileVersion VersionType,
    svn SvnType,
    euiccFirmwareVer VersionType,
    extCardResource OCTET STRING OPTIONAL,
    uiccCapability OCTET STRING OPTIONAL,
    ts102241Version VersionType OPTIONAL,
    globalplatformVersion VersionType OPTIONAL,
    rspCapability RspCapability,
    euiccCiPKIdList SEQUENCE OF SubjectKeyIdentifier,
    euiccCategory OCTET STRING OPTIONAL,
    forbiddenProfilePolicyRules SEQUENCE OF ProfilePolicy OPTIONAL
}
```

#### AuthenticateServerResponse
```asn1
AuthenticateServerResponse ::= CHOICE {
    authenticateResponseOk AuthenticateResponseOk,
    authenticateResponseError INTEGER {
        undefinedError(127)
    }
}
```

#### BoundProfilePackage
```asn1
BoundProfilePackage ::= [54] SEQUENCE {
    initialiseSecureChannelRequest [35] InitialiseSecureChannelRequest,
    firstSequenceOf87 [0] SEQUENCE OF [7] OCTET STRING,
    sequenceOf88 [1] SEQUENCE OF [8] OCTET STRING,
    secondSequenceOf87 [2] SEQUENCE OF [7] OCTET STRING OPTIONAL,
    sequenceOf86 [3] SEQUENCE OF [6] OCTET STRING
}
```

## Cryptographic Functions

### ECDSA Operations

#### Signature Generation
```c
int ecdsa_sign(const uint8_t *data, uint32_t data_len,
               EVP_PKEY *private_key,
               uint8_t **signature, uint32_t *signature_len);
```

**Parameters**:
- `data`: Data to sign
- `data_len`: Length of data
- `private_key`: ECDSA private key
- `signature`: Output signature buffer (DER format)
- `signature_len`: Length of signature

**Returns**: 0 on success, -1 on error

#### Signature Verification
```python
def _ecdsa_verify(certificate, signature, data):
    """Verify ECDSA signature using certificate public key"""
```

**Parameters**:
- `certificate`: X.509 certificate containing public key
- `signature`: Signature to verify (DER format)
- `data`: Original data that was signed

**Returns**: `True` if signature is valid, `False` otherwise

### BSP Key Derivation

```python
def derive_bsp_keys(shared_secret, eid, host_id):
    """Derive BSP keys from ECDH shared secret"""

    # KDF input
    kdf_input = b'\x88' + shared_secret + eid + host_id

    # Derive keys
    s_enc = hkdf(kdf_input, length=16, salt=b'\x00'*16)
    s_mac = hkdf(kdf_input, length=16, salt=b'\x11'*16)
    s_rmac = hkdf(kdf_input, length=16, salt=b'\x22'*16)

    return BspInstance(s_enc, s_mac, s_rmac)
```

## Internal APIs

### eUICC State Management

```c
// Initialize eUICC state
void euicc_state_init(struct euicc_state *state);

// Reset eUICC state
void euicc_state_reset(struct euicc_state *state);

// Load certificates from files
int euicc_state_load_certificates(struct euicc_state *state, const char *cert_dir);
```

### APDU Processing

```c
// Process APDU command
int apdu_handle_transmit(struct euicc_state *state,
                        uint8_t **response, uint32_t *response_len,
                        const uint8_t *command, uint32_t command_len);

// Generate APDU response
int apdu_generate_response(struct euicc_state *state,
                          uint16_t sw, uint8_t *data, uint32_t data_len,
                          uint8_t **response, uint32_t *response_len);
```

### Cryptographic Utilities

```c
// Generate EC key pair
EVP_PKEY *generate_ec_keypair(void);

// Extract public key in uncompressed format
uint8_t *extract_ec_public_key_uncompressed(EVP_PKEY *keypair, uint32_t *out_len);

// Generate secure random data
int generate_random(uint8_t *buffer, size_t length);
```

## Response Codes

### APDU Status Words

| Status Word | Description | Meaning |
|-------------|-------------|---------|
| `9000` | Success | Command completed successfully |
| `6D00` | INS not supported | Command not recognized |
| `6F00` | Technical problem | Internal error |
| `6981` | Command incompatible | Command not allowed in current state |
| `6982` | Security status not satisfied | Authentication required |

### ES9+ Error Codes

| Error Code | Subject Code | Description |
|------------|--------------|-------------|
| `8.1` | `6.1` | Invalid signature |
| `8.2` | `3.8` | Access denied |
| `8.4` | `3.5` | Invalid profile package |
| `8.8` | `3.10` | Invalid SM-DP+ OID |
| `8.10` | `3.9` | Session expired |

## Network Protocol

### HTTP Headers

**ES9+ API**:
```
POST /gsma/rsp2/es9plus/initiateAuthentication HTTP/1.1
Host: testsmdpplus1.example.com:8443
Content-Type: application/json
User-Agent: gsma-rsp-lpad
```

**Response Headers**:
```
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 1221
```

### TLS Configuration

**Required TLS Version**: TLS 1.3

**Certificate Validation**:
- Server certificate must chain to GSMA root CA
- Certificate must be valid (not expired, not revoked)
- Subject Alternative Name must contain correct SM-DP+ OID

## Error Handling

### Exception Types

**API Errors**:
```python
class ApiError(Exception):
    def __init__(self, error_code, subject_code, message):
        self.error_code = error_code
        self.subject_code = subject_code
        self.message = message
```

**APDU Errors**:
```c
// Error response generation
int apdu_send_error(uint16_t sw, uint8_t **response, uint32_t *response_len);
```

## Testing APIs

### Test Utilities

```python
# Test certificate validation
def test_certificate_validation():
    cert_data = load_test_certificate()
    assert validate_certificate_chain(cert_data, gsma_root)

# Test signature operations
def test_ecdsa_operations():
    data = b"test data"
    signature = ecdsa_sign(data, private_key)
    assert verify_ecdsa_signature(public_key, signature, data)

# Test BPP encoding/decoding
def test_bpp_operations():
    upp = UnprotectedProfilePackage.from_der(profile_data)
    bpp = BoundProfilePackage.from_upp(upp)
    bpp_data = bpp.encode(session_state, smdp_cert)

    # Verify BPP structure
    assert bpp_data.startswith(b'\xbf\x23')
    assert b'\xa3' in bpp_data
```

## Performance Metrics

### Benchmark Results

**Authentication Performance**:
- Mutual authentication: ~50ms
- Certificate validation: ~10ms
- Signature verification: ~5ms

**Profile Operations**:
- Profile package binding: ~100ms
- BPP command processing: ~20ms per command
- Profile installation: ~200ms

**Memory Usage**:
- Base eUICC memory: ~2MB
- Profile buffer capacity: ~10MB
- Peak memory during installation: ~15MB

## Next Steps

- [🛠️ Development Guide](development)
- [❓ Troubleshooting](troubleshooting)
