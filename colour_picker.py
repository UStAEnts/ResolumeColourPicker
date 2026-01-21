import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QGridLayout, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from concurrent.futures import ThreadPoolExecutor


# =========================
# CONFIGURATION
# =========================

COLUMNS = ["ALL" , "Outer", "Middle", "Inner", "DJ"]
ALL_COLUMN = "ALL"

COLOUR_ROWS = [
    {"label": "Red",    "hex": "#FF0000"},
    {"label": "Blue",   "hex": "#0000FF"},
    {"label": "Yellow", "hex": "#FFFF00"},
    {"label": "Orange", "hex": "#FFA500"},
    {"label": "Green",  "hex": "#00B050"},
    {"label": "Purple", "hex": "#800080"},
    {"label": "Pink",   "hex": "#FF69B4"},
    {"label": "White",   "hex": "#FFFFFF"},
]

WINDOW_SIZE = (900, 700)
BUTTON_HEIGHT = 55
DARKEN_FACTOR = 0.65

API_BASE_URL = "http://localhost:8080/api/v1/composition"

LAYER_MAP = {
    "Inner": 1,
    "Middle": 2,
    "Outer": 3,
    "DJ": 4,
}




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
# MAIN APP
# =========================

class ColourPickerEngine(QWidget):
    def __init__(self):

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

        self.build_ui()

    def build_ui(self):
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
            colour = QColor(entry["hex"])
            label = entry["label"]

            for col, column_name in enumerate(COLUMNS):
                btn = QPushButton(label)
                btn.setFixedHeight(BUTTON_HEIGHT)
                btn.setStyleSheet(button_stylesheet(colour))

                btn.clicked.connect(
                    lambda _, c=column_name, r=row: self.on_press(c, r)
                )

                self.layout.addWidget(btn, row + 1, col)

                self.buttons[(column_name, row)] = btn
                self.base_colours[(column_name, row)] = colour

    # =========================
    # INTERACTION LOGIC
    # =========================

    def on_press(self, column, row):
        print(f"{column} → {COLOUR_ROWS[row]['label']}")

        if column == ALL_COLUMN:
            self.apply_row(row)
            self.send_all_api_requests(row)
        else:
            self.select_single(column, row)
            self.send_api_request(column, row)

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

    def send_api_request(self, column, row):
        layer = LAYER_MAP[column]
        clip = row + 1
        url = f"{API_BASE_URL}/layers/{layer}/clips/{clip}/connect"

        def task():
            try:
                self.session.post(url, timeout=(0.05, 0.2))
            except Exception as e:
                print(f"API error: {e}")

        self.executor.submit(task)


    def send_all_api_requests(self, row):
        clip = row + 1

        def task(layer):
            url = f"{API_BASE_URL}/layers/{layer}/clips/{clip}/connect"
            try:
                self.session.post(url, timeout=(0.05, 0.2))
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


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    
    app = QApplication(sys.argv)
    window = ColourPickerEngine()
    window.show()
    sys.exit(app.exec())
