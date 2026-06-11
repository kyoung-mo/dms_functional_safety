"""
DMS 데모 데이터 - 3일치 추가 (0607, 0608, 0609)
"""
import firebase_admin
from firebase_admin import credentials, db
import datetime
import random
import math

CREDENTIAL_PATH = "/home/pi/projects/dms/rpi5_navi/gps/dms-navi-firebase-adminsdk-fbsvc-2f5171bc60.json"
DATABASE_URL = "https://dms-navi-default-rtdb.asia-southeast1.firebasedatabase.app"

cred = credentials.Certificate(CREDENTIAL_PATH)
firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})

CENTER_LAT = 37.5422
CENTER_LON = 126.8416

def generate_path(start_lat, start_lon, direction_deg, num_points=40, step=0.0008):
    path = []
    lat, lon = start_lat, start_lon
    angle = math.radians(direction_deg)
    for i in range(num_points):
        noise_lat = random.uniform(-0.0001, 0.0001)
        noise_lon = random.uniform(-0.0001, 0.0001)
        lat += math.cos(angle) * step + noise_lat
        lon += math.sin(angle) * step + noise_lon
        if i % 10 == 9:
            angle += math.radians(random.uniform(-30, 30))
        path.append({"lat": round(lat, 7), "lon": round(lon, 7)})
    return path

# 날짜별 세션 설정
SESSIONS = [
    # (날짜, driver_id, start_offset, direction, hour, min, events_idx)
    # 0607
    ("20260607", "driver_a", (0.001, -0.002), 60,  8, 0,  [12, 28]),
    ("20260607", "driver_b", (-0.002, 0.003), 150, 9, 30, [20]),
    ("20260607", "driver_c", (0.003, -0.001), 240, 7, 0,  [5, 18, 32]),

    # 0608
    ("20260608", "driver_a", (-0.001, 0.002), 30,  8, 15, [8]),
    ("20260608", "driver_b", (0.002, -0.003), 200, 8, 45, [15, 30]),
    ("20260608", "driver_c", (-0.003, 0.001), 310, 7, 30, [10, 22, 35]),

    # 0609
    ("20260609", "driver_a", (0.002, 0.001),  90,  9, 0,  [5, 20, 33]),
    ("20260609", "driver_b", (-0.001,-0.002), 120, 8, 0,  [18]),
    ("20260609", "driver_c", (0.001, 0.003),  280, 7, 15, [7, 25]),
]

print("3일치 데모 데이터 생성 중...")

for date, driver_id, offset, direction, hour, minute, event_idxs in SESSIONS:
    start_lat = CENTER_LAT + offset[0]
    start_lon = CENTER_LON + offset[1]
    path = generate_path(start_lat, start_lon, direction)

    session_id = f"{date}_{hour:02d}{minute:02d}00"
    start_time = f"2026-{date[4:6]}-{date[6:8]}T{hour:02d}:{minute:02d}:00"

    db.reference(f"/sessions/{driver_id}/{session_id}/start_time").set(start_time)

    for i, point in enumerate(path):
        ts = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
        ts += datetime.timedelta(seconds=i*30)
        db.reference(f"/sessions/{driver_id}/{session_id}/gps_path/{i}").set({
            "lat": point["lat"],
            "lon": point["lon"],
            "timestamp": ts.isoformat()
        })

    for idx in event_idxs:
        if idx < len(path):
            ts = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
            ts += datetime.timedelta(seconds=idx*30)
            db.reference(f"/sessions/{driver_id}/{session_id}/events").push({
                "timestamp": ts.isoformat(),
                "state": 2,
                "lat": path[idx]["lat"],
                "lon": path[idx]["lon"]
            })

    print(f"[{driver_id}] {session_id} 저장 완료 ({len(event_idxs)}개 이벤트)")

print("\n✅ 3일치 데모 데이터 생성 완료!")
