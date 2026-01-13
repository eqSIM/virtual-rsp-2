from PySide6.QtWidgets import (QMainWindow, QTabWidget, QVBoxLayout, QWidget, 
                                QLabel, QStatusBar)
from PySide6.QtCore import Qt, QTimer
import subprocess

from mno.services.smdp_api import SmdpApiService
from mno.services.config import Config
from mno.widgets.dashboard_panel import DashboardPanel
from mno.widgets.profile_panel import ProfilePanel
from mno.widgets.session_panel import SessionPanel
from mno.widgets.eid_panel import EIDPanel
from mno.widgets.device_control_panel import DeviceControlPanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.api = SmdpApiService(Config.SMDP_BASE_URL)
        
        self.setWindowTitle("MNO Management Console - SM-DP+ Administration")
        self.setGeometry(100, 100, 1100, 750)
        
        self._setup_ui()
        self._setup_status_bar()
        self._apply_styles()
        
        # Periodic status refresh
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_status)
        self.timer.start(2000)
        
    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        self.tabs = QTabWidget()
        
        self.dashboard_panel = DashboardPanel(self.api)
        self.profile_panel = ProfilePanel(self.api)
        self.session_panel = SessionPanel(self.api)
        self.eid_panel = EIDPanel(self.api)
        self.device_panel = DeviceControlPanel(self.api)
        
        self.tabs.addTab(self.dashboard_panel, "Dashboard")
        self.tabs.addTab(self.profile_panel, "Profile Inventory")
        self.tabs.addTab(self.session_panel, "Active Sessions")
        self.tabs.addTab(self.eid_panel, "EID History")
        self.tabs.addTab(self.device_panel, "Device Control")
        
        layout.addWidget(self.tabs)
        
    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.svc_label = QLabel("Services: Checking...")
        self.status_bar.addPermanentWidget(self.svc_label)
        self.status_bar.showMessage(f"SM-DP+ Server: {Config.SMDP_BASE_URL}")

    def _is_service_running(self, service: str) -> bool:
        """Check if a service is running"""
        try:
            if service == 'veuicc':
                result = subprocess.run(['pgrep', '-f', 'v-euicc-daemon'], 
                                       capture_output=True, text=True)
            elif service == 'smdp':
                result = subprocess.run(['pgrep', '-f', 'osmo-smdpp'], 
                                       capture_output=True, text=True)
            elif service == 'nginx':
                result = subprocess.run(['pgrep', '-f', 'nginx.*nginx-smdpp'], 
                                       capture_output=True, text=True)
            else:
                return False
            return result.returncode == 0
        except:
            return False

    def _update_status(self):
        v = self._is_service_running('veuicc')
        s = self._is_service_running('smdp')
        n = self._is_service_running('nginx')
        
        def indicator(run): 
            return '<span style="color: #107c10;">●</span>' if run else '<span style="color: #d83b01;">●</span>'
        
        status_html = (
            f'v-euicc: {indicator(v)} | '
            f'SM-DP+: {indicator(s)} | '
            f'nginx: {indicator(n)}'
        )
        self.svc_label.setText(status_html)
        self.svc_label.setTextFormat(Qt.RichText)
        
    def _apply_styles(self):
        self.setStyleSheet("""
            QMainWindow, QDialog, QMessageBox, QMenu {
                background-color: #f5f5f5;
                color: #333333;
            }
            QWidget {
                color: #333333;
            }
            QLabel {
                color: #333333 !important;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background-color: white;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #e1e1e1;
                color: #333333;
                padding: 10px 20px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #0078d4;
                border: 1px solid #cccccc;
                border-bottom: none;
                font-weight: bold;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                color: #333333;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #333333;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QPushButton#danger {
                background-color: #d83b01;
            }
            QPushButton#danger:hover {
                background-color: #c23400;
            }
            QTableWidget {
                border: 1px solid #dddddd;
                gridline-color: #f5f5f5;
                background-color: white;
                color: #333333;
            }
            QHeaderView::section {
                background-color: #f8f8f8;
                color: #333333;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #cccccc;
                font-weight: bold;
            }
            QStatusBar {
                background-color: #f8f8f8;
                border-top: 1px solid #cccccc;
                color: #333333;
            }
            QLineEdit, QComboBox {
                background-color: white;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 4px;
            }
            QMessageBox QLabel {
                color: #333333 !important;
                min-width: 300px;
            }
        """)
