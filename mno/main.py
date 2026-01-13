import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mno.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MNO Management Console")
    app.setOrganizationName("Virtual RSP")
    app.setApplicationVersion("1.0.0")
    
    # Global styling to ensure visibility in all themes (Dark/Light)
    app.setStyleSheet("""
        QWidget {
            color: #333333;
        }
        QDialog, QMessageBox, QMenu {
            background-color: #f5f5f5;
            color: #333333;
        }
        QLabel {
            color: #333333;
        }
    """)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
