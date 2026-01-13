from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QTableWidget, QTableWidgetItem, QHeaderView, 
                                QFileDialog, QMessageBox, QLabel, QGroupBox)
from PySide6.QtCore import Qt
import os

class ProfilePanel(QWidget):
    """
    Manage profile inventory on SM-DP+ server.
    Lists all available UPP profiles that can be distributed to devices.
    """
    
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._setup_ui()
        self.refresh_profiles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_group = QGroupBox("SM-DP+ Profile Inventory")
        header_layout = QHBoxLayout(header_group)
        
        self.count_label = QLabel("0 profiles available")
        header_layout.addWidget(self.count_label)
        header_layout.addStretch()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_profiles)
        header_layout.addWidget(self.refresh_btn)
        
        self.upload_btn = QPushButton("Upload Profile (.der)")
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                font-size: 12px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #0e6b0e;
            }
        """)
        self.upload_btn.clicked.connect(self.upload_profile)
        header_layout.addWidget(self.upload_btn)
        
        layout.addWidget(header_group)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Matching ID", "Size (bytes)", "Modified", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.table)
        
        # Info
        info = QLabel(
            "<b>Server Inventory:</b> Manage profile packages stored on the SM-DP+ server. "
            "Upload new profiles (.der files) or remove unused ones. These profiles are available "
            "for distribution to connected devices."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666666; font-size: 11px; margin-top: 10px;")
        layout.addWidget(info)

    def refresh_profiles(self):
        profiles = self.api.list_profiles()
        self.table.setRowCount(0)
        
        self.count_label.setText(f"{len(profiles)} profile(s) available")
        
        for profile in profiles:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            matching_id = profile.get('matching_id', 'Unknown')
            size = profile.get('size', 0)
            modified = profile.get('modified', 'Unknown')
            
            self.table.setItem(row, 0, QTableWidgetItem(matching_id))
            self.table.setItem(row, 1, QTableWidgetItem(f"{size:,}"))
            self.table.setItem(row, 2, QTableWidgetItem(modified))
            
            # Action buttons
            actions = QWidget()
            act_layout = QHBoxLayout(actions)
            act_layout.setContentsMargins(2, 2, 2, 2)
            
            del_btn = QPushButton("Delete")
            del_btn.setObjectName("danger")
            del_btn.setStyleSheet("padding: 6px 12px; font-size: 11px;")
            del_btn.clicked.connect(lambda checked, m=matching_id: self.delete_profile(m))
            
            act_layout.addWidget(del_btn)
            self.table.setCellWidget(row, 3, actions)

    def upload_profile(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Profile Package", 
            "", 
            "DER Files (*.der);;All Files (*)"
        )
        if filepath:
            filename = os.path.basename(filepath)
            reply = QMessageBox.question(
                self,
                "Upload Profile",
                f"Upload profile package:\n{filename}\n\nThis will make it available for download by devices.",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                if self.api.upload_profile(filepath):
                    QMessageBox.information(self, "Success", f"Profile {filename} uploaded successfully")
                    self.refresh_profiles()
                else:
                    QMessageBox.critical(self, "Error", "Failed to upload profile")

    def delete_profile(self, matching_id):
        reply = QMessageBox.warning(
            self, 
            "Delete Profile", 
            f"Delete profile '{matching_id}' from SM-DP+ server?\n\n"
            "This will remove the profile package (.der file) from the server inventory. "
            "Already downloaded profiles on devices will not be affected.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.api.delete_profile(matching_id):
                QMessageBox.information(self, "Success", f"Profile {matching_id} deleted")
                self.refresh_profiles()
            else:
                QMessageBox.critical(self, "Error", "Failed to delete profile")
