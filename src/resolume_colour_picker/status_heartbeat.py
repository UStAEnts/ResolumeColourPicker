import requests
import time

from PySide6.QtCore import Signal, QObject


class StatusHeartbeat(QObject):
    """Emits status updates for the Resolume connection"""
    status_updated = Signal(str, float, str)  # status, latency, colour
    
    def __init__(self, config):
        super().__init__()
        self.session = requests.Session()
        self.running = False
        self.config = config

        self.resolume_product_url = f"http://{self.config["WEBSERVER_IP"]}:{self.config["WEBSERVER_PORT"]}/api/v1/product"
        self.config.value_changed.connect(self.config_callback)

    def config_callback(self, key, value):
        if key == "WEBSERVER_IP" or key == "WEBSERVER_PORT":
            self.resolume_product_url = f"http://{self.config["WEBSERVER_IP"]}:{self.config["WEBSERVER_PORT"]}/api/v1/product"

    def check_status(self):
        """Poll the Resolume /product endpoint"""
        try:
            start_time = time.time()
            response = self.session.get(self.resolume_product_url, timeout=2)
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
                status += " to Resolume @ " + self.config["WEBSERVER_IP"] 
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