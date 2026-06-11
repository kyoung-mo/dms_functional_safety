import firebase_admin
from firebase_admin import credentials, db
import datetime, random, math

CREDENTIAL_PATH = "/home/pi/projects/dms/rpi5_navi/gps/dms-navi-firebase-adminsdk-fbsvc-2f5171bc60.json"
DATABASE_URL = "https://dms-navi-default-rtdb.asia-southeast1.firebasedatabase.app"
cred = credentials.Certificate(CREDENTIAL_PATH)
firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})

CENTER_LAT = 37.5422
CENTER_LON = 126.8416

def generate_path(slat, slon, deg, n=40, step=0.0008):
    path, lat, lon = [], slat, slon
    angle = math.radians(deg)
    for i in range(n):
        lat += math.cos(angle)*step + random.uniform(-0.0001,0.0001)
        lon += math.sin(angle)*step + random.uniform(-0.0001,0.0001)
        if i%10==9: angle += math.radians(random.uniform(-30,30))
        path.append({"lat":round(lat,7),"lon":round(lon,7)})
    return path

SESSIONS = [
    ("20260605", (-0.001,-0.002), 45,  8, 30, [10,25]),
    ("20260606", (0.002,-0.001),  130, 9,  0, [15]),
    ("20260607", (-0.002,0.001),  220, 8, 15, [8,20,33]),
    ("20260608", (0.001,0.002),   310, 9, 30, [12]),
    ("20260609", (-0.001,0.003),  60,  8,  0, [5,28]),
    ("20260610", (0.002,-0.003),  170, 9, 15, [18]),
]

for date, offset, direction, hour, minute, event_idxs in SESSIONS:
    path = generate_path(CENTER_LAT+offset[0], CENTER_LON+offset[1], direction)
    sid = f"{date}_{hour:02d}{minute:02d}00"
    st = f"2026-{date[4:6]}-{date[6:8]}T{hour:02d}:{minute:02d}:00"
    db.reference(f"/sessions/kym/{sid}/start_time").set(st)
    for i,p in enumerate(path):
        ts = (datetime.datetime.strptime(st,"%Y-%m-%dT%H:%M:%S") + datetime.timedelta(seconds=i*30)).isoformat()
        db.reference(f"/sessions/kym/{sid}/gps_path/{i}").set({"lat":p["lat"],"lon":p["lon"],"timestamp":ts})
    for idx in event_idxs:
        if idx < len(path):
            ts = (datetime.datetime.strptime(st,"%Y-%m-%dT%H:%M:%S") + datetime.timedelta(seconds=idx*30)).isoformat()
            db.reference(f"/sessions/kym/{sid}/events").push({"timestamp":ts,"state":2,"lat":path[idx]["lat"],"lon":path[idx]["lon"]})
    print(f"[kym] {sid} 완료")

print("완료!")
