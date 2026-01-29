from PySide6.QtWidgets import (
    QPushButton, QLabel, QVBoxLayout, QHBoxLayout,
    QDialog, QTableWidget, QLineEdit,
    QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt


class LayerMapDialog(QDialog):

    def __init__(self, config, parent=None):
        super().__init__(parent)

        self.layer_list = []
        self.config = config

        self.setWindowTitle("Layer Map")
        self.init_ui()
        self.resize(600, 400)

    def delete_row(self, label_item):
        row = 0
        for i in range(len(self.layer_list)):
            if self.layer_list[i][0] == label_item:
                row = i

        self.layer_list.pop(row)
        self.table.removeRow(row)
        self.table.setRowCount(len(self.layer_list))

    def new_row(self):
        found_name = False
        index = 0
        new_name = f"new layer ({index})"
        while not found_name:
            found_name = True
            new_name = f"new layer ({index})"

            for (layer_item, _) in self.layer_list:
                if new_name == layer_item.text().strip():
                    found_name = False

            index += 1
        
        new_row = len(self.layer_list)

        label_item = QLineEdit(new_name)
        value_item = QLineEdit("0")
        
        delete_button = QPushButton("X")
        delete_button.clicked.connect(lambda checked, row=new_row: self.delete_row(row))

        
        self.layer_list.append((label_item, value_item))
        self.table.setRowCount(len(self.layer_list))

        self.table.setCellWidget(new_row, 0, label_item)
        self.table.setCellWidget(new_row, 1, value_item)
        self.table.setCellWidget(new_row, 2, delete_button)



    def init_ui(self):
        layout = QVBoxLayout()
        
        # Instructions
        info_label = QLabel("Change settings")
        layout.addWidget(info_label)
        
        # Table for editing colours
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Layer Name", "Layer Number", "Delete"])
        self.table.setRowCount(len(self.config["LAYER_MAP"]))

        # Populate table with current colours in their original positions
        for row, (key, value) in enumerate(self.config["LAYER_MAP"].items()):
            label_item = QLineEdit(key)
            value_item = QLineEdit(str(value))
            
            delete_button = QPushButton("X")
            delete_button.clicked.connect(lambda checked, label=label_item: self.delete_row(label_item))
    
            self.table.setCellWidget(row, 0, label_item)
            self.table.setCellWidget(row, 1, value_item)
            self.table.setCellWidget(row, 2, delete_button)
            
            
            self.layer_list.append((label_item, value_item))
        
        # Resize columns to fit content
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        
        layout.addWidget(self.table)
        
        # Buttons
        button_layout = QHBoxLayout()
        new_btn = QPushButton("New")
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        
        new_btn.clicked.connect(self.new_row)
        save_btn.clicked.connect(self.save_changes)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(new_btn)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def save_changes(self):
        """Save changes"""
        new_layer_map = {}
        for label, value in self.layer_list:
            try:
                    value_int = int(value.text().strip())
                    new_layer_map[label.text().strip()] = value_int
            except ValueError:
                value_clean = value.text().strip().upper()
                if value_clean != "ALL":
                    QMessageBox.critical(
                        self,
                        "Error",
                        'Layer map can be a number or "ALL"'
                    )
                    return
                new_layer_map[label.text().strip()] = value_clean
        
        self.config["LAYER_MAP"] = new_layer_map
        self.accept()