"""
LPA Command Service for MNO - Sends commands to eUICC via lpac
Uses the shared ProfileStore for profile persistence (same as main GUI).
"""

import subprocess
import json
import os
import sys
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Add project root to path to import shared services
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from gui.services.profile_store import ProfileStore, Profile, ProfileState

class LpaCommandService:
    """
    Service to send LPA commands to the eUICC device.
    Used by MNO to remotely manage profiles on devices.
    """
    
    def __init__(self, project_root: str = None):
        if project_root:
            self.project_root = Path(project_root)
        else:
            self.project_root = Path(__file__).parent.parent.parent
        
        self.lpac_path = self.project_root / "build/lpac/src/lpac"
        
        # Use the SAME ProfileStore as the main GUI (single source of truth)
        self.profile_store = ProfileStore(str(self.project_root / "data" / "profiles.json"))
        
        # Environment for lpac socket driver
        self.env = os.environ.copy()
        self.env.update({
            'LPAC_APDU': 'socket',
            'LPAC_APDU_SOCKET_HOST': '127.0.0.1',
            'LPAC_APDU_SOCKET_PORT': '8765',
            'DYLD_LIBRARY_PATH': str(self.project_root / 'build/lpac/euicc') + ':' + 
                                 str(self.project_root / 'build/lpac/utils') + ':' + 
                                 str(self.project_root / 'build/lpac/driver'),
            'LD_LIBRARY_PATH': str(self.project_root / 'build/lpac/euicc') + ':' + 
                               str(self.project_root / 'build/lpac/utils') + ':' + 
                               str(self.project_root / 'build/lpac/driver')
        })
    
    def _run_lpac(self, args: List[str], timeout: int = 30) -> Tuple[bool, str, str]:
        """Run lpac command and return (success, stdout, stderr)"""
        try:
            result = subprocess.run(
                [str(self.lpac_path)] + args,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.project_root)
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def get_chip_info(self) -> Optional[Dict]:
        """Get eUICC chip information"""
        success, stdout, stderr = self._run_lpac(['chip', 'info'])
        if success:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                return None
        return None
    
    def list_profiles(self) -> List[Dict]:
        """List all installed profiles from the shared ProfileStore"""
        try:
            profiles = self.profile_store.list_profiles()
            return [
                {
                    'iccid': p.iccid,
                    'profileName': p.profile_name,
                    'profileState': p.state,
                    'serviceProviderName': p.service_provider,
                    'matching_id': p.matching_id,
                    'installed_at': p.installed_at
                }
                for p in profiles
            ]
        except Exception as e:
            print(f"Error listing profiles: {e}")
            return []
    
    def enable_profile(self, iccid: str) -> Tuple[bool, str]:
        """Enable profile by ICCID using ProfileStore (also sends to v-euicc)"""
        # First update ProfileStore (source of truth)
        success, msg = self.profile_store.enable_profile(iccid=iccid)
        if not success:
            return False, msg
        
        # Also send command to v-euicc (best effort, store is authoritative)
        self._run_lpac(['profile', 'enable', iccid])
        return True, f"Profile {iccid} enabled"
    
    def disable_profile(self, iccid: str) -> Tuple[bool, str]:
        """Disable profile by ICCID using ProfileStore"""
        # First update ProfileStore (source of truth)
        success, msg = self.profile_store.disable_profile(iccid=iccid)
        if not success:
            return False, msg
        
        # Also send command to v-euicc (best effort)
        self._run_lpac(['profile', 'disable', iccid])
        return True, f"Profile {iccid} disabled"
    
    def delete_profile(self, iccid: str) -> Tuple[bool, str]:
        """Delete profile by ICCID using ProfileStore"""
        # Get profile to find matching_id (needed for unique deletion)
        profile = self.profile_store.get_profile(iccid=iccid)
        if not profile:
            return False, "Profile not found"
        
        # Delete from ProfileStore (source of truth)
        success, msg = self.profile_store.delete_profile(matching_id=profile.matching_id)
        if not success:
            return False, msg
        
        # Also send command to v-euicc (best effort)
        self._run_lpac(['profile', 'delete', iccid])
        return True, f"Profile {iccid} deleted"
    
    def download_profile(self, smdp_address: str, matching_id: str) -> Tuple[bool, str]:
        """
        Download profile from SM-DP+ to the connected eUICC.
        On success, adds profile to the shared ProfileStore.
        """
        success, stdout, stderr = self._run_lpac(
            ['profile', 'download', '-s', smdp_address, '-m', matching_id],
            timeout=120  # Profile downloads can take time
        )
        if success:
            # Add profile to ProfileStore (single source of truth)
            new_profile = Profile(
                iccid="89" + matching_id[-17:].replace("-", "")[:17].ljust(17, '0'),  # Generate ICCID
                isdp_aid="",
                state=ProfileState.DISABLED,
                profile_name=matching_id,
                service_provider="OsmocomSPN",
                matching_id=matching_id
            )
            self.profile_store.add_profile(new_profile)
            return True, f"Profile {matching_id} downloaded and installed"
        return False, stderr or stdout or "Download failed"
    
    def switch_profile(self, from_iccid: str, to_iccid: str) -> Tuple[bool, str]:
        """
        Switch from one profile to another (disable old, enable new).
        This is an atomic operation for better UX.
        """
        # First enable the new profile (this auto-disables the old one per SGP.22)
        success, msg = self.enable_profile(to_iccid)
        return success, msg
    
    def get_eid(self) -> Optional[str]:
        """Get EID from ProfileStore (same as main GUI)"""
        try:
            return self.profile_store.get_eid()
        except Exception:
            return None
