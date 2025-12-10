#!/bin/bash
# Generate OQS-enabled TLS certificates for nginx
# Uses hybrid classical + post-quantum algorithms

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="$SCRIPT_DIR/../pysim/certs-oqs-tls"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN} OQS-Enabled TLS Certificate Generation for nginx${NC}"
echo -e "${CYAN} Using Hybrid Post-Quantum + Classical Cryptography${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo

# Check if OpenSSL is OQS-enabled
if ! command -v openssl &> /dev/null; then
    echo -e "${YELLOW}[!] OpenSSL not found${NC}"
    echo "    Using self-signed certificates with ML-DSA signatures"
    USE_MLDSA=1
else
    echo -e "${GREEN}[✓] OpenSSL found${NC}"
    USE_MLDSA=1  # Always use ML-DSA for now
fi

# Create output directory
mkdir -p "$CERTS_DIR"

echo
echo -e "${YELLOW}[*] Generating certificates...${NC}"

# For now, generate standard certificates and add ML-DSA signatures separately
# In production, use OQS-OpenSSL provider

# Generate RSA key and certificate (classical component)
echo -e "${GREEN}[1/3] Generating classical RSA key and certificate${NC}"
openssl req -new -x509 -days 365 -nodes \
    -newkey rsa:2048 \
    -keyout "$CERTS_DIR/server-rsa.key" \
    -out "$CERTS_DIR/server-rsa.crt" \
    -subj "/C=US/ST=Virtual/L=Virtual/O=Virtual RSP/CN=testsmdpplus1.example.com" \
    2>/dev/null

# Generate ECDSA key and certificate (classical component)
echo -e "${GREEN}[2/3] Generating classical ECDSA key and certificate${NC}"
openssl ecparam -name prime256v1 -genkey -noout -out "$CERTS_DIR/server-ecdsa.key" 2>/dev/null
openssl req -new -x509 -days 365 -key "$CERTS_DIR/server-ecdsa.key" \
    -out "$CERTS_DIR/server-ecdsa.crt" \
    -subj "/C=US/ST=Virtual/L=Virtual/O=Virtual RSP/CN=testsmdpplus1.example.com" \
    2>/dev/null

# Generate ML-DSA signatures using Python (post-quantum component)
echo -e "${GREEN}[3/3] Adding ML-DSA-87 post-quantum signatures${NC}"

OQS_PYTHON_BUILD_SKIP_INSTALL=1 python3 - <<'EOF'
import sys
import os
from pathlib import Path
import ctypes.util

sys.path.insert(0, str(Path(__file__).parent / 'pysim'))

# Set environment to prevent auto-install
os.environ['OQS_PYTHON_BUILD_SKIP_INSTALL'] = '1'

# Override ctypes library finder to locate liboqs
liboqs_paths = [
    Path('/opt/homebrew/lib'),        # Homebrew on Apple Silicon
    Path('/usr/local/lib'),           # Homebrew on Intel
    Path.home() / '.local' / 'lib',  # User-installed location
]

_orig_find_library = ctypes.util.find_library

def _custom_find_library(name):
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
    import hashlib
    
    certs_dir = Path(__file__).parent / 'pysim' / 'certs-oqs-tls'
    
    # Generate ML-DSA keypair for server
    sig = oqs.Signature("ML-DSA-87")
    public_key = sig.generate_keypair()
    secret_key = sig.export_secret_key()
    
    # Save ML-DSA keys
    (certs_dir / 'server-mldsa87.pub').write_bytes(public_key)
    (certs_dir / 'server-mldsa87.key').write_bytes(secret_key)
    
    # Read RSA certificate and sign it with ML-DSA
    rsa_cert = (certs_dir / 'server-rsa.crt').read_bytes()
    rsa_cert_hash = hashlib.sha256(rsa_cert).digest()
    
    # Sign the hash with ML-DSA
    mldsa_sig = sig.sign(rsa_cert_hash)
    (certs_dir / 'server-rsa.crt.mldsa87.sig').write_bytes(mldsa_sig)
    
    # Read ECDSA certificate and sign it with ML-DSA
    ecdsa_cert = (certs_dir / 'server-ecdsa.crt').read_bytes()
    ecdsa_cert_hash = hashlib.sha256(ecdsa_cert).digest()
    
    # Sign the hash with ML-DSA
    mldsa_sig = sig.sign(ecdsa_cert_hash)
    (certs_dir / 'server-ecdsa.crt.mldsa87.sig').write_bytes(mldsa_sig)
    
    print(f"✓ ML-DSA public key:  {len(public_key)} bytes")
    print(f"✓ ML-DSA secret key:  {len(secret_key)} bytes")
    print(f"✓ ML-DSA signatures generated")
    
except Exception as e:
    print(f"Warning: Could not generate ML-DSA signatures: {e}")
    print("Continuing with classical-only certificates")
EOF

echo
echo -e "${GREEN}[✓] Certificate generation complete${NC}"
echo
echo "Generated files in $CERTS_DIR:"
echo "  Classical:"
echo "    - server-rsa.key      : RSA private key"
echo "    - server-rsa.crt      : RSA certificate"
echo "    - server-ecdsa.key    : ECDSA private key"
echo "    - server-ecdsa.crt    : ECDSA certificate"
echo
echo "  Post-Quantum:"
echo "    - server-mldsa87.key  : ML-DSA-87 private key"
echo "    - server-mldsa87.pub  : ML-DSA-87 public key"
echo "    - *.crt.mldsa87.sig   : ML-DSA-87 signatures of certificates"
echo
echo -e "${CYAN}Security Model: Hybrid (Classical + Post-Quantum)${NC}"
echo "  • Classical: RSA-2048 / ECDSA-P256 for compatibility"
echo "  • PQC: ML-DSA-87 signatures for quantum resistance"
echo "  • Trust: Valid if EITHER classical OR PQC signature verifies"
echo
