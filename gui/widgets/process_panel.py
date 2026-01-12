"""
Process Panel - Control v-euicc, SM-DP+, and nginx processes
"""

from PySide6.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton,
                                QLabel, QWidget)
from PySide6.QtCore import Qt, Signal, QTimer
from gui.services.process_manager import ProcessManager


class ProcessPanel(QGroupBox):
    """
    Panel for starting/stopping backend processes.
    Shows status indicators and control buttons.
    """
    
    status_changed = Signal(str, bool)  # service_name, is_running
    
    def __init__(self, process_manager: ProcessManager):
        super().__init__("Process Control")
        self.process_manager = process_manager
        self._setup_ui()
        
        # Setup periodic status refresh (every 2 seconds)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._refresh_status)
        self.status_timer.start(2000)
    
    def _setup_ui(self):
        """Create UI layout"""
        layout = QVBoxLayout()
        
        # v-euicc controls
        veuicc_layout = QHBoxLayout()
        self.veuicc_indicator = QLabel("●")
        self.veuicc_indicator.setStyleSheet("color: red; font-size: 20px;")
        veuicc_layout.addWidget(self.veuicc_indicator)
        veuicc_layout.addWidget(QLabel("v-euicc:"))
        veuicc_layout.addStretch()
        
        self.veuicc_start_btn = QPushButton("Start")
        self.veuicc_start_btn.clicked.connect(self._start_veuicc)
        veuicc_layout.addWidget(self.veuicc_start_btn)
        
        self.veuicc_stop_btn = QPushButton("Stop")
        self.veuicc_stop_btn.clicked.connect(self._stop_veuicc)
        self.veuicc_stop_btn.setEnabled(False)
        veuicc_layout.addWidget(self.veuicc_stop_btn)
        
        layout.addLayout(veuicc_layout)
        
        # SM-DP+ controls
        smdp_layout = QHBoxLayout()
        self.smdp_indicator = QLabel("●")
        self.smdp_indicator.setStyleSheet("color: red; font-size: 20px;")
        smdp_layout.addWidget(self.smdp_indicator)
        smdp_layout.addWidget(QLabel("SM-DP+:"))
        smdp_layout.addStretch()
        
        self.smdp_start_btn = QPushButton("Start")
        self.smdp_start_btn.clicked.connect(self._start_smdp)
        smdp_layout.addWidget(self.smdp_start_btn)
        
        self.smdp_stop_btn = QPushButton("Stop")
        self.smdp_stop_btn.clicked.connect(self._stop_smdp)
        self.smdp_stop_btn.setEnabled(False)
        smdp_layout.addWidget(self.smdp_stop_btn)
        
        layout.addLayout(smdp_layout)
        
        # nginx controls
        nginx_layout = QHBoxLayout()
        self.nginx_indicator = QLabel("●")
        self.nginx_indicator.setStyleSheet("color: red; font-size: 20px;")
        nginx_layout.addWidget(self.nginx_indicator)
        nginx_layout.addWidget(QLabel("nginx:"))
        nginx_layout.addStretch()
        
        self.nginx_start_btn = QPushButton("Start")
        self.nginx_start_btn.clicked.connect(self._start_nginx)
        nginx_layout.addWidget(self.nginx_start_btn)
        
        self.nginx_stop_btn = QPushButton("Stop")
        self.nginx_stop_btn.clicked.connect(self._stop_nginx)
        self.nginx_stop_btn.setEnabled(False)
        nginx_layout.addWidget(self.nginx_stop_btn)
        
        layout.addLayout(nginx_layout)
        
        # Status message
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def _start_veuicc(self):
        """Start v-euicc daemon"""
        success, msg = self.process_manager.start_veuicc()
        self._show_status(msg, success)
        if success:
            self.veuicc_indicator.setStyleSheet("color: green; font-size: 20px;")
            self.veuicc_start_btn.setEnabled(False)
            self.veuicc_stop_btn.setEnabled(True)
            self.status_changed.emit('veuicc', True)
    
    def _stop_veuicc(self):
        """Stop v-euicc daemon"""
        success, msg = self.process_manager.stop_veuicc()
        self._show_status(msg, success)
        if success:
            self.veuicc_indicator.setStyleSheet("color: red; font-size: 20px;")
            self.veuicc_start_btn.setEnabled(True)
            self.veuicc_stop_btn.setEnabled(False)
            self.status_changed.emit('veuicc', False)
    
    def _start_smdp(self):
        """Start SM-DP+ server"""
        success, msg = self.process_manager.start_smdp()
        self._show_status(msg, success)
        if success:
            self.smdp_indicator.setStyleSheet("color: green; font-size: 20px;")
            self.smdp_start_btn.setEnabled(False)
            self.smdp_stop_btn.setEnabled(True)
            self.status_changed.emit('smdp', True)
    
    def _stop_smdp(self):
        """Stop SM-DP+ server"""
        success, msg = self.process_manager.stop_smdp()
        self._show_status(msg, success)
        if success:
            self.smdp_indicator.setStyleSheet("color: red; font-size: 20px;")
            self.smdp_start_btn.setEnabled(True)
            self.smdp_stop_btn.setEnabled(False)
            self.status_changed.emit('smdp', False)
    
    def _start_nginx(self):
        """Start nginx proxy"""
        success, msg = self.process_manager.start_nginx()
        self._show_status(msg, success)
        if success:
            self.nginx_indicator.setStyleSheet("color: green; font-size: 20px;")
            self.nginx_start_btn.setEnabled(False)
            self.nginx_stop_btn.setEnabled(True)
            self.status_changed.emit('nginx', True)
    
    def _stop_nginx(self):
        """Stop nginx proxy"""
        success, msg = self.process_manager.stop_nginx()
        self._show_status(msg, success)
        if success:
            self.nginx_indicator.setStyleSheet("color: red; font-size: 20px;")
            self.nginx_start_btn.setEnabled(True)
            self.nginx_stop_btn.setEnabled(False)
            self.status_changed.emit('nginx', False)
    
    def _show_status(self, message: str, is_success: bool):
        """Show status message"""
        color = "green" if is_success else "red"
        self.status_label.setText(f'<span style="color: {color};">{message}</span>')
        self.status_label.setTextFormat(Qt.RichText)
    
    def _refresh_status(self):
        """Periodically refresh process status indicators"""
        # Check v-euicc
        if self.process_manager.is_running('veuicc'):
            if self.veuicc_indicator.styleSheet() != "color: green; font-size: 20px;":
                self.veuicc_indicator.setStyleSheet("color: green; font-size: 20px;")
                self.veuicc_start_btn.setEnabled(False)
                self.veuicc_stop_btn.setEnabled(True)
        else:
            if self.veuicc_indicator.styleSheet() != "color: red; font-size: 20px;":
                self.veuicc_indicator.setStyleSheet("color: red; font-size: 20px;")
                self.veuicc_start_btn.setEnabled(True)
                self.veuicc_stop_btn.setEnabled(False)
        
        # Check SM-DP+
        if self.process_manager.is_running('smdp'):
            if self.smdp_indicator.styleSheet() != "color: green; font-size: 20px;":
                self.smdp_indicator.setStyleSheet("color: green; font-size: 20px;")
                self.smdp_start_btn.setEnabled(False)
                self.smdp_stop_btn.setEnabled(True)
        else:
            if self.smdp_indicator.styleSheet() != "color: red; font-size: 20px;":
                self.smdp_indicator.setStyleSheet("color: red; font-size: 20px;")
                self.smdp_start_btn.setEnabled(True)
                self.smdp_stop_btn.setEnabled(False)
        
        # Check nginx
        if self.process_manager.is_running('nginx'):
            if self.nginx_indicator.styleSheet() != "color: green; font-size: 20px;":
                self.nginx_indicator.setStyleSheet("color: green; font-size: 20px;")
                self.nginx_start_btn.setEnabled(False)
                self.nginx_stop_btn.setEnabled(True)
        else:
            if self.nginx_indicator.styleSheet() != "color: red; font-size: 20px;":
                self.nginx_indicator.setStyleSheet("color: red; font-size: 20px;")
                self.nginx_start_btn.setEnabled(True)
                self.nginx_stop_btn.setEnabled(False)

