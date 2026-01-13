from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
                                QGroupBox)
from PySide6.QtCore import Qt, QTimer
from mno.services.config import Config

class SessionPanel(QWidget):
    """
    Monitor active RSP sessions from SM-DP+ server perspective.
    Shows ongoing downloads, authentication sessions, and their states.
    """
    
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._setup_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_sessions)
        self.timer.start(Config.REFRESH_INTERVAL_MS)
        
        self.refresh_sessions()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_group = QGroupBox("Active RSP Sessions")
        header_layout = QHBoxLayout(header_group)
        
        self.status_label = QLabel("Auto-refreshing every 2 seconds...")
        self.status_label.setStyleSheet("color: #666666; font-size: 11px;")
        header_layout.addWidget(self.status_label)
        
        header_layout.addStretch()
        
        self.refresh_btn = QPushButton("Refresh Now")
        self.refresh_btn.clicked.connect(self.refresh_sessions)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(header_group)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Transaction ID", "EID", "Profile (Matching ID)", "Started At"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.table)
        
        # Info
        info = QLabel(
            "<b>Server-Side View:</b> These are active RSP sessions managed by the SM-DP+ server. "
            "Each session represents an ongoing profile download process with mutual authentication."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666666; font-size: 11px; margin-top: 10px;")
        layout.addWidget(info)

    def refresh_sessions(self):
        sessions = self.api.list_sessions()
        self.table.setRowCount(0)
        
        for session in sessions:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            tid = session.get('transaction_id', 'Unknown')
            eid = session.get('eid') or 'Authenticating...'
            matching_id = session.get('matching_id') or 'N/A'
            started = session.get('started_at', 'Unknown')
            
            self.table.setItem(row, 0, QTableWidgetItem(tid))
            self.table.setItem(row, 1, QTableWidgetItem(eid))
            self.table.setItem(row, 2, QTableWidgetItem(matching_id))
            self.table.setItem(row, 3, QTableWidgetItem(started))
        
        if not sessions:
            self.status_label.setText("No active sessions")
            self.status_label.setStyleSheet("color: #d83b01; font-size: 11px;")
        else:
            self.status_label.setText(f"{len(sessions)} active session(s) - Auto-refreshing")
            self.status_label.setStyleSheet("color: #107c10; font-size: 11px;")
