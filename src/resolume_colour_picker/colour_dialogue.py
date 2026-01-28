from PySide6.QtWidgets import (
    QPushButton, QLabel, QVBoxLayout, QHBoxLayout,
    QDialog, QTableWidget, QLineEdit,
    QHeaderView, QColorDialog
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor


class ColourConfigDialog(QDialog):
    """Dialog for configuring colour palette"""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        
        self.setWindowTitle("Configure Colour Palette")
        # Store as ordered list of (label, hex) to maintain positions
        self.colour_items = list(self.config["COLOUR_SET"].items())
        self.hex_inputs = []  # Store references to hex input widgets
        self.init_ui()
        self.resize(600, 400)
        
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Instructions
        info_label = QLabel("Edit colour labels and pick hex values. Must have exactly 8 colours.")
        layout.addWidget(info_label)
        
        # Table for editing colours
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Label", "Hex Value", "Pick"])
        self.table.setRowCount(8)
        
        # Populate table with current colours in their original positions
        for row, (label, hex_val) in enumerate(self.colour_items):
            label_item = QLineEdit(label)
            hex_item = QLineEdit(hex_val)
            hex_item.setReadOnly(True)
            
            pick_btn = QPushButton("...")
            pick_btn.clicked.connect(lambda checked, r=row: self.pick_colour(r))
            
            self.table.setCellWidget(row, 0, label_item)
            self.table.setCellWidget(row, 1, hex_item)
            self.table.setCellWidget(row, 2, pick_btn)
            
            self.hex_inputs.append(hex_item)
        
        # Resize columns to fit content
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        
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
    
    def pick_colour(self, row):
        """Open colour picker for the given row"""
        current_hex = self.hex_inputs[row].text()
        current_colour = QColor(current_hex)
        
        colour = QColorDialog.getColor(current_colour, self, "Pick colour")
        
        if colour.isValid():
            self.hex_inputs[row].setText(colour.name())
    
    def save_changes(self):
        """Save changes to colour set, maintaining position order from table"""
        new_colours = {}
        
        # Read table in row order (0-7) to maintain positions
        for row in range(8):
            label_widget = self.table.cellWidget(row, 0)
            hex_widget = self.hex_inputs[row]
            
            if label_widget is None or hex_widget is None:
                continue
                
            label = label_widget.text().strip()
            hex_val = hex_widget.text().strip()
            
            if not label or not hex_val:
                continue
            
            # Ensure hex format
            if not hex_val.startswith("#"):
                hex_val = "#" + hex_val
            
            if len(hex_val) != 7:
                continue
            
            new_colours[label] = hex_val
        
        if len(new_colours) == 8:
            self.config.set("COLOUR_SET", new_colours)
            self.accept()
