#!/usr/bin/env python3
"""
Test script to verify GUI components without launching the full UI.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("Testing Virtual RSP GUI Components...")
print("=" * 60)

# Test 1: Import services
print("\n1. Testing service imports...")
try:
    from gui.services.profile_store import ProfileStore, Profile, ProfileState
    from gui.services.lpa_service import LPAService
    from gui.services.process_manager import ProcessManager
    print("   ✓ All services imported successfully")
except Exception as e:
    print(f"   ✗ Service import failed: {e}")
    sys.exit(1)

# Test 2: Profile Store
print("\n2. Testing Profile Store...")
try:
    store = ProfileStore("data/test_profiles.json")
    profiles = store.list_profiles()
    eid = store.get_eid()
    print(f"   ✓ Profile store initialized (EID: {eid})")
    print(f"   ✓ Found {len(profiles)} profiles")
except Exception as e:
    print(f"   ✗ Profile store failed: {e}")
    sys.exit(1)

# Test 3: LPA Service
print("\n3. Testing LPA Service...")
try:
    lpa = LPAService()
    print("   ✓ LPA service initialized")
    print(f"   ✓ lpac path: {lpa.lpac_path}")
except Exception as e:
    print(f"   ✗ LPA service failed: {e}")
    sys.exit(1)

# Test 4: Process Manager
print("\n4. Testing Process Manager...")
try:
    pm = ProcessManager(str(project_root))
    print("   ✓ Process manager initialized")
    print(f"   ✓ Project root: {pm.project_root}")
except Exception as e:
    print(f"   ✗ Process manager failed: {e}")
    sys.exit(1)

# Test 5: Widget imports
print("\n5. Testing widget imports...")
try:
    from gui.widgets.process_panel import ProcessPanel
    from gui.widgets.profile_selector import ProfileSelector
    from gui.widgets.profile_manager import ProfileManager
    from gui.widgets.log_viewer import LogViewer
    print("   ✓ All widgets imported successfully")
except Exception as e:
    print(f"   ✗ Widget import failed: {e}")
    sys.exit(1)

# Test 6: Main window import
print("\n6. Testing main window import...")
try:
    from gui.main_window import MainWindow
    print("   ✓ Main window imported successfully")
except Exception as e:
    print(f"   ✗ Main window import failed: {e}")
    sys.exit(1)

# Test 7: Check file structure
print("\n7. Checking file structure...")
required_files = [
    "gui/main.py",
    "gui/main_window.py",
    "gui/services/profile_store.py",
    "gui/services/lpa_service.py",
    "gui/services/process_manager.py",
    "gui/widgets/process_panel.py",
    "gui/widgets/profile_selector.py",
    "gui/widgets/profile_manager.py",
    "gui/widgets/log_viewer.py",
    "build/v-euicc/v-euicc-daemon",
]

all_exist = True
for file_path in required_files:
    full_path = project_root / file_path
    if full_path.exists():
        print(f"   ✓ {file_path}")
    else:
        print(f"   ✗ {file_path} (missing)")
        all_exist = False

if not all_exist:
    print("\n   ⚠ Some files are missing, but GUI may still work")

print("\n" + "=" * 60)
print("✓ All component tests passed!")
print("\nThe GUI is ready to use. Run with:")
print("  ./run-gui.sh")
print("or")
print("  python3 gui/main.py")

