import firebase_admin
from firebase_admin import credentials, db
import threading
import datetime
import math
import time

CREDENTIAL_PATH = "/home/pi/projects/dms/rpi5_navi/gps/dms-navi-firebase-adminsdk-fbsvc-2f5171bc60.json"
DATABASE_URL = "https://dms-navi-default-rtdb.asia-southeast1.firebasedatabase.app"

DRIVER_ID = "kym"
SESSION_TIMEOUT = 180   # 3분 이상 신호 없으면 새 세션
MIN_DIST_M = 10         # 10m 이상 이동했을 때만 경로 저장

latest_gps = {"lat": None, "lon": None}
session_id = None
gps_index = 0
last_gps_time = None      # 마지막 GPS 신호 수신 시각
last_saved_pos = None     # 마지막으로 저장된 위치

def init_firebase():
    cred = credentials.Certificate(CREDENTIAL_PATH)
    firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})

def get_distance_m(lat1, lon1, lat2, lon2):
    """두 좌표 사이 거리 (미터)"""
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def start_session():
    global session_id, gps_index, last_saved_pos
    today = datetime.datetime.now().strftime("%Y%m%d")

    # 오늘 날짜 세션이 이미 있으면 재사용
    existing = db.reference(f"/sessions/{DRIVER_ID}").get() or {}
    today_sessions = sorted([k for k in existing.keys() if k.startswith(today)])

    if today_sessions:
        session_id = today_sessions[-1]  # 가장 최근 세션 재사용
        gps_data = existing[session_id].get("gps_path", {})
        if isinstance(gps_data, list):
            gps_data = {str(i): v for i, v in enumerate(gps_data) if v}
        gps_index = len(gps_data)
        last_saved_pos = None
        if gps_data:
            last_pt = gps_data.get(str(gps_index-1))
            if last_pt:
                last_saved_pos = (last_pt["lat"], last_pt["lon"])
        print(f"[Session] 기존 세션 재사용: {session_id} (포인트 {gps_index}개)")
    else:
        session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        gps_index = 0
        last_saved_pos = None
        db.reference(f"/sessions/{DRIVER_ID}/{session_id}/start_time").set(
            datetime.datetime.now().isoformat()
        )
        print(f"[Session] 새 세션 시작: {session_id}")

def gps_listener(event):
    global gps_index, last_gps_time, last_saved_pos, session_id

    data = event.data
    if not data or "lat" not in data or "lon" not in data:
        return

    lat, lon = data["lat"], data["lon"]
    now = datetime.datetime.now()

    # 3분 이상 끊겼으면 새 세션 시작
    if last_gps_time is not None:
        elapsed = (now - last_gps_time).total_seconds()
        if elapsed > SESSION_TIMEOUT:
            print(f"[Session] {elapsed:.0f}초 경과 → 새 세션 시작")
            start_session()

    last_gps_time = now

    latest_gps["lat"] = lat
    latest_gps["lon"] = lon

    # 현재 위치 업데이트
    db.reference(f"/gps/{DRIVER_ID}").set({
        "lat": lat,
        "lon": lon,
        "timestamp": now.isoformat()
    })

    # 거리 확인 후 경로 저장
    if session_id:
        should_save = False
        if last_saved_pos is None:
            should_save = True  # 첫 포인트는 무조건 저장
        else:
            dist = get_distance_m(last_saved_pos[0], last_saved_pos[1], lat, lon)
            if dist >= MIN_DIST_M:
                should_save = True

        if should_save:
            db.reference(f"/sessions/{DRIVER_ID}/{session_id}/gps_path/{gps_index}").set({
                "lat": lat,
                "lon": lon,
                "timestamp": now.isoformat()
            })
            gps_index += 1
            last_saved_pos = (lat, lon)
            print(f"[GPS] 저장 ({gps_index}번째): {lat:.5f}, {lon:.5f}")
        else:
            print(f"[GPS] 수신 (저장 안함): {lat:.5f}, {lon:.5f}")

def save_event_firebase(state, lat, lon):
    if not session_id:
        return
    db.reference(f"/sessions/{DRIVER_ID}/{session_id}/events").push({
        "timestamp": datetime.datetime.now().isoformat(),
        "state": state,
        "lat": lat,
        "lon": lon
    })
    print(f"[Event] 졸음 이벤트 저장: state={state}")

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
    while True:
        time.sleep(1)
