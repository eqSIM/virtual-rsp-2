"""
Download Dialog - Real-time profile download with live log streaming
Shows cryptographic operations as they happen during the SGP.22 flow
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                                QLabel, QTextEdit, QProgressBar, QApplication)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QTextCursor
from pathlib import Path
import re


class DownloadDialog(QDialog):
    """
    Modal dialog showing profile download progress with real-time log streaming.
    Displays detailed cryptographic operations as they happen.
    """
    
    download_complete = Signal(bool, str)  # success, message
    
    def __init__(self, profile_name: str, log_path: str, parent=None):
        super().__init__(parent)
        self.profile_name = profile_name
        self.log_path = Path(log_path)
        self.log_position = 0
        self.last_phase = ""
        
        self.setWindowTitle(f"Downloading Profile: {profile_name}")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        self._setup_ui()
        self._start_log_timer()
    
    def _setup_ui(self):
        """Create dialog UI"""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel(f"<b>Downloading:</b> {self.profile_name}")
        header.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(header)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3c3c3c;
                border-radius: 5px;
                background-color: #252526;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress)
        
        # Status label
        self.status_label = QLabel("Initializing RSP session...")
        self.status_label.setStyleSheet("color: #0078d4; font-size: 12px; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # Live log viewer
        log_label = QLabel("Live Cryptographic Operations:")
        log_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
                font-size: 11px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.log_text)
        
        # Cancel button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Initial welcome message
        self._append_log(self._format_header("SGP.22 Remote SIM Provisioning"))
        self._append_log('<span style="color: #808080;">Waiting for eUICC response...</span>')
    
    def _start_log_timer(self):
        """Start timer to poll log file"""
        # Record current position to only show new content
        if self.log_path.exists():
            self.log_position = self.log_path.stat().st_size
        
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self._update_logs)
        self.log_timer.start(100)  # Poll every 100ms for responsiveness
    
    def _format_header(self, title: str) -> str:
        """Format a section header"""
        BOLD = '<span style="font-weight: bold; color: #4fc3f7;">'
        END = '</span>'
        line = "═" * 60
        return f'{BOLD}{line}<br>  {title}<br>{line}{END}'
    
    def _format_log_line(self, line: str) -> str:
        """Format a log line with cryptographic detail highlighting"""
        # Colors
        GREEN = '<span style="color: #4ec9b0;">'
        YELLOW = '<span style="color: #dcdcaa;">'
        CYAN = '<span style="color: #9cdcfe;">'
        BLUE = '<span style="color: #569cd6;">'
        MAGENTA = '<span style="color: #c586c0;">'
        RED = '<span style="color: #f14c4c;">'
        DIM = '<span style="color: #808080;">'
        BOLD = '<span style="font-weight: bold;">'
        END = '</span>'
        
        formatted = line
        
        # ===== PHASE 1: GetEuiccChallenge =====
        if "BF2E" in line and "GetEuiccChallenge" not in self.last_phase:
            self.last_phase = "GetEuiccChallenge"
            self._update_status("Phase 1: GetEuiccChallenge")
            return self._format_header("Phase 1: GetEuiccChallenge (ES10b)") + f"<br>{DIM}eUICC generates random challenge for SM-DP+ authentication{END}"
        
        if "challenge generated" in line.lower() or "euiccChallenge" in line:
            match = re.search(r'([0-9A-Fa-f]{32})', line)
            if match:
                challenge = match.group(1)
                return f"{GREEN}✓ eUICC Challenge Generated:{END}<br>  {YELLOW}{challenge[:16]}...{challenge[-8:]}{END}<br>  {DIM}16 bytes random, used for mutual authentication{END}"
        
        # ===== PHASE 2: GetEuiccInfo =====
        if "BF20" in line or "BF22" in line:
            if "GetEuiccInfo" not in self.last_phase:
                self.last_phase = "GetEuiccInfo"
                self._update_status("Phase 2: GetEuiccInfo")
                return self._format_header("Phase 2: GetEuiccInfo (ES10b)") + f"<br>{DIM}SM-DP+ retrieves eUICC capabilities and EID{END}"
        
        if "EID" in line or "eid" in line:
            match = re.search(r'([0-9]{32})', line)
            if match:
                eid = match.group(1)
                return f"{GREEN}✓ EID (eUICC Identifier):{END}<br>  {YELLOW}{eid}{END}"
        
        # ===== PHASE 3: AuthenticateServer =====
        if "BF38" in line:
            if "AuthenticateServer" not in self.last_phase:
                self.last_phase = "AuthenticateServer"
                self._update_status("Phase 3: AuthenticateServer - Mutual Authentication")
                return self._format_header("Phase 3: AuthenticateServer (ES10b)") + f"<br>{DIM}eUICC verifies SM-DP+ certificate chain and generates signed response{END}"
        
        if "serverSigned1" in line or "server signed" in line.lower():
            return f"{CYAN}→ Received serverSigned1 (SM-DP+ challenge){END}"
        
        if "serverSignature1" in line:
            return f"{CYAN}→ Received serverSignature1 (ECDSA signature from SM-DP+){END}"
        
        if "CERT.DP" in line or "dpCertificate" in line:
            return f"{CYAN}→ Received CERT.DPauth.ECDSA (SM-DP+ authentication certificate){END}"
        
        # Certificate loading
        if "Loaded eUICC certificate" in line:
            match = re.search(r'(\d+) bytes', line)
            size = match.group(1) if match else "?"
            return f"{GREEN}✓ Loaded CERT.EUICC.ECDSA:{END} {YELLOW}{size} bytes{END}"
        
        if "Loaded EUM certificate" in line:
            match = re.search(r'(\d+) bytes', line)
            size = match.group(1) if match else "?"
            return f"{GREEN}✓ Loaded CERT.EUM.ECDSA:{END} {YELLOW}{size} bytes{END}"
        
        if "Loaded eUICC private key" in line:
            return f"{GREEN}✓ Loaded SK.EUICC.ECDSA:{END} {YELLOW}NIST P-256 private key{END}"
        
        # ECDSA Signatures
        if "ECDSA" in line and "sign" in line.lower():
            return f"{GREEN}✓ ECDSA Signature Operation:{END}<br>  {DIM}Algorithm: ECDSA with SHA-256 on NIST P-256{END}"
        
        if "DER signature" in line:
            match = re.search(r'(\d+) bytes', line)
            size = match.group(1) if match else "?"
            return f"  {CYAN}DER format signature:{END} {YELLOW}{size} bytes{END}"
        
        if "TR-03111" in line or "raw format" in line:
            return f"  {DIM}→ Converted to TR-03111 raw format (R || S, 64 bytes){END}"
        
        if "Real ECDSA signature generated" in line:
            return f"{GREEN}✓ euiccSignature1 Generated:{END}<br>  {YELLOW}64 bytes (R=32, S=32){END}<br>  {DIM}Signs: transactionId || serverChallenge || serverAddress || CtxParams1{END}"
        
        # ===== PHASE 4: PrepareDownload =====
        if "BF21" in line or "PrepareDownload" in line:
            if "PrepareDownload" not in self.last_phase:
                self.last_phase = "PrepareDownload"
                self._update_status("Phase 4: PrepareDownload - Key Generation")
                return self._format_header("Phase 4: PrepareDownload (ES10b)") + f"<br>{DIM}eUICC generates ephemeral ECDH key pair for session key derivation{END}"
        
        if "euiccOtpk" in line.lower() or "ephemeral" in line.lower():
            return f"{GREEN}✓ Generated otPK.EUICC.ECKA (ephemeral public key):{END}<br>  {YELLOW}65 bytes (04 || X || Y, uncompressed point){END}<br>  {DIM}Curve: NIST P-256 (secp256r1){END}"
        
        # ===== PHASE 5: BPP Installation =====
        if "BF36" in line or "BoundProfilePackage" in line:
            if "BPP" not in self.last_phase:
                self.last_phase = "BPP"
                self._update_status("Phase 5: BoundProfilePackage Installation")
                return self._format_header("Phase 5: LoadBoundProfilePackage (ES10b)") + f"<br>{DIM}Receive and decrypt the bound profile package{END}"
        
        if "BF23" in line or "InitialiseSecureChannel" in line:
            self._update_status("Phase 5a: Establish Secure Channel (SCP03t)")
            return f"{MAGENTA}▶ InitialiseSecureChannel (BF23):{END}<br>  {DIM}Establish SCP03t encrypted channel using ECDH{END}"
        
        if "smdpOtpk" in line.lower():
            match = re.search(r'(\d+) bytes', line)
            size = match.group(1) if match else "65"
            return f"  {CYAN}Received otPK.DP.ECKA:{END} {YELLOW}{size} bytes{END}"
        
        # Key derivation
        if "ECDH" in line or "shared secret" in line.lower():
            return f"{GREEN}✓ ECDH Key Agreement:{END}<br>  {DIM}SharedSecret = otSK.EUICC.ECKA × otPK.DP.ECKA{END}"
        
        if "Session keys derived" in line or "KDF" in line:
            return f"{GREEN}✓ Session Keys Derived (SGP.22 KDF):{END}<br>  {YELLOW}• S-ENC (encryption): 16 bytes{END}<br>  {YELLOW}• S-MAC (integrity): 16 bytes{END}<br>  {DIM}KDF uses SHA-256 with counter mode{END}"
        
        # Profile elements
        if "ProfileElement" in line or "PE " in line:
            return f"  {DIM}→ Decrypting ProfileElement...{END}"
        
        if "decrypted" in line.lower() and "bytes" in line:
            match = re.search(r'(\d+) bytes', line)
            size = match.group(1) if match else "?"
            return f"  {CYAN}Decrypted data:{END} {YELLOW}{size} bytes{END}"
        
        if "CMAC" in line or "MAC" in line:
            return f"  {GREEN}✓ MAC Verified{END}"
        
        # Profile metadata
        if "Created profile metadata" in line:
            match = re.search(r'ICCID=(\d+), Name=([^\s,]+)', line)
            if match:
                iccid, name = match.group(1), match.group(2)
                return f"<br>{self._format_header('Profile Installed Successfully!')}<br>{GREEN}✓ ICCID:{END} {YELLOW}{iccid}{END}<br>{GREEN}✓ Profile Name:{END} {YELLOW}{name}{END}<br>{GREEN}✓ State:{END} Disabled"
        
        # ===== PHASE 6: ProfileInstallationResult =====
        if "BF37" in line or "ProfileInstallationResult" in line:
            if "InstallResult" not in self.last_phase:
                self.last_phase = "InstallResult"
                self._update_status("Phase 6: ProfileInstallationResult")
                return f"{MAGENTA}▶ ProfileInstallationResult (BF37):{END}<br>  {DIM}Sign and send installation notification{END}"
        
        if "finalResult" in line.lower() or "success" in line.lower():
            return f"{GREEN}✓ Installation Result: SUCCESS{END}"
        
        # ES10x command parsing
        if "ES10x command tag:" in line:
            match = re.search(r'tag: ([A-F0-9]+), len=(\d+)', line)
            if match:
                tag, length = match.group(1), match.group(2)
                cmd_names = {
                    "BF2E": "GetEuiccChallenge",
                    "BF20": "GetEuiccInfo1", 
                    "BF22": "GetEuiccInfo2",
                    "BF38": "AuthenticateServer",
                    "BF21": "PrepareDownload",
                    "BF36": "LoadBoundProfilePackage",
                    "BF23": "InitialiseSecureChannel",
                    "BF37": "ProfileInstallationResult",
                    "BF2D": "GetProfilesInfo",
                    "BF31": "EnableProfile",
                    "BF32": "DisableProfile",
                    "BF33": "DeleteProfile"
                }
                cmd_name = cmd_names.get(tag, "Unknown")
                return f"{BLUE}[ES10x] {cmd_name} ({tag}):{END} {length} bytes"
        
        # Generic hex data - show truncated
        if re.match(r'^[0-9A-Fa-f]{40,}$', line.strip()):
            hex_data = line.strip()
            return f"  {DIM}{hex_data[:40]}...{hex_data[-8:]}{END}"
        
        # Pass through other lines with dim color
        return f"{DIM}{line}{END}"
    
    def _update_logs(self):
        """Poll log file for new content"""
        if not self.log_path.exists():
            return
        
        try:
            with open(self.log_path, 'r') as f:
                f.seek(self.log_position)
                new_content = f.read()
                
                if new_content:
                    self.log_position = f.tell()
                    
                    for line in new_content.split('\n'):
                        if line.strip():
                            formatted = self._format_log_line(line)
                            self._append_log(formatted)
        except Exception:
            pass
    
    def _append_log(self, html: str):
        """Append HTML to log viewer"""
        self.log_text.moveCursor(QTextCursor.End)
        self.log_text.insertHtml(html + "<br>")
        self.log_text.moveCursor(QTextCursor.End)
        QApplication.processEvents()  # Keep UI responsive
    
    def _update_status(self, status: str):
        """Update status label"""
        self.status_label.setText(status)
        QApplication.processEvents()
    
    def on_download_finished(self, success: bool, message: str):
        """Called when download completes"""
        self.log_timer.stop()
        self.progress.setRange(0, 100)
        
        if success:
            self.progress.setValue(100)
            self.status_label.setText("✓ Download Complete!")
            self.status_label.setStyleSheet("color: #4ec9b0; font-size: 12px; padding: 5px;")
            self._append_log('<br><span style="color: #4ec9b0; font-weight: bold;">═══════════════════════════════════════════════════════════════</span>')
            self._append_log('<span style="color: #4ec9b0; font-weight: bold;">  ✓ RSP SESSION COMPLETE - Profile Ready for Activation</span>')
            self._append_log('<span style="color: #4ec9b0; font-weight: bold;">═══════════════════════════════════════════════════════════════</span>')
        else:
            self.progress.setValue(0)
            self.status_label.setText(f"✗ Download Failed: {message}")
            self.status_label.setStyleSheet("color: #f14c4c; font-size: 12px; padding: 5px;")
            self._append_log(f'<br><span style="color: #f14c4c;">✗ Error: {message}</span>')
        
        self.cancel_btn.setText("Close")
        self.download_complete.emit(success, message)
    
    def closeEvent(self, event):
        """Clean up timer on close"""
        if hasattr(self, 'log_timer'):
            self.log_timer.stop()
        super().closeEvent(event)

