import os
import sys
from flask import Flask, render_template_string, request, redirect, send_from_directory
from datetime import datetime

# ----- Projektpfad richtig setzen -----
# BASE_DIR = .../Parking/frontend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ROOT_DIR = .../Parking
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from backend.status import state  # gemeinsamer Status

app = Flask(__name__)

# einfache Whitelist – kannst du später mit eurer DB verknüpfen
erlaubte_kennzeichen = {"ABC1234", "XYZ9876"}


def led_html():
    color = "#46fa5a" if state.zufahrt_erlaubt else "#fa4646"
    text = "●"
    return f'<span style="font-size:60px; color:{color};text-shadow:0 0 10px {color}">{text}</span>'


@app.route('/parkinglogo.jpg')
def logo_image():
    return send_from_directory(BASE_DIR, 'parkinglogo.jpg')


@app.route('/')
def index():
    return render_template_string("""
    <html>
    <head>
      <title>Smart Parking System</title>
      <style>
        body {background:#181825;color:#fafcff;font-family:sans-serif;padding:0;margin:0;}
        .container {max-width:650px;margin:30px auto;padding:35px;background:rgba(30,30,40,0.95);border-radius:18px;box-shadow:0 0 20px #0005;}
        h1 {text-align:center;}
        .headerimg {display:block;margin:0 auto 20px;border-radius:16px;box-shadow:0 0 18px #00f7;}
        table {width:100%;margin-top:10px;background:#222428;border-radius:7px;overflow:hidden;}
        th,td {padding:10px;text-align:center;}
        th {background:#212351;}
        tr:nth-child(even) {background:#212134;}
        .state {font-weight:bold;font-size:1.3em;letter-spacing:1px;padding:10px;border-radius:10px; background: #212351;}
        .led {margin:3px;}
        .btn, button {background:#295fee;color:#fff;padding:11px 28px;border:none;border-radius:7px;cursor:pointer;font-size:1em;}
        .btn {margin-right:7px;}
        input {padding:8px;border-radius:5px;border:none;width:210px;}
        .admin-link {display:inline-block;background:#4077ff;padding:7px 18px;border-radius:6px;margin:14px 0;color:#fff;text-decoration:none;}
        .msg {color:#79f679;font-weight:bold;}
        .back {color:#bbb;}
        .section-title {border-bottom:2px solid #295fee;display:inline-block;padding-bottom:2px;margin-bottom:11px;}
        .info {font-size:0.95em; color:#aaa; margin-top:14px;}
      </style>
    </head>
    <body>
      <div class="container">
        <img class="headerimg" src="/parkinglogo.jpg" width="350" height="150">
        <h1>Smart Parking System</h1>
        <div class="state">
          Status: {{ 'Zufahrt gewährt' if zufahrt_erlaubt else 'Zufahrt gesperrt' }}
          <span class="led">{{ led|safe }}</span>
        </div>
        <p>Letztes erkanntes Kennzeichen: <b>{{ letztes }}</b></p>
        <form method="post" action="/toggle">
           <button type="submit">{{ 'Zufahrt sperren' if zufahrt_erlaubt else 'Zufahrt erlauben' }}</button>
        </form>
        <hr>
        <form method="post" action="/simulate_recognize">
            <label>
                Neues Kennzeichen simulieren:
                <input name="kennzeichen" required>
            </label>
            <button type="submit" class="btn">Erkennen</button>
        </form>
        <hr>
        <div class="section-title">Log – erkannte Kennzeichen:</div>
        <table border="0">
        <tr><th>Kennzeichen</th><th>Zeit</th><th>Status</th></tr>
        {% for entry in log %}
           <tr>
             <td>{{ entry.kennzeichen }}</td>
             <td>{{ entry.zeit }}</td>
             <td>{{ 'Erlaubt' if entry.erlaubt else 'Gesperrt' }}</td>
           </tr>
        {% endfor %}
        </table>
        <hr>
        <a class="admin-link" href="/admin">Adminbereich</a>
        <div class="info">Systemzeit: {{ time }}</div>
      </div>
    </body>
    </html>
    """,
    zufahrt_erlaubt=state.zufahrt_erlaubt,
    led=led_html(),
    letztes=state.letztes_kennzeichen,
    log=state.log[::-1],
    time=datetime.now().strftime("%d.%m.%Y %H:%M:%S"))


@app.route('/toggle', methods=['POST'])
def toggle():
    state.zufahrt_erlaubt = not state.zufahrt_erlaubt
    return redirect('/')


@app.route('/simulate_recognize', methods=['POST'])
def simulate_recognize():
    kenn = request.form['kennzeichen'].strip().upper()
    erlaubt = kenn in erlaubte_kennzeichen and state.zufahrt_erlaubt
    state.add_event(kenn, erlaubt)
    return redirect('/')


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    global erlaubte_kennzeichen
    msg = ""
    if request.method == 'POST':
        neu = request.form.get('neu', "").strip().upper()
        if neu:
            erlaubte_kennzeichen.add(neu)
            msg = f"{neu} hinzugefügt."
        entfernen = request.form.get('entfernen')
        if entfernen:
            erlaubte_kennzeichen.discard(entfernen)
            msg = f"{entfernen} entfernt."
    return render_template_string("""
    <html><head><title>Adminbereich</title><style>
        body {background:#1c1c24;color:#fff;font-family:sans-serif;}
        .container {max-width:460px;margin:24px auto;padding:19px;background:#202045;border-radius:18px;box-shadow:0 0 12px #000;}
        .btn, button {background:#295fee;color:#fff;padding:8px 18px;border:none;border-radius:7px;}
        input {padding:6px;border-radius:5px;border:none;}
        ul {list-style:none;padding-left:0;}
        li {margin:5px 0;}
        a {color:#8bc4ff;}
        .msg {color:#69e869;font-weight:bold;}
    </style></head><body>
    <div class="container">
    <h2>Adminbereich</h2>
    <h3>Erlaubte Kennzeichen</h3>
    <ul>
      {% for k in erlaubt %}
        <li>{{ k }}
          <form style="display:inline" method="post">
             <input type="hidden" name="entfernen" value="{{ k }}">
             <button type="submit">Entfernen</button>
          </form>
        </li>
      {% endfor %}
    </ul>
    <form method="post">
        <label>Neues Kennzeichen hinzufügen: <input name="neu"></label>
        <button type="submit" class="btn">Hinzufügen</button>
    </form>
    <p class="msg">{{ msg }}</p>
    <a class="back" href="/">Zurück</a>
    </div>
    </body></html>
    """, erlaubt=sorted(erlaubte_kennzeichen), msg=msg)


if __name__ == "__main__":
    app.run(debug=True)
