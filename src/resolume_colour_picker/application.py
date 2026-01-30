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
from resolume_colour_picker.api_settings_dialogue import APISettingsDialog
from resolume_colour_picker.layer_map_dialogue import LayerMapDialog

class ColourPickerEngine(QWidget):
    def __init__(self, config, consts):
        self.config = config
        self.config.value_changed.connect(self.config_callback, Qt.ConnectionType.QueuedConnection)
        
        self.api_base_url = f"http://{self.config["WEBSERVER_IP"]}:{self.config["WEBSERVER_PORT"]}/api/v1/composition"
        self.colour_rows = list(self.config["COLOUR_SET"].items())
        self.columns = self.config["LAYER_MAP"].keys()
        self.all_columns = []
        self.non_all_columns = []
        for col in self.columns:
            if self.config["LAYER_MAP"][col] == "ALL":
                self.all_columns.append(col)
            else:
                self.non_all_columns.append(col)
    
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

        self.selected_in_column = {}
        self.buttons = {}
        self.base_colours = {}
        
        # Scene Master Mode
        self.scene_master_mode = False
        self.queued_changes = []  # List of (column, colour_hex) tuples
        self.standby_selections = {}  # Tracks which buttons are selected in standby mode
        self.live_selections = {}  # Tracks which buttons are actually live
        
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
        
        elif key == "LAYER_MAP":

            self.columns = self.config["LAYER_MAP"].keys()
            self.all_columns = []
            self.non_all_columns = []
            for col in self.columns:
                if self.config["LAYER_MAP"][col] == "ALL":
                    self.all_columns.append(col)
                else:
                    self.non_all_columns.append(col)
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

    def desaturate(self, colour: QColor, factor=0.5) -> QColor:
        """Desaturate a colour for standby indication"""
        h = colour.hue()
        s = int(colour.saturation() * factor)
        v = colour.value()
        result = QColor()
        result.setHsv(h, s, v)
        return result

    def button_stylesheet(self, colour: QColor, selected=False, standby=False) -> str:
        border = "3px solid black" if selected else "1px solid #444"
        text_colour = "black" if colour.lightness() > 120 else "white"
        
        # Apply standby styling if in standby mode
        if standby:
            display_colour = self.desaturate(colour)
            border = "3px dashed #999"
        else:
            display_colour = colour

        return f"""
            QPushButton {{
                background-color: {display_colour.name()};
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
        
        # Add buttons
        colour_btn = QPushButton("Configure Colours")
        colour_btn.clicked.connect(self.open_colour_config)
        status_layout.addWidget(colour_btn)

        api_btn = QPushButton("API Settings")
        api_btn.clicked.connect(self.open_api_settings)
        status_layout.addWidget(api_btn)

        layers_btn = QPushButton("Layer Mappings")
        layers_btn.clicked.connect(self.open_layer_map_settings)
        status_layout.addWidget(layers_btn)

        reset_btn = QPushButton("!RESET!")
        reset_btn.clicked.connect(self.reset)
        status_layout.addWidget(reset_btn)
        

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
        for col, name in enumerate(self.columns):
            label = QLabel(name)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-weight: bold;font-size: 32px;")
            self.layout.addWidget(label, 0, col)

    def _add_buttons(self):
        for row, entry in enumerate(self.colour_rows):
            colour = QColor(entry[1])  # hex is second element
            label = entry[0]  # label is first element

            for col, column_name in enumerate(self.columns):
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
            if column in self.all_columns:
                # Queue for all layers
                for col in self.non_all_columns:
                    # Remove any existing queued changes for this column
                    self.queued_changes = [(c, clr) for c, clr in self.queued_changes if c != col]
                    # Add new change
                    self.queued_changes.append((col, colour_hex))
                    self.select_single(col, row)
            else:
                # Queue for single layer
                # Remove any existing queued changes for this column
                self.queued_changes = [(c, clr) for c, clr in self.queued_changes if c != column]
                # Add new change
                self.queued_changes.append((column, colour_hex))
                self.select_single(column, row)
            print(f"Queued: {len(self.queued_changes)} changes pending")
        else:
            # Live mode - send immediately
            if column in self.all_columns:
                self.apply_row(row)
                self.send_all_api_requests(colour_hex)
            else:
                self.select_single(column, row)
                self.send_api_request(column, colour_hex)

    def select_single(self, column, row):
        # In Scene Master mode, allow deselecting a standby selection by clicking it again
        if self.scene_master_mode and (column, row) in self.standby_selections:
            # Deselect the standby selection
            self._set_button_state(column, row, selected=False, standby=False)
            self.standby_selections.pop((column, row), None)
            # Remove from queued changes
            self.queued_changes = [(c, clr) for c, clr in self.queued_changes if c != column]
            # Keep live selection in selected_in_column if it exists for this column
            if (column, row) not in self.live_selections:
                # Find if there's a live selection in this column
                for (col, r) in self.live_selections.keys():
                    if col == column:
                        self.selected_in_column[column] = r
                        break
            return
        
        if column in self.selected_in_column:
            prev_row = self.selected_in_column[column]
            # In Scene Master mode, always deselect previous standby selections
            # but keep live selections visible
            if self.scene_master_mode:
                if (column, prev_row) in self.standby_selections:
                    # Deselect previous standby selection
                    self._set_button_state(column, prev_row, selected=False, standby=False)
                    self.standby_selections.pop((column, prev_row), None)
                # Don't deselect live selections - keep them visible
            else:
                # In live mode, always deselect previous selection
                is_prev_standby = (column, prev_row) in self.standby_selections
                self._set_button_state(column, prev_row, selected=False, standby=is_prev_standby)

        # In Scene Master mode, check if this is a new selection or keeping a live one
        if self.scene_master_mode:
            # If this selection was already live, keep it in live style (not standby)
            is_standby = (column, row) not in self.live_selections
            self._set_button_state(column, row, selected=True, standby=is_standby)
            # Only track as standby if it's a new selection
            if is_standby:
                self.standby_selections[(column, row)] = True
            else:
                # Remove from standby if it's a live selection
                self.standby_selections.pop((column, row), None)
        else:
            self._set_button_state(column, row, selected=True, standby=False)
            self.live_selections[(column, row)] = True
            self.standby_selections.pop((column, row), None)
        
        self.selected_in_column[column] = row
    def apply_row(self, row):
        for column in self.non_all_columns:
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

        for col in self.non_all_columns:
            self.executor.submit(task, self.config["LAYER_MAP"][col])


    # =========================
    # VISUAL STATE HANDLING
    # =========================

    def _set_button_state(self, column, row, selected, standby=False):
        btn = self.buttons[(column, row)]
        base_colour = self.base_colours[(column, row)]
        
        if selected:
            # When selected, darken the colour
            colour = self.darken(base_colour)
        else:
            colour = base_colour
        
        btn.setStyleSheet(self.button_stylesheet(colour, selected, standby=standby))
    
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
            # Save current live selections from selected_in_column
            self.live_selections = {}
            for column, row in self.selected_in_column.items():
                self.live_selections[(column, row)] = True
            # Display all current live selections with live style (solid border)
            self.standby_selections = {}
            for (column, row) in self.live_selections.keys():
                self._set_button_state(column, row, selected=True, standby=False)
            print("Scene Master Mode: ACTIVE")
        else:
            self.scene_mode_label.setText("Live Mode")
            self.scene_mode_label.setStyleSheet("font-weight: bold; color: #00AA00;")
            self.go_btn.hide()
            self.cancel_btn.hide()
            self.queued_changes = []
            self.standby_selections = {}
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
        
        # Deselect old live selections that are being replaced by standby selections
        for (column, row) in list(self.live_selections.keys()):
            # If this column has a new standby selection, deselect the old live one
            if any(col == column for col, _ in self.standby_selections.keys()):
                self._set_button_state(column, row, selected=False, standby=False)
                self.live_selections.pop((column, row), None)
        
        # Update standby selections to be the new live selections
        # This makes the dashed-border buttons become the new live selections
        for (column, row) in list(self.standby_selections.keys()):
            # Update the button styling to remove dashed border (now live)
            self._set_button_state(column, row, selected=True, standby=False)
            # Track as live selection
            self.live_selections[(column, row)] = True
            self.selected_in_column[column] = row
        
        print("All queued changes sent!")
        
        # Clear state and exit scene master mode
        self.queued_changes = []
        self.standby_selections = {}
        self.scene_master_mode = False
        self.scene_mode_label.setText("Live Mode")
        self.scene_mode_label.setStyleSheet("font-weight: bold; color: #00AA00;")
        self.go_btn.hide()
        self.cancel_btn.hide()
    
    def cancel_scene_master(self):
        """Cancel scene master mode without sending changes"""
        print(f"Cancelled {len(self.queued_changes)} queued changes")
        
        # Reset all buttons that were in standby mode to unselected
        for (column, row) in list(self.standby_selections.keys()):
            self._set_button_state(column, row, selected=False, standby=False)
        
        # Restore buttons that were live before entering Scene Master mode
        for (column, row) in list(self.live_selections.keys()):
            self._set_button_state(column, row, selected=True, standby=False)
            self.selected_in_column[column] = row
        
        # Clear standby selections
        self.standby_selections = {}
        self.queued_changes = []
        
        # Exit scene master mode
        self.scene_master_mode = False
        self.scene_mode_label.setText("Live Mode")
        self.scene_mode_label.setStyleSheet("font-weight: bold; color: #00AA00;")
        self.go_btn.hide()
        self.cancel_btn.hide()
    
    def open_colour_config(self):
        """Open the colour configuration dialog"""
        dialog = ColourConfigDialog(self.config, self)
        dialog.exec()

    def open_api_settings(self):
        """Open the colour configuration dialog"""
        dialog = APISettingsDialog(self.config, self)
        dialog.exec()
    
    def open_layer_map_settings(self):
        """Open the colour configuration dialog"""
        dialog = LayerMapDialog(self.config, self)
        dialog.exec()
    
    def reset(self):
        self.config.reset(broadcast=True)