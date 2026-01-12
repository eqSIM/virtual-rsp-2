#!/usr/bin/env python3
"""
Initialize profiles database with current v-euicc profiles.
Scans v-euicc state and populates profiles.json.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from gui.services.profile_store import ProfileStore, Profile, ProfileState


def init_database():
    """Initialize profiles database"""
    db_path = project_root / "data/profiles.json"
    
    print(f"Initializing profile database: {db_path}")
    
    # Create store (will initialize with empty DB if doesn't exist)
    store = ProfileStore(str(db_path))
    
    # Get EID (default from v-euicc)
    eid = store.get_eid()
    print(f"EID: {eid}")
    
    # List current profiles
    profiles = store.list_profiles()
    print(f"Current profiles: {len(profiles)}")
    
    if profiles:
        print("\nInstalled profiles:")
        for p in profiles:
            state_str = "ENABLED" if p.state == ProfileState.ENABLED else "disabled"
            print(f"  - {p.iccid}: {p.profile_name} [{state_str}]")
    else:
        print("\nNo profiles installed yet.")
        print("Use the GUI to download profiles from the UPP directory.")
    
    print(f"\n✓ Database initialized successfully")
    print(f"  Location: {db_path}")


if __name__ == "__main__":
    init_database()

