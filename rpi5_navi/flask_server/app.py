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

            # ── 0x100: 졸음 상태 ──
            if msg.arbitration_id == 0x100:
                if len(msg.data) < 2:
                    continue
                driver_state = msg.data[0]
                rpi_alive    = msg.data[1]
                current_state = driver_state

                # [추가] 0x101 ACK 송신 — 수신 확인 응답
                try:
                    ack = can.Message(arbitration_id=0x101,
                                      data=[0x01],
                                      is_extended_id=False)
                    bus.send(ack)
                except can.CanError:
                    pass   # ACK 실패는 치명적이지 않음, 본 처리 계속

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

            # ── 0x7DF: DTC (STM32 Failsafe) ──
            elif msg.arbitration_id == 0x7DF:
                print(f"[DTC] Failsafe 수신: {msg.data.hex()}")
                socketio.emit("dtc_alert", {"data": msg.data.hex()})

            # ── 0x200: STM32 Heartbeat (현재는 무시, 예정 기능) ──
            # elif msg.arbitration_id == 0x200: ...

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
