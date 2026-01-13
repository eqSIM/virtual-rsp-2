from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QTableWidget, QTableWidgetItem, QHeaderView, QLabel, 
                                QLineEdit, QSplitter, QGroupBox)
from PySide6.QtCore import Qt
from collections import defaultdict

class EIDPanel(QWidget):
    """
    Track download history from SM-DP+ server perspective.
    Shows which devices (EIDs) have downloaded which profiles.
    """
    
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.history = []
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_group = QGroupBox("Download History by Device")
        header_layout = QHBoxLayout(header_group)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)
        header_layout.addWidget(self.refresh_btn)
        
        header_layout.addWidget(QLabel("Filter:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by EID...")
        self.search_input.textChanged.connect(self.filter_data)
        header_layout.addWidget(self.search_input)
        
        header_layout.addStretch()
        
        layout.addWidget(header_group)
        
        # Splitter for EID list and History
        splitter = QSplitter(Qt.Vertical)
        
        # EID Summary Table
        eid_container = QWidget()
        eid_layout = QVBoxLayout(eid_container)
        eid_layout.setContentsMargins(0, 0, 0, 0)
        
        eid_label = QLabel("<b>Devices (EIDs)</b> - Click to see history")
        eid_label.setStyleSheet("color: #666666; font-size: 11px; margin: 5px 0;")
        eid_layout.addWidget(eid_label)
        
        self.eid_table = QTableWidget()
        self.eid_table.setColumnCount(3)
        self.eid_table.setHorizontalHeaderLabels(["EID", "Total Downloads", "Last Seen"])
        self.eid_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.eid_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.eid_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.eid_table.itemSelectionChanged.connect(self.show_eid_history)
        eid_layout.addWidget(self.eid_table)
        
        # History Table for selected EID
        history_container = QWidget()
        history_layout = QVBoxLayout(history_container)
        history_layout.setContentsMargins(0, 0, 0, 0)
        
        history_label = QLabel("<b>Download History</b> - Select a device above")
        history_label.setStyleSheet("color: #666666; font-size: 11px; margin: 5px 0;")
        history_layout.addWidget(history_label)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["Timestamp", "Profile", "ICCID", "Status"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        history_layout.addWidget(self.history_table)
        
        splitter.addWidget(eid_container)
        splitter.addWidget(history_container)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        # Info
        info = QLabel(
            "<b>Server-Side Tracking:</b> View download activity from the SM-DP+ perspective. "
            "Track which devices downloaded which profiles and monitor success rates."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666666; font-size: 11px; margin-top: 10px;")
        layout.addWidget(info)
    def refresh_data(self):
        self.history = self.api.get_download_history()
        self.filter_data()

    def filter_data(self):
        search_term = self.search_input.text().lower()
        
        # Group by EID
        eid_stats = defaultdict(lambda: {'count': 0, 'last_seen': ''})
        for record in self.history:
            eid = record.get('eid', 'Unknown')
            if not eid:
                eid = 'Unknown'
            if search_term and search_term not in eid.lower():
                continue
            
            eid_stats[eid]['count'] += 1
            timestamp = record.get('timestamp', '')
            if timestamp > eid_stats[eid]['last_seen']:
                eid_stats[eid]['last_seen'] = timestamp
        
        self.eid_table.setRowCount(0)
        for eid, stats in sorted(eid_stats.items()):
            row = self.eid_table.rowCount()
            self.eid_table.insertRow(row)
            
            self.eid_table.setItem(row, 0, QTableWidgetItem(eid))
            self.eid_table.setItem(row, 1, QTableWidgetItem(str(stats['count'])))
            self.eid_table.setItem(row, 2, QTableWidgetItem(stats['last_seen']))

    def show_eid_history(self):
        selected_items = self.eid_table.selectedItems()
        if not selected_items:
            self.history_table.setRowCount(0)
            return
            
        eid = selected_items[0].text()
        self.history_table.setRowCount(0)
        
        for record in sorted(self.history, key=lambda x: x.get('timestamp', ''), reverse=True):
            record_eid = record.get('eid', 'Unknown') or 'Unknown'
            if record_eid == eid:
                row = self.history_table.rowCount()
                self.history_table.insertRow(row)
                
                self.history_table.setItem(row, 0, QTableWidgetItem(record.get('timestamp', '')))
                self.history_table.setItem(row, 1, QTableWidgetItem(record.get('matching_id', '')))
                self.history_table.setItem(row, 2, QTableWidgetItem(record.get('iccid', '')))
                
                status = record.get('status', '')
                status_item = QTableWidgetItem(status)
                if status == 'success':
                    status_item.setForeground(Qt.green)
                elif status == 'failed':
                    status_item.setForeground(Qt.red)
                self.history_table.setItem(row, 3, status_item)
