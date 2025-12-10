ML-DSA-87 Post-Quantum Certificates
Generated: 2025-12-10T04:41:31.588244

This directory contains ML-DSA-87 (Dilithium) certificates that replace
the traditional GSMA PKI hierarchy with post-quantum cryptography.

Files:
------
eUICC:
  - euicc_cert_mldsa87.der    : Self-signed ML-DSA certificate
  - euicc_sk_mldsa87.key      : Private signing key
  - euicc_pk_mldsa87.pub      : Public verification key

SM-DP+:
  - smdp_cert_mldsa87.der     : Self-signed ML-DSA certificate
  - smdp_sk_mldsa87.key       : Private signing key
  - smdp_pk_mldsa87.pub       : Public verification key

Root CA (Trust Anchor):
  - root_ca_mldsa87.der       : Self-signed ML-DSA certificate
  - root_ca_sk_mldsa87.key    : Private signing key
  - root_ca_pk_mldsa87.pub    : Public verification key

Security Properties:
--------------------
- Algorithm: ML-DSA-87 (NIST FIPS 204)
- Security Level: NIST Level 5 (~256-bit classical security)
- Quantum Security: Exceeds AES-256
- Signature Size: ~4627 bytes
- Public Key Size: ~4864 bytes
- Secret Key Size: ~2560 bytes

Advantages over GSMA PKI:
--------------------------
✓ Quantum-resistant signatures
✓ No reliance on centralized CA infrastructure
✓ Self-signed certificates with direct trust
✓ Simpler trust model
✓ No certificate expiration issues
✓ Full control over cryptographic operations

Usage:
------
The certificates are used during SGP.22 mutual authentication:
1. eUICC presents its ML-DSA certificate
2. SM-DP+ verifies the ML-DSA signature
3. SM-DP+ presents its ML-DSA certificate
4. eUICC verifies the ML-DSA signature
5. Both parties establish trust without traditional PKI

This replaces the GSMA EUM/EIC certificate hierarchy with a simpler,
quantum-safe trust model.
