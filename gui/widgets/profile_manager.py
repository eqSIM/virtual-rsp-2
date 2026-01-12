"""
Profile Manager - Table view of installed profiles with enable/disable/delete actions
"""

from PySide6.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton,
                                QTableWidget, QTableWidgetItem, QHeaderView,
                                QMessageBox, QLabel)
from PySide6.QtCore import Qt, Signal
from gui.services.lpa_service import LPAService
from gui.services.profile_store import ProfileStore, ProfileState, Profile
import re
from pathlib import Path


class ProfileManager(QGroupBox):
    """
    Panel for managing installed profiles.
    Shows table with ICCID, name, state, and action buttons.
    Implements SGP.22 profile lifecycle (enable/disable/delete).
    """
    
    profile_changed = Signal()  # Emitted when profile list changes
    
    def __init__(self, lpa_service: LPAService, profile_store: ProfileStore):
        super().__init__("Installed Profiles")
        self.lpa_service = lpa_service
        self.profile_store = profile_store
        self._setup_ui()
        self.refresh_profiles()
    
    def _setup_ui(self):
        """Create UI layout"""
        layout = QVBoxLayout()
        
        # Top bar with refresh button
        top_layout = QHBoxLayout()
        self.profile_count_label = QLabel("0 profiles installed")
        top_layout.addWidget(self.profile_count_label)
        top_layout.addStretch()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_profiles)
        top_layout.addWidget(refresh_btn)
        
        layout.addLayout(top_layout)
        
        # Profile table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ICCID", "Profile Name", "Service Provider", "State", "Actions"
        ])
        
        # Configure table
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(False)
        
        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)  # ICCID
        header.setSectionResizeMode(1, QHeaderView.Stretch)      # Profile Name
        header.setSectionResizeMode(2, QHeaderView.Stretch)      # Service Provider
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # State
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Actions
        
        self.table.setColumnWidth(0, 180)
        
        layout.addWidget(self.table)
        
        # Info label
        info_label = QLabel(
            "<b>SGP.22 Rules:</b> Only ONE profile can be enabled at a time. "
            "Cannot delete an enabled profile (disable it first)."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")
        layout.addWidget(info_label)
        
        self.setLayout(layout)
    
    def refresh_profiles(self):
        """Refresh profile list from store and sync with v-euicc"""
        # First try to sync from lpac if services are running
        self._sync_profiles_from_veuicc()
        
        profiles = self.profile_store.list_profiles()
        
        # Update count
        self.profile_count_label.setText(f"{len(profiles)} profile(s) installed")
        
        # Clear table
        self.table.setRowCount(0)
        
        # Populate table
        for profile in profiles:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # ICCID
            iccid_item = QTableWidgetItem(profile.iccid)
            self.table.setItem(row, 0, iccid_item)
            
            # Profile Name
            name_item = QTableWidgetItem(profile.profile_name or profile.matching_id)
            self.table.setItem(row, 1, name_item)
            
            # Service Provider
            sp_item = QTableWidgetItem(profile.service_provider or "Unknown")
            self.table.setItem(row, 2, sp_item)
            
            # State
            state_item = QTableWidgetItem(profile.state.capitalize())
            if profile.state == ProfileState.ENABLED:
                state_item.setForeground(Qt.green)
            else:
                state_item.setForeground(Qt.gray)
            self.table.setItem(row, 3, state_item)
            
            # Actions
            actions_widget = self._create_action_buttons(profile)
            self.table.setCellWidget(row, 4, actions_widget)
    
    def _create_action_buttons(self, profile):
        """Create action buttons for a profile row"""
        widget = QLabel()  # Container
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        if profile.state == ProfileState.ENABLED:
            # Show Disable and Delete (disabled)
            disable_btn = QPushButton("Disable")
            disable_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d83b01;
                    padding: 5px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #c23400;
                }
            """)
            disable_btn.clicked.connect(lambda: self._disable_profile(profile.iccid))
            layout.addWidget(disable_btn)
            
            delete_btn = QPushButton("Delete")
            delete_btn.setEnabled(False)
            delete_btn.setToolTip("Cannot delete enabled profile")
            delete_btn.setStyleSheet("padding: 5px 10px; font-size: 11px;")
            layout.addWidget(delete_btn)
        else:
            # Show Enable and Delete
            enable_btn = QPushButton("Enable")
            enable_btn.setStyleSheet("""
                QPushButton {
                    background-color: #107c10;
                    padding: 5px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #0e6b0e;
                }
            """)
            enable_btn.clicked.connect(lambda: self._enable_profile(profile.iccid))
            layout.addWidget(enable_btn)
            
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #a80000;
                    padding: 5px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #8b0000;
                }
            """)
            delete_btn.clicked.connect(lambda checked, p=profile: self._delete_profile(p.iccid, p.matching_id))
            layout.addWidget(delete_btn)
        
        layout.addStretch()
        return widget
    
    def _enable_profile(self, iccid: str):
        """Enable profile via LPA"""
        reply = QMessageBox.question(
            self,
            "Enable Profile",
            f"Enable profile {iccid}?\n\nThis will disable any currently enabled profile.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, msg = self.lpa_service.enable_profile(iccid)
            
            if success:
                # Update store
                self.profile_store.enable_profile(iccid=iccid)
                QMessageBox.information(self, "Success", msg)
                self.refresh_profiles()
                self.profile_changed.emit()
            else:
                # Fallback: Try local-only operation if v-euicc doesn't have the profile
                local_success, local_msg = self.profile_store.enable_profile(iccid=iccid)
                if local_success:
                    QMessageBox.information(self, "Success", f"Profile enabled (local store)\n\nNote: v-euicc may need restart to sync.")
                    self.refresh_profiles()
                    self.profile_changed.emit()
                else:
                    QMessageBox.critical(self, "Error", f"Failed to enable profile:\n\n{msg}")
    
    def _disable_profile(self, iccid: str):
        """Disable profile via LPA"""
        reply = QMessageBox.question(
            self,
            "Disable Profile",
            f"Disable profile {iccid}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, msg = self.lpa_service.disable_profile(iccid)
            
            if success:
                # Update store
                self.profile_store.disable_profile(iccid=iccid)
                QMessageBox.information(self, "Success", msg)
                self.refresh_profiles()
                self.profile_changed.emit()
            else:
                # Fallback: Try local-only operation
                local_success, local_msg = self.profile_store.disable_profile(iccid=iccid)
                if local_success:
                    QMessageBox.information(self, "Success", f"Profile disabled (local store)\n\nNote: v-euicc may need restart to sync.")
                    self.refresh_profiles()
                    self.profile_changed.emit()
                else:
                    QMessageBox.critical(self, "Error", f"Failed to disable profile:\n\n{msg}")
    
    def _delete_profile(self, iccid: str, matching_id: str = None):
        """Delete profile via LPA"""
        display_name = matching_id or iccid
        reply = QMessageBox.warning(
            self,
            "Delete Profile",
            f"Permanently delete profile?\n\nName: {display_name}\nICCID: {iccid}\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, msg = self.lpa_service.delete_profile(iccid)
            
            if success:
                # Update store using matching_id (more unique for test profiles)
                self.profile_store.delete_profile(matching_id=matching_id) if matching_id else self.profile_store.delete_profile(iccid=iccid)
                QMessageBox.information(self, "Success", msg)
                self.refresh_profiles()
                self.profile_changed.emit()
            else:
                # Fallback: Try local-only deletion if v-euicc doesn't have the profile
                # Use matching_id as key (more unique for test profiles)
                local_success, local_msg = self.profile_store.delete_profile(matching_id=matching_id) if matching_id else self.profile_store.delete_profile(iccid=iccid)
                
                if local_success:
                    QMessageBox.information(self, "Success", f"Profile deleted from local store.\n\nThe profile was removed from the database.")
                    self.refresh_profiles()
                    self.profile_changed.emit()
                else:
                    QMessageBox.critical(self, "Error", f"Failed to delete profile:\n\n{msg}")
    
    def _sync_profiles_from_veuicc(self):
        """
        Sync profiles from v-euicc logs to the profile store.
        Only adds NEW profiles, never re-adds deleted ones.
        """
        # Don't sync if we just deleted something (to avoid re-adding)
        # This is controlled by checking if we're in a delete operation
        # Better approach: Track deleted ICCIDs in a separate list
        pass  # Disabled for now - only sync on download, not on refresh

