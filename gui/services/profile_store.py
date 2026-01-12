"""
Profile Store - JSON-based profile persistence for Virtual RSP
Implements SGP.22 profile state management with atomic updates.
"""

import json
import os
import tempfile
import fcntl
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class ProfileState:
    """SGP.22 Profile States"""
    DISABLED = "disabled"
    ENABLED = "enabled"


class Profile:
    """Profile metadata matching v-euicc profile_metadata structure"""
    
    def __init__(self, iccid: str, isdp_aid: str, state: str = ProfileState.DISABLED,
                 profile_name: str = "", service_provider: str = "",
                 matching_id: str = "", installed_at: str = None):
        self.iccid = iccid
        self.isdp_aid = isdp_aid
        self.state = state
        self.profile_name = profile_name
        self.service_provider = service_provider
        self.matching_id = matching_id
        self.installed_at = installed_at or datetime.utcnow().isoformat() + 'Z'
    
    def to_dict(self) -> Dict:
        return {
            'iccid': self.iccid,
            'isdp_aid': self.isdp_aid,
            'state': self.state,
            'profile_name': self.profile_name,
            'service_provider': self.service_provider,
            'matching_id': self.matching_id,
            'installed_at': self.installed_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Profile':
        return cls(
            iccid=data['iccid'],
            isdp_aid=data['isdp_aid'],
            state=data.get('state', ProfileState.DISABLED),
            profile_name=data.get('profile_name', ''),
            service_provider=data.get('service_provider', ''),
            matching_id=data.get('matching_id', ''),
            installed_at=data.get('installed_at')
        )


class ProfileStore:
    """
    Thread-safe JSON profile storage with SGP.22 compliance.
    
    Key rules:
    - Only ONE profile can be enabled at a time
    - Cannot delete an enabled profile
    - Atomic file updates with temp file + rename
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Initialize database file if it doesn't exist"""
        if not self.db_path.exists():
            initial_data = {
                'eid': '89049032001001234500012345678901',
                'profiles': [],
                'last_modified': datetime.utcnow().isoformat() + 'Z'
            }
            self._write_atomic(initial_data)
    
    def _read_db(self) -> Dict:
        """Read database with file locking"""
        with open(self.db_path, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data
    
    def _write_atomic(self, data: Dict):
        """Atomic write with temp file + rename"""
        data['last_modified'] = datetime.utcnow().isoformat() + 'Z'
        
        # Write to temp file in same directory
        fd, temp_path = tempfile.mkstemp(
            dir=self.db_path.parent,
            prefix='.profiles_',
            suffix='.json.tmp'
        )
        
        try:
            with os.fdopen(fd, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            # Atomic rename
            os.rename(temp_path, self.db_path)
        except:
            # Cleanup on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    
    def list_profiles(self) -> List[Profile]:
        """Get all profiles"""
        data = self._read_db()
        return [Profile.from_dict(p) for p in data.get('profiles', [])]
    
    def get_profile(self, iccid: str = None, isdp_aid: str = None, matching_id: str = None) -> Optional[Profile]:
        """Find profile by ICCID, ISD-P AID, or matching_id"""
        profiles = self.list_profiles()
        for profile in profiles:
            # Matching ID is the unique key for test profiles (they share ICCIDs)
            if matching_id and profile.matching_id == matching_id:
                return profile
            if (iccid and profile.iccid == iccid and not matching_id) or \
               (isdp_aid and profile.isdp_aid == isdp_aid):
                return profile
        return None
    
    def get_enabled_profile(self) -> Optional[Profile]:
        """Get the currently enabled profile (only one allowed)"""
        profiles = self.list_profiles()
        for profile in profiles:
            if profile.state == ProfileState.ENABLED:
                return profile
        return None
    
    def add_profile(self, profile: Profile) -> bool:
        """
        Add new profile (installs as disabled by default).
        Uses matching_id as unique key (test profiles share ICCIDs).
        Returns False if profile with same matching_id already exists.
        """
        data = self._read_db()
        
        # Check for duplicates by matching_id (unique per profile)
        for existing in data['profiles']:
            if existing.get('matching_id') == profile.matching_id and profile.matching_id:
                return False  # Already exists
        
        # Add profile
        data['profiles'].append(profile.to_dict())
        self._write_atomic(data)
        return True
    
    def enable_profile(self, iccid: str = None, isdp_aid: str = None) -> tuple[bool, str]:
        """
        Enable profile by ICCID or ISD-P AID.
        Auto-disables currently enabled profile (SGP.22 rule).
        
        Returns: (success: bool, message: str)
        """
        data = self._read_db()
        profiles = data['profiles']
        
        target_idx = None
        for i, p in enumerate(profiles):
            if (iccid and p['iccid'] == iccid) or \
               (isdp_aid and p['isdp_aid'] == isdp_aid):
                target_idx = i
                break
        
        if target_idx is None:
            return False, "Profile not found"
        
        # Disable all other profiles (SGP.22: only one enabled at a time)
        for i, p in enumerate(profiles):
            if i != target_idx and p['state'] == ProfileState.ENABLED:
                p['state'] = ProfileState.DISABLED
        
        # Enable target
        profiles[target_idx]['state'] = ProfileState.ENABLED
        
        self._write_atomic(data)
        return True, "Profile enabled"
    
    def disable_profile(self, iccid: str = None, isdp_aid: str = None) -> tuple[bool, str]:
        """
        Disable profile by ICCID or ISD-P AID.
        
        Returns: (success: bool, message: str)
        """
        data = self._read_db()
        profiles = data['profiles']
        
        target_idx = None
        for i, p in enumerate(profiles):
            if (iccid and p['iccid'] == iccid) or \
               (isdp_aid and p['isdp_aid'] == isdp_aid):
                target_idx = i
                break
        
        if target_idx is None:
            return False, "Profile not found"
        
        if profiles[target_idx]['state'] != ProfileState.ENABLED:
            return False, "Profile already disabled"
        
        profiles[target_idx]['state'] = ProfileState.DISABLED
        
        self._write_atomic(data)
        return True, "Profile disabled"
    
    def delete_profile(self, iccid: str = None, isdp_aid: str = None, matching_id: str = None) -> tuple[bool, str]:
        """
        Delete profile by ICCID, ISD-P AID, or matching_id.
        Cannot delete enabled profile (SGP.22 rule).
        
        Returns: (success: bool, message: str)
        """
        data = self._read_db()
        profiles = data['profiles']
        
        target_idx = None
        for i, p in enumerate(profiles):
            # Match by matching_id first (most unique for test profiles)
            if matching_id and p.get('matching_id') == matching_id:
                target_idx = i
                break
            if (iccid and p['iccid'] == iccid and not matching_id) or \
               (isdp_aid and p['isdp_aid'] == isdp_aid):
                target_idx = i
                break
        
        if target_idx is None:
            return False, "Profile not found"
        
        if profiles[target_idx]['state'] == ProfileState.ENABLED:
            return False, "Cannot delete enabled profile (disable it first)"
        
        # Remove profile
        profiles.pop(target_idx)
        
        self._write_atomic(data)
        return True, "Profile deleted"
    
    def get_eid(self) -> str:
        """Get eUICC EID"""
        data = self._read_db()
        return data.get('eid', '89049032001001234500012345678901')
    
    def set_eid(self, eid: str):
        """Set eUICC EID"""
        data = self._read_db()
        data['eid'] = eid
        self._write_atomic(data)

