from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from db.log import save_event
import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

current_state = 0

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/state", methods=["POST"])
def receive_state():
    global current_state
    data = request.get_json()
    current_state = data.get("state", 0)
    socketio.emit("state_update", {"state": current_state})
    if current_state >= 1:
        save_event(current_state)
    return jsonify({"ok": True})

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
