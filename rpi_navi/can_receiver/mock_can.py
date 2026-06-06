import requests
import time

FLASK_URL = "http://localhost:5000/state"

scenarios = [0, 0, 1, 0, 0, 2, 1, 0]

for state in scenarios:
    try:
        requests.post(FLASK_URL, json={"state": state})
        print(f"Sent state: {state}")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(2)
