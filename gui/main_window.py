"""
Main Window - Virtual RSP Control Center
PySide6-based GUI for managing v-euicc, SM-DP+, and profile operations
"""

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                QSplitter, QGroupBox, QLabel, QStatusBar)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from gui.widgets.process_panel import ProcessPanel
from gui.widgets.profile_selector import ProfileSelector
from gui.widgets.profile_manager import ProfileManager
from gui.widgets.log_viewer import LogViewer
from gui.services.process_manager import ProcessManager
from gui.services.lpa_service import LPAService
from gui.services.profile_store import ProfileStore


class MainWindow(QMainWindow):
    """
    Main application window for Virtual RSP Control Center.
    
    Layout:
    - Top row: Process Control (left) | Profile Selector (right)
    - Middle row: Installed Profiles table
    - Bottom row: Log viewer with tab selection
    """
    
    def __init__(self, project_root: str = "/Users/jhurykevinlastre/Documents/projects/virtual-rsp"):
        super().__init__()
        
        self.project_root = project_root
        
        # Initialize services
        self.process_manager = ProcessManager(project_root)
        self.lpa_service = LPAService()
        self.profile_store = ProfileStore(f"{project_root}/data/profiles.json")
        
        self.setWindowTitle("Virtual RSP Control Center - SGP.22 v2.5")
        self.setGeometry(100, 100, 1400, 900)
        
        self._setup_ui()
        self._setup_status_bar()
        self._setup_timers()
        
        # Apply stylesheet
        self._apply_styles()
    
    def _setup_ui(self):
        """Create main UI layout"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Top row: Process control and profile selector
        top_splitter = QSplitter(Qt.Horizontal)
        
        # Process control panel
        self.process_panel = ProcessPanel(self.process_manager)
        top_splitter.addWidget(self.process_panel)
        
        # Profile selector panel
        self.profile_selector = ProfileSelector(
            self.lpa_service,
            self.profile_store,
            f"{self.project_root}/pysim/smdpp-data/upp",
            log_path=f"{self.project_root}/data/veuicc.log"
        )
        top_splitter.addWidget(self.profile_selector)
        
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(top_splitter)
        
        # Middle row: Installed profiles manager
        self.profile_manager = ProfileManager(
            self.lpa_service,
            self.profile_store
        )
        main_layout.addWidget(self.profile_manager)
        
        # Bottom row: Log viewer
        self.log_viewer = LogViewer(self.process_manager)
        main_layout.addWidget(self.log_viewer)
        
        # Set stretch factors
        main_layout.setStretch(0, 2)  # Top row
        main_layout.setStretch(1, 3)  # Profile manager
        main_layout.setStretch(2, 2)  # Logs
        
        # Connect signals
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect inter-widget signals"""
        # When profile is downloaded, refresh the profile manager
        self.profile_selector.profile_downloaded.connect(
            self.profile_manager.refresh_profiles
        )
        
        # When profile operation completes, refresh the display
        self.profile_manager.profile_changed.connect(
            self.profile_selector.refresh_available_profiles
        )
    
    def _setup_status_bar(self):
        """Create status bar with service indicators"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Service status labels
        self.veuicc_status = QLabel("v-euicc: Stopped")
        self.smdp_status = QLabel("SM-DP+: Stopped")
        self.nginx_status = QLabel("nginx: Stopped")
        
        self.status_bar.addWidget(self.veuicc_status)
        self.status_bar.addWidget(QLabel("  |  "))
        self.status_bar.addWidget(self.smdp_status)
        self.status_bar.addWidget(QLabel("  |  "))
        self.status_bar.addWidget(self.nginx_status)
        
        self.status_bar.addPermanentWidget(QLabel("SGP.22 v2.5 Compliant"))
    
    def _setup_timers(self):
        """Setup periodic updates"""
        # Update service status every second
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_service_status)
        self.status_timer.start(1000)
        
        # Update logs every 500ms
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.log_viewer.update_logs)
        self.log_timer.start(500)
    
    def _update_service_status(self):
        """Update service status indicators"""
        veuicc_running = self.process_manager.is_running('veuicc')
        smdp_running = self.process_manager.is_running('smdp')
        nginx_running = self.process_manager.is_running('nginx')

        running_html = '<span style="color: green;">Running</span>'
        stopped_html = '<span style="color: red;">Stopped</span>'

        self.veuicc_status.setText(f"v-euicc: {running_html if veuicc_running else stopped_html}")
        self.veuicc_status.setTextFormat(Qt.RichText)
        
        self.smdp_status.setText(f"SM-DP+: {running_html if smdp_running else stopped_html}")
        self.smdp_status.setTextFormat(Qt.RichText)
        
        self.nginx_status.setText(f"nginx: {running_html if nginx_running else stopped_html}")
        self.nginx_status.setTextFormat(Qt.RichText)
    
    def _apply_styles(self):
        """Apply custom stylesheet"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
                color: #333333;
            }
            QWidget {
                color: #333333;
            }
            QLabel {
                color: #333333;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                gridline-color: #e0e0e0;
                background-color: white;
                color: #333333;
            }
            QTableWidget::item {
                padding: 5px;
                color: #333333;
                background-color: white;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                color: #333333;
                padding: 6px;
                border: none;
                border-right: 1px solid #ccc;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
            QComboBox {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
                color: #333333;
            }
            QLineEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
                color: #333333;
            }
            QStatusBar {
                background-color: #e8e8e8;
                border-top: 1px solid #cccccc;
            }
            QMessageBox {
                background-color: #f5f5f5;
                color: #333333;
            }
            QMessageBox QLabel {
                color: #333333;
            }
            QMessageBox QPushButton {
                min-width: 80px;
            }
        """)
    
    def closeEvent(self, event):
        """Handle window close - stop all services"""
        self.process_manager.stop_all()
        event.accept()

