from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from db.log import save_event
import sys
import os
import can
from threading import Thread
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from gps.firebase_gps import start, latest_gps, save_event_firebase

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
current_state = 0

def can_reader_thread():
    global current_state
    try:
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        for msg in bus:
            if len(msg.data) < 2:
                continue
            driver_state = msg.data[0]
            rpi_alive    = msg.data[1]
            current_state = driver_state
            lat = latest_gps.get("lat")
            lon = latest_gps.get("lon")
            socketio.emit("state_update", {
                "state": driver_state,
                "alive": rpi_alive,
                "lat": lat,
                "lon": lon
            })
            if driver_state >= 2:
                save_event(driver_state, lat, lon)
                save_event_firebase(driver_state, lat, lon)
    except Exception as e:
        print(f"[CAN ERROR] {e}")

@app.route("/gps-sender")
def gps_sender():
    return render_template("gps_sender.html")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/control")
def control():
    return render_template("control_center.html")

if __name__ == "__main__":
    start()
    t = Thread(target=can_reader_thread, daemon=True)
    t.start()
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
