import os
import re
import sqlite3
from datetime import datetime

HERE     = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.abspath(os.path.join(HERE, ".."))
DB_PATH  = os.path.join(ROOT_DIR, "parking.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_plate(text: str) -> str:
    """Entfernt alle Nicht-Buchstaben/Ziffern, Grossbuchstaben.
    Konsistent mit main.py UND web_app.py (nach dem Fix)."""
    return re.sub(r"[^A-Z0-9]", "", (text or "").strip().upper())


def create_tables() -> None:
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS allowedplates (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT UNIQUE NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS parkingevents (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            plate     TEXT    NOT NULL,
            direction TEXT    NOT NULL,
            timestamp TEXT    NOT NULL,
            allowed   INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def is_allowed_plate(plate: str) -> bool:
    plate = normalize_plate(plate)
    if not plate:
        return False
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT 1 FROM allowedplates WHERE plate = ?", (plate,))
    result = cur.fetchone() is not None
    conn.close()
    return result


def get_allowed_plates() -> list:
    """Nur aus allowedplates (nie aus Event-History!)."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT plate FROM allowedplates")
    plates = [normalize_plate(row["plate"]) for row in cur.fetchall()]
    conn.close()
    return [p for p in plates if 5 <= len(p) <= 10]


def log_event(plate: str, direction: str, allowed: bool) -> None:
    plate = normalize_plate(plate)
    if not plate:
        return
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO parkingevents (plate, direction, timestamp, allowed) VALUES (?, ?, ?, ?)",
        (plate, direction, datetime.now().isoformat(timespec="seconds"), int(allowed)),
    )
    conn.commit()
    conn.close()


def get_last_event(plate: str):
    plate = normalize_plate(plate)
    if not plate:
        return None
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, plate, direction, timestamp, allowed
        FROM   parkingevents
        WHERE  plate = ?
        ORDER  BY datetime(timestamp) DESC
        LIMIT  1
    """, (plate,))
    row = cur.fetchone()
    conn.close()
    return row


if __name__ == "__main__":
    create_tables()
    print("DB OK:", DB_PATH)