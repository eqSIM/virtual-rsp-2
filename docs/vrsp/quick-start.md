# Quick Start Guide

## Choose Your Demo Type

### 🎯 Interactive Menu (Easiest)
```bash
./demo-profile-menu.sh
```
**Best for:** First-time users, exploring different profiles

**Features:**
- ✅ Numbered list of all 18 test profiles
- ✅ Color-coded profile features (BER-TLV, SAIP2, SUCI)
- ✅ Choose between quick or detailed demo
- ✅ No command-line arguments needed

---

### 🚀 Quick Demo (Default Profile)
```bash
./demo-profile-install.sh
```
**Best for:** Quick testing, verification

**Shows:**
- eUICC information (EID, capabilities)
- Profile download and installation
- Installation summary

**Duration:** ~15 seconds

---

### 🔬 Detailed Technical Demo (Default Profile)
```bash
./demo-detailed.sh
```
**Best for:** Learning SGP.22, debugging, education

**Shows:**
- 📜 Certificate chains and PKIDs
- 🔐 Authentication flow with signature details
- 🔑 ECDH key agreement and KDF
- 📦 All BPP commands with crypto operations
- 📊 Complete operation summary

**Duration:** ~20 seconds

---

## Install Specific Profiles

### Method 1: Command Line
```bash
# Quick demo with custom profile
./demo-profile-install.sh testsmdpplus1.example.com:8443 TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE

# Detailed demo with custom profile
./demo-detailed.sh testsmdpplus1.example.com:8443 TS48V3-SAIP2-1-BERTLV-UNIQUE
```

### Method 2: See Available Profiles
```bash
./demo-profile-install.sh --help
./demo-detailed.sh --help
```

---

## Recommended Profiles

### For General Testing
```bash
TS48V2-SAIP2-1-BERTLV-UNIQUE    # Default, well-tested
```

### For 5G Testing
```bash
TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE    # Latest, with SUCI support
```

### For Storage Optimization
```bash
TS48V4-SAIP2-3-NOBERTLV-UNIQUE    # Compact encoding
```

### For Latest Features
```bash
TS48V5-SAIP2-1B-NOBERTLV-UNIQUE    # Latest spec, enhanced features
```

---

## Profile Features at a Glance

| Feature | Meaning | When to Use |
|---------|---------|-------------|
| **BER-TLV** | Standard encoding | Maximum compatibility |
| **NOBERTLV** | Compact encoding | Save storage space |
| **SAIP2.1** | Basic connectivity | Simple use cases |
| **SAIP2.3** | Enhanced profile | Advanced features |
| **SUCI** | 5G privacy (TS48V5 only) | 5G standalone networks |

---

## Example Workflows

### Workflow 1: First Time User
```bash
# Use interactive menu
./demo-profile-menu.sh

# Select option 3 (or any profile)
# Choose detailed demo (option 2)
# Review crypto operations
```

### Workflow 2: Testing Different Profiles
```bash
# Install BER-TLV version
./demo-profile-install.sh testsmdpplus1.example.com:8443 TS48V4-SAIP2-3-BERTLV-UNIQUE

# Install compact version
./demo-profile-install.sh testsmdpplus1.example.com:8443 TS48V4-SAIP2-3-NOBERTLV-UNIQUE

# Compare results
```

### Workflow 3: Learning Cryptography
```bash
# Run detailed demo
./demo-detailed.sh

# Check logs for crypto details
tail -f /tmp/detailed-euicc.log

# Review technical documentation
cat docs/vrsp/cryptography.md
```

---

## All 18 Available Profiles

### Version 1 (Basic)
- TS48V1-A-UNIQUE
- TS48V1-B-UNIQUE

### Version 2 (SAIP2 Introduction)
- TS48V2-SAIP2-1-BERTLV-UNIQUE ⭐ *Default*
- TS48V2-SAIP2-1-NOBERTLV-UNIQUE
- TS48V2-SAIP2-3-BERTLV-UNIQUE
- TS48V2-SAIP2-3-NOBERTLV-UNIQUE

### Version 3 (Updated Spec)
- TS48V3-SAIP2-1-BERTLV-UNIQUE
- TS48V3-SAIP2-1-NOBERTLV-UNIQUE
- TS48V3-SAIP2-3-BERTLV-UNIQUE
- TS48V3-SAIP2-3-NOBERTLV-UNIQUE

### Version 4 (Variants)
- TS48V4-SAIP2-1A-NOBERTLV-UNIQUE
- TS48V4-SAIP2-1B-NOBERTLV-UNIQUE
- TS48V4-SAIP2-3-BERTLV-UNIQUE
- TS48V4-SAIP2-3-NOBERTLV-UNIQUE

### Version 5 (Latest + 5G)
- TS48V5-SAIP2-1A-NOBERTLV-UNIQUE
- TS48V5-SAIP2-1B-NOBERTLV-UNIQUE
- TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE 🔥 *5G with SUCI*
- TS48V5-SAIP2-3-NOBERTLV-UNIQUE

---

## Logs and Debugging

### Log Locations
```bash
# Quick/Detailed demos
/tmp/demo-euicc.log      # or /tmp/detailed-euicc.log
/tmp/demo-smdpp.log      # or /tmp/detailed-smdpp.log
/tmp/demo-lpac.log       # or /tmp/detailed-lpac.log

# Menu demo
/tmp/menu-euicc.log
/tmp/menu-smdpp.log
/tmp/menu-lpac.log
```

### View Logs
```bash
# Real-time monitoring
tail -f /tmp/detailed-euicc.log

# Search for crypto operations
grep "ECDSA signature\|Session keys\|BPP command" /tmp/detailed-euicc.log
```

---

## Troubleshooting

### Services Not Starting
```bash
# Kill all instances and retry
pkill -9 -f "v-euicc-daemon"
pkill -9 -f "osmo-smdpp"
pkill -9 nginx

# Wait and retry
sleep 2
./demo-profile-menu.sh
```

### Profile Not Found
```bash
# Check exact name (case-sensitive)
ls pysim/smdpp-data/upp/ | grep -i saip2
```

### Connection Failed
```bash
# Ensure hosts entry exists
grep testsmdpplus1 /etc/hosts

# If missing, add it
echo "127.0.0.1 testsmdpplus1.example.com" | sudo tee -a /etc/hosts
```

---

## Next Steps

1. ✅ Run interactive menu: `./demo-profile-menu.sh`
2. ✅ Try different profiles
3. ✅ Review logs to see crypto operations
4. ✅ Read technical documentation
5. ✅ Experiment with custom profiles

---

**Implementation Status:** ✅ Fully Functional  
**Total Profiles:** 18 test profiles  
**SGP.22 Compliance:** v2.5  
**Last Updated:** October 23, 2025
