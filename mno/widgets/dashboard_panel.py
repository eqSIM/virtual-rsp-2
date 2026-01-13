from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                                QGroupBox, QGridLayout)
from PySide6.QtCore import Qt, QTimer
from mno.services.config import Config

class StatCard(QGroupBox):
    def __init__(self, title, value="0"):
        super().__init__(title)
        layout = QVBoxLayout(self)
        self.label = QLabel(value)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("""
            font-size: 28px; 
            font-weight: bold; 
            color: #0078d4;
            padding: 10px;
        """)
        layout.addWidget(self.label)

    def set_value(self, value):
        self.label.setText(str(value))

class DashboardPanel(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._setup_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_stats)
        self.timer.start(Config.REFRESH_INTERVAL_MS * 2)
        
        self.refresh_stats()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("SM-DP+ Operator Dashboard")
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin: 10px 0; color: #333333;")
        layout.addWidget(title)
        
        # Stats cards in grid
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(15)
        
        self.card_profiles = StatCard("Total Profiles on Server")
        self.card_sessions = StatCard("Active RSP Sessions")
        self.card_downloads = StatCard("Total Downloads Served")
        self.card_success = StatCard("Success Rate")
        self.card_failed = StatCard("Failed Downloads")
        
        grid.addWidget(self.card_profiles, 0, 0)
        grid.addWidget(self.card_sessions, 0, 1)
        grid.addWidget(self.card_downloads, 1, 0)
        grid.addWidget(self.card_success, 1, 1)
        grid.addWidget(self.card_failed, 2, 0, 1, 2)
        
        layout.addLayout(grid)
        layout.addStretch()
        
        # Info
        info = QLabel(
            "<b>Server Statistics:</b> Real-time metrics from the SM-DP+ server showing "
            "profile inventory, active download sessions, and historical success rates."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666666; font-size: 11px; margin-top: 15px;")
        layout.addWidget(info)

    def refresh_stats(self):
        stats = self.api.get_stats()
        
        self.card_profiles.set_value(stats.get('total_profiles', 0))
        self.card_sessions.set_value(stats.get('active_sessions', 0))
        self.card_downloads.set_value(stats.get('total_downloads', 0))
        
        rate = stats.get('success_rate', 0)
        self.card_success.set_value(f"{rate:.1f}%")
        
        self.card_failed.set_value(stats.get('failed_count', 0))
