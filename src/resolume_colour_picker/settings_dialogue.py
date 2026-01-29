from PySide6.QtWidgets import (
    QPushButton, QLabel, QVBoxLayout, QHBoxLayout,
    QDialog, QTableWidget, QLineEdit,
    QHeaderView
)
from PySide6.QtCore import QTimer

class SettingsDialog(QDialog):
    """Dialog for changing settings"""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.parent_obj = parent
        self.config = config
        self.settings = [("WEBSERVER_IP", "input"), ("WEBSERVER_PORT","input"), ("RESET", "button", self.reset)]
        self.setting_val = []
        
        self.setWindowTitle("Settings")
        self.init_ui()
        self.resize(600, 400)
    
    def reset(self):
        self.config.reset(broadcast=False)
        self.config.broadcast_change("COLOUR_SET")
        self.config.broadcast_change("WEBSERVER_IP")
        QTimer.singleShot(0, self._reopen_dialog)

        self.reject()

    def _reopen_dialog(self):
        dialog = SettingsDialog(self.config, self.parent())
        dialog.exec()
        
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Instructions
        info_label = QLabel("Change settings")
        layout.addWidget(info_label)
        
        # Table for editing colours
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Setting", "Value"])
        self.table.setRowCount(len(self.settings))

        # Populate table with current colours in their original positions
        for row, setting in enumerate(self.settings):
            label_item = QLineEdit(setting[0])
            label_item.setReadOnly(True)

            if setting[1] == "input":
                value = QLineEdit(self.config[setting[0]])
            elif setting[1] == "button":
                value = QPushButton("...")
                value.clicked.connect(lambda checked: setting[2]())
    
            self.table.setCellWidget(row, 0, label_item)
            self.table.setCellWidget(row, 1, value)
            
            self.setting_val.append(value)
        
        # Resize columns to fit content
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        
        layout.addWidget(self.table)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        
        save_btn.clicked.connect(self.save_changes)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def save_changes(self):
        """Save changes"""

        for row in range(len(self.settings)):
            val_widget = self.setting_val[row]


            key = self.settings[row][0]
            setting_val = val_widget.text().strip()

            self.config[key] = setting_val

        self.accept()
