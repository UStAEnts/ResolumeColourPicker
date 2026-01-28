import copy
import json
import requests
from importlib.resources import files
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtWidgets import (
    QWidget, QPushButton,
    QGridLayout, QLabel, QVBoxLayout, QHBoxLayout,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from resolume_colour_picker.status_heartbeat import StatusHeartbeat
from resolume_colour_picker.colour_dialogue import ColourConfigDialog

class ColourPickerEngine(QWidget):
    def __init__(self, config, consts):
        self.config = config
        self.config.value_changed.connect(self.config_callback)
        
        self.api_base_url = f"http://{self.config["WEBSERVER_IP"]}:{self.config["WEBSERVER_PORT"]}/api/v1/composition"
        self.colour_rows = list(self.config["COLOUR_SET"].items())

        self.consts = consts

        self.BASE_PAYLOAD = json.loads(
            files("resolume_colour_picker.data")
            .joinpath("get_colourize.json")
            .read_text(encoding="utf-8")
        )

        self.executor = ThreadPoolExecutor(max_workers=4)
        self.session = requests.Session()

        super().__init__()

        self.setWindowTitle("Colour Picker Engine")
        self.resize(*consts["WINDOW_SIZE"])

        self.layout = QGridLayout(self)
        self.setLayout(self.layout)

        self.selected_in_column = {}
        self.buttons = {}
        self.base_colours = {}
        
        # Scene Master Mode
        self.scene_master_mode = False
        self.queued_changes = []  # List of (column, colour_hex) tuples
        
        # Status heartbeat components
        self.heartbeat = StatusHeartbeat(self.config)
        self.status_label = QLabel("Initialising...")
        self.status_square = QLabel()
        self.latency_label = QLabel("-- ms")
        self.scene_mode_label = QLabel("Live Mode")
        self.timer = QTimer()
        self.timer.timeout.connect(self.heartbeat.check_status)

        self.build_ui()
        self.setup_heartbeat()

    def config_callback(self, key, value):
        if key == "WEBSERVER_IP" or key == "WEBSERVER_PORT":
            self.api_base_url = f"http://{self.config["WEBSERVER_IP"]}:{self.config["WEBSERVER_PORT"]}/api/v1/composition"

        elif key == "COLOUR_SET":
            self.colour_rows = list(self.config["COLOUR_SET"].items())

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
        
        elif key == "COLUMNS":
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
    # STYLE HELPERS
    # =========================

    def darken(self, colour: QColor, factor=None) -> QColor:
        if factor is None:
            factor = self.consts["DARKEN_FACTOR"]
        return QColor(
            int(colour.red() * factor),
            int(colour.green() * factor),
            int(colour.blue() * factor),
        )


    def button_stylesheet(self, colour: QColor, selected=False) -> str:
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
        
        # Add scene mode indicator
        self.scene_mode_label.setStyleSheet("font-weight: bold; color: #00AA00;")
        status_layout.addWidget(self.scene_mode_label)
        
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
        
        # Add scene control buttons at bottom
        scene_control_layout = QHBoxLayout()
        
        self.scene_master_btn = QPushButton("Scene Master")
        self.scene_master_btn.setFixedHeight(self.consts["BUTTON_HEIGHT"])
        self.scene_master_btn.clicked.connect(self.toggle_scene_master)
        scene_control_layout.addWidget(self.scene_master_btn)
        
        # Add go/cancel buttons (hidden by default)
        self.go_btn = QPushButton("GO")
        self.go_btn.setFixedHeight(self.consts["BUTTON_HEIGHT"])
        self.go_btn.setStyleSheet("background-color: #00AA00; color: white; font-weight: bold;")
        self.go_btn.clicked.connect(self.send_queued_changes)
        self.go_btn.hide()
        scene_control_layout.addWidget(self.go_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(self.consts["BUTTON_HEIGHT"])
        self.cancel_btn.setStyleSheet("background-color: #FF6600; color: white; font-weight: bold;")
        self.cancel_btn.clicked.connect(self.cancel_scene_master)
        self.cancel_btn.hide()
        scene_control_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(scene_control_layout)
        
        # Set the main layout
        self.setLayout(main_layout)
        
        self._add_headers()
        self._add_buttons()

    def _add_headers(self):
        for col, name in enumerate(self.config["COLUMNS"]):
            label = QLabel(name)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-weight: bold;font-size: 32px;")
            self.layout.addWidget(label, 0, col)

    def _add_buttons(self):
        for row, entry in enumerate(self.colour_rows):
            colour = QColor(entry[1])  # hex is second element
            label = entry[0]  # label is first element

            for col, column_name in enumerate(self.config["COLUMNS"]):
                btn = QPushButton(label)
                btn.setFixedHeight(self.consts["BUTTON_HEIGHT"])
                btn.setStyleSheet(self.button_stylesheet(colour))

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
        colour_name = self.colour_rows[row][0]
        colour_hex = self.config["COLOUR_SET"][colour_name]
        print(f"{column} → {self.colour_rows[row][0]}")

        if self.scene_master_mode:
            # Queue the change
            if column == self.config["ALL_COLUMN"]:
                # Queue for all layers
                for col in self.config["LAYER_MAP"].keys():
                    self.queued_changes.append((col, colour_hex))
                    self.select_single(col, row)
            else:
                # Queue for single layer
                self.queued_changes.append((column, colour_hex))
                self.select_single(column, row)
            print(f"Queued: {len(self.queued_changes)} changes pending")
        else:
            # Live mode - send immediately
            if column == self.config["ALL_COLUMN"]:
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
        for column in self.config["LAYER_MAP"].keys():
            self.select_single(column, row)

    # =========================
    # API HANDLING
    # =========================

    def send_api_request(self, column, colour):
        payload = copy.deepcopy(self.BASE_PAYLOAD)
        payload["video"]["effects"][0]["params"]["Color"]["value"] = colour
        layer = self.config["LAYER_MAP"][column]
        url = f"{self.api_base_url}/layers/{layer}/clips/1"
        print(payload)
        def task():
            try:
                self.session.put(url, json=payload, timeout=(0.05, 0.2))
            except Exception as e:
                print(f"API error: {e}")

        self.executor.submit(task)


    def send_all_api_requests(self, colour):
        def task(layer):
            url = f"{self.api_base_url}/layers/{layer}/clips/1"
            payload = copy.deepcopy(self.BASE_PAYLOAD)
            payload["video"]["effects"][0]["params"]["Color"]["value"] = colour
            try:
                self.session.put(url, json=payload, timeout=(0.05, 0.2))
            except Exception as e:
                print(f"API error: {e}")

        for layer in self.config["LAYER_MAP"].values():
            self.executor.submit(task, layer)


    # =========================
    # VISUAL STATE HANDLING
    # =========================

    def _set_button_state(self, column, row, selected):
        btn = self.buttons[(column, row)]
        base_colour = self.base_colours[(column, row)]
        colour = self.darken(base_colour) if selected else base_colour
        btn.setStyleSheet(self.button_stylesheet(colour, selected))
    
    def setup_heartbeat(self):
        """Set up the status heartbeat polling"""
        self.heartbeat.status_updated.connect(self.update_status_display)
        self.timer.start(self.consts["HEARTBEAT_INTERVAL"])
        # Perform initial check immediately
        self.heartbeat.check_status()
    
    def update_status_display(self, status: str, latency: float, colour: str):
        """Update the status display with new information"""
        self.status_label.setText(status)
        self.latency_label.setText(f"{latency:.1f} ms" if latency > 0 else "-- ms")
        self.status_square.setStyleSheet(f"background-color: {colour}; border: 2px solid #333;")
    
    def toggle_scene_master(self):
        """Toggle scene master mode on/off"""
        self.scene_master_mode = not self.scene_master_mode
        
        if self.scene_master_mode:
            self.scene_mode_label.setText("SCENE MASTER MODE")
            self.scene_mode_label.setStyleSheet("font-weight: bold; color: #FF6600;")
            self.go_btn.show()
            self.cancel_btn.show()
            self.queued_changes = []
            print("Scene Master Mode: ACTIVE")
        else:
            self.scene_mode_label.setText("Live Mode")
            self.scene_mode_label.setStyleSheet("font-weight: bold; color: #00AA00;")
            self.go_btn.hide()
            self.cancel_btn.hide()
            self.queued_changes = []
            print("Scene Master Mode: INACTIVE")
    
    def send_queued_changes(self):
        """Send all queued changes to Resolume"""
        print(f"Sending {len(self.queued_changes)} queued changes...")
        
        # Group changes by column
        changes_by_column = {}
        for column, colour in self.queued_changes:
            changes_by_column[column] = colour
        
        # Send each change
        for column, colour in changes_by_column.items():
            self.send_api_request(column, colour)
        
        print("All queued changes sent!")
        self.toggle_scene_master()  # Exit scene master mode
    
    def cancel_scene_master(self):
        """Cancel scene master mode without sending changes"""
        print(f"Cancelled {len(self.queued_changes)} queued changes")
        
        # Reset button states
        for column in self.selected_in_column.keys():
            row = self.selected_in_column[column]
            self._set_button_state(column, row, selected=False)
        
        self.selected_in_column = {}
        self.toggle_scene_master()  # Exit scene master mode
    
    def open_colour_config(self):
        """Open the colour configuration dialog"""
        dialog = ColourConfigDialog(self.config, self)
        dialog.exec()
    