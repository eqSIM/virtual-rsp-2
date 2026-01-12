# Virtual RSP GUI - Quick Reference

## Quick Start (3 Steps)

1. **Launch GUI**:
   ```bash
   ./run-gui.sh
   ```

2. **Start Services** (in GUI):
   - Click Start on v-euicc
   - Click Start on SM-DP+
   - Click Start on nginx

3. **Download Profile**:
   - Select profile from dropdown
   - Click "Download Profile"
   - Wait for completion

## Common Operations

### Enable Profile
```
Installed Profiles → [Profile Row] → Enable button
```
**Note**: Auto-disables other profiles (SGP.22 rule)

### Disable Profile
```
Installed Profiles → [Profile Row] → Disable button
```

### Delete Profile
```
Installed Profiles → [Profile Row] → Disable first → Delete button
```
**Note**: Cannot delete enabled profile

## Keyboard Shortcuts

- **Ctrl+Q**: Quit application
- **Ctrl+R**: Refresh profile list

## Available Test Profiles

The GUI scans `pysim/smdpp-data/upp/` for profiles ending in `-UNIQUE.der`:

- **TS48V2-SAIP2-1-BERTLV-UNIQUE** (default, recommended for testing)
- **TS48V5-SAIP2-3-BERTLV-SUCI-UNIQUE** (5G with SUCI support)
- **TS48V3-SAIP2-1-NOBERTLV-UNIQUE** (compact encoding)
- ... and 15+ more variants

## Troubleshooting Quick Fixes

| Issue | Solution |
|-------|----------|
| Services won't start | `pkill -9 v-euicc-daemon nginx` then retry |
| Download fails | Check all services are running (green indicators) |
| Can't delete profile | Disable it first |
| No profiles in dropdown | Check `pysim/smdpp-data/upp/` exists |
| Log viewer empty | Start services first |

## File Locations

- **Profiles DB**: `data/profiles.json`
- **Logs**: `data/*.log` (veuicc.log, smdp.log, nginx.log)
- **v-euicc binary**: `build/v-euicc/v-euicc-daemon`
- **lpac binary**: `build/lpac/src/lpac`

## Architecture Flow

```
User clicks "Download Profile"
    ↓
LPA Service calls lpac CLI
    ↓
lpac → v-euicc (ES10b APDU over socket:8765)
    ↓
lpac → SM-DP+ (ES9+ HTTP over nginx:8443)
    ↓
Profile data flows through BPP commands
    ↓
v-euicc stores profile metadata
    ↓
Profile Store (profiles.json) updated
    ↓
GUI table refreshes automatically
```

## SGP.22 Compliance

✅ **ES10c Commands Implemented**:
- BF31: EnableProfile
- BF32: DisableProfile
- BF33: DeleteProfile
- BF2D: GetProfilesInfo

✅ **State Machine Rules**:
- Only ONE profile enabled at a time
- Cannot delete enabled profile
- Enable auto-disables others

## Advanced Usage

### Manual lpac Commands (Terminal)

If you need to test lpac directly without the GUI:

```bash
export LPAC_APDU=socket
export LPAC_APDU_SOCKET_HOST=127.0.0.1
export LPAC_APDU_SOCKET_PORT=8765
export DYLD_LIBRARY_PATH=./build/lpac/euicc:./build/lpac/utils:./build/lpac/driver

./build/lpac/src/lpac chip info
./build/lpac/src/lpac profile list
./build/lpac/src/lpac profile enable <ICCID>
```

### Direct Profile Store Access (Python)

```python
from gui.services.profile_store import ProfileStore

store = ProfileStore("data/profiles.json")
profiles = store.list_profiles()

for p in profiles:
    print(f"{p.iccid}: {p.state}")

# Enable profile
store.enable_profile(iccid="8901234567890123456")
```

## Support

For issues or questions:
1. Check logs in GUI (bottom panel)
2. Review `gui/README.md` for detailed docs
3. Check troubleshooting section in main README

