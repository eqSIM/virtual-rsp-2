# Virtual RSP Documentation

Welcome to the Virtual RSP (Remote SIM Provisioning) documentation. This is a comprehensive guide to the GSMA SGP.22 v2.5 compliant virtual eUICC implementation.

## 📚 Documentation Structure

All documentation is organized in the `vrsp/` directory using **Docsify** for easy navigation and search.

### Quick Navigation

- **[🚀 Quick Start](vrsp/quick-start.md)** - Get started with demo scripts and profile selection
- **[🏗️ Setup & Configuration](vrsp/setup.md)** - Installation and configuration guide
- **[🏛️ Architecture Overview](vrsp/architecture.md)** - System design and components
- **[🔐 Authentication](vrsp/authentication.md)** - Mutual authentication flow
- **[📦 Profile Download](vrsp/profile-download.md)** - Profile download and installation process
- **[🔐 Cryptographic Operations](vrsp/cryptography.md)** - Detailed crypto operations and key derivation
- **[🧪 Test Profiles](vrsp/test-profiles.md)** - Available test profiles (18 profiles)
- **[🔧 API Reference](vrsp/api-reference.md)** - API endpoints and interfaces
- **[🛠️ Development Guide](vrsp/development.md)** - Development and contribution guide
- **[❓ Troubleshooting](vrsp/troubleshooting.md)** - Common issues and solutions

## 🎯 Key Features

### Complete SGP.22 v2.5 Implementation
- ✅ Mutual authentication (ES9+/ES10b)
- ✅ Session key derivation (ECDH + KDF)
- ✅ Bound Profile Package (BPP) processing
- ✅ Profile installation with encryption/MAC
- ✅ ProfileInstallationResult generation

### 18 Test Profiles Available
- Version 1: Basic profiles (TS48V1-A, TS48V1-B)
- Version 2: SAIP2 introduction (4 variants)
- Version 3: Updated spec (4 variants)
- Version 4: Profile variants (4 variants)
- Version 5: Latest + 5G SUCI (4 variants including SUCI-enabled)

### Interactive Demo Scripts
- `./demo-profile-menu.sh` - Interactive profile selection
- `./demo-profile-install.sh` - Quick profile installation
- `./demo-detailed.sh` - Detailed cryptographic operations

## 🚀 Getting Started

### 1. Quick Start (Easiest)
```bash
./demo-profile-menu.sh
```

### 2. Install Specific Profile
```bash
./demo-detailed.sh testsmdpplus1.example.com:8443 TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE
```

### 3. View Available Profiles
```bash
./demo-profile-install.sh --help
```

## 📖 Documentation Highlights

### New Documentation Added
- **quick-start.md** - Complete quick start guide with all demo types
- **cryptography.md** - Detailed technical explanation of all cryptographic operations
- **test-profiles.md** - Complete reference for all 18 available test profiles

### Updated Structure
- All documentation now organized in `docs/vrsp/` for Docsify
- Sidebar navigation updated with new sections
- Removed duplicate markdown files from `docs/` root

## 🔐 Cryptographic Operations

The implementation includes:
- **3 ECDSA Signatures** (AuthenticateServer, PrepareDownload, ProfileInstallationResult)
- **2 ECDH Key Agreements** (Session key derivation)
- **1 KDF Operation** (SGP.22 Annex G - SHA256 based)
- **4+ Certificate Verifications** (eUICC and SM-DP+ chains)
- **15+ AES Operations** (CMAC for MAC, CBC for encryption)

## 📋 Test Profiles

### Recommended Profiles
- **General Testing**: `TS48V2-SAIP2-1-BERTLV-UNIQUE` (default)
- **5G Testing**: `TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE` (with SUCI)
- **Storage Optimization**: `TS48V4-SAIP2-3-NOBERTLV-UNIQUE` (compact)
- **Latest Features**: `TS48V5-SAIP2-1B-NOBERTLV-UNIQUE` (V5 enhanced)

## 🛠️ Development

### Project Structure
```
virtual-rsp/
├── docs/vrsp/              # Docsify documentation
├── v-euicc/                # Virtual eUICC implementation
├── pysim/                  # SM-DP+ server and profiles
├── lpac/                   # LPA client (external)
├── demo-*.sh               # Demo scripts
└── test-*.sh               # Test scripts
```

### Key Components
- **v-euicc**: C implementation of eUICC with cryptographic operations
- **osmo-smdpp**: Python SM-DP+ server with profile generation
- **lpac**: LPA client for profile download and installation

## 📚 References

- [GSMA eSIM Specification](https://www.gsma.com/solutions-and-impact/technologies/esim/esim-specification/)
- [Osmocom pySim Project](https://osmocom.org/projects/pysim)
- [GlobalPlatform Card Specification](https://www.globalplatform.org/)

## ✅ Implementation Status

- **SGP.22 Compliance**: v2.5 ✅
- **Mutual Authentication**: Complete ✅
- **Profile Download**: Complete ✅
- **Profile Installation**: Complete ✅
- **Cryptographic Operations**: Complete ✅
- **Test Profiles**: 18 available ✅
- **Documentation**: Complete ✅

## 📞 Support

For issues, questions, or contributions, please refer to:
- [Troubleshooting Guide](vrsp/troubleshooting.md)
- [Development Guide](vrsp/development.md)
- [GitHub Repository](https://github.com/Lavelliane/virtual-rsp-2)

---

**Last Updated**: October 23, 2025  
**Documentation Version**: 2.0  
**Implementation Status**: Production Ready ✅
