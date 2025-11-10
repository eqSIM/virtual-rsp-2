#!/usr/bin/env python3
"""
Hybrid Key Agreement Module for SM-DP+ Server
Implements ECDH + ML-KEM-768 hybrid key exchange

This module provides the SM-DP+ side of the hybrid key agreement protocol,
complementing the eUICC-side implementation in v-euicc/src/crypto.c
"""

import os
import sys
from pathlib import Path
import ctypes.util

# Override ctypes library finder to locate liboqs in custom locations
# This is necessary on macOS where DYLD_LIBRARY_PATH is stripped by SIP
liboqs_paths = [
    Path.home() / '.local' / 'lib',  # User-installed location
    Path('/usr/local/lib'),           # System-wide location
    Path('/opt/homebrew/lib'),        # Homebrew on Apple Silicon
]

# Monkey-patch ctypes.util.find_library to check our custom paths
_orig_find_library = ctypes.util.find_library

def _custom_find_library(name):
    """Custom library finder that checks liboqs_paths before falling back to system search"""
    if name == 'oqs':
        for lib_dir in liboqs_paths:
            # Try different library name patterns
            for lib_name in ['liboqs.dylib', 'liboqs.so', 'liboqs.so.8']:
                lib_path = lib_dir / lib_name
                if lib_path.exists():
                    return str(lib_path)
    # Fall back to original finder
    return _orig_find_library(name)

ctypes.util.find_library = _custom_find_library

import hashlib
import struct
from typing import Tuple, Optional

try:
    import oqs
    PQC_AVAILABLE = True
except (ImportError, RuntimeError, Exception) as e:
    PQC_AVAILABLE = False
    print(f"Warning: liboqs-python not available ({e.__class__.__name__}), PQC support disabled")
    print("Note: liboqs must be built as a shared library for Python bindings to work")
    print(f"Searched library paths: {', '.join(str(p) for p in liboqs_paths)}")

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend


class HybridKeyAgreement:
    """
    Hybrid key agreement using ECDH P-256 + ML-KEM-768
    
    Implements the SM-DP+ side of SGP.22 key agreement with PQC support.
    Matches the implementation in v-euicc/src/crypto.c
    """
    
    def __init__(self, enable_pqc: bool = True):
        """
        Initialize hybrid key agreement
        
        Args:
            enable_pqc: Enable PQC support if available
        """
        self.pqc_enabled = enable_pqc and PQC_AVAILABLE
        self.mode = "hybrid" if self.pqc_enabled else "classical"
        
        if self.pqc_enabled:
            self.kem = oqs.KeyEncapsulation("ML-KEM-768")
            print(f"[hybrid_ka] Initialized with ML-KEM-768 (ct={self.kem.details['length_ciphertext']}, "
                  f"ss={self.kem.details['length_shared_secret']})")
        else:
            self.kem = None
            print("[hybrid_ka] Initialized in classical mode")
    
    def perform_key_agreement(self, 
                             euicc_pk_ec: bytes, 
                             euicc_pk_kem: Optional[bytes] = None) -> Tuple[bytes, Optional[bytes], bytes, bytes]:
        """
        Perform hybrid key agreement and derive session keys
        
        Args:
            euicc_pk_ec: eUICC ECDH public key (65 bytes, uncompressed P-256)
            euicc_pk_kem: eUICC ML-KEM public key (1184 bytes, optional)
        
        Returns:
            Tuple of (smdp_pk_ec, smdp_ct_kem, kek, km)
            - smdp_pk_ec: SM-DP+ ECDH public key (65 bytes)
            - smdp_ct_kem: ML-KEM ciphertext (1088 bytes) or None
            - kek: Key Encryption Key (16 bytes)
            - km: Key for MAC (16 bytes)
        """
        # Step 1: Perform classical ECDH
        smdp_private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        smdp_public_key = smdp_private_key.public_key()
        
        # Serialize SM-DP+ public key in uncompressed format
        smdp_pk_ec_bytes = smdp_public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        
        # Load eUICC public key
        euicc_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), euicc_pk_ec
        )
        
        # Perform ECDH
        shared_key = smdp_private_key.exchange(ec.ECDH(), euicc_public_key)
        Z_ec = shared_key  # 32 bytes
        
        print(f"[hybrid_ka] ECDH completed: Z_ec={len(Z_ec)} bytes")
        
        # Step 2: Perform ML-KEM encapsulation if in hybrid mode
        smdp_ct_kem = None
        Z_kem = None
        
        if self.pqc_enabled and euicc_pk_kem and len(euicc_pk_kem) == 1184:
            try:
                # ML-KEM encapsulation
                ciphertext, shared_secret = self.kem.encap_secret(euicc_pk_kem)
                smdp_ct_kem = ciphertext  # 1088 bytes
                Z_kem = shared_secret     # 32 bytes
                
                print(f"[hybrid_ka] ML-KEM encapsulation completed: ct={len(smdp_ct_kem)} bytes, "
                      f"Z_kem={len(Z_kem)} bytes")
                
            except Exception as e:
                print(f"[hybrid_ka] ML-KEM encapsulation failed: {e}, falling back to classical")
                Z_kem = None
                smdp_ct_kem = None
        
        # Step 3: Derive session keys
        if Z_kem is not None:
            # Hybrid KDF (matches v-euicc implementation)
            kek, km = self._derive_session_keys_hybrid(Z_ec, Z_kem)
            print("[hybrid_ka] Hybrid session keys derived")
        else:
            # Classical KDF (SGP.22 Annex G)
            kek, km = self._derive_session_keys_classical(Z_ec)
            print("[hybrid_ka] Classical session keys derived")
        
        return smdp_pk_ec_bytes, smdp_ct_kem, kek, km
    
    def _derive_session_keys_classical(self, Z: bytes) -> Tuple[bytes, bytes]:
        """
        Classical session key derivation (SGP.22 Annex G)
        
        Args:
            Z: Shared secret (32 bytes)
        
        Returns:
            Tuple of (KEK, KM) each 16 bytes
        """
        # KEK = SHA256(Z || 0x00000001)[0:16]
        kek_input = Z + struct.pack('>I', 1)
        kek_hash = hashlib.sha256(kek_input).digest()
        kek = kek_hash[:16]
        
        # KM = SHA256(Z || 0x00000002)[0:16]
        km_input = Z + struct.pack('>I', 2)
        km_hash = hashlib.sha256(km_input).digest()
        km = km_hash[:16]
        
        return kek, km
    
    def _derive_session_keys_hybrid(self, Z_ec: bytes, Z_kem: bytes) -> Tuple[bytes, bytes]:
        """
        Hybrid session key derivation (nested KDF, NIST SP 800-56C style)
        
        Must match the implementation in v-euicc/src/crypto.c:derive_session_keys_hybrid()
        
        Args:
            Z_ec: ECDH shared secret (32 bytes)
            Z_kem: ML-KEM shared secret (32 bytes)
        
        Returns:
            Tuple of (KEK, KM) each 16 bytes
        """
        # Step 1: Domain-separated extraction (using HKDF with salt as label)
        # Extract K_ec from Z_ec with label "ECDH-P256"
        hkdf_ec = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"ECDH-P256",
            info=b"",
            backend=default_backend()
        )
        K_ec = hkdf_ec.derive(Z_ec)
        
        # Extract K_kem from Z_kem with label "ML-KEM-768"
        hkdf_kem = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"ML-KEM-768",
            info=b"",
            backend=default_backend()
        )
        K_kem = hkdf_kem.derive(Z_kem)
        
        # Step 2: Combine intermediate keys
        combined = K_ec + K_kem  # 64 bytes
        
        # Step 3: Final KDF using SGP.22 Annex G format
        # KEK = SHA256(combined || 0x00000001)[0:16]
        kek_input = combined + struct.pack('>I', 1)
        kek_hash = hashlib.sha256(kek_input).digest()
        kek = kek_hash[:16]
        
        # KM = SHA256(combined || 0x00000002)[0:16]
        km_input = combined + struct.pack('>I', 2)
        km_hash = hashlib.sha256(km_input).digest()
        km = km_hash[:16]
        
        return kek, km


# Import serialization for EC key operations
from cryptography.hazmat.primitives import serialization


def test_hybrid_ka():
    """Test hybrid key agreement"""
    print("\n=== Testing Hybrid Key Agreement ===\n")
    
    # Generate eUICC keys (simulated)
    euicc_private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    euicc_public_key = euicc_private_key.public_key()
    euicc_pk_ec = euicc_public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    
    print(f"eUICC ECDH public key: {len(euicc_pk_ec)} bytes")
    
    # Test classical mode
    print("\n--- Classical Mode ---")
    ka_classical = HybridKeyAgreement(enable_pqc=False)
    smdp_pk, ct, kek, km = ka_classical.perform_key_agreement(euicc_pk_ec, None)
    print(f"SM-DP+ public key: {len(smdp_pk)} bytes")
    print(f"Ciphertext: {ct}")
    print(f"KEK: {kek.hex()[:32]}...")
    print(f"KM: {km.hex()[:32]}...")
    
    # Test hybrid mode
    if PQC_AVAILABLE:
        print("\n--- Hybrid Mode ---")
        
        # Generate eUICC ML-KEM key (simulated)
        kem = oqs.KeyEncapsulation("ML-KEM-768")
        euicc_pk_kem = kem.generate_keypair()
        print(f"eUICC ML-KEM public key: {len(euicc_pk_kem)} bytes")
        
        ka_hybrid = HybridKeyAgreement(enable_pqc=True)
        smdp_pk, ct, kek, km = ka_hybrid.perform_key_agreement(euicc_pk_ec, euicc_pk_kem)
        print(f"SM-DP+ public key: {len(smdp_pk)} bytes")
        print(f"Ciphertext: {len(ct) if ct else 0} bytes")
        print(f"KEK: {kek.hex()[:32]}...")
        print(f"KM: {km.hex()[:32]}...")
    
    print("\n=== Test Complete ===\n")


if __name__ == "__main__":
    test_hybrid_ka()

