import firebase_admin
from firebase_admin import credentials, db
import threading

CREDENTIAL_PATH = "/home/pi/projects/dms/rpi_navi/gps/dms-navi-firebase-adminsdk-fbsvc-2f5171bc60.json"
DATABASE_URL = "https://dms-navi-default-rtdb.asia-southeast1.firebasedatabase.app"

latest_gps = {"lat": None, "lon": None}

def init_firebase():
    cred = credentials.Certificate(CREDENTIAL_PATH)
    firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})

def gps_listener(event):
    data = event.data
    if data and "lat" in data and "lon" in data:
        latest_gps["lat"] = data["lat"]
        latest_gps["lon"] = data["lon"]
        print(f"GPS updated: {latest_gps}")

def start_gps_stream():
    ref = db.reference("/gps")
    ref.listen(gps_listener)

def start():
    init_firebase()
    t = threading.Thread(target=start_gps_stream, daemon=True)
    t.start()

if __name__ == "__main__":
    start()
    import time
    while True:
        time.sleep(1)
