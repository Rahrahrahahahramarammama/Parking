import os
import sys
from flask import Flask, render_template_string
from datetime import datetime

# Pfade setzen
BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # .../Parking/frontend
ROOT_DIR = os.path.dirname(BASE_DIR)                    # .../Parking
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from backend.status import state  # gemeinsamer Status

app = Flask(__name__)


@app.route("/")
def index():
    return render_template_string("""
    <html>
    <head>
      <title>Erkannte Kennzeichen</title>
      <meta http-equiv="refresh" content="1">
      <style>
        body {background:#181825;color:#fafcff;font-family:sans-serif;margin:0;padding:0;}
        .container {max-width:700px;margin:30px auto;padding:25px;background:#202030;border-radius:16px;}
        h1 {text-align:center;margin-top:0;}
        table {width:100%;border-collapse:collapse;margin-top:15px;}
        th, td {padding:8px 10px;text-align:center;}
        th {background:#303060;}
        tr:nth-child(even) {background:#25253a;}
        .ok {color:#6df56d;font-weight:bold;}
        .bad {color:#ff6666;font-weight:bold;}
        .small {font-size:0.9em;color:#aaa;margin-top:10px;text-align:right;}
      </style>
    </head>
    <body>
      <div class="container">
        <h1>Erkannte Kennzeichen</h1>
        <table>
          <tr><th>Zeit</th><th>Kennzeichen</th><th>Status</th></tr>
          {% for e in log %}
            <tr>
              <td>{{ e.zeit }}</td>
              <td>{{ e.kennzeichen }}</td>
              <td class="{{ 'ok' if e.erlaubt else 'bad' }}">
                {{ 'OK' if e.erlaubt else 'NICHT OK' }}
              </td>
            </tr>
          {% endfor %}
        </table>
        <div class="small">
          Letzte Aktualisierung: {{ now }}
        </div>
      </div>
    </body>
    </html>
    """,
    log=state.log[::-1],  # neueste zuerst
    now=datetime.now().strftime("%d.%m.%Y %H:%M:%S"))


if __name__ == "__main__":
    app.run(debug=True)
