#!/usr/bin/env python3
"""
Virtual RSP Control Center - Main Entry Point
GSMA SGP.22 v2.5 Profile Management GUI
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from gui.main_window import MainWindow


def main():
    """Main application entry point"""
    # Enable high DPI support (Qt 6 handles this automatically)
    
    app = QApplication(sys.argv)
    app.setApplicationName("Virtual RSP Control Center")
    app.setOrganizationName("Virtual RSP")
    app.setApplicationVersion("1.0.0")
    
    # Create and show main window
    window = MainWindow(str(project_root))
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

