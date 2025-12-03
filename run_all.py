import threading
import time
import os
import sys
import cv2

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))          # .../Parking
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
for p in (ROOT_DIR, BACKEND_DIR):
    if p not in sys.path:
        sys.path.append(p)

from frontend.web_app import app
import license_plate_recognition as lpr   # aus backend/


def start_flask():
    app.run(debug=False, host="0.0.0.0", port=5000)


def start_recognition():
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
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            time.sleep(1)
    finally:
        lpr.cleanup_leds()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    t_flask = threading.Thread(target=start_flask, daemon=True)
    t_flask.start()

    import webbrowser
    time.sleep(1)
    webbrowser.open("http://localhost:5000")

    start_recognition()
