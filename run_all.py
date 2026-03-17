import os
import sys
import time
import threading
import subprocess
import atexit
import webbrowser
import traceback
import socket

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))  # .../Parking
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

for p in (ROOT_DIR, BACKEND_DIR, FRONTEND_DIR):
    if p not in sys.path:
        sys.path.append(p)

from frontend.web_app import app


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_flask():
    # Wichtig: 0.0.0.0 = erreichbar für andere Geräte im WLAN
    app.run(debug=False, host="0.0.0.0", port=5000, use_reloader=False)


def start_recognition_background():
    """
    Läuft im Hintergrund-Thread, damit Flask nie abstürzt/blocked,
    selbst wenn ultralytics/torch lange lädt.
    """
    try:
        import cv2
        import license_plate_recognition as lpr

        lpr.create_tables()
        lpr.setup_leds()
        camera = lpr.Camera()

        try:
            while True:
                frame = camera.get_frame()
                if frame is None:
                    print("Kamera-Frame konnte nicht gelesen werden")
                    break

                lpr.recognize_license_plate(frame, show_debug=True)

                cv2.imshow("Live Kamera", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

                time.sleep(0.01)
        finally:
            try:
                lpr.cleanup_leds()
            except Exception:
                pass
            try:
                camera.release()
            except Exception:
                pass
            cv2.destroyAllWindows()

    except Exception:
        print("ERROR: Recognition-Thread ist abgestürzt, Flask läuft weiter.")
        traceback.print_exc()


def start_caddy():
    caddyfile = os.path.join(ROOT_DIR, "Caddyfile")
    if not os.path.exists(caddyfile):
        return None
    try:
        return subprocess.Popen(["caddy", "run", "--config", caddyfile], cwd=ROOT_DIR)
    except FileNotFoundError:
        print("Caddy nicht gefunden (nicht im PATH). Starte nur Flask auf Port 5000.")
        return None


def main():
    lan_ip = get_lan_ip()

    # 1) Flask starten
    t_flask = threading.Thread(target=start_flask, daemon=True)
    t_flask.start()

    # 2) Caddy optional (Port 80 -> Proxy auf 5000)
    caddy_proc = start_caddy()

    def cleanup():
        if caddy_proc and caddy_proc.poll() is None:
            try:
                caddy_proc.terminate()
            except Exception:
                pass

    atexit.register(cleanup)

    # 3) Browser öffnen (lokal)
    time.sleep(1.2)
    if caddy_proc:
        webbrowser.open("http://localhost/login")
        print(f"LAN-URL für andere Geräte: http://{lan_ip}/login")
    else:
        webbrowser.open("http://127.0.0.1:5000/login")
        print(f"LAN-URL für andere Geräte: http://{lan_ip}:5000/login")

    # 4) Recognition im Hintergrund starten
    t_rec = threading.Thread(target=start_recognition_background, daemon=True)
    t_rec.start()

    # 5) Main-Thread am Leben halten
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
