#!/usr/bin/env python3
"""
End-to-End Post-Quantum Cryptography Test
Demonstrates full hybrid key agreement between eUICC and SM-DP+
"""

import sys
sys.path.insert(0, 'pysim')

from hybrid_ka import HybridKeyAgreement, PQC_AVAILABLE
import os

print("╔══════════════════════════════════════════════════════════════════╗")
print("║  END-TO-END PQC TEST: Full Hybrid Key Agreement Simulation      ║")
print("╚══════════════════════════════════════════════════════════════════╝")
print()

# Step 1: Check PQC availability
print("STEP 1: Verify PQC Support")
print("─" * 70)
print(f"PQC Available: {PQC_AVAILABLE}")
if not PQC_AVAILABLE:
    print("❌ Cannot proceed without PQC support")
    sys.exit(1)
print("✅ Both sides have ML-KEM-768 support")
print()

# Step 2: eUICC generates hybrid keypairs
print("STEP 2: eUICC Generates Hybrid Keypairs")
print("─" * 70)
print("Simulating eUICC-side key generation...")

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import oqs

# Generate ECDH keypair (simulating eUICC)
euicc_ec_private = ec.generate_private_key(ec.SECP256R1(), default_backend())
euicc_ec_public = euicc_ec_private.public_key()
euicc_otpk = euicc_ec_public.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)

# Generate ML-KEM keypair (simulating eUICC)
euicc_kem = oqs.KeyEncapsulation("ML-KEM-768")
euicc_pk_kem = euicc_kem.generate_keypair()
euicc_sk_kem = euicc_kem.export_secret_key()

print(f"✅ ECDH Public Key (otPK.EUICC.ECKA): {len(euicc_otpk)} bytes")
print(f"✅ ML-KEM Public Key (PK.KEM.EUICC): {len(euicc_pk_kem)} bytes")
print(f"   Expected: 1184 bytes for ML-KEM-768")
print()

# Step 3: SM-DP+ performs hybrid key agreement
print("STEP 3: SM-DP+ Performs Hybrid Key Agreement")
print("─" * 70)
print("Simulating SM-DP+ side...")

smdp_ka = HybridKeyAgreement(enable_pqc=True)

# SM-DP+ performs key agreement with eUICC's public keys
smdp_otpk, smdp_ct_kem, kek, km = smdp_ka.perform_key_agreement(
    euicc_otpk, 
    euicc_pk_kem
)

print(f"✅ Generated SM-DP+ ECDH Public Key: 65 bytes")
print(f"✅ Generated ML-KEM Ciphertext: {len(smdp_ct_kem)} bytes")
print(f"   Expected: 1088 bytes for ML-KEM-768")
print(f"✅ Derived KEK (Key Encryption Key): {len(kek)} bytes")
print(f"✅ Derived KM (Key for MAC): {len(km)} bytes")
print()

# Show ciphertext preview
print("   ML-KEM Ciphertext (first 64 bytes):")
print(f"   {smdp_ct_kem[:64].hex()}")
print()

# Step 4: eUICC decapsulates and derives same keys
print("STEP 4: eUICC Decapsulates and Derives Session Keys")
print("─" * 70)
print("Simulating eUICC receiving SM-DP+ response...")

# eUICC receives smdp_otpk and smdp_ct_kem
# Then decapsulates ML-KEM and performs ECDH

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

try:
    # Perform ML-KEM decapsulation (eUICC side)
    # Re-create KEM object with secret key for decapsulation
    euicc_kem_for_decap = oqs.KeyEncapsulation("ML-KEM-768", euicc_sk_kem)
    shared_secret_kem = euicc_kem_for_decap.decap_secret(smdp_ct_kem)
    print(f"✅ ML-KEM Decapsulation: {len(shared_secret_kem)} bytes shared secret")
    
    # Perform ECDH (eUICC side)
    smdp_public_key_obj = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), smdp_otpk
    )
    shared_secret_ecdh = euicc_ec_private.exchange(
        ec.ECDH(), smdp_public_key_obj
    )
    print(f"✅ ECDH: {len(shared_secret_ecdh)} bytes shared secret")
    
    # Perform nested KDF (eUICC side - same as SM-DP+)
    # Must match hybrid_ka._derive_session_keys_hybrid exactly
    
    # Step 1: Domain-separated extraction (using HKDF with salt as label)
    K_ec = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"ECDH-P256",
        info=b"",
        backend=default_backend()
    ).derive(shared_secret_ecdh)
    
    K_kem = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"ML-KEM-768",
        info=b"",
        backend=default_backend()
    ).derive(shared_secret_kem)
    
    # Step 2: Combine intermediate keys
    combined = K_ec + K_kem  # 64 bytes
    
    # Step 3: Final KDF using SGP.22 Annex G format (with counters)
    # KEK = SHA256(combined || 0x00000001)[0:16]
    # KM = SHA256(combined || 0x00000002)[0:16]
    import hashlib
    import struct
    
    kek_input = combined + struct.pack('>I', 1)
    kek_hash = hashlib.sha256(kek_input).digest()
    euicc_kek = kek_hash[:16]
    
    km_input = combined + struct.pack('>I', 2)
    km_hash = hashlib.sha256(km_input).digest()
    euicc_km = km_hash[:16]
    
    print(f"✅ Derived KEK: {len(euicc_kek)} bytes")
    print(f"✅ Derived KM: {len(euicc_km)} bytes")
    
except Exception as e:
    print(f"❌ Error in eUICC decapsulation: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Step 5: Verify keys match
print("STEP 5: Verify Session Keys Match")
print("─" * 70)

if euicc_kek == kek:
    print("✅ KEK matches perfectly!")
else:
    print(f"❌ KEK mismatch!")
    print(f"   SM-DP+: {kek.hex()}")
    print(f"   eUICC:  {euicc_kek.hex()}")

if euicc_km == km:
    print("✅ KM matches perfectly!")
else:
    print(f"❌ KM mismatch!")
    print(f"   SM-DP+: {km.hex()}")
    print(f"   eUICC:  {euicc_km.hex()}")

print()
print("═" * 70)
print()

if euicc_kek == kek and euicc_km == km:
    print("🎉 SUCCESS: END-TO-END HYBRID PQC VERIFIED!")
    print()
    print("Proof:")
    print("  ✅ eUICC generated ML-KEM-768 + ECDH keypairs")
    print("  ✅ SM-DP+ encapsulated to eUICC's ML-KEM public key")
    print("  ✅ SM-DP+ performed ECDH key agreement")
    print("  ✅ SM-DP+ derived session keys using nested KDF")
    print("  ✅ eUICC decapsulated ML-KEM ciphertext")
    print("  ✅ eUICC performed ECDH key agreement")
    print("  ✅ eUICC derived identical session keys")
    print("  ✅ Both sides arrived at same KEK and KM")
    print()
    print("Security:")
    print("  • Classical: 128-bit (ECDH P-256)")
    print("  • Quantum: 192-bit equivalent (ML-KEM-768)")
    print("  • Combined: Secure if EITHER is unbroken")
    print("  • Quantum-resistant: YES ✅")
    sys.exit(0)
else:
    print("❌ FAILURE: Session keys do not match")
    sys.exit(1)

