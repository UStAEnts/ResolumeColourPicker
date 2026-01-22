import copy
import json
import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QGridLayout, QLabel, QVBoxLayout, QHBoxLayout,
    QDialog, QTableWidget, QTableWidgetItem, QLineEdit,
    QHeaderView, QColorDialog
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QColor
from concurrent.futures import ThreadPoolExecutor
import time


# =========================
# CONFIGURATION
# =========================

COLUMNS = ["ALL" , "Outer", "Middle", "Inner", "DJ"]
ALL_COLUMN = "ALL"

# Define colours as a dictionary
_COLOUR_SET = {
    "1 - Red": "#FF0000",
    "2 - Blue": "#0000FF",
    "3 - Yellow": "#FFFF00",
    "4 - Orange": "#FFA500",
    "5 - Green": "#00B050",
    "6 - Purple": "#800080",
    "7 - Pink": "#FF69B4",
    "8 - White": "#FFFFFF",
}

# Convert to list maintaining order
COLOUR_ROWS = list(_COLOUR_SET.items())

WINDOW_SIZE = (900, 700)
BUTTON_HEIGHT = 55
DARKEN_FACTOR = 0.65

WEBSERVER_IP = "localhost"
WEBSERVER_PORT = 8080
API_BASE_URL = f"http://{WEBSERVER_IP}:{WEBSERVER_PORT}/api/v1/composition"

LAYER_MAP = {
    "Inner": 1,
    "Middle": 2,
    "Outer": 3,
    "DJ": 4,
}

RESOLUME_PRODUCT_URL = f"http://{WEBSERVER_IP}:{WEBSERVER_PORT}/api/v1/product"
HEARTBEAT_INTERVAL = 3000  # 3 seconds in milliseconds



# =========================
# STYLE HELPERS
# =========================

def darken(colour: QColor, factor=DARKEN_FACTOR) -> QColor:
    return QColor(
        int(colour.red() * factor),
        int(colour.green() * factor),
        int(colour.blue() * factor),
    )


def button_stylesheet(colour: QColor, selected=False) -> str:
    border = "3px solid black" if selected else "1px solid #444"
    text_colour = "black" if colour.lightness() > 120 else "white"

    return f"""
        QPushButton {{
            background-color: {colour.name()};
            color: {text_colour};
            border: {border};
            border-radius: 6px;
            font-weight: bold;
            padding: 4px;
            font-size: 20px;
        }}
    """


# =========================
# COLOUR CONFIGURATION DIALOG
# =========================

class ColourConfigDialog(QDialog):
    """Dialog for configuring colour palette"""
    colours_updated = Signal(dict)  # Emits updated _COLOUR_SET
    
    def __init__(self, colour_set, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Colour Palette")
        # Store as ordered list of (label, hex) to maintain positions
        self.colour_items = list(colour_set.items())
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
            self.colours_updated.emit(new_colours)
            self.accept()


# =========================
# STATUS HEARTBEAT
# =========================

class StatusHeartbeat(QObject):
    """Emits status updates for the Resolume connection"""
    status_updated = Signal(str, float, str)  # status, latency, colour
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.running = False
    
    def check_status(self):
        """Poll the Resolume /product endpoint"""
        try:
            start_time = time.time()
            response = self.session.get(RESOLUME_PRODUCT_URL, timeout=2)
            latency = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            if response.status_code == 200:
                if latency < 100:
                    colour = "#00AA00"  # Green - fast
                    status = "Connected"
                elif latency < 500:
                    colour = "#FFAA00"  # Orange - moderate
                    status = "Connected"
                else:
                    colour = "#FF6600"  # Orange-red - slow
                    status = "Slow"
                status += " to Resolume @ " + WEBSERVER_IP 
            else:
                colour = "#FF0000"  # Red - error
                status = f"Error {response.status_code}"
                latency = 0
                
            self.status_updated.emit(status, latency, colour)
        except requests.Timeout:
            self.status_updated.emit("Timeout", 0, "#FF0000")
        except requests.ConnectionError:
            self.status_updated.emit("Offline", 0, "#FF0000")
        except Exception as e:
            self.status_updated.emit(f"Error", 0, "#FF0000")


# =========================
# MAIN APP
# =========================

class ColourPickerEngine(QWidget):
    def __init__(self):

        with open("get_colorize.json", "r") as f:
            self.BASE_PAYLOAD = json.load(f)

        self.executor = ThreadPoolExecutor(max_workers=4)
        self.session = requests.Session()

        super().__init__()

        self.setWindowTitle("Colour Picker Engine")
        self.resize(*WINDOW_SIZE)

        self.layout = QGridLayout(self)
        self.setLayout(self.layout)

        self.selected_in_column = {}
        self.buttons = {}
        self.base_colours = {}
        
        # Status heartbeat components
        self.heartbeat = StatusHeartbeat()
        self.status_label = QLabel("Initialising...")
        self.status_square = QLabel()
        self.latency_label = QLabel("-- ms")
        self.timer = QTimer()
        self.timer.timeout.connect(self.heartbeat.check_status)

        self.build_ui()
        self.setup_heartbeat()

    def build_ui(self):
        # Create main container layout
        main_layout = QVBoxLayout()
        
        # Add status bar at the top
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        
        self.status_square.setFixedSize(30, 30)
        self.status_square.setStyleSheet("background-color: #CCCCCC; border: 1px solid #444;")
        status_layout.addWidget(self.status_square)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(QLabel("Latency:"))
        status_layout.addWidget(self.latency_label)
        
        # Add configure button
        config_btn = QPushButton("Configure Colours")
        config_btn.clicked.connect(self.open_colour_config)
        status_layout.addWidget(config_btn)
        
        status_layout.addStretch()
        
        main_layout.addLayout(status_layout)
        
        # Add colour picker grid
        grid_widget = QWidget()
        grid_widget.setLayout(self.layout)
        main_layout.addWidget(grid_widget)
        
        # Set the main layout
        self.setLayout(main_layout)
        
        self._add_headers()
        self._add_buttons()

    def _add_headers(self):
        for col, name in enumerate(COLUMNS):
            label = QLabel(name)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-weight: bold;font-size: 32px;")
            self.layout.addWidget(label, 0, col)

    def _add_buttons(self):
        for row, entry in enumerate(COLOUR_ROWS):
            colour = QColor(entry[1])  # hex is second element
            label = entry[0]  # label is first element

            for col, column_name in enumerate(COLUMNS):
                btn = QPushButton(label)
                btn.setFixedHeight(BUTTON_HEIGHT)
                btn.setStyleSheet(button_stylesheet(colour))

                btn.clicked.connect(
                    lambda _, c=column_name, r=row: self.on_press(c, r, entry[1])
                )

                self.layout.addWidget(btn, row + 1, col)

                self.buttons[(column_name, row)] = btn
                self.base_colours[(column_name, row)] = colour

    # =========================
    # INTERACTION LOGIC
    # =========================

    def on_press(self, column, row, colour):
        colour_name = COLOUR_ROWS[row][0]
        colour_hex = _COLOUR_SET[colour_name]
        print(f"{column} → {COLOUR_ROWS[row][0]}")

        

        if column == ALL_COLUMN:
            self.apply_row(row)
            self.send_all_api_requests(colour_hex)
        else:
            self.select_single(column, row)
            self.send_api_request(column, colour_hex)

    def select_single(self, column, row):
        if column in self.selected_in_column:
            prev_row = self.selected_in_column[column]
            self._set_button_state(column, prev_row, selected=False)

        self._set_button_state(column, row, selected=True)
        self.selected_in_column[column] = row

    def apply_row(self, row):
        for column in LAYER_MAP.keys():
            self.select_single(column, row)

    # =========================
    # API HANDLING
    # =========================

    def send_api_request(self, column, colour):
        payload = copy.deepcopy(self.BASE_PAYLOAD)
        payload["video"]["effects"][0]["params"]["Color"]["value"] = colour
        layer = LAYER_MAP[column]
        url = f"{API_BASE_URL}/layers/{layer}/clips/1"
        print(payload)
        def task():
            try:
                self.session.put(url, json=payload, timeout=(0.05, 0.2))
            except Exception as e:
                print(f"API error: {e}")

        self.executor.submit(task)


    def send_all_api_requests(self, colour):
        def task(layer):
            url = f"{API_BASE_URL}/layers/{layer}/clips/1"
            payload = copy.deepcopy(self.BASE_PAYLOAD)
            payload["video"]["effects"][0]["params"]["Color"]["value"] = colour
            try:
                self.session.put(url, json=payload, timeout=(0.05, 0.2))
            except Exception as e:
                print(f"API error: {e}")

        for layer in LAYER_MAP.values():
            self.executor.submit(task, layer)


    # =========================
    # VISUAL STATE HANDLING
    # =========================

    def _set_button_state(self, column, row, selected):
        btn = self.buttons[(column, row)]
        base_colour = self.base_colours[(column, row)]
        colour = darken(base_colour) if selected else base_colour
        btn.setStyleSheet(button_stylesheet(colour, selected))
    
    def setup_heartbeat(self):
        """Set up the status heartbeat polling"""
        self.heartbeat.status_updated.connect(self.update_status_display)
        self.timer.start(HEARTBEAT_INTERVAL)
        # Perform initial check immediately
        self.heartbeat.check_status()
    
    def update_status_display(self, status: str, latency: float, colour: str):
        """Update the status display with new information"""
        self.status_label.setText(status)
        self.latency_label.setText(f"{latency:.1f} ms" if latency > 0 else "-- ms")
        self.status_square.setStyleSheet(f"background-color: {colour}; border: 2px solid #333;")
    
    def open_colour_config(self):
        """Open the colour configuration dialog"""
        dialog = ColourConfigDialog(_COLOUR_SET, self)
        dialog.colours_updated.connect(self.update_colours)
        dialog.exec()
    
    def update_colours(self, new_colours):
        """Update the colour palette and refresh UI"""
        global _COLOUR_SET, COLOUR_ROWS
        
        _COLOUR_SET = new_colours
        COLOUR_ROWS = list(_COLOUR_SET.items())
        
        # Clear and rebuild the button grid
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.buttons.clear()
        self.base_colours.clear()
        self.selected_in_column.clear()
        
        self._add_headers()
        self._add_buttons()


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    
    app = QApplication(sys.argv)
    window = ColourPickerEngine()
    window.show()
    sys.exit(app.exec())
