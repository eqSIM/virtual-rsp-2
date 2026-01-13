import requests
import os
from typing import List, Dict, Optional

class SmdpApiService:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url

    def list_profiles(self) -> List[Dict]:
        """List all available UPP profiles"""
        try:
            response = requests.get(f"{self.base_url}/mno/profiles")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error listing profiles: {e}")
            return []

    def upload_profile(self, filepath: str) -> bool:
        """Upload new profile (.der file)"""
        try:
            filename = os.path.basename(filepath)
            with open(filepath, 'rb') as f:
                content = f.read()
            
            response = requests.post(
                f"{self.base_url}/mno/profiles",
                data=content,
                headers={'X-Filename': filename}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error uploading profile: {e}")
            return False

    def delete_profile(self, matching_id: str) -> bool:
        """Delete a profile"""
        try:
            response = requests.delete(f"{self.base_url}/mno/profiles/{matching_id}")
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error deleting profile: {e}")
            return False

    def list_sessions(self) -> List[Dict]:
        """List active RSP sessions"""
        try:
            response = requests.get(f"{self.base_url}/mno/sessions")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error listing sessions: {e}")
            return []

    def get_download_history(self) -> List[Dict]:
        """Get download history"""
        try:
            response = requests.get(f"{self.base_url}/mno/downloads")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting download history: {e}")
            return []

    def get_stats(self) -> Dict:
        """Dashboard statistics"""
        try:
            response = requests.get(f"{self.base_url}/mno/stats")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {
                'total_profiles': 0,
                'active_sessions': 0,
                'total_downloads': 0,
                'success_rate': 0,
                'failed_count': 0
            }
