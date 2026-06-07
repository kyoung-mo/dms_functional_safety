from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from db.log import save_event
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from gps.firebase_gps import start, latest_gps

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

current_state = 0

@app.route("/gps-sender")
def gps_sender():
    return render_template("gps_sender.html")
@app.route("/")

def index():
    return render_template("index.html")

@app.route("/state", methods=["POST"])
def receive_state():
    global current_state
    data = request.get_json()
    current_state = data.get("state", 0)
    lat = latest_gps.get("lat")
    lon = latest_gps.get("lon")
    socketio.emit("state_update", {
        "state": current_state,
        "lat": lat,
        "lon": lon
    })
    if current_state >= 1:
        save_event(current_state, lat, lon)
    return jsonify({"ok": True})

if __name__ == "__main__":
    start()  # Firebase GPS 스트림 시작
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
