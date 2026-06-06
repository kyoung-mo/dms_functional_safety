import sqlite3
import datetime

DB_PATH = "db/driving_log.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        state INTEGER,
        lat REAL,
        lon REAL
    )''')
    conn.commit()
    conn.close()

def save_event(state, lat=None, lon=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO events VALUES (NULL, ?, ?, ?, ?)",
              (datetime.datetime.now().isoformat(), state, lat, lon))
    conn.commit()
    conn.close()

init_db()
