from concurrent.futures import ThreadPoolExecutor
import copy
from typing import Callable, Optional

import requests

from resolume_colour_picker import Config

BASE_REQUEST = {"video": {"effects": [{"params": {"Color": {"value": "#FFFFFF"}}}]}}


Callback = Callable[[Optional[requests.Response], Optional[Exception]], None]

class API:
    def __init__(self, config: Config, workers: int = 4):
        self.config = config
        self.config.connect(self.config_callback)

        self.executor = ThreadPoolExecutor(max_workers=workers)
        self.session = requests.Session()

        self.api_base_url = f"http://{self.config["WEBSERVER_IP"]}:{self.config["WEBSERVER_PORT"]}/api/v1/composition"

    def config_callback(self, key, value):
        if key == "WEBSERVER_IP" or key == "WEBSERVER_PORT":
            self.api_base_url = f"http://{self.config["WEBSERVER_IP"]}:{self.config["WEBSERVER_PORT"]}/api/v1/composition"

    def update_colour(self, layer, colour):
        payload = copy.deepcopy(self.BASE_PAYLOAD)
        payload["video"]["effects"][0]["params"]["Color"]["value"] = colour
        endpoint = f"/layers/{layer}/clips/1"

        self.put(endpoint, payload)

    def put(self, endpoint:str, payload=None, callback:Callback|None=None, timeout=(0.05, 0.2)):
        def task(url, payload, callback, timeout):
            try:
                res = self.session.put(url, json=payload, timeout=timeout)
                exc = None
            except Exception as e:
                res = None
                exc = e
                print(f"API error: {e}")

            if callback is not None:
                callback(res, exc)

        url = self.api_base_url + endpoint
        return self.executor.submit(task, url, payload, callback, timeout)
    
    def get(self, endpoint:str, callback:Callback|None=None, timeout=(0.05, 0.2)):
        def task(url:str, callback:Callback|None, timeout):
            try:
                res = self.session.get(url, timeout=timeout)
                exc = None
            except Exception as e:
                res = None
                exc = e
                print(f"API error: {e}")

            if callback is not None:
                callback(res, exc)

        url = self.api_base_url + endpoint
        return self.executor.submit(task, url, callback, timeout)
