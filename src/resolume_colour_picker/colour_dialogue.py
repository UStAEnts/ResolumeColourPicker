from PySide6.QtWidgets import (
    QPushButton, QLabel, QVBoxLayout, QHBoxLayout,
    QDialog, QTableWidget, QLineEdit,
    QHeaderView, QColorDialog
)
from PySide6.QtGui import QColor


class ColourConfigDialog(QDialog):
    """Dialog for configuring colour palette"""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        
        self.setWindowTitle("Configure Colour Palette")
        # Store as ordered list of (idx, label, hex) to maintain positions
        self.colour_items = []
        self.init_ui()
        self.resize(600, 400)
        
    def delete_row(self):
        button = self.sender()
        if not button:
            return

        index = self.table.indexAt(button.pos())
        row = index.row()

        self.table.removeRow(row)
        self.colour_items.pop(row)
        self.table.setRowCount(len(self.colour_items))

    def new_row(self):
        found_name = False
        index = 0
        new_name = f"new colour ({index})"
        while not found_name:
            found_name = True
            new_name = f"new colour ({index})"

            for (label_item, _) in self.colour_items:
                if new_name == label_item.text().strip():
                    found_name = False

            index += 1

        new_row = len(self.colour_items)

        label_item = QLineEdit(new_name)
        hex_item = QLineEdit("#ffffff")
        hex_item.setReadOnly(True)
        
        pick_btn = QPushButton("...")
        pick_btn.clicked.connect(self.pick_colour)

        delete_button = QPushButton("X")
        delete_button.clicked.connect(self.delete_row)

        self.colour_items.append((label_item, hex_item))
        self.table.setRowCount(len(self.colour_items))

        self.table.setCellWidget(new_row, 0, label_item)
        self.table.setCellWidget(new_row, 1, hex_item)
        self.table.setCellWidget(new_row, 2, pick_btn)
        self.table.setCellWidget(new_row, 3, delete_button)



    def init_ui(self):
        layout = QVBoxLayout()
        
        # Instructions
        info_label = QLabel("Edit colour labels and pick hex values. Must have exactly 8 colours.")
        layout.addWidget(info_label)
        
        # Table for editing colours
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Label", "Hex Value", "Pick", "Delete"])
        self.table.setRowCount(len(self.config["COLOUR_SET"]))
        
        # Populate table with current colours in their original positions
        for row, (label, hex_val) in enumerate(self.config["COLOUR_SET"].items()):
            label_item = QLineEdit(label)
            hex_item = QLineEdit(hex_val)
            hex_item.setReadOnly(True)
            
            pick_btn = QPushButton("...")
            pick_btn.clicked.connect(self.pick_colour)
            
            delete_button = QPushButton("X")
            delete_button.clicked.connect(self.delete_row)
            
            self.table.setCellWidget(row, 0, label_item)
            self.table.setCellWidget(row, 1, hex_item)
            self.table.setCellWidget(row, 2, pick_btn)
            self.table.setCellWidget(row, 3, delete_button)
            
            self.colour_items.append((label_item, hex_item))
        # Resize columns to fit content
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
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
    
    def pick_colour(self):
        """Open colour picker for the given row"""
        button = self.sender()
        if not button:
            return

        index = self.table.indexAt(button.pos())
        row = index.row()

        if row < 0:
            return

        current_hex = self.colour_items[row][1].text()
        current_colour = QColor(current_hex)
        
        colour = QColorDialog.getColor(current_colour, self, "Pick colour")
        
        if colour.isValid():
            self.colour_items[row][1].setText(colour.name())
    
    def save_changes(self):
        """Save changes to colour set, maintaining position order from table"""
        new_colours = {}
        
        # Read table in row order (0-7) to maintain positions
        for (label_widget, hex_widget) in self.colour_items:
                
            label = label_widget.text().strip()
            hex_val = hex_widget.text().strip()
        
            new_colours[label] = hex_val
        
        self.config.set("COLOUR_SET", new_colours)
        self.accept()