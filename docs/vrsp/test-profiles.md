# Available Test Profiles

This document lists all available test profiles that can be installed on the virtual eUICC.

## Profile Location

All profiles are stored in: `pysim/smdpp-data/upp/`

## How to Use Different Profiles

### Method 1: Interactive Menu (Recommended)
```bash
./demo-profile-menu.sh
```

This will show a numbered list of all available profiles and let you choose which one to install.

### Method 2: Command Line Arguments
```bash
# Basic demo
./demo-profile-install.sh testsmdpplus1.example.com:8443 <MATCHING_ID>

# Detailed demo
./demo-detailed.sh testsmdpplus1.example.com:8443 <MATCHING_ID>
```

### Method 3: List Available Profiles
```bash
./demo-profile-install.sh --help
```

---

## Available Profiles

### Test Specification 48 Version 1

| Matching ID | Features | Size |
|-------------|----------|------|
| `TS48V1-A-UNIQUE` | Basic test profile A | 11.5 KB |
| `TS48V1-B-UNIQUE` | Basic test profile B | 11.5 KB |

**Characteristics:**
- Basic SAIP1 implementation
- Suitable for initial testing

---

### Test Specification 48 Version 2

| Matching ID | Features | Size |
|-------------|----------|------|
| `TS48V2-SAIP2-1-BERTLV-UNIQUE` | SAIP2.1, BER-TLV encoding | 12.0 KB |
| `TS48V2-SAIP2-1-NOBERTLV-UNIQUE` | SAIP2.1, No BER-TLV | 11.9 KB |
| `TS48V2-SAIP2-3-BERTLV-UNIQUE` | SAIP2.3, BER-TLV encoding | 12.0 KB |
| `TS48V2-SAIP2-3-NOBERTLV-UNIQUE` | SAIP2.3, No BER-TLV | 12.0 KB |

**Characteristics:**
- SAIP2 (Secure Application for Internet Protocol)
- Options for BER-TLV vs. compact TLV encoding
- SAIP2.1: Basic internet connectivity profile
- SAIP2.3: Enhanced profile with additional services

**Default in demos:** `TS48V2-SAIP2-1-BERTLV-UNIQUE`

---

### Test Specification 48 Version 3

| Matching ID | Features | Size |
|-------------|----------|------|
| `TS48V3-SAIP2-1-BERTLV-UNIQUE` | SAIP2.1, BER-TLV encoding | 11.8 KB |
| `TS48V3-SAIP2-1-NOBERTLV-UNIQUE` | SAIP2.1, No BER-TLV | 11.8 KB |
| `TS48V3-SAIP2-3-BERTLV-UNIQUE` | SAIP2.3, BER-TLV encoding | 11.9 KB |
| `TS48V3-SAIP2-3-NOBERTLV-UNIQUE` | SAIP2.3, No BER-TLV | 11.8 KB |

**Characteristics:**
- Updated test specification
- Improved file structure
- Better SAIP2 implementation

---

### Test Specification 48 Version 4

| Matching ID | Features | Size |
|-------------|----------|------|
| `TS48V4-SAIP2-1A-NOBERTLV-UNIQUE` | SAIP2.1A variant, No BER-TLV | 11.8 KB |
| `TS48V4-SAIP2-1B-NOBERTLV-UNIQUE` | SAIP2.1B variant, No BER-TLV | 11.8 KB |
| `TS48V4-SAIP2-3-BERTLV-UNIQUE` | SAIP2.3, BER-TLV encoding | 11.9 KB |
| `TS48V4-SAIP2-3-NOBERTLV-UNIQUE` | SAIP2.3, No BER-TLV | 11.8 KB |

**Characteristics:**
- Introduces SAIP2.1A and SAIP2.1B variants
- 1A: Basic connectivity
- 1B: Extended connectivity features

---

### Test Specification 48 Version 5 (Latest)

| Matching ID | Features | Size |
|-------------|----------|------|
| `TS48V5-SAIP2-1A-NOBERTLV-UNIQUE` | SAIP2.1A, No BER-TLV | 11.8 KB |
| `TS48V5-SAIP2-1B-NOBERTLV-UNIQUE` | SAIP2.1B, No BER-TLV | 11.9 KB |
| `TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE` | SAIP2.3, BER-TLV, **SUCI support** | 12.0 KB |
| `TS48V5-SAIP2-3-NOBERTLV-UNIQUE` | SAIP2.3, No BER-TLV | 11.9 KB |

**Characteristics:**
- Latest test specification
- **SUCI (Subscription Concealed Identifier) support** for 5G privacy
- Most advanced test profiles available

**Recommended for 5G testing:** `TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE`

---

## Profile Features Explained

### BER-TLV Encoding
- **BER-TLV**: Basic Encoding Rules - Tag Length Value
- Standard encoding format for UICC files
- More verbose but widely compatible
- **Use when:** You need standard compatibility

### No BER-TLV (Compact TLV)
- Compact encoding format
- Saves space on eUICC
- **Use when:** Storage optimization is important

### SAIP Levels

#### SAIP2.1
- Basic internet connectivity profile
- Standard APN settings
- Suitable for basic data services

#### SAIP2.1A
- SAIP2.1 variant A
- Specific configuration variant

#### SAIP2.1B
- SAIP2.1 variant B
- Alternative configuration

#### SAIP2.3
- Enhanced profile
- Additional services and configurations
- More file structures

### SUCI Support
- **SUCI**: Subscription Concealed Identifier
- 5G NR privacy feature
- Encrypts IMSI/SUPI before sending to network
- Required for 5G standalone networks
- **Only available in:** TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE

---

## Usage Examples

### Example 1: Install Default Profile
```bash
./demo-profile-install.sh
# Uses: TS48V2-SAIP2-1-BERTLV-UNIQUE
```

### Example 2: Install 5G Profile with SUCI
```bash
./demo-profile-install.sh testsmdpplus1.example.com:8443 TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE
```

### Example 3: Install Compact Profile
```bash
./demo-detailed.sh testsmdpplus1.example.com:8443 TS48V4-SAIP2-3-NOBERTLV-UNIQUE
```

### Example 4: Interactive Selection
```bash
./demo-profile-menu.sh
# Choose from numbered list
```

### Example 5: List All Available
```bash
ls -1 pysim/smdpp-data/upp/*.der | xargs -n1 basename | grep UNIQUE
```

---

## Profile Contents

Each profile contains:

### Mandatory Files
- **EF_ICCID**: Integrated Circuit Card Identifier
- **EF_DIR**: Application directory
- **EF_ARR**: Access Rule Reference
- **MF (Master File)**: Root directory
- **ADF_USIM**: USIM application

### SAIP-specific Files
- **EF_IMSI**: International Mobile Subscriber Identity
- **EF_ACC**: Access control class
- **EF_FPLMN**: Forbidden PLMNs
- **EF_LOCI**: Location information
- **EF_AD**: Administrative data
- **EF_UST**: USIM Service Table
- **EF_SPN**: Service Provider Name
- **EF_EST**: Enabled Services Table

### SAIP2.3 Additional Files
- Extended service files
- Additional application data
- Enhanced network configurations

### SUCI-specific Files (TS48V5 SUCI variant)
- **EF_SUCI_Calc_Info**: SUCI calculation parameters
- **EF_SUPI_NAI**: SUPI in NAI format
- Protection scheme configurations

---

## Troubleshooting

### Profile Not Found
```bash
# Check if profile exists
ls pysim/smdpp-data/upp/ | grep <MATCHING_ID>
```

### Wrong Profile Installed
```bash
# The matching ID must EXACTLY match the filename (without .der)
# Case-sensitive!
```

### View Profile Metadata
```bash
# Use lpac after installation
LPAC_APDU=socket LPAC_APDU_SOCKET_HOST=127.0.0.1 LPAC_APDU_SOCKET_PORT=8765 \
./build/lpac/src/lpac profile list
```

---

## Adding Custom Profiles

To add your own profiles:

1. Create profile package (UPP - Unprotected Profile Package) in DER format
2. Place in `pysim/smdpp-data/upp/`
3. Filename becomes the Matching ID
4. Must end with `.der`

**Example:**
```bash
cp my-custom-profile.der pysim/smdpp-data/upp/MY-CUSTOM-PROFILE-UNIQUE.der
./demo-profile-install.sh testsmdpplus1.example.com:8443 MY-CUSTOM-PROFILE-UNIQUE
```

---

**Total Profiles Available:** 18 unique test profiles
