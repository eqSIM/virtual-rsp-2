"""
LPA Service - Wrapper around lpac CLI for profile operations
Follows the exact flow from demo-detailed.sh
"""

import subprocess
import os
import json
from typing import List, Dict, Optional, Tuple


class LPAService:
    """
    Wrapper around lpac CLI tool for LPA operations.
    Implements ES10c profile management per SGP.22.
    """
    
    def __init__(self, lpac_path: str = "./build/lpac/src/lpac",
                 apdu_host: str = "127.0.0.1",
                 apdu_port: int = 8765):
        self.lpac_path = lpac_path
        self.apdu_host = apdu_host
        self.apdu_port = apdu_port
        
        # Set environment variables for lpac
        self.env = os.environ.copy()
        self.env.update({
            'LPAC_APDU': 'socket',
            'LPAC_APDU_SOCKET_HOST': apdu_host,
            'LPAC_APDU_SOCKET_PORT': str(apdu_port),
            'DYLD_LIBRARY_PATH': './build/lpac/euicc:./build/lpac/utils:./build/lpac/driver',
            'LD_LIBRARY_PATH': './build/lpac/euicc:./build/lpac/utils:./build/lpac/driver'
        })
    
    def _run_lpac(self, args: List[str], timeout: int = 30) -> Tuple[bool, str, str]:
        """
        Run lpac command and return (success, stdout, stderr)
        """
        try:
            result = subprocess.run(
                [self.lpac_path] + args,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd='/Users/jhurykevinlastre/Documents/projects/virtual-rsp'
            )
            success = result.returncode == 0
            return success, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def get_chip_info(self) -> Optional[Dict]:
        """
        Get eUICC chip information (ES10c.GetEUICCInfo).
        Returns parsed JSON or None on failure.
        """
        success, stdout, stderr = self._run_lpac(['chip', 'info'])
        
        if not success:
            return None
        
        try:
            # lpac outputs JSON
            data = json.loads(stdout)
            return data
        except json.JSONDecodeError:
            return None
    
    def download_profile(self, smdp_address: str, matching_id: str) -> Tuple[bool, str]:
        """
        Download and install profile from SM-DP+.
        
        Args:
            smdp_address: SM-DP+ address (e.g., "testsmdpplus1.example.com:8443")
            matching_id: Profile matching ID
        
        Returns: (success, message)
        """
        success, stdout, stderr = self._run_lpac(
            ['profile', 'download', '-s', smdp_address, '-m', matching_id],
            timeout=120  # Profile download can take time
        )
        
        if success:
            return True, "Profile downloaded successfully"
        else:
            return False, stderr or stdout or "Download failed"
    
    def list_profiles(self) -> List[Dict]:
        """
        List all installed profiles.
        
        Returns: List of profile dictionaries with keys:
            - iccid: Profile ICCID
            - isdp_aid: ISD-P AID
            - state: "enabled" or "disabled"
            - profile_name: Display name
            - service_provider: Provider name
        """
        success, stdout, stderr = self._run_lpac(['profile', 'list'])
        
        if not success:
            return []
        
        try:
            data = json.loads(stdout)
            # Parse lpac JSON format
            profiles = data.get('payload', {}).get('data', {}).get('profileInfoList', [])
            return profiles
        except (json.JSONDecodeError, KeyError):
            return []
    
    def enable_profile(self, iccid: str) -> Tuple[bool, str]:
        """
        Enable profile by ICCID (ES10c.EnableProfile).
        
        Args:
            iccid: Profile ICCID
        
        Returns: (success, message)
        """
        success, stdout, stderr = self._run_lpac(['profile', 'enable', iccid])
        
        if success:
            return True, f"Profile {iccid} enabled"
        else:
            return False, stderr or stdout or "Enable failed"
    
    def disable_profile(self, iccid: str) -> Tuple[bool, str]:
        """
        Disable profile by ICCID (ES10c.DisableProfile).
        
        Args:
            iccid: Profile ICCID
        
        Returns: (success, message)
        """
        success, stdout, stderr = self._run_lpac(['profile', 'disable', iccid])
        
        if success:
            return True, f"Profile {iccid} disabled"
        else:
            return False, stderr or stdout or "Disable failed"
    
    def delete_profile(self, iccid: str) -> Tuple[bool, str]:
        """
        Delete profile by ICCID (ES10c.DeleteProfile).
        
        Args:
            iccid: Profile ICCID
        
        Returns: (success, message)
        """
        success, stdout, stderr = self._run_lpac(['profile', 'delete', iccid])
        
        if success:
            return True, f"Profile {iccid} deleted"
        else:
            return False, stderr or stdout or "Delete failed"
    
    def get_eid(self) -> Optional[str]:
        """
        Get eUICC EID from chip info.
        
        Returns: EID string or None
        """
        chip_info = self.get_chip_info()
        if chip_info:
            try:
                eid = chip_info.get('payload', {}).get('data', {}).get('eidValue')
                return eid
            except (KeyError, TypeError):
                pass
        return None

