# Virtual RSP Control Center - GUI Application

A PySide6-based graphical interface for managing GSMA SGP.22 v2.5 compliant virtual eUICC operations.

## Features

- **Process Management**: Independent control of v-euicc daemon, SM-DP+ server, and nginx proxy
- **Profile Selection**: Browse and download profiles from UPP directory (`pysim/smdpp-data/upp/`)
- **Profile Lifecycle**: Complete ES10c operations (Enable, Disable, Delete) per SGP.22 specifications
- **Real-time Logs**: Tail-following log viewer with service selection
- **JSON Storage**: Persistent profile database with atomic updates

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  Virtual RSP Control Center                  │
├──────────────────────┬───────────────────────────────────────┤
│  Process Control     │  Profile Selector                     │
│  ○ v-euicc           │  ┌─────────────────────────────────┐  │
│  ○ SM-DP+            │  │ Select from UPP directory       │  │
│  ○ nginx             │  └─────────────────────────────────┘  │
├──────────────────────┴───────────────────────────────────────┤
│  Installed Profiles                                          │
│  [ICCID] [Name] [Provider] [State] [Enable/Disable] [Delete]│
├──────────────────────────────────────────────────────────────┤
│  Log Output (Real-time)                                      │
│  [v-euicc ▼] [Clear]                                        │
└──────────────────────────────────────────────────────────────┘
```

## Installation

1. **Install PySide6**:
```bash
pip install -r requirements-gui.txt
```

2. **Build v-euicc** (if not already done):
```bash
mkdir -p build
cd build
cmake ..
make
cd ..
```

3. **Ensure lpac is built**:
The GUI expects `./build/lpac/src/lpac` to exist.

## Usage

### Starting the GUI

```bash
cd /Users/jhurykevinlastre/Documents/projects/virtual-rsp
python3 gui/main.py
```

Or make it executable and run directly:
```bash
./gui/main.py
```

### Workflow

1. **Start Backend Services**:
   - Click "Start" for v-euicc (port 8765)
   - Click "Start" for SM-DP+ (port 8000)
   - Click "Start" for nginx (HTTPS proxy, port 8443)
   - Status indicators turn green when services are running

2. **Download a Profile**:
   - Select a profile from the dropdown (scans `pysim/smdpp-data/upp/*.der`)
   - Verify SM-DP+ address (default: `testsmdpplus1.example.com:8443`)
   - Click "Download Profile"
   - Monitor progress and logs in real-time

3. **Manage Profiles**:
   - View all installed profiles in the table
   - **Enable**: Click "Enable" to activate (auto-disables others per SGP.22)
   - **Disable**: Click "Disable" to deactivate
   - **Delete**: Click "Delete" (only works if profile is disabled)

4. **Monitor Logs**:
   - Select service from dropdown (v-euicc, SM-DP+, nginx)
   - Logs auto-update every 500ms
   - Click "Clear" to reset view

### SGP.22 Compliance

The GUI enforces GSMA SGP.22 rules:

- **Only ONE profile enabled at a time**: Enabling a profile automatically disables the currently enabled one
- **Cannot delete enabled profile**: Must disable first
- **ES10c Commands**: All operations use proper ES10c APDU commands (BF31, BF32, BF33)

## Architecture Details

### Components

- **`gui/main.py`**: Application entry point
- **`gui/main_window.py`**: Main window with 4-panel layout
- **`gui/widgets/`**: UI components
  - `process_panel.py`: Process start/stop controls
  - `profile_selector.py`: UPP profile browser and downloader
  - `profile_manager.py`: Installed profiles table with actions
  - `log_viewer.py`: Real-time log tail viewer
- **`gui/services/`**: Backend services
  - `process_manager.py`: Subprocess management (v-euicc, SM-DP+, nginx)
  - `lpa_service.py`: lpac CLI wrapper
  - `profile_store.py`: JSON profile persistence

### Profile Storage

Profiles are stored in `data/profiles.json`:

```json
{
  "eid": "89049032001001234500012345678901",
  "profiles": [
    {
      "iccid": "8901234567890123456",
      "isdp_aid": "A0000005591010FFFFFFFF8900001000",
      "state": "disabled",
      "profile_name": "TS48V2-SAIP2-1",
      "service_provider": "OsmocomSPN",
      "matching_id": "TS48V2-SAIP2-1-BERTLV-UNIQUE",
      "installed_at": "2026-01-07T10:30:00Z"
    }
  ],
  "last_modified": "2026-01-07T10:30:00Z"
}
```

### Log Files

Logs are written to `data/`:
- `data/veuicc.log` - v-euicc daemon output
- `data/smdp.log` - SM-DP+ server output
- `data/nginx.log` - nginx proxy output

## Troubleshooting

### "v-euicc binary not found"
- Ensure you've built the project: `cd build && cmake .. && make`
- Check that `./build/v-euicc/v-euicc-daemon` exists

### "Profile download failed"
- Verify all three services are running (green indicators)
- Check that `/etc/hosts` has entry: `127.0.0.1 testsmdpplus1.example.com`
- Review logs in the log viewer panel

### "Cannot delete profile"
- Profiles must be disabled before deletion (SGP.22 rule)
- Click "Disable" first, then "Delete"

### Port already in use
- Stop any existing processes: `pkill -9 v-euicc-daemon; pkill -9 nginx`
- Or use different ports in the process manager

## Development

### Adding New Features

1. **New Widget**: Add to `gui/widgets/`
2. **New Service**: Add to `gui/services/`
3. **Update Main Window**: Import and instantiate in `main_window.py`

### Extending Profile Operations

Profile operations follow this pattern:
1. LPA service calls lpac CLI
2. Update profile store (JSON)
3. Refresh UI
4. Emit signal for other components

## References

- [GSMA SGP.22 v2.5](https://www.gsma.com/esim/wp-content/uploads/2020/06/SGP.22-v2.5.pdf)
- [lpac Documentation](../lpac/docs/)
- [Virtual eUICC](../v-euicc/)
- [osmo-smdpp](../pysim/osmo-smdpp.py)

## License

Same as parent project.

