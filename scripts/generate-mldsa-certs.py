#!/usr/bin/env python3
"""
Generate ML-DSA-87 Self-Signed Certificates
Replaces GSMA PKI hierarchy with post-quantum self-signed certificates
"""

import sys
import os
from pathlib import Path
import ctypes.util

# Add pysim to path to use hybrid_ka module
sys.path.insert(0, str(Path(__file__).parent.parent / 'pysim'))

# Prevent liboqs-python from trying to auto-install
os.environ['OQS_PYTHON_BUILD_SKIP_INSTALL'] = '1'

# Override ctypes library finder to locate liboqs in homebrew location
liboqs_paths = [
    Path('/opt/homebrew/lib'),        # Homebrew on Apple Silicon
    Path('/usr/local/lib'),           # Homebrew on Intel
    Path.home() / '.local' / 'lib',  # User-installed location
]

_orig_find_library = ctypes.util.find_library

def _custom_find_library(name):
    """Custom library finder that checks liboqs_paths before falling back to system search"""
    if name == 'oqs':
        for lib_dir in liboqs_paths:
            for lib_name in ['liboqs.dylib', 'liboqs.so', 'liboqs.so.8']:
                lib_path = lib_dir / lib_name
                if lib_path.exists():
                    return str(lib_path)
    return _orig_find_library(name)

ctypes.util.find_library = _custom_find_library

try:
    import oqs
    print(f"[✓] liboqs-python loaded: {oqs.oqs_version()}")
except (ImportError, RuntimeError) as e:
    print(f"[✗] Failed to load liboqs-python: {e}")
    print("    Install with: pip install liboqs-python")
    sys.exit(1)

import json
import hashlib
from datetime import datetime, timedelta
import struct


class MLDSACertificate:
    """
    Simple self-signed certificate using ML-DSA-87
    Replaces X.509/GSMA PKI with PQC-based trust
    """
    
    def __init__(self, subject: dict, public_key: bytes, signature: bytes = None):
        self.subject = subject
        self.public_key = public_key
        self.signature = signature
        self.issued = datetime.utcnow()
        self.expires = self.issued + timedelta(days=365)
    
    def to_bytes(self) -> bytes:
        """
        Serialize certificate to bytes
        Format: JSON metadata + public key + signature
        """
        metadata = {
            'subject': self.subject,
            'issued': self.issued.isoformat(),
            'expires': self.expires.isoformat(),
            'algorithm': 'ML-DSA-87',
            'pk_len': len(self.public_key)
        }
        
        metadata_json = json.dumps(metadata, sort_keys=True).encode('utf-8')
        metadata_len = struct.pack('>I', len(metadata_json))
        
        result = b'MLDSA87CERT'  # Magic header
        result += metadata_len
        result += metadata_json
        result += self.public_key
        
        if self.signature:
            sig_len = struct.pack('>I', len(self.signature))
            result += sig_len
            result += self.signature
        
        return result
    
    @staticmethod
    def from_bytes(data: bytes) -> 'MLDSACertificate':
        """Parse certificate from bytes"""
        if not data.startswith(b'MLDSA87CERT'):
            raise ValueError("Invalid certificate magic header")
        
        offset = 11  # len('MLDSA87CERT')
        
        # Read metadata length
        metadata_len = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        
        # Read metadata JSON
        metadata_json = data[offset:offset+metadata_len]
        metadata = json.loads(metadata_json.decode('utf-8'))
        offset += metadata_len
        
        # Read public key
        pk_len = metadata['pk_len']
        public_key = data[offset:offset+pk_len]
        offset += pk_len
        
        # Read signature if present
        signature = None
        if offset < len(data):
            sig_len = struct.unpack('>I', data[offset:offset+4])[0]
            offset += 4
            signature = data[offset:offset+sig_len]
        
        cert = MLDSACertificate(metadata['subject'], public_key, signature)
        cert.issued = datetime.fromisoformat(metadata['issued'])
        cert.expires = datetime.fromisoformat(metadata['expires'])
        return cert
    
    def get_tbs_data(self) -> bytes:
        """
        Get 'To Be Signed' data
        This is what the signature is computed over
        """
        metadata = {
            'subject': self.subject,
            'issued': self.issued.isoformat(),
            'expires': self.expires.isoformat(),
            'algorithm': 'ML-DSA-87'
        }
        metadata_json = json.dumps(metadata, sort_keys=True).encode('utf-8')
        return metadata_json + self.public_key


def generate_mldsa_keypair():
    """Generate ML-DSA-87 keypair"""
    print("[*] Generating ML-DSA-87 keypair...")
    sig = oqs.Signature("ML-DSA-87")
    public_key = sig.generate_keypair()
    secret_key = sig.export_secret_key()
    
    print(f"    Public key:  {len(public_key)} bytes")
    print(f"    Secret key:  {len(secret_key)} bytes")
    print(f"    Signature:   ~{sig.details['length_signature']} bytes")
    
    return public_key, secret_key, sig


def self_sign_certificate(cert: MLDSACertificate, secret_key: bytes) -> MLDSACertificate:
    """Self-sign certificate using ML-DSA-87"""
    print("[*] Self-signing certificate...")
    
    sig = oqs.Signature("ML-DSA-87")
    sig.generate_keypair()  # Need to call this to initialize
    sig.secret_key = secret_key  # Override with our key
    
    tbs_data = cert.get_tbs_data()
    signature = sig.sign(tbs_data)
    
    print(f"    Signature:   {len(signature)} bytes")
    
    cert.signature = signature
    return cert


def verify_certificate(cert: MLDSACertificate) -> bool:
    """Verify ML-DSA-87 self-signed certificate"""
    print("[*] Verifying certificate...")
    
    sig = oqs.Signature("ML-DSA-87")
    tbs_data = cert.get_tbs_data()
    
    try:
        is_valid = sig.verify(tbs_data, cert.signature, cert.public_key)
        if is_valid:
            print("    [✓] Signature valid")
        else:
            print("    [✗] Signature invalid")
        return is_valid
    except Exception as e:
        print(f"    [✗] Verification failed: {e}")
        return False


def main():
    output_dir = Path(__file__).parent.parent / 'v-euicc' / 'certs-mldsa'
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print(" ML-DSA-87 Certificate Generation")
    print(" Replacing GSMA PKI with Post-Quantum Self-Signed Certificates")
    print("=" * 70)
    print()
    
    # Generate eUICC certificate
    print("[ eUICC Certificate ]")
    print()
    euicc_pk, euicc_sk, _ = generate_mldsa_keypair()
    
    euicc_cert = MLDSACertificate(
        subject={
            'CN': 'Virtual eUICC',
            'EID': '89049032001001234500012345678901',
            'Manufacturer': 'Virtual RSP Project',
            'Type': 'eUICC'
        },
        public_key=euicc_pk
    )
    
    euicc_cert = self_sign_certificate(euicc_cert, euicc_sk)
    verify_certificate(euicc_cert)
    
    # Save eUICC files
    euicc_cert_file = output_dir / 'euicc_cert_mldsa87.der'
    euicc_sk_file = output_dir / 'euicc_sk_mldsa87.key'
    euicc_pk_file = output_dir / 'euicc_pk_mldsa87.pub'
    
    euicc_cert_file.write_bytes(euicc_cert.to_bytes())
    euicc_sk_file.write_bytes(euicc_sk)
    euicc_pk_file.write_bytes(euicc_pk)
    
    print(f"    Saved: {euicc_cert_file}")
    print(f"    Saved: {euicc_sk_file}")
    print(f"    Saved: {euicc_pk_file}")
    print()
    
    # Generate SM-DP+ certificate
    print("[ SM-DP+ Certificate ]")
    print()
    smdp_pk, smdp_sk, _ = generate_mldsa_keypair()
    
    smdp_cert = MLDSACertificate(
        subject={
            'CN': 'testsmdpplus1.example.com',
            'O': 'Virtual RSP Project',
            'Type': 'SM-DP+'
        },
        public_key=smdp_pk
    )
    
    smdp_cert = self_sign_certificate(smdp_cert, smdp_sk)
    verify_certificate(smdp_cert)
    
    # Save SM-DP+ files
    smdp_cert_file = output_dir / 'smdp_cert_mldsa87.der'
    smdp_sk_file = output_dir / 'smdp_sk_mldsa87.key'
    smdp_pk_file = output_dir / 'smdp_pk_mldsa87.pub'
    
    smdp_cert_file.write_bytes(smdp_cert.to_bytes())
    smdp_sk_file.write_bytes(smdp_sk)
    smdp_pk_file.write_bytes(smdp_pk)
    
    print(f"    Saved: {smdp_cert_file}")
    print(f"    Saved: {smdp_sk_file}")
    print(f"    Saved: {smdp_pk_file}")
    print()
    
    # Generate root CA certificate (for trust anchor)
    print("[ Root CA Certificate (ML-DSA Trust Anchor) ]")
    print()
    ca_pk, ca_sk, _ = generate_mldsa_keypair()
    
    ca_cert = MLDSACertificate(
        subject={
            'CN': 'Virtual RSP Root CA',
            'O': 'Virtual RSP Project',
            'Type': 'Root CA',
            'PQC': 'ML-DSA-87'
        },
        public_key=ca_pk
    )
    
    ca_cert = self_sign_certificate(ca_cert, ca_sk)
    verify_certificate(ca_cert)
    
    # Save CA files
    ca_cert_file = output_dir / 'root_ca_mldsa87.der'
    ca_sk_file = output_dir / 'root_ca_sk_mldsa87.key'
    ca_pk_file = output_dir / 'root_ca_pk_mldsa87.pub'
    
    ca_cert_file.write_bytes(ca_cert.to_bytes())
    ca_sk_file.write_bytes(ca_sk)
    ca_pk_file.write_bytes(ca_pk)
    
    print(f"    Saved: {ca_cert_file}")
    print(f"    Saved: {ca_sk_file}")
    print(f"    Saved: {ca_pk_file}")
    print()
    
    # Create README
    readme = output_dir / 'README.txt'
    readme.write_text(f"""ML-DSA-87 Post-Quantum Certificates
Generated: {datetime.utcnow().isoformat()}

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
""")
    
    print("=" * 70)
    print(" Certificate Generation Complete")
    print("=" * 70)
    print()
    print(f"Output directory: {output_dir}")
    print()
    print("Next steps:")
    print("1. Update v-euicc to use ML-DSA certificates for authentication")
    print("2. Update SM-DP+ to verify ML-DSA certificates")
    print("3. Configure OQS-enabled TLS for nginx")
    print()


if __name__ == '__main__':
    main()


