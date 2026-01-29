import copy
import json
import sys
import requests
import time
from importlib.resources import files
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QGridLayout, QLabel, QVBoxLayout, QHBoxLayout,
    QDialog, QTableWidget, QTableWidgetItem, QLineEdit,
    QHeaderView, QColorDialog
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QColor

from resolume_colour_picker.application import ColourPickerEngine
from resolume_colour_picker.config import Config

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

CONSTS = {
    "WINDOW_SIZE": (900, 700),
    "BUTTON_HEIGHT": 55,
    "DARKEN_FACTOR": 0.65,
    "HEARTBEAT_INTERVAL": 3000  # 3 seconds in milliseconds
}


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






# =========================
# STATUS HEARTBEAT
# =========================

# =========================
# MAIN APP
# =========================


def start():
    defaults = json.loads(
        files("resolume_colour_picker.data")
        .joinpath("defaults.json")
        .read_text(encoding="utf-8")
    )

    app = QApplication(sys.argv)
    config = Config("Colour Picker Engine", defaults=defaults)
    window = ColourPickerEngine(config, CONSTS)
    window.show()
    app.aboutToQuit.connect(config.save)
    sys.exit(app.exec())