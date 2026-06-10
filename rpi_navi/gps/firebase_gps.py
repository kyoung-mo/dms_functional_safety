import firebase_admin
from firebase_admin import credentials, db
import threading
import datetime

CREDENTIAL_PATH = "/home/pi/projects/dms/rpi_navi/gps/dms-navi-firebase-adminsdk-fbsvc-2f5171bc60.json"
DATABASE_URL = "https://dms-navi-default-rtdb.asia-southeast1.firebasedatabase.app"

DRIVER_ID = "kym"  # 각 트럭마다 고정 설정

latest_gps = {"lat": None, "lon": None}
session_id = None
gps_index = 0

def init_firebase():
    cred = credentials.Certificate(CREDENTIAL_PATH)
    firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})

def start_session():
    """주행 세션 시작 - session_id 생성 및 Firebase에 등록"""
    global session_id, gps_index
    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    gps_index = 0
    db.reference(f"/sessions/{DRIVER_ID}/{session_id}/start_time").set(
        datetime.datetime.now().isoformat()
    )
    print(f"[Session] 시작: {session_id}")

def gps_listener(event):
    """스마트폰 GPS 수신 → Firebase /gps/{driver_id} 업데이트 + 경로 기록"""
    global gps_index
    data = event.data
    if data and "lat" in data and "lon" in data:
        latest_gps["lat"] = data["lat"]
        latest_gps["lon"] = data["lon"]

        # 현재 위치 업데이트 (/gps/{driver_id})
        db.reference(f"/gps/{DRIVER_ID}").set({
            "lat": data["lat"],
            "lon": data["lon"],
            "timestamp": datetime.datetime.now().isoformat()
        })

        # 경로 기록 (/sessions/{driver_id}/{session_id}/gps_path)
        if session_id:
            db.reference(f"/sessions/{DRIVER_ID}/{session_id}/gps_path/{gps_index}").set({
                "lat": data["lat"],
                "lon": data["lon"],
                "timestamp": datetime.datetime.now().isoformat()
            })
            gps_index += 1

        print(f"[GPS] {data['lat']}, {data['lon']}")

def save_event_firebase(state, lat, lon):
    """졸음 이벤트 Firebase 저장"""
    if not session_id:
        return
    ref = db.reference(f"/sessions/{DRIVER_ID}/{session_id}/events")
    ref.push({
        "timestamp": datetime.datetime.now().isoformat(),
        "state": state,
        "lat": lat,
        "lon": lon
    })
    print(f"[Event] 졸음 이벤트 저장: state={state}, lat={lat}, lon={lon}")

def start_gps_stream():
    ref = db.reference(f"/gps/{DRIVER_ID}")
    ref.listen(gps_listener)

def start():
    init_firebase()
    start_session()
    t = threading.Thread(target=start_gps_stream, daemon=True)
    t.start()

if __name__ == "__main__":
    start()
    import time
    while True:
        time.sleep(1)
