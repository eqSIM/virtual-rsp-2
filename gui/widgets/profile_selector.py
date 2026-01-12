"""
Profile Selector - Browse and download profiles from UPP directory
"""

from PySide6.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton,
                                QLabel, QComboBox, QLineEdit, QMessageBox)
from PySide6.QtCore import Qt, Signal, QThread
from pathlib import Path
from typing import List
import re

from gui.services.lpa_service import LPAService
from gui.services.profile_store import ProfileStore, Profile, ProfileState
from gui.widgets.download_dialog import DownloadDialog


class DownloadThread(QThread):
    """Background thread for profile download"""
    finished = Signal(bool, str)  # success, message
    
    def __init__(self, lpa_service: LPAService, smdp_address: str, matching_id: str):
        super().__init__()
        self.lpa_service = lpa_service
        self.smdp_address = smdp_address
        self.matching_id = matching_id
    
    def run(self):
        """Execute download in background"""
        success, msg = self.lpa_service.download_profile(self.smdp_address, self.matching_id)
        self.finished.emit(success, msg)


class ProfileSelector(QGroupBox):
    """
    Panel for selecting and downloading profiles from UPP directory.
    Scans pysim/smdpp-data/upp/ for available .der files.
    """
    
    profile_downloaded = Signal()  # Emitted when download completes
    
    def __init__(self, lpa_service: LPAService, profile_store: ProfileStore, 
                 upp_dir: str, log_path: str = None):
        super().__init__("Profile Selector")
        self.lpa_service = lpa_service
        self.profile_store = profile_store
        self.upp_dir = Path(upp_dir)
        self.log_path = log_path or "/Users/jhurykevinlastre/Documents/projects/virtual-rsp/data/veuicc.log"
        self.download_thread = None
        self.download_dialog = None
        
        self._setup_ui()
        self._scan_profiles()
    
    def _setup_ui(self):
        """Create UI layout"""
        layout = QVBoxLayout()
        
        # SM-DP+ address
        addr_layout = QHBoxLayout()
        addr_layout.addWidget(QLabel("SM-DP+ Address:"))
        self.smdp_address = QLineEdit("testsmdpplus1.example.com:8443")
        addr_layout.addWidget(self.smdp_address)
        layout.addLayout(addr_layout)
        
        # Profile dropdown
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(300)
        profile_layout.addWidget(self.profile_combo)
        layout.addLayout(profile_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._scan_profiles)
        btn_layout.addWidget(self.refresh_btn)
        
        self.download_btn = QPushButton("Download Profile")
        self.download_btn.clicked.connect(self._download_profile)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                font-size: 13px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #0e6b0e;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        btn_layout.addWidget(self.download_btn)
        
        layout.addLayout(btn_layout)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        # Info label
        info_label = QLabel(
            "<b>Note:</b> Ensure v-euicc, SM-DP+, and nginx are running before downloading."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #0078d4; font-size: 10px; margin-top: 10px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def _scan_profiles(self):
        """Scan UPP directory for available profiles"""
        self.profile_combo.clear()
        
        if not self.upp_dir.exists():
            self.status_label.setText(f'<span style="color: red;">UPP directory not found: {self.upp_dir}</span>')
            self.status_label.setTextFormat(Qt.RichText)
            return
        
        # Find all .der files with UNIQUE suffix (for testing)
        profiles = sorted(self.upp_dir.glob("*-UNIQUE.der"))
        
        if not profiles:
            self.status_label.setText('<span style="color: orange;">No profiles found in UPP directory</span>')
            self.status_label.setTextFormat(Qt.RichText)
            return
        
        # Add to combo box (use stem as matching ID)
        for profile in profiles:
            matching_id = profile.stem  # Remove .der extension
            self.profile_combo.addItem(matching_id)
        
        self.status_label.setText(f'<span style="color: green;">Found {len(profiles)} available profiles</span>')
        self.status_label.setTextFormat(Qt.RichText)
    
    def _download_profile(self):
        """Start profile download with live log dialog"""
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, "Download in Progress", "Please wait for current download to complete.")
            return
        
        matching_id = self.profile_combo.currentText()
        smdp_address = self.smdp_address.text()
        
        if not matching_id:
            QMessageBox.warning(self, "No Profile Selected", "Please select a profile to download.")
            return
        
        # Disable controls
        self.download_btn.setEnabled(False)
        self.profile_combo.setEnabled(False)
        self.smdp_address.setEnabled(False)
        
        # Create and show download dialog with live logs
        self.download_dialog = DownloadDialog(matching_id, self.log_path, self)
        
        # Start download thread
        self.download_thread = DownloadThread(self.lpa_service, smdp_address, matching_id)
        self.download_thread.finished.connect(self._on_download_complete)
        self.download_thread.start()
        
        # Show dialog (non-blocking since download is in background thread)
        self.download_dialog.exec()
    
    def _on_download_complete(self, success: bool, message: str):
        """Handle download completion"""
        # Re-enable controls
        self.download_btn.setEnabled(True)
        self.profile_combo.setEnabled(True)
        self.smdp_address.setEnabled(True)
        
        matching_id = self.profile_combo.currentText()
        
        # Update dialog if still open
        if self.download_dialog:
            self.download_dialog.on_download_finished(success, message)
        
        if success:
            # Sync ALL profiles from v-euicc logs to store
            self._sync_all_profiles_from_logs()
            
            self.status_label.setText(f'<span style="color: green;">✓ {message}</span>')
            self.status_label.setTextFormat(Qt.RichText)
            self.profile_downloaded.emit()
        else:
            self.status_label.setText(f'<span style="color: red;">✗ {message}</span>')
            self.status_label.setTextFormat(Qt.RichText)
    
    def refresh_available_profiles(self):
        """Public method to refresh profile list"""
        self._scan_profiles()
    
    def _sync_all_profiles_from_logs(self):
        """
        Sync ALL installed profiles from v-euicc logs to profile store.
        This finds all profiles in logs and adds any missing ones.
        Uses matching_id (profile name) as unique key since test profiles share ICCIDs.
        """
        log_paths = [
            Path(self.log_path),
            Path("/tmp/detailed-euicc.log")
        ]
        
        found_profiles = []
        
        for log_path in log_paths:
            if not log_path.exists():
                continue
            
            try:
                content = log_path.read_text()
                
                # Look for ALL "Created profile metadata:" lines
                pattern = r'Created profile metadata: ICCID=(\d+), Name=([^\s,]+)'
                matches = re.findall(pattern, content)
                
                for iccid, name in matches:
                    found_profiles.append((iccid, name))
            except Exception:
                pass
        
        # Add all found profiles that aren't already in the store
        # Use matching_id (profile name) as unique key
        for iccid, name in found_profiles:
            existing = self.profile_store.get_profile(matching_id=name)
            if not existing:
                profile = Profile(
                    iccid=iccid,
                    isdp_aid="",
                    state=ProfileState.DISABLED,
                    profile_name=name,
                    service_provider="OsmocomSPN",
                    matching_id=name
                )
                self.profile_store.add_profile(profile)
