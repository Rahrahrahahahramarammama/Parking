import os
import sys
import sqlite3
import re
from functools import wraps
from datetime import datetime, date, timedelta
from urllib.parse import urlparse

from flask import Flask, render_template_string, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix


# ----- Pfade -----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # .../Parking/frontend
ROOT_DIR = os.path.dirname(BASE_DIR)                    # .../Parking
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

DB_PATH = os.path.join(ROOT_DIR, "parking.db")

app = Flask(__name__)

# SECRET_KEY: bitte als ENV setzen (Windows PowerShell):
#   setx SECRET_KEY "lange-zufallszeichenkette"
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE_ME_DEV_ONLY")

# Hinter Reverse Proxy (Caddy) -> HTTPS korrekt erkennen
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Session Cookie (LAN: HTTP möglich, deshalb Secure dynamisch)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

@app.before_request
def _set_cookie_secure_flag():
    # Nur Secure-Cookies, wenn der aktuelle Request HTTPS ist
    app.config["SESSION_COOKIE_SECURE"] = bool(request.is_secure)


# Security-Header (HSTS nur bei HTTPS sinnvoll)
@app.after_request
def add_security_headers(resp):
    if request.is_secure:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=86400; includeSubDomains")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    return resp


# ---------- Theme / Settings ----------

THEMES = {
    "dark": "Dark (Standard)",
    "light": "White / Light",
    "ocean": "Ocean Blue",
    "forest": "Forest Green",
    "violet": "Violet",
    "amber": "Amber",
}

THEME_SWATCH = {
    "dark":   "#0f172a",
    "light":  "#ffffff",
    "ocean":  "#0077b6",
    "forest": "#2d6a4f",
    "violet": "#6d28d9",
    "amber":  "#b38b00",
}


def get_theme() -> str:
    t = (session.get("theme") or "dark").strip().lower()
    return t if t in THEMES else "dark"


def _is_safe_next(next_url: str) -> bool:
    if not next_url:
        return False
    p = urlparse(next_url)
    return (p.scheme == "" and p.netloc == "" and next_url.startswith("/") and not next_url.startswith("//"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    msg = None
    next_url = (request.args.get("next") or request.form.get("next") or "").strip()
    if not _is_safe_next(next_url):
        next_url = url_for("dashboard") if session.get("user_id") else url_for("login")

    if request.method == "POST":
        chosen = (request.form.get("theme") or "").strip().lower()
        if chosen in THEMES:
            session["theme"] = chosen
            return redirect(next_url)
        msg = "Ungültiges Theme."

    theme = get_theme()

    return render_template_string(r"""
    <html>
    <head>
      <title>Einstellungen</title>
      <style>
        body {background:#181825;color:#fafcff;font-family:sans-serif;margin:0;padding:0;}
        .container {max-width:650px;margin:30px auto;padding:25px;background:#202030;
                    border-radius:16px;box-shadow:0 0 18px #0006;}
        h1 {margin:0 0 14px 0;}
        .row {display:flex;gap:10px;align-items:center;flex-wrap:wrap;}
        .btn {padding:7px 12px;border-radius:8px;border:none;cursor:pointer;
              background:#295fee;color:#fff;text-decoration:none;display:inline-block;}
        .btn-secondary {background:#444;}
        .msg {margin:10px 0;color:#ffcc66;}
        .small {font-size:0.9em;color:#aaa;margin-top:10px;}

        .theme-picker {position:relative; min-width:320px;}
        .tp-btn {
          width:100%;
          display:flex; align-items:center; gap:10px;
          padding:8px 10px;
          border-radius:10px;
          border:none;
          cursor:pointer;
          background:#ffffff;
          color:#111;
        }
        .tp-btn:focus {outline:2px solid #295fee; outline-offset:2px;}
        .tp-swatch {
          width:18px; height:18px; border-radius:999px;
          background: var(--swatch, #999);
          box-shadow: inset 0 0 0 1px #0003;
          flex:0 0 auto;
        }
        .tp-swatch.light-edge {
          box-shadow: inset 0 0 0 1px #0003, 0 0 0 1px #cfd6e4;
        }
        .tp-label {flex:1; text-align:left;}
        .tp-caret {opacity:0.7; font-size:12px; padding-left:6px;}
        .tp-menu {
          position:absolute; left:0; right:0; top:calc(100% + 6px);
          background:#ffffff;
          border-radius:12px;
          box-shadow:0 12px 30px #0005;
          overflow:hidden;
          display:none;
          z-index:50;
        }
        .tp-menu.open {display:block;}
        .tp-item {
          width:100%;
          display:flex; align-items:center; gap:10px;
          padding:9px 10px;
          border:none;
          background:transparent;
          cursor:pointer;
          text-align:left;
          color:#111;
        }
        .tp-item:hover {background:#eef1f6;}
        .tp-item.active {background:#dfe7ff;}
        .tp-item .tp-swatch {box-shadow: inset 0 0 0 1px #0002;}

        /* --- Theme Overrides --- */
        body.theme-light {background:#f4f6fb;color:#111;}
        body.theme-light .container {background:#ffffff; box-shadow:0 0 18px #0002; color:#111;}
        body.theme-light .small {color:#555;}
        body.theme-light .btn-secondary {background:#666;}

        body.theme-ocean {background:#071925;color:#eef7ff;}
        body.theme-ocean .container {background:#0b2433;}
        body.theme-ocean .btn {background:#0077b6;}
        body.theme-ocean .btn-secondary {background:#1f3b4a;}

        body.theme-forest {background:#0b1a12;color:#ecfff2;}
        body.theme-forest .container {background:#102419;}
        body.theme-forest .btn {background:#2d6a4f;}
        body.theme-forest .btn-secondary {background:#2a3b33;}

        body.theme-violet {background:#140f1f;color:#f7f2ff;}
        body.theme-violet .container {background:#1d1630;}
        body.theme-violet .btn {background:#6d28d9;}
        body.theme-violet .btn-secondary {background:#3b2d55;}

        body.theme-amber {background:#1a140a;color:#fff6e6;}
        body.theme-amber .container {background:#231b0d;}
        body.theme-amber .btn {background:#b38b00;}
        body.theme-amber .btn-secondary {background:#3a3120;}
      </style>
    </head>
    <body class="theme-{{ theme }}">
      <div class="container">
        <div class="row" style="justify-content:space-between;">
          <h1>Einstellungen</h1>
          <a class="btn btn-secondary" href="{{ next_url }}">« Zurück</a>
        </div>

        {% if msg %}<div class="msg">{{ msg }}</div>{% endif %}

        <form method="post" class="row" style="margin-top:8px;">
          <input type="hidden" name="next" value="{{ next_url }}">
          <label for="theme">Theme:</label>

          <input type="hidden" id="theme" name="theme" value="{{ theme }}">

          <div class="theme-picker" id="themePicker">
            <button type="button" class="tp-btn" id="tpBtn" aria-haspopup="listbox" aria-expanded="false">
              <span class="tp-swatch" id="tpSwatch"></span>
              <span class="tp-label" id="tpLabel"></span>
              <span class="tp-caret">▼</span>
            </button>

            <div class="tp-menu" id="tpMenu" role="listbox" tabindex="-1">
              {% for key, label in themes.items() %}
                <button type="button"
                        class="tp-item {% if key == theme %}active{% endif %}"
                        data-value="{{ key }}"
                        data-color="{{ theme_swatch.get(key, '#999') }}"
                        role="option">
                  <span class="tp-swatch" style="--swatch: {{ theme_swatch.get(key, '#999') }}"></span>
                  <span class="tp-label">{{ label }}</span>
                </button>
              {% endfor %}
            </div>
          </div>

          <button class="btn" type="submit">Speichern</button>
        </form>

        <div class="small">
          Tipp: Du kannst jederzeit zurückwechseln. (Die Auswahl gilt pro Browser/Session.)
        </div>
      </div>

      <script>
        (function(){
          const picker = document.getElementById("themePicker");
          const btn = document.getElementById("tpBtn");
          const menu = document.getElementById("tpMenu");
          const hidden = document.getElementById("theme");
          const label = document.getElementById("tpLabel");
          const swatch = document.getElementById("tpSwatch");

          function isVeryLight(hex){
            if(!hex || hex[0] !== "#" || hex.length !== 7) return false;
            const r = parseInt(hex.slice(1,3), 16);
            const g = parseInt(hex.slice(3,5), 16);
            const b = parseInt(hex.slice(5,7), 16);
            const lum = (0.2126*r + 0.7152*g + 0.0722*b) / 255;
            return lum > 0.92;
          }

          function setCurrentFromValue(val){
            const item = menu.querySelector('.tp-item[data-value="' + val + '"]');
            if(!item) return;
            const txt = item.querySelector(".tp-label").textContent;
            const color = item.getAttribute("data-color") || "#999";
            label.textContent = txt;
            swatch.style.setProperty("--swatch", color);
            swatch.classList.toggle("light-edge", isVeryLight(color));

            menu.querySelectorAll(".tp-item").forEach(x => x.classList.remove("active"));
            item.classList.add("active");
            hidden.value = val;
          }

          function openMenu(){
            menu.classList.add("open");
            btn.setAttribute("aria-expanded", "true");
          }
          function closeMenu(){
            menu.classList.remove("open");
            btn.setAttribute("aria-expanded", "false");
          }

          btn.addEventListener("click", () => {
            if(menu.classList.contains("open")) closeMenu(); else openMenu();
          });

          menu.addEventListener("click", (e) => {
            const item = e.target.closest(".tp-item");
            if(!item) return;
            setCurrentFromValue(item.getAttribute("data-value"));
            closeMenu();
          });

          document.addEventListener("click", (e) => {
            if(!picker.contains(e.target)) closeMenu();
          });

          document.addEventListener("keydown", (e) => {
            if(e.key === "Escape") closeMenu();
          });

          setCurrentFromValue(hidden.value);
        })();
      </script>
    </body>
    </html>
    """, theme=theme, themes=THEMES, theme_swatch=THEME_SWATCH, msg=msg, next_url=next_url)


# ---------- DB Helpers ----------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_has_column(conn, table, column):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols


def init_tables():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            passwordhash TEXT NOT NULL,
            role TEXT NOT NULL,
            plate TEXT
        )
    """)

    # Erweiterte Userfelder
    if not table_has_column(conn, "users", "fullname"):
        try:
            cur.execute("ALTER TABLE users ADD COLUMN fullname TEXT")
        except sqlite3.OperationalError:
            pass
    if not table_has_column(conn, "users", "email"):
        try:
            cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass
    if not table_has_column(conn, "users", "phone"):
        try:
            cur.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        except sqlite3.OperationalError:
            pass

    cur.execute("""
        CREATE TABLE IF NOT EXISTS allowedplates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT UNIQUE NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS parkingevents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT NOT NULL,
            direction TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    if not table_has_column(conn, "parkingevents", "allowed"):
        try:
            cur.execute("ALTER TABLE parkingevents ADD COLUMN allowed INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass

    # Default Accounts
    cur.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1")
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (username, passwordhash, role, plate, fullname, email, phone) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin", None, "Admin", None, None),
        )

    cur.execute("SELECT 1 FROM users WHERE role='user' LIMIT 1")
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (username, passwordhash, role, plate, fullname, email, phone) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("user1", generate_password_hash("user123"), "user", "S-AB1234", "User One", None, None),
        )

    cur.execute("SELECT COUNT(*) AS c FROM allowedplates")
    if cur.fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO allowedplates (plate) VALUES (?)",
            [("S-AB1234",), ("S-XY9876",)]
        )

    conn.commit()
    conn.close()


def normalize_plate(p: str) -> str:
         """Konsistent mit main.py: entfernt Bindestriche, Leerzeichen etc."""
         return re.sub(r"[^A-Z0-9]", "", (p or "").strip().upper())

def get_allowed_flag(plate: str) -> int:
    plate = normalize_plate(plate)
    if not plate:
        return 0
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM allowedplates WHERE plate = ?", (plate,))
    allowed = 1 if cur.fetchone() else 0
    conn.close()
    return allowed


def log_event(plate: str, direction: str, allowed: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO parkingevents (plate, direction, timestamp, allowed)
        VALUES (?, ?, ?, ?)
    """, (normalize_plate(plate), direction, datetime.now().isoformat(timespec="seconds"), int(allowed)))
    conn.commit()
    conn.close()


def get_last_event(plate: str):
    plate = normalize_plate(plate)
    if not plate:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, plate, direction, timestamp, allowed
        FROM parkingevents
        WHERE plate = ?
        ORDER BY datetime(timestamp) DESC
        LIMIT 1
    """, (plate,))
    row = cur.fetchone()
    conn.close()
    return row


# ---------- Auth Helpers ----------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper


def _get_user_pw_hash(user_row):
    if user_row is None:
        return None
    try:
        keys = set(user_row.keys())
        for k in ("passwordhash", "password_hash", "password"):
            if k in keys:
                return user_row[k]
    except Exception:
        pass
    try:
        return user_row[2]
    except Exception:
        return None


# ---------- Admin Filter Helpers ----------

def _parse_date(s: str):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _resolve_preset(preset: str):
    today = date.today()
    if preset == "today":
        return today, today
    if preset == "last7":
        return today - timedelta(days=6), today
    if preset == "thisweek":
        start = _monday_of_week(today)
        end = start + timedelta(days=6)
        return start, end
    if preset == "lastweek":
        end_last = _monday_of_week(today) - timedelta(days=1)
        start_last = _monday_of_week(end_last)
        return start_last, end_last
    return None, None


def _date_to_str(d: date):
    return d.strftime("%Y-%m-%d")


# ---------- Routes ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        pw_hash = _get_user_pw_hash(user)
        if user and pw_hash and check_password_hash(pw_hash, password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["plate"] = user["plate"]
            return redirect(url_for("dashboard"))

        error = "Falscher Benutzername oder Passwort."

    theme = get_theme()

    return render_template_string("""
    <html>
    <head>
      <title>Login</title>
      <style>
        body {background:#181825;color:#fafcff;font-family:sans-serif;margin:0;}
        .box {max-width:380px;margin:80px auto;padding:25px;background:#202030;
              border-radius:16px;box-shadow:0 0 18px #0006;}
        input {width:100%;padding:8px;border-radius:6px;border:none;margin-top:4px;}
        button {margin-top:12px;width:100%;padding:9px;border-radius:7px;border:none;
                background:#295fee;color:#fff;font-size:1em;cursor:pointer;}
        .error {color:#ff7777;margin-top:8px;}
        .hint {margin-top:12px;font-size:0.9em;color:#aaa;}
        .btn-top {margin:0;width:auto;padding:7px 10px;background:#444;border-radius:8px;border:none;color:#fff;cursor:pointer;text-decoration:none;display:inline-block;}

        body.theme-light {background:#f4f6fb;color:#111;}
        body.theme-light .box {background:#ffffff; box-shadow:0 0 18px #0002; color:#111;}
        body.theme-light input {background:#fff; border:1px solid #cfd6e4; color:#111;}
        body.theme-light .hint {color:#555;}
        body.theme-light .error {color:#b00020;}

        body.theme-ocean {background:#071925;color:#eef7ff;}
        body.theme-ocean .box {background:#0b2433;}
        body.theme-ocean button {background:#0077b6;}
        body.theme-ocean .btn-top {background:#1f3b4a;}

        body.theme-forest {background:#0b1a12;color:#ecfff2;}
        body.theme-forest .box {background:#102419;}
        body.theme-forest button {background:#2d6a4f;}
        body.theme-forest .btn-top {background:#2a3b33;}

        body.theme-violet {background:#140f1f;color:#f7f2ff;}
        body.theme-violet .box {background:#1d1630;}
        body.theme-violet button {background:#6d28d9;}
        body.theme-violet .btn-top {background:#3b2d55;}

        body.theme-amber {background:#1a140a;color:#fff6e6;}
        body.theme-amber .box {background:#231b0d;}
        body.theme-amber button {background:#b38b00;}
        body.theme-amber .btn-top {background:#3a3120;}
      </style>
    </head>
    <body class="theme-{{ theme }}">
      <div class="box">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;">
          <h2 style="margin:0;">Smart Parking Login</h2>
          <a class="btn-top" href="{{ url_for('settings', next=request.path) }}">Einstellungen</a>
        </div>

        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="post">
          <p><label>Benutzername<br><input name="username" autocomplete="username"></label></p>
          <p><label>Passwort<br><input type="password" name="password" autocomplete="current-password"></label></p>
          <button type="submit">Einloggen</button>
        </form>
        <div class="hint">
          Beispiel-Admin: <b>admin / admin123</b><br>
          Beispiel-User: <b>user1 / user123</b> (Kennzeichen: S-AB1234)
        </div>
      </div>
    </body>
    </html>
    """, error=error, theme=theme)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def _load_events_for_view(role, plate, filter_plate, from_str, to_str, preset):
    from_date = None
    to_date = None
    if role == "admin":
        p_from, p_to = _resolve_preset(preset) if preset else (None, None)
        from_date = p_from or _parse_date(from_str)
        to_date = p_to or _parse_date(to_str)

    conn = get_db()
    cur = conn.cursor()

    if role == "admin":
        where = []
        params = []

        if filter_plate:
            where.append("plate = ?")
            params.append(filter_plate)

        if from_date and to_date:
            where.append("substr(timestamp,1,10) BETWEEN ? AND ?")
            params.extend([_date_to_str(from_date), _date_to_str(to_date)])
        elif from_date:
            where.append("substr(timestamp,1,10) >= ?")
            params.append(_date_to_str(from_date))
        elif to_date:
            where.append("substr(timestamp,1,10) <= ?")
            params.append(_date_to_str(to_date))

        sql = """
            SELECT id, plate, direction, timestamp, allowed
            FROM parkingevents
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY datetime(timestamp) DESC LIMIT 2000"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    else:
        cur.execute("""
            SELECT id, plate, direction, timestamp, allowed
            FROM parkingevents
            WHERE plate = ?
            ORDER BY datetime(timestamp) DESC
            LIMIT 500
        """, (normalize_plate(plate),))
        rows = cur.fetchall()

    conn.close()
    return rows


@app.route("/admin/events_fragment")
@admin_required
def admin_events_fragment():
    role = session.get("role")
    plate = session.get("plate")

    filter_plate = normalize_plate(request.args.get("plate", ""))
    from_str = (request.args.get("from", "") or "").strip()
    to_str = (request.args.get("to", "") or "").strip()
    preset = (request.args.get("preset", "") or "").strip()

    rows = _load_events_for_view(role, plate, filter_plate, from_str, to_str, preset)

    return render_template_string("""
      <table>
        <tr>
          <th><input type="checkbox" id="chkAll"></th>
          <th>Zeit</th>
          <th>Kennzeichen</th>
          <th>Richtung</th>
          <th>Berechtigt?</th>
          <th>Einzeln</th>
        </tr>

        {% for e in rows %}
          <tr>
            <td><input type="checkbox" name="delete_ids" value="{{ e.id }}"></td>
            <td>{{ e.timestamp }}</td>
            <td>{{ e.plate }}</td>
            <td class="{{ e.direction }}">{{ 'Zufahrt' if e.direction == 'in' else 'Ausfahrt' }}</td>
            <td class="{{ 'yes' if e.allowed == 1 else 'no' }}">
              {{ 'Ja' if e.allowed == 1 else 'Nein' }}
            </td>
            <td>
              <form class="inline" method="post" action="{{ url_for('admin_delete_event', event_id=e.id) }}"
                    onsubmit="return confirm('Eintrag wirklich löschen?');">
                <button class="btn btn-danger" type="submit">Löschen</button>
              </form>
            </td>
          </tr>
        {% endfor %}
      </table>
      <div class="info">Letzte Aktualisierung: {{ now }}</div>
    """, rows=rows, now=datetime.now().strftime("%d.%m.%Y %H:%M:%S"))


@app.route("/", endpoint="dashboard")
@login_required
def dashboard():
    role = session.get("role")
    plate = session.get("plate")
    msg = session.pop("msg", None)

    refresh_seconds = 3 if role != "admin" else None

    can_exit = False
    exit_hint = None
    if role != "admin":
        last = get_last_event(plate)
        if last is None:
            can_exit = False
            exit_hint = "Ausfahrt erst möglich, nachdem eine Zufahrt erkannt wurde."
        elif last["direction"] == "in":
            can_exit = True
        else:
            can_exit = False
            exit_hint = "Ausfahrt wurde bereits gemeldet. Warte auf die nächste Zufahrt."

    filter_plate = normalize_plate(request.args.get("plate", ""))
    from_str = (request.args.get("from", "") or "").strip()
    to_str = (request.args.get("to", "") or "").strip()
    preset = (request.args.get("preset", "") or "").strip()

    rows = _load_events_for_view(role, plate, filter_plate, from_str, to_str, preset)

    theme = get_theme()

    return render_template_string("""
    <html>
    <head>
      <title>Parking Dashboard</title>
      {% if refresh_seconds %}
        <meta http-equiv="refresh" content="{{ refresh_seconds }}">
      {% endif %}
      <style>
        body {background:#181825;color:#fafcff;font-family:sans-serif;margin:0;padding:0;}
        .container {max-width:1150px;margin:30px auto;padding:25px;background:#202030;
                    border-radius:16px;box-shadow:0 0 18px #0006;}
        h1 {text-align:center;margin-top:0;}
        table {width:100%;border-collapse:collapse;margin-top:15px;}
        th, td {padding:8px 10px;text-align:center;}
        th {background:#303060;}
        tr:nth-child(even) {background:#25253a;}
        .in {color:#6df56d;font-weight:bold;}
        .out {color:#ffcc66;font-weight:bold;}
        .yes {color:#6df56d;font-weight:bold;}
        .no {color:#ff6666;font-weight:bold;}
        .topbar {display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:12px;flex-wrap:wrap;}
        .btn {padding:7px 12px;border-radius:8px;border:none;cursor:pointer;
              background:#295fee;color:#fff;text-decoration:none;display:inline-block;}
        .btn-secondary {background:#444;}
        .btn-danger {background:#b33232;}
        .btn-warning {background:#b38b00;}
        .btn-disabled {background:#333;color:#999;cursor:not-allowed;}
        .info {font-size:0.9em;color:#aaa;margin-top:8px;text-align:right;}
        .msg {margin:8px 0;color:#ffcc66;}
        .hint {margin-top:6px;font-size:0.9em;color:#aaa;}
        form.inline {display:inline;}
        .filter {background:#1c1c2a;border-radius:12px;padding:12px;margin:10px 0;}
        .filter input {padding:6px;border-radius:6px;border:none;margin:4px 6px;}
        .filter label {font-size:0.9em;color:#ccc;margin-right:6px;}
        .small {font-size:0.85em;color:#aaa;}

        body.theme-light {background:#f4f6fb;color:#111;}
        body.theme-light .container {background:#ffffff; box-shadow:0 0 18px #0002; color:#111;}
        body.theme-light .filter {background:#eef1f6;}
        body.theme-light th {background:#d7deee; color:#111;}
        body.theme-light tr:nth-child(even) {background:#f4f6fb;}
        body.theme-light .info {color:#555;}
        body.theme-light .hint {color:#555;}
        body.theme-light .small {color:#666;}
        body.theme-light .filter label {color:#444;}
        body.theme-light .filter input {background:#fff; border:1px solid #cfd6e4; color:#111;}

        body.theme-ocean {background:#071925;color:#eef7ff;}
        body.theme-ocean .container {background:#0b2433;}
        body.theme-ocean .filter {background:#0d2b3d;}
        body.theme-ocean th {background:#103a52;}
        body.theme-ocean tr:nth-child(even) {background:#0c2a3a;}
        body.theme-ocean .btn {background:#0077b6;}
        body.theme-ocean .btn-secondary {background:#1f3b4a;}
        body.theme-ocean .btn-disabled {background:#133140;color:#8aa0aa;}

        body.theme-forest {background:#0b1a12;color:#ecfff2;}
        body.theme-forest .container {background:#102419;}
        body.theme-forest .filter {background:#0f2a1c;}
        body.theme-forest th {background:#123022;}
        body.theme-forest tr:nth-child(even) {background:#10261a;}
        body.theme-forest .btn {background:#2d6a4f;}
        body.theme-forest .btn-secondary {background:#2a3b33;}
        body.theme-forest .btn-disabled {background:#183028;color:#9fb8ab;}

        body.theme-violet {background:#140f1f;color:#f7f2ff;}
        body.theme-violet .container {background:#1d1630;}
        body.theme-violet .filter {background:#1a1430;}
        body.theme-violet th {background:#2a1f4a;}
        body.theme-violet tr:nth-child(even) {background:#1a1430;}
        body.theme-violet .btn {background:#6d28d9;}
        body.theme-violet .btn-secondary {background:#3b2d55;}
        body.theme-violet .btn-disabled {background:#2b2340;color:#b7a9d6;}

        body.theme-amber {background:#1a140a;color:#fff6e6;}
        body.theme-amber .container {background:#231b0d;}
        body.theme-amber .filter {background:#2a1f0f;}
        body.theme-amber th {background:#3b2c14;}
        body.theme-amber tr:nth-child(even) {background:#241c0d;}
        body.theme-amber .btn {background:#b38b00;}
        body.theme-amber .btn-secondary {background:#3a3120;}
        body.theme-amber .btn-disabled {background:#2b2416;color:#c6b894;}
      </style>
    </head>
    <body class="theme-{{ theme }}">
      <div class="container">
        <div class="topbar">
          <div>
            Angemeldet als: <b>{{ session.username }}</b> ({{ session.role }})
            {% if session.role != 'admin' and session.plate %}
              – Kennzeichen: <b>{{ session.plate }}</b>
            {% endif %}
          </div>
          <div>
            <a href="{{ url_for('settings', next=request.full_path) }}" class="btn btn-secondary">Einstellungen</a>

            {% if session.role == 'admin' %}
              <a href="{{ url_for('admin_center') }}" class="btn btn-secondary">Admin Center</a>

              <form class="inline" method="post" action="{{ url_for('admin_delete_all_events') }}"
                    onsubmit="return confirm('Wirklich ALLE History-Einträge löschen?');">
                <button class="btn btn-danger" type="submit">Alles löschen</button>
              </form>
            {% endif %}

            {% if session.role != 'admin' and session.plate %}
              <form class="inline" method="post" action="{{ url_for('user_exit') }}">
                <button class="btn {% if not can_exit %}btn-disabled{% endif %}" type="submit"
                        {% if not can_exit %}disabled{% endif %}>
                  Ausfahrt melden
                </button>
              </form>
            {% endif %}

            <a href="{{ url_for('logout') }}" class="btn btn-secondary">Logout</a>
          </div>
        </div>

        {% if msg %}<div class="msg">{{ msg }}</div>{% endif %}
        {% if session.role != 'admin' and exit_hint %}<div class="hint">{{ exit_hint }}</div>{% endif %}

        {% if session.role == 'admin' %}
          <div class="filter" id="adminFilter">
            <form method="get" action="{{ url_for('dashboard') }}">
              <label>Kennzeichen:</label>
              <input name="plate" value="{{ filter_plate }}" placeholder="z.B. S-AB1234">

              <label>Von:</label>
              <input type="date" name="from" value="{{ from_str }}">

              <label>Bis:</label>
              <input type="date" name="to" value="{{ to_str }}">

              <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px;">
                <button class="btn btn-secondary" type="submit">Filtern</button>

                <a class="btn btn-secondary" href="{{ url_for('dashboard', preset='today', plate=filter_plate) }}">Heute</a>
                <a class="btn btn-secondary" href="{{ url_for('dashboard', preset='last7', plate=filter_plate) }}">Letzte 7 Tage</a>
                <a class="btn btn-secondary" href="{{ url_for('dashboard', preset='thisweek', plate=filter_plate) }}">Diese Woche</a>
                <a class="btn btn-secondary" href="{{ url_for('dashboard', preset='lastweek', plate=filter_plate) }}">Letzte Woche</a>

                <span style="flex:1;"></span>
                <a class="btn btn-warning" href="{{ url_for('dashboard') }}">Reset</a>
              </div>
            </form>

            <div class="small" style="margin-top:10px;">
              Auto-Refresh läuft im Admin automatisch und pausiert, sobald du arbeitest (Tippen/Klicken/Scroll/Fokus).
            </div>
          </div>
        {% endif %}

        <h1>Park-Historie</h1>

        {% if session.role == 'admin' %}
          <form method="post" action="{{ url_for('admin_delete_selected_events') }}"
                onsubmit="return confirm('Ausgewählte Einträge wirklich löschen?');" id="bulkDeleteForm">
        {% endif %}

        <div id="eventsBlock">
          {% if session.role == 'admin' %}
            <table>
              <tr>
                <th><input type="checkbox" id="chkAllInit"></th>
                <th>Zeit</th>
                <th>Kennzeichen</th>
                <th>Richtung</th>
                <th>Berechtigt?</th>
                <th>Einzeln</th>
              </tr>

              {% for e in rows %}
                <tr>
                  <td><input type="checkbox" name="delete_ids" value="{{ e.id }}"></td>
                  <td>{{ e.timestamp }}</td>
                  <td>{{ e.plate }}</td>
                  <td class="{{ e.direction }}">{{ 'Zufahrt' if e.direction == 'in' else 'Ausfahrt' }}</td>
                  <td class="{{ 'yes' if e.allowed == 1 else 'no' }}">
                    {{ 'Ja' if e.allowed == 1 else 'Nein' }}
                  </td>
                  <td>
                    <form class="inline" method="post" action="{{ url_for('admin_delete_event', event_id=e.id) }}"
                          onsubmit="return confirm('Eintrag wirklich löschen?');">
                      <button class="btn btn-danger" type="submit">Löschen</button>
                    </form>
                  </td>
                </tr>
              {% endfor %}
            </table>
            <div class="info">Letzte Aktualisierung: {{ now }}</div>
          {% else %}
            <table>
              <tr>
                <th>Zeit</th>
                <th>Kennzeichen</th>
                <th>Richtung</th>
              </tr>
              {% for e in rows %}
                <tr>
                  <td>{{ e.timestamp }}</td>
                  <td>{{ e.plate }}</td>
                  <td class="{{ e.direction }}">{{ 'Zufahrt' if e.direction == 'in' else 'Ausfahrt' }}</td>
                </tr>
              {% endfor %}
            </table>
            <div class="info">Letzte Aktualisierung: {{ now }}</div>
          {% endif %}
        </div>

        {% if session.role == 'admin' %}
          <div style="margin-top:10px;">
            <button class="btn btn-danger" type="submit">Ausgewählte löschen</button>
            <span class="small">Markiere mehrere Zeilen über die Checkboxen.</span>
          </div>
          </form>
        {% endif %}
      </div>

      <script>
        function bindCheckAll(){
          const all = document.getElementById("chkAll") || document.getElementById("chkAllInit");
          if(!all) return;
          all.addEventListener("change", () => {
            document.querySelectorAll('input[name="delete_ids"]').forEach(cb => cb.checked = all.checked);
          });
        }
        bindCheckAll();

        (function(){
          const isAdmin = {{ 'true' if session.role == 'admin' else 'false' }};
          if(!isAdmin) return;

          const block = document.getElementById("eventsBlock");
          let pausedUntil = 0;
          let inFlight = false;

          function pause(ms){ pausedUntil = Date.now() + ms; }

          ["keydown","input","change","focusin","mousedown","wheel","touchstart"].forEach(ev => {
            document.addEventListener(ev, () => pause(6000), {passive:true});
          });

          document.addEventListener("visibilitychange", () => {
            if (document.hidden) pause(60000);
          });

          function currentQuery(){ return window.location.search || ""; }

          async function refreshBlock(){
            if(inFlight) return;
            if(Date.now() < pausedUntil) return;

            inFlight = true;
            try{
              const url = "/admin/events_fragment" + currentQuery();
              const r = await fetch(url, {cache: "no-store"});
              if(!r.ok) return;
              const html = await r.text();

              const checked = new Set(Array.from(document.querySelectorAll('input[name="delete_ids"]:checked')).map(x => x.value));
              block.innerHTML = html;
              document.querySelectorAll('input[name="delete_ids"]').forEach(cb => {
                if(checked.has(cb.value)) cb.checked = true;
              });
              bindCheckAll();
            } finally {
              inFlight = false;
            }
          }

          setInterval(refreshBlock, 3000);
        })();
      </script>
    </body>
    </html>
    """,
    rows=rows,
    now=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
    can_exit=can_exit,
    exit_hint=exit_hint,
    msg=msg,
    filter_plate=filter_plate,
    from_str=from_str,
    to_str=to_str,
    preset=preset,
    refresh_seconds=refresh_seconds,
    theme=theme
    )


@app.route("/user_exit", methods=["POST"])
@login_required
def user_exit():
    role = session.get("role")
    plate = session.get("plate")

    if role == "admin" or not plate:
        return redirect(url_for("dashboard"))

    last = get_last_event(plate)
    if last is None:
        session["msg"] = "Keine Ausfahrt möglich: Es wurde noch keine Zufahrt erkannt."
        return redirect(url_for("dashboard"))

    if last["direction"] != "in":
        session["msg"] = "Ausfahrt wurde bereits gemeldet. Warte auf die nächste Zufahrt."
        return redirect(url_for("dashboard"))

    allowed = get_allowed_flag(plate)
    log_event(plate, "out", allowed)
    session["msg"] = "Ausfahrt gespeichert."
    return redirect(url_for("dashboard"))


# ---------- Admin: Delete events ----------

@app.route("/admin/delete_event/<int:event_id>", methods=["POST"])
@admin_required
def admin_delete_event(event_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM parkingevents WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    session["msg"] = f"Eintrag {event_id} gelöscht."
    return redirect(url_for("dashboard"))


@app.route("/admin/delete_selected_events", methods=["POST"])
@admin_required
def admin_delete_selected_events():
    ids = request.form.getlist("delete_ids")
    ids = [int(x) for x in ids if str(x).isdigit()]

    if not ids:
        session["msg"] = "Keine Einträge ausgewählt."
        return redirect(url_for("dashboard"))

    placeholders = ",".join(["?"] * len(ids))
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM parkingevents WHERE id IN ({placeholders})", tuple(ids))
    conn.commit()
    conn.close()
    session["msg"] = f"{len(ids)} Einträge gelöscht."
    return redirect(url_for("dashboard"))


@app.route("/admin/delete_all_events", methods=["POST"])
@admin_required
def admin_delete_all_events():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM parkingevents")
    conn.commit()
    conn.close()
    session["msg"] = "Alle History-Einträge gelöscht."
    return redirect(url_for("dashboard"))


# ---------- Admin Center ----------

@app.route("/admin_center")
@admin_required
def admin_center():
    msg = session.pop("msg", None)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, plate FROM allowedplates ORDER BY plate")
    allowed_list = cur.fetchall()

    cur.execute("""
        SELECT pe.plate AS plate,
               MAX(pe.timestamp) AS lastseen,
               COUNT(*) AS totalevents,
               CASE WHEN ap.plate IS NULL THEN 0 ELSE 1 END AS isallowed
        FROM parkingevents pe
        LEFT JOIN allowedplates ap ON ap.plate = pe.plate
        GROUP BY pe.plate
        ORDER BY datetime(lastseen) DESC
        LIMIT 3000
    """)
    seen_plates = cur.fetchall()

    cur.execute("""
        SELECT id, username, role, plate,
               COALESCE(fullname,'') AS fullname,
               COALESCE(email,'') AS email,
               COALESCE(phone,'') AS phone
        FROM users
        ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END, username
    """)
    users = cur.fetchall()

    conn.close()

    theme = get_theme()

    return render_template_string("""
    <html>
    <head>
      <title>Admin Center</title>
      <style>
        body {background:#181825;color:#fafcff;font-family:sans-serif;margin:0;padding:0;}
        .container {max-width:1150px;margin:30px auto;padding:25px;background:#202030;
                    border-radius:16px;box-shadow:0 0 18px #0006;}
        h1 {margin:0 0 12px 0;}
        h2 {margin:22px 0 10px 0;}
        table {width:100%;border-collapse:collapse;margin-top:10px;}
        th, td {padding:8px 10px;text-align:center;}
        th {background:#303060;}
        tr:nth-child(even) {background:#25253a;}
        .topbar {display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;}
        .btn {padding:7px 12px;border-radius:8px;border:none;cursor:pointer;
              background:#295fee;color:#fff;text-decoration:none;display:inline-block;}
        .btn-secondary {background:#444;}
        .btn-danger {background:#b33232;}
        .btn-warning {background:#b38b00;}
        .yes {color:#6df56d;font-weight:bold;}
        .no {color:#ff6666;font-weight:bold;}
        .msg {margin:10px 0;color:#ffcc66;}
        input {padding:6px;border-radius:6px;border:none;}
        form.inline {display:inline;}
        .grid {display:grid;grid-template-columns:1fr;gap:14px;}
        .card {background:#1c1c2a;border-radius:12px;padding:14px;}
        .small {font-size:0.85em;color:#aaa;}

        body.theme-light {background:#f4f6fb;color:#111;}
        body.theme-light .container {background:#ffffff; box-shadow:0 0 18px #0002; color:#111;}
        body.theme-light .card {background:#eef1f6;}
        body.theme-light th {background:#d7deee; color:#111;}
        body.theme-light tr:nth-child(even) {background:#f4f6fb;}
        body.theme-light .small {color:#666;}
        body.theme-light input {background:#fff; border:1px solid #cfd6e4; color:#111;}

        body.theme-ocean {background:#071925;color:#eef7ff;}
        body.theme-ocean .container {background:#0b2433;}
        body.theme-ocean .card {background:#0d2b3d;}
        body.theme-ocean th {background:#103a52;}
        body.theme-ocean tr:nth-child(even) {background:#0c2a3a;}
        body.theme-ocean .btn {background:#0077b6;}
        body.theme-ocean .btn-secondary {background:#1f3b4a;}

        body.theme-forest {background:#0b1a12;color:#ecfff2;}
        body.theme-forest .container {background:#102419;}
        body.theme-forest .card {background:#0f2a1c;}
        body.theme-forest th {background:#123022;}
        body.theme-forest tr:nth-child(even) {background:#10261a;}
        body.theme-forest .btn {background:#2d6a4f;}
        body.theme-forest .btn-secondary {background:#2a3b33;}

        body.theme-violet {background:#140f1f;color:#f7f2ff;}
        body.theme-violet .container {background:#1d1630;}
        body.theme-violet .card {background:#1a1430;}
        body.theme-violet th {background:#2a1f4a;}
        body.theme-violet tr:nth-child(even) {background:#1a1430;}
        body.theme-violet .btn {background:#6d28d9;}
        body.theme-violet .btn-secondary {background:#3b2d55;}

        body.theme-amber {background:#1a140a;color:#fff6e6;}
        body.theme-amber .container {background:#231b0d;}
        body.theme-amber .card {background:#2a1f0f;}
        body.theme-amber th {background:#3b2c14;}
        body.theme-amber tr:nth-child(even) {background:#241c0d;}
        body.theme-amber .btn {background:#b38b00;}
        body.theme-amber .btn-secondary {background:#3a3120;}
      </style>
    </head>
    <body class="theme-{{ theme }}">
      <div class="container">
        <div class="topbar">
          <div>
            <h1>Admin Center</h1>
            <div class="small">Hier kannst du erlaubte Kennzeichen, erkannte Kennzeichen und User verwalten.</div>
          </div>
          <div>
            <a class="btn btn-secondary" href="{{ url_for('settings', next=request.full_path) }}">Einstellungen</a>
            <a class="btn btn-secondary" href="{{ url_for('dashboard') }}">« Zurück</a>
          </div>
        </div>

        {% if msg %}<div class="msg">{{ msg }}</div>{% endif %}

        <div class="grid">
          <div class="card">
            <h2>Erlaubte Kennzeichen bearbeiten</h2>
            <form method="post" action="{{ url_for('admin_allowed_add') }}">
              <input name="plate" placeholder="Neues Kennzeichen (z.B. S-AB1234)">
              <button class="btn" type="submit">Hinzufügen</button>
            </form>

            <table>
              <tr><th>ID</th><th>Kennzeichen</th><th>Ändern</th><th>Löschen</th></tr>
              {% for a in allowed_list %}
                <tr>
                  <td>{{ a.id }}</td>
                  <td>{{ a.plate }}</td>
                  <td>
                    <form class="inline" method="post" action="{{ url_for('admin_allowed_update', plate_id=a.id) }}">
                      <input name="plate" value="{{ a.plate }}" style="width:160px">
                      <button class="btn btn-warning" type="submit">Speichern</button>
                    </form>
                  </td>
                  <td>
                    <form class="inline" method="post" action="{{ url_for('admin_allowed_delete', plate_id=a.id) }}"
                          onsubmit="return confirm('Berechtigung wirklich entfernen?');">
                      <button class="btn btn-danger" type="submit">Entfernen</button>
                    </form>
                  </td>
                </tr>
              {% endfor %}
            </table>
          </div>

          <div class="card">
            <h2>Alle erkannten Kennzeichen (aus Events)</h2>
            <div class="small">Du kannst hier Kennzeichen direkt erlauben/entfernen (Berechtigung umschalten).</div>
            <table>
              <tr><th>Kennzeichen</th><th>Letztes Mal</th><th>Events</th><th>Berechtigt?</th><th>Aktion</th></tr>
              {% for p in seen_plates %}
                <tr>
                  <td>{{ p.plate }}</td>
                  <td>{{ p.lastseen }}</td>
                  <td>{{ p.totalevents }}</td>
                  <td class="{{ 'yes' if p.isallowed == 1 else 'no' }}">{{ 'Ja' if p.isallowed == 1 else 'Nein' }}</td>
                  <td>
                    <form class="inline" method="post" action="{{ url_for('admin_allowed_toggle') }}">
                      <input type="hidden" name="plate" value="{{ p.plate }}">
                      {% if p.isallowed == 1 %}
                        <button class="btn btn-danger" type="submit">Entfernen</button>
                      {% else %}
                        <button class="btn" type="submit">Erlauben</button>
                      {% endif %}
                    </form>
                  </td>
                </tr>
              {% endfor %}
            </table>
          </div>

          <div class="card">
            <h2>User verwalten (Name / Email / Telefon / Kennzeichen)</h2>
            <div class="small">Tipp: Deinen eigenen Admin-Account kannst du nicht auf user ändern (Lockout-Schutz).</div>

            <table>
              <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Role</th>
                <th>Name</th>
                <th>Email</th>
                <th>Telefon</th>
                <th>Kennzeichen</th>
                <th>Speichern</th>
              </tr>

              {% for u in users %}
                <tr>
                  <td>{{ u.id }}</td>
                  <td>{{ u.username }}</td>

                  <td>
                    <form class="inline" method="post" action="{{ url_for('admin_user_update', user_id=u.id) }}">
                      <select name="role">
                        <option value="admin" {% if u.role == 'admin' %}selected{% endif %}>admin</option>
                        <option value="user" {% if u.role == 'user' %}selected{% endif %}>user</option>
                      </select>
                  </td>

                  <td><input name="fullname" value="{{ u.fullname }}" placeholder="Vorname Nachname" style="width:160px"></td>
                  <td><input name="email" value="{{ u.email }}" placeholder="email@..." style="width:200px"></td>
                  <td><input name="phone" value="{{ u.phone }}" placeholder="+43..." style="width:140px"></td>
                  <td><input name="plate" value="{{ u.plate or '' }}" placeholder="z.B. S-AB1234" style="width:140px"></td>

                  <td>
                      <button class="btn btn-warning" type="submit">Speichern</button>
                    </form>
                  </td>
                </tr>
              {% endfor %}
            </table>
          </div>
        </div>
      </div>
    </body>
    </html>
    """, allowed_list=allowed_list, seen_plates=seen_plates, users=users, msg=msg, theme=theme)


@app.route("/admin/allowed_add", methods=["POST"])
@admin_required
def admin_allowed_add():
    plate = normalize_plate(request.form.get("plate", ""))
    if not plate:
        session["msg"] = "Bitte Kennzeichen eingeben."
        return redirect(url_for("admin_center"))

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO allowedplates (plate) VALUES (?)", (plate,))
        conn.commit()
        session["msg"] = f"{plate} hinzugefügt."
    except sqlite3.IntegrityError:
        session["msg"] = f"{plate} existiert bereits."
    finally:
        conn.close()
    return redirect(url_for("admin_center"))


@app.route("/admin/allowed_delete/<int:plate_id>", methods=["POST"])
@admin_required
def admin_allowed_delete(plate_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM allowedplates WHERE id = ?", (plate_id,))
    conn.commit()
    conn.close()
    session["msg"] = "Berechtigung entfernt."
    return redirect(url_for("admin_center"))


@app.route("/admin/allowed_update/<int:plate_id>", methods=["POST"])
@admin_required
def admin_allowed_update(plate_id: int):
    new_plate = normalize_plate(request.form.get("plate", ""))
    if not new_plate:
        session["msg"] = "Kennzeichen darf nicht leer sein."
        return redirect(url_for("admin_center"))

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE allowedplates SET plate = ? WHERE id = ?", (new_plate, plate_id))
        conn.commit()
        session["msg"] = "Kennzeichen aktualisiert."
    except sqlite3.IntegrityError:
        session["msg"] = f"{new_plate} existiert bereits."
    finally:
        conn.close()
    return redirect(url_for("admin_center"))


@app.route("/admin/allowed_toggle", methods=["POST"])
@admin_required
def admin_allowed_toggle():
    plate = normalize_plate(request.form.get("plate", ""))
    if not plate:
        session["msg"] = "Ungültiges Kennzeichen."
        return redirect(url_for("admin_center"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM allowedplates WHERE plate = ?", (plate,))
    exists = cur.fetchone() is not None

    if exists:
        cur.execute("DELETE FROM allowedplates WHERE plate = ?", (plate,))
        session["msg"] = f"{plate} entfernt (nicht mehr berechtigt)."
    else:
        try:
            cur.execute("INSERT INTO allowedplates (plate) VALUES (?)", (plate,))
            session["msg"] = f"{plate} erlaubt (berechtigt)."
        except sqlite3.IntegrityError:
            session["msg"] = f"{plate} existiert bereits."

    conn.commit()
    conn.close()
    return redirect(url_for("admin_center"))


@app.route("/admin/user_update/<int:user_id>", methods=["POST"])
@admin_required
def admin_user_update(user_id: int):
    new_role = (request.form.get("role") or "").strip()
    new_plate = normalize_plate(request.form.get("plate", ""))
    fullname = (request.form.get("fullname") or "").strip()
    email = (request.form.get("email") or "").strip()
    phone = (request.form.get("phone") or "").strip()

    if new_role not in ("admin", "user"):
        session["msg"] = "Ungültige Rolle."
        return redirect(url_for("admin_center"))

    if user_id == session.get("user_id") and new_role != "admin":
        session["msg"] = "Du kannst deinen eigenen Admin-Account nicht zu user ändern."
        return redirect(url_for("admin_center"))

    if new_role == "admin":
        plate_db = None
    else:
        if not new_plate:
            session["msg"] = "User müssen ein Kennzeichen haben."
            return redirect(url_for("admin_center"))
        plate_db = new_plate

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET role = ?, plate = ?, fullname = ?, email = ?, phone = ?
        WHERE id = ?
    """, (
        new_role,
        plate_db,
        fullname if fullname else None,
        email if email else None,
        phone if phone else None,
        user_id
    ))
    conn.commit()
    conn.close()

    # Wenn Admin sich selbst bearbeitet: Session aktualisieren
    if user_id == session.get("user_id"):
        session["role"] = new_role
        session["plate"] = plate_db

    session["msg"] = "User aktualisiert."
    return redirect(url_for("admin_center"))


def ensure_schema_compat():
    init_tables()


ensure_schema_compat()


if __name__ == "__main__":
    # Direktstart (wenn du NICHT run_all.py verwendest):
    app.run(host="0.0.0.0", port=5000, debug=False)
