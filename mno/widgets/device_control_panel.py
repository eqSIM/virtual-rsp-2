"""
Device Control Panel - Send LPA commands to eUICC from MNO perspective
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QTableWidget, QTableWidgetItem, QHeaderView, 
                                QMessageBox, QLabel, QGroupBox, QDialog, QFormLayout,
                                QComboBox, QLineEdit, QDialogButtonBox, QTextEdit,
                                QSplitter)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QProcess
from PySide6.QtGui import QTextCursor, QColor
from mno.services.lpa_command import LpaCommandService
from mno.services.config import Config
import os


class DownloadWorker(QThread):
    """Worker thread for profile downloads with real-time log output"""
    finished = Signal(bool, str)  # success, message
    log_output = Signal(str)  # real-time log line
    
    def __init__(self, lpa_service, smdp_address, matching_id):
        super().__init__()
        self.lpa = lpa_service
        self.smdp_address = smdp_address
        self.matching_id = matching_id
    
    def run(self):
        import subprocess
        
        self.log_output.emit(f"[INFO] Starting download: {self.matching_id}")
        self.log_output.emit(f"[INFO] SM-DP+ Address: {self.smdp_address}")
        self.log_output.emit(f"[INFO] Running lpac profile download...")
        self.log_output.emit("")
        
        try:
            # Run lpac with real-time output capture
            args = ['profile', 'download', '-s', self.smdp_address, '-m', self.matching_id]
            
            process = subprocess.Popen(
                [str(self.lpa.lpac_path)] + args,
                env=self.lpa.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(self.lpa.project_root),
                bufsize=1
            )
            
            output_lines = []
            # Read output line by line
            for line in iter(process.stdout.readline, ''):
                if line:
                    line = line.strip()
                    output_lines.append(line)
                    # Parse and emit formatted log
                    self._emit_log_line(line)
            
            process.wait(timeout=120)
            
            full_output = '\n'.join(output_lines)
            
            if process.returncode == 0:
                # Add profile to ProfileStore (single source of truth)
                from gui.services.profile_store import Profile, ProfileState
                new_profile = Profile(
                    iccid="8949449999999990049",  # Standard test ICCID
                    isdp_aid="",
                    state=ProfileState.DISABLED,
                    profile_name=self.matching_id,
                    service_provider="OsmocomSPN",
                    matching_id=self.matching_id
                )
                self.lpa.profile_store.add_profile(new_profile)
                
                self.log_output.emit("")
                self.log_output.emit("[SUCCESS] Profile downloaded and saved!")
                self.finished.emit(True, f"Profile {self.matching_id} downloaded successfully")
            else:
                self.log_output.emit("")
                self.log_output.emit(f"[ERROR] Download failed (exit code: {process.returncode})")
                self.finished.emit(False, full_output or "Download failed")
                
        except subprocess.TimeoutExpired:
            self.log_output.emit("[ERROR] Command timed out after 120 seconds")
            self.finished.emit(False, "Command timed out")
        except Exception as e:
            self.log_output.emit(f"[ERROR] Exception: {str(e)}")
            self.finished.emit(False, str(e))
    
    def _emit_log_line(self, line: str):
        """Parse lpac JSON output and emit readable log"""
        import json
        try:
            data = json.loads(line)
            msg_type = data.get('type', '')
            payload = data.get('payload', {})
            
            if msg_type == 'progress':
                step = payload.get('message', 'unknown')
                code = payload.get('code', -1)
                extra = payload.get('data', '')
                
                # Format step name nicely
                step_display = step.replace('_', ' ').title()
                
                if code == 0:
                    self.log_output.emit(f"  ✓ {step_display}")
                    if isinstance(extra, dict):
                        # Show profile metadata if available
                        if 'iccid' in extra:
                            self.log_output.emit(f"      ICCID: {extra.get('iccid')}")
                        if 'profileName' in extra:
                            self.log_output.emit(f"      Name: {extra.get('profileName')}")
                else:
                    self.log_output.emit(f"  ✗ {step_display} (code: {code})")
                    
            elif msg_type == 'lpa':
                code = payload.get('code', -1)
                msg = payload.get('message', '')
                data_info = payload.get('data', '')
                
                if code == 0:
                    self.log_output.emit(f"[LPA] {msg}: Success")
                else:
                    self.log_output.emit(f"[LPA ERROR] {msg}: {data_info}")
            else:
                # Unknown type, just show raw
                self.log_output.emit(f"  {line[:100]}")
        except json.JSONDecodeError:
            # Not JSON, show as-is
            if line.strip():
                self.log_output.emit(f"  {line}")


class DownloadProfileDialog(QDialog):
    """Dialog for initiating profile download to connected device"""
    
    def __init__(self, smdp_api, parent=None):
        super().__init__(parent)
        self.smdp_api = smdp_api
        self.setWindowTitle("Download Profile to Device")
        self.setMinimumWidth(400)
        self._setup_ui()
        self._load_available_profiles()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        # SM-DP+ Address
        self.smdp_input = QLineEdit("testsmdpplus1.example.com:8443")
        form.addRow("SM-DP+ Address:", self.smdp_input)
        
        # Profile Selection
        self.profile_combo = QComboBox()
        form.addRow("Profile:", self.profile_combo)
        
        layout.addLayout(form)
        
        # Info
        info = QLabel(
            "<b>Note:</b> This will download the selected profile from the SM-DP+ "
            "server to the currently connected eUICC device."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666666; font-size: 11px; margin: 10px 0;")
        layout.addWidget(info)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _load_available_profiles(self):
        """Load available profiles from SM-DP+ server"""
        profiles = self.smdp_api.list_profiles()
        self.profile_combo.clear()
        
        if profiles:
            for profile in profiles:
                matching_id = profile.get('matching_id', 'Unknown')
                self.profile_combo.addItem(matching_id)
        else:
            self.profile_combo.addItem("No profiles available")
    
    def get_values(self):
        """Get selected values"""
        return {
            'smdp_address': self.smdp_input.text(),
            'matching_id': self.profile_combo.currentText()
        }


class DeviceControlPanel(QWidget):
    """
    Panel for MNO to control profiles on connected eUICC device.
    Allows enable/disable/switch operations via LPA commands.
    """
    
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.lpa = LpaCommandService(Config.PROJECT_ROOT)
        self._setup_ui()
        
        # Auto-refresh
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_device_state)
        self.timer.start(3000)
        
        # Initial refresh - don't crash if device not connected
        try:
            self.refresh_device_state()
        except Exception:
            pass  # Will retry on next timer tick

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Device Info Section
        info_group = QGroupBox("Connected eUICC Device")
        info_layout = QHBoxLayout(info_group)
        
        self.eid_label = QLabel("EID: Not connected")
        self.eid_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        info_layout.addWidget(self.eid_label)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_device_state)
        info_layout.addWidget(self.refresh_btn)
        
        info_layout.addStretch()
        layout.addWidget(info_group)
        
        # Action Buttons
        action_group = QGroupBox("Profile Operations")
        action_layout = QHBoxLayout(action_group)
        
        self.download_btn = QPushButton("Download Profile to Device")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                font-size: 13px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #0e6b0e;
            }
        """)
        self.download_btn.clicked.connect(self.download_profile)
        action_layout.addWidget(self.download_btn)
        
        action_layout.addStretch()
        layout.addWidget(action_group)
        
        # Profiles Table
        profiles_group = QGroupBox("Installed Profiles on Device")
        profiles_layout = QVBoxLayout(profiles_group)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ICCID", "Profile Name", "State", "Provider", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        profiles_layout.addWidget(self.table)
        layout.addWidget(profiles_group)
        
        # Log Viewer
        log_group = QGroupBox("Operation Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMaximumHeight(150)
        self.log_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
                font-size: 11px;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        self.log_viewer.setPlaceholderText("Operation logs will appear here...")
        log_layout.addWidget(self.log_viewer)
        
        # Clear log button
        clear_btn = QPushButton("Clear Log")
        clear_btn.setFixedWidth(100)
        clear_btn.clicked.connect(self.log_viewer.clear)
        log_layout.addWidget(clear_btn, alignment=Qt.AlignRight)
        
        layout.addWidget(log_group)

    def refresh_device_state(self):
        """Refresh device information and profile list"""
        try:
            # Get EID
            eid = self.lpa.get_eid()
            if eid:
                self.eid_label.setText(f"EID: {eid}")
                self.eid_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #107c10;")
            else:
                self.eid_label.setText("EID: Device not connected")
                self.eid_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #d83b01;")
                self.table.setRowCount(0)
                return
            
            # Get profiles
            profiles = self.lpa.list_profiles()
            if not isinstance(profiles, list):
                profiles = []
            
            self.table.setRowCount(0)
            
            for profile in profiles:
                if not isinstance(profile, dict):
                    continue
                    
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                iccid = profile.get('iccid', 'Unknown')
                name = profile.get('profileName', profile.get('profileNickname', 'Unknown'))
                state = profile.get('profileState', 'Unknown')
                provider = profile.get('serviceProviderName', 'Unknown')
                
                self.table.setItem(row, 0, QTableWidgetItem(str(iccid)))
                self.table.setItem(row, 1, QTableWidgetItem(str(name)))
                
                state_item = QTableWidgetItem(str(state))
                if str(state).lower() == 'enabled':
                    state_item.setForeground(Qt.green)
                else:
                    state_item.setForeground(Qt.gray)
                self.table.setItem(row, 2, state_item)
                
                self.table.setItem(row, 3, QTableWidgetItem(str(provider)))
                
                # Action buttons
                actions = QWidget()
                act_layout = QHBoxLayout(actions)
                act_layout.setContentsMargins(2, 2, 2, 2)
                act_layout.setSpacing(4)
                
                if str(state).lower() == 'enabled':
                    disable_btn = QPushButton("Disable")
                    disable_btn.setObjectName("danger")
                    disable_btn.setStyleSheet("padding: 4px 8px; font-size: 11px;")
                    disable_btn.clicked.connect(lambda checked, i=iccid: self.disable_profile(i))
                    act_layout.addWidget(disable_btn)
                    
                    # Delete button (disabled for enabled profiles)
                    delete_btn = QPushButton("Delete")
                    delete_btn.setEnabled(False)
                    delete_btn.setStyleSheet("padding: 4px 8px; font-size: 11px;")
                    delete_btn.setToolTip("Disable profile first before deleting")
                    act_layout.addWidget(delete_btn)
                else:
                    enable_btn = QPushButton("Enable")
                    enable_btn.setStyleSheet("background-color: #107c10; padding: 4px 8px; font-size: 11px;")
                    enable_btn.clicked.connect(lambda checked, i=iccid: self.enable_profile(i))
                    act_layout.addWidget(enable_btn)
                    
                    # Delete button (enabled for disabled profiles)
                    delete_btn = QPushButton("Delete")
                    delete_btn.setObjectName("danger")
                    delete_btn.setStyleSheet("padding: 4px 8px; font-size: 11px;")
                    delete_btn.clicked.connect(lambda checked, i=iccid: self.delete_profile(i))
                    act_layout.addWidget(delete_btn)
                
                act_layout.addStretch()
                self.table.setCellWidget(row, 4, actions)
        except Exception as e:
            # Handle any errors gracefully
            self.eid_label.setText(f"EID: Error - {str(e)}")
            self.eid_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #d83b01;")
            self.table.setRowCount(0)
    
    def _append_log(self, text: str):
        """Append text to log viewer with color coding"""
        cursor = self.log_viewer.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Color code based on content
        if text.startswith('[ERROR]') or text.startswith('[LPA ERROR]') or '✗' in text:
            color = '#f14c4c'  # Red
        elif text.startswith('[SUCCESS]') or '✓' in text:
            color = '#4ec9b0'  # Green
        elif text.startswith('[INFO]') or text.startswith('[LPA]'):
            color = '#569cd6'  # Blue
        elif text.startswith('      '):
            color = '#9cdcfe'  # Light blue for details
        else:
            color = '#d4d4d4'  # Default gray
        
        cursor.insertHtml(f'<span style="color: {color};">{text}</span><br>')
        self.log_viewer.setTextCursor(cursor)
        self.log_viewer.ensureCursorVisible()

    def download_profile(self):
        """Open dialog to download profile to device"""
        dialog = DownloadProfileDialog(self.api, self)
        if dialog.exec() == QDialog.Accepted:
            values = dialog.get_values()
            smdp_address = values['smdp_address']
            matching_id = values['matching_id']
            
            if matching_id == "No profiles available":
                QMessageBox.warning(self, "No Profiles", "No profiles available on SM-DP+ server")
                return
            
            # Show confirmation
            reply = QMessageBox.question(
                self,
                "Download Profile",
                f"Download profile '{matching_id}' from {smdp_address} to the connected device?\n\n"
                "This will initiate a full RSP session.",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Clear log and add start message
                self.log_viewer.clear()
                self._append_log("=" * 50)
                self._append_log(f"[INFO] Download started at {self._get_timestamp()}")
                self._append_log("=" * 50)
                
                # Disable download button during operation
                self.download_btn.setEnabled(False)
                self.download_btn.setText("Downloading...")
                
                # Create and start worker thread
                self.download_worker = DownloadWorker(self.lpa, smdp_address, matching_id)
                self.download_worker.log_output.connect(self._append_log)
                self.download_worker.finished.connect(self._on_download_complete)
                self.download_worker.start()
    
    def _get_timestamp(self):
        """Get current timestamp string"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")

    def _on_download_complete(self, success: bool, msg: str):
        """Handle download completion"""
        # Re-enable download button
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Download Profile to Device")
        
        self._append_log("=" * 50)
        self._append_log(f"[INFO] Download completed at {self._get_timestamp()}")
        
        if success:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Error", f"Download failed:\n{msg}")
        
        self.refresh_device_state()

    def enable_profile(self, iccid: str):
        """Enable profile on device"""
        reply = QMessageBox.question(
            self,
            "Enable Profile",
            f"Enable profile {iccid} on the connected device?\n\n"
            "This will disable any currently enabled profile (SGP.22 rule).",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._append_log(f"[INFO] Enabling profile: {iccid}")
            success, msg = self.lpa.enable_profile(iccid)
            if success:
                self._append_log(f"[SUCCESS] Profile enabled: {iccid}")
                QMessageBox.information(self, "Success", msg)
            else:
                self._append_log(f"[ERROR] Enable failed: {msg}")
                QMessageBox.critical(self, "Error", f"Failed to enable profile:\n{msg}")
            self.refresh_device_state()

    def disable_profile(self, iccid: str):
        """Disable profile on device"""
        reply = QMessageBox.question(
            self,
            "Disable Profile",
            f"Disable profile {iccid} on the connected device?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._append_log(f"[INFO] Disabling profile: {iccid}")
            success, msg = self.lpa.disable_profile(iccid)
            if success:
                self._append_log(f"[SUCCESS] Profile disabled: {iccid}")
                QMessageBox.information(self, "Success", msg)
            else:
                self._append_log(f"[ERROR] Disable failed: {msg}")
                QMessageBox.critical(self, "Error", f"Failed to disable profile:\n{msg}")
            self.refresh_device_state()
    
    def delete_profile(self, iccid: str):
        """Delete profile from device"""
        reply = QMessageBox.warning(
            self,
            "Delete Profile",
            f"Permanently delete profile {iccid} from the connected device?\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._append_log(f"[INFO] Deleting profile: {iccid}")
            success, msg = self.lpa.delete_profile(iccid)
            if success:
                self._append_log(f"[SUCCESS] Profile deleted: {iccid}")
                QMessageBox.information(self, "Success", msg)
            else:
                self._append_log(f"[ERROR] Delete failed: {msg}")
                QMessageBox.critical(self, "Error", f"Failed to delete profile:\n{msg}")
            self.refresh_device_state()
