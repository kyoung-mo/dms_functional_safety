import requests
import time
import random

FLASK_URL = "http://localhost:5000/state"

print("DMS Mock CAN 시작 (Ctrl+C로 종료)")

for i in range(30):
    state = random.choice([0, 1, 2])
    label = ["정상", "주의", "졸음"][state]
    try:
        requests.post(FLASK_URL, json={"state": state})
        print(f"[{i+1}/30] Sent state: {state} ({label})")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(1)

print("완료")
