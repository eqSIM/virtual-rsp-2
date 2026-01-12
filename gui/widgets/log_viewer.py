"""
Log Viewer - Real-time detailed log display with cryptographic information parsing
Mimics the detailed output format of demo-detailed.sh
"""

from PySide6.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton,
                                QTextEdit, QComboBox, QLabel)
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QColor, QTextCharFormat, QFont
from pathlib import Path
from typing import Dict
import re

from gui.services.process_manager import ProcessManager


class LogViewer(QGroupBox):
    """
    Real-time log viewer with detailed cryptographic information.
    Parses v-euicc logs to show SGP.22 protocol flow like demo-detailed.sh.
    """
    
    def __init__(self, process_manager: ProcessManager):
        super().__init__("Log Output")
        self.process_manager = process_manager
        self.log_positions: Dict[str, int] = {}
        self.last_phase = ""
        self._setup_ui()
    
    def _setup_ui(self):
        """Create UI layout"""
        layout = QVBoxLayout()
        
        # Top bar with log selector and clear button
        top_layout = QHBoxLayout()
        
        top_layout.addWidget(QLabel("Service:"))
        self.log_selector = QComboBox()
        self.log_selector.addItems(["v-euicc", "SM-DP+", "nginx"])
        self.log_selector.currentTextChanged.connect(self._on_log_changed)
        top_layout.addWidget(self.log_selector)
        
        top_layout.addStretch()
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear_log)
        top_layout.addWidget(self.clear_btn)
        
        layout.addLayout(top_layout)
        
        # Log text area with monospace font
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        
        # Set dark theme with better contrast
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
                font-size: 12px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.log_text)
        
        self.setLayout(layout)
    
    def _get_current_log_path(self) -> str:
        """Get log file path for currently selected service"""
        service = self.log_selector.currentText()
        service_map = {
            "v-euicc": "veuicc",
            "SM-DP+": "smdp",
            "nginx": "nginx"
        }
        
        service_key = service_map.get(service)
        if not service_key:
            return None
        
        log_path = self.process_manager.get_log_file(service_key)
        if log_path:
            return log_path
        
        # Fallback to default path
        project_root = Path(self.process_manager.project_root)
        default_paths = {
            "veuicc": project_root / "data/veuicc.log",
            "smdp": project_root / "data/smdp.log",
            "nginx": project_root / "data/nginx.log"
        }
        
        return str(default_paths.get(service_key, ""))
    
    def _on_log_changed(self):
        """Handle log selection change"""
        self.log_text.clear()
        self.last_phase = ""
        log_path = self._get_current_log_path()
        if log_path:
            self.log_positions[log_path] = 0
    
    def _clear_log(self):
        """Clear the log display"""
        self.log_text.clear()
        self.last_phase = ""
        log_path = self._get_current_log_path()
        if log_path:
            self.log_positions[log_path] = 0
    
    def _format_log_line(self, line: str) -> str:
        """
        Format a log line with detailed cryptographic information.
        Parses v-euicc output and formats it like demo-detailed.sh.
        """
        # Color codes for different types of information
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
        
        # Phase headers - Authentication
        if "ES10x command tag: BF38" in line:
            if self.last_phase != "auth":
                self.last_phase = "auth"
                header = f"\n{BOLD}═══════════════════════════════════════════════════════════════{END}\n"
                header += f"{BOLD}  Phase 2: AuthenticateServer (ES10b){END}\n"
                header += f"{DIM}  eUICC verifies SM-DP+ certificate and generates challenge response{END}\n"
                header += f"{BOLD}═══════════════════════════════════════════════════════════════{END}\n"
                formatted = header + formatted
        
        # Phase headers - PrepareDownload
        if "ES10x command tag: BF21" in line or "PrepareDownloadRequest" in line:
            if self.last_phase != "prepare":
                self.last_phase = "prepare"
                header = f"\n{BOLD}═══════════════════════════════════════════════════════════════{END}\n"
                header += f"{BOLD}  Phase 3: PrepareDownload (ES10b){END}\n"
                header += f"{DIM}  eUICC generates ephemeral ECKA key pair for session keys{END}\n"
                header += f"{BOLD}═══════════════════════════════════════════════════════════════{END}\n"
                formatted = header + formatted
        
        # Phase headers - BPP
        if "ES10x command tag: BF36" in line or "BF23" in line:
            if self.last_phase != "bpp":
                self.last_phase = "bpp"
                header = f"\n{BOLD}═══════════════════════════════════════════════════════════════{END}\n"
                header += f"{BOLD}  Phase 4: Bound Profile Package (BPP) Installation{END}\n"
                header += f"{DIM}  Establish encrypted session using ECDH key agreement{END}\n"
                header += f"{BOLD}═══════════════════════════════════════════════════════════════{END}\n"
                formatted = header + formatted
        
        # Highlight specific cryptographic operations
        
        # ECDSA signature generation
        if "DER signature generated" in line:
            match = re.search(r'(\d+) bytes', line)
            if match:
                formatted = f"{GREEN}✓ ECDSA Signature:{END} {YELLOW}DER format, {match.group(1)} bytes{END}"
        
        if "TR-03111 raw format" in line:
            match = re.search(r'(\d+) bytes \(R=(\d+), S=(\d+)\)', line)
            if match:
                formatted = f"  {DIM}→ Converted to TR-03111 raw format: {match.group(1)} bytes (R={match.group(2)}, S={match.group(3)}){END}"
        
        if "Real ECDSA signature generated" in line:
            match = re.search(r'\((\d+) bytes\)', line)
            size = match.group(1) if match else "64"
            formatted = f"{GREEN}✓ Real ECDSA Signature Generated:{END} {YELLOW}{size} bytes{END}\n"
            formatted += f"  {DIM}Algorithm: ECDSA with NIST P-256 curve{END}\n"
            formatted += f"  {DIM}Format: TR-03111 raw format (R || S, 32+32 bytes){END}"
        
        # Server address
        if "Extracted serverAddress:" in line:
            match = re.search(r'serverAddress: ([^\s]+)', line)
            if match:
                formatted = f"{CYAN}→ Server Address:{END} {YELLOW}{match.group(1)}{END}"
        
        # Matching ID
        if "Extracted matchingID:" in line:
            match = re.search(r'matchingID: ([^\s]+)', line)
            if match:
                formatted = f"{CYAN}→ Matching ID:{END} {YELLOW}{match.group(1)}{END}"
        
        # Transaction ID
        if "Extracted transactionID:" in line:
            formatted = f"{CYAN}→ Transaction ID:{END} {YELLOW}<16 bytes, hidden for security>{END}"
        
        # Ephemeral key generation
        if "Generated valid euiccOtpk:" in line:
            match = re.search(r': (.+)', line)
            key_preview = match.group(1)[:30] + "..." if match else ""
            formatted = f"{GREEN}✓ Generated Ephemeral Key Pair (otPK/otSK.EUICC.ECKA){END}\n"
            formatted += f"  {CYAN}Public Key:{END} {YELLOW}{key_preview}{END}\n"
            formatted += f"  {DIM}Curve: NIST P-256 (secp256r1){END}\n"
            formatted += f"  {DIM}Format: Uncompressed point (04 || X || Y), 65 bytes{END}"
        
        # Session keys derived
        if "Session keys derived" in line:
            formatted = f"{GREEN}✓ Session Keys Derived (SGP.22 Annex G):{END}\n"
            formatted += f"  {DIM}1. ECDH shared secret = otSK.EUICC.ECKA × otPK.DP.ECKA{END}\n"
            formatted += f"  {DIM}2. KDF (SHA-256 based) derives KEK and KM{END}\n"
            formatted += f"  {YELLOW}• KEK (Key Encryption Key): 16 bytes{END}\n"
            formatted += f"  {YELLOW}• KM (Key for MAC): 16 bytes{END}"
        
        # Profile metadata created
        if "Created profile metadata:" in line:
            match = re.search(r'ICCID=(\d+), Name=([^\s,]+)', line)
            if match:
                formatted = f"\n{GREEN}{'═' * 60}{END}\n"
                formatted += f"{GREEN}✓ Profile Successfully Installed!{END}\n"
                formatted += f"{GREEN}{'═' * 60}{END}\n"
                formatted += f"  {CYAN}ICCID:{END} {YELLOW}{match.group(1)}{END}\n"
                formatted += f"  {CYAN}Profile Name:{END} {YELLOW}{match.group(2)}{END}\n"
                formatted += f"  {CYAN}Service Provider:{END} OsmocomSPN\n"
                formatted += f"  {CYAN}State:{END} Disabled (default)"
        
        # ProfileInstallationResult
        if "ProfileInstallationResult built successfully" in line:
            match = re.search(r'\((\d+) bytes\)', line)
            size = match.group(1) if match else "?"
            formatted = f"{CYAN}→ ProfileInstallationResult (BF37):{END} {YELLOW}{size} bytes{END}\n"
            formatted += f"  {DIM}Structure: BF37 {{ BF27 {{ transactionId, notificationMetadata,{END}\n"
            formatted += f"  {DIM}           smdpOid, finalResult }}, euiccSignPIR }}{END}"
        
        # BPP commands
        if "BF36 wrapper detected" in line:
            match = re.search(r'len=(\d+)', line)
            size = match.group(1) if match else "?"
            formatted = f"{GREEN}✓ BoundProfilePackage Received:{END} {YELLOW}{size} bytes{END}"
        
        # InitialiseSecureChannel
        if "InitialiseSecureChannelRequest" in line and "BF23" in line:
            formatted = f"{CYAN}→ InitialiseSecureChannel (BF23):{END}\n"
            formatted += f"  {DIM}Establish encrypted session using ECDH key agreement{END}"
        
        # smdpOtpk extraction
        if "Extracted smdpOtpk" in line:
            match = re.search(r'(\d+) bytes', line)
            size = match.group(1) if match else "65"
            formatted = f"  {CYAN}SM-DP+ Public Key (otPK.DP.ECKA):{END} {YELLOW}{size} bytes{END}"
        
        # Certificate loading
        if "Loaded eUICC certificate:" in line:
            match = re.search(r'(\d+) bytes', line)
            size = match.group(1) if match else "?"
            formatted = f"{GREEN}✓ Loaded CERT.EUICC.ECDSA:{END} {size} bytes"
        
        if "Loaded EUM certificate:" in line:
            match = re.search(r'(\d+) bytes', line)
            size = match.group(1) if match else "?"
            formatted = f"{GREEN}✓ Loaded CERT.EUM.ECDSA:{END} {size} bytes"
        
        if "Loaded eUICC private key" in line:
            formatted = f"{GREEN}✓ Loaded SK.EUICC.ECDSA (P-256 private key){END}"
        
        # ES10x commands
        if "ES10x command tag:" in line:
            match = re.search(r'tag: ([A-F0-9]+), len=(\d+)', line)
            if match:
                tag = match.group(1)
                length = match.group(2)
                cmd_names = {
                    "BF2E": "GetEuiccChallenge",
                    "BF20": "GetEuiccInfo1",
                    "BF22": "GetEuiccInfo2",
                    "BF38": "AuthenticateServer",
                    "BF21": "PrepareDownload",
                    "BF36": "LoadBoundProfilePackage",
                    "BF23": "InitialiseSecureChannel",
                    "BF2D": "GetProfilesInfo",
                    "BF31": "EnableProfile",
                    "BF32": "DisableProfile",
                    "BF33": "DeleteProfile",
                    "BF3E": "GetEuiccData",
                    "BF3C": "GetConfiguredAddresses",
                    "BF41": "CancelSession"
                }
                cmd_name = cmd_names.get(tag, "Unknown")
                formatted = f"{BLUE}[ES10x] {cmd_name} ({tag}):{END} {length} bytes"
        
        # Stored BPP data
        if "Stored" in line and "BPP data" in line:
            match = re.search(r'total: (\d+)', line)
            if match:
                formatted = f"  {DIM}→ Total encrypted profile data: {match.group(1)} bytes{END}"
        
        return formatted
    
    def update_logs(self):
        """
        Update log display with new content (called periodically by timer).
        Parses and formats logs with detailed cryptographic information.
        """
        log_path = self._get_current_log_path()
        if not log_path or not Path(log_path).exists():
            return
        
        try:
            current_pos = self.log_positions.get(log_path, 0)
            
            with open(log_path, 'r') as f:
                f.seek(current_pos)
                new_content = f.read()
                
                if new_content:
                    self.log_positions[log_path] = f.tell()
                    
                    # Process each line
                    lines = new_content.split('\n')
                    for line in lines:
                        if line.strip():
                            formatted_line = self._format_log_line(line)
                            # Append as HTML
                            self.log_text.moveCursor(QTextCursor.End)
                            self.log_text.insertHtml(formatted_line + "<br>")
                    
                    # Auto-scroll to bottom
                    self.log_text.moveCursor(QTextCursor.End)
        
        except Exception:
            pass
    
    def load_full_log(self):
        """Load entire log file (for initial view or after clear)"""
        log_path = self._get_current_log_path()
        if not log_path or not Path(log_path).exists():
            return
        
        try:
            with open(log_path, 'r') as f:
                content = f.read()
                
                # Clear and reformat entire log
                self.log_text.clear()
                
                lines = content.split('\n')
                for line in lines:
                    if line.strip():
                        formatted_line = self._format_log_line(line)
                        self.log_text.append(formatted_line)
                
                self.log_positions[log_path] = f.tell()
                self.log_text.moveCursor(QTextCursor.End)
        except Exception:
            pass
