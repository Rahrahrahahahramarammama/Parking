import os
import sys
import time

import cv2
import easyocr
from ultralytics import YOLO
from Levenshtein import distance as levenshtein_distance

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import (
    create_tables, normalize_plate,
    is_allowed_plate, get_allowed_plates, log_event,
)
from backend.camera_module import Camera
from backend.display_control import show_access, setup_leds, cleanup_leds

# Modell suchen
_HERE      = os.path.abspath(os.path.dirname(__file__))
_ROOT      = os.path.abspath(os.path.join(_HERE, ".."))
MODEL_PATH = next(
    (p for p in [
        os.path.join(_ROOT, "license_plate_detector.pt"),
        os.path.join(_ROOT, "licenseplatedetector.pt"),
        os.path.join(_HERE, "license_plate_detector.pt"),
    ] if os.path.exists(p)), None,
)
if MODEL_PATH is None:
    raise FileNotFoundError("Kein YOLO-Modell (.pt) gefunden.")

LOOP_DELAY_SECONDS     = 1
DUPLICATE_COOLDOWN_SEC = 8

reader = easyocr.Reader(["en"], gpu=False)
model  = YOLO(MODEL_PATH)
_last_logged: dict = {}


# Bildverarbeitung

def crop_eu_blue_strip(img, ratio: float = 0.15):
    h, w = img.shape[:2]
    return img[:, int(w * ratio):] if w > 0 else img

def scale_plate(img, target_height: int = 180):
    h, w = img.shape[:2]
    if h <= 0 or w <= 0:
        return img
    scale = target_height / h
    return cv2.resize(img, (max(1, int(w * scale)), target_height),
                      interpolation=cv2.INTER_CUBIC)

def preprocess_for_ocr(img):
    # gibt IMMER ein 1-Kanal-Graustufenbild zurueck
    gray     = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    clahe    = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
    _, binarized = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binarized

def ocr_easyocr_only(image) -> str:
    # FIX: preprocess_for_ocr gibt Graustufen (1 Kanal) zurueck ->
    #      COLOR_BGR2RGB wuerde crashen. Jetzt wird korrekt konvertiert.
    if len(image.shape) == 2:
        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = reader.readtext(rgb)
    text = "".join(res[1] for res in results if len(res) >= 3 and res[2] > 0.3)
    return normalize_plate(text)[:10]

def plausible_plate(text: str) -> bool:
    return 5 <= len(text) <= 10

def trim_ghost_endings(text: str) -> str:
    while len(text) > 6 and text[-1] in "IZ1Q":
        text = text[:-1]
    return text

def find_similar_plate(plate: str, max_distance: int = 1):
    # FIX: nur allowedplates – verhindert falsche Korrekturen
    for known in get_allowed_plates():
        if levenshtein_distance(plate, known) <= max_distance:
            return known
    return None

def _should_log(plate: str) -> bool:
    now  = time.time()
    last = _last_logged.get(plate, 0)
    if now - last < DUPLICATE_COOLDOWN_SEC:
        return False
    # FIX: altes Dict bereinigen um Speicherleck zu verhindern
    cutoff = now - DUPLICATE_COOLDOWN_SEC * 10
    for k in [k for k, v in _last_logged.items() if v < cutoff]:
        del _last_logged[k]
    _last_logged[plate] = now
    return True


# Haupterkennung

def recognize_license_plate(img, show_debug: bool = False):
    results = model(img, verbose=False)
    if not results or results[0].boxes is None or len(results[0].boxes) == 0:
        if show_debug:
            print("Keine Kennzeichen erkannt.")
        show_access("unknown")
        return None

    img_h, img_w = img.shape[:2]

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            x1, x2 = max(0, x1), min(img_w, x2)
            y1, y2 = max(0, y1), min(img_h, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            plate_img = img[y1:y2, x1:x2]
            if plate_img.size == 0:
                continue

            if show_debug:
                cv2.imshow("YOLO ROI", plate_img); cv2.waitKey(1)

            processed   = preprocess_for_ocr(scale_plate(crop_eu_blue_strip(plate_img)))

            if show_debug:
                cv2.imshow("Vorverarbeitet", processed); cv2.waitKey(1)

            text        = ocr_easyocr_only(processed)
            text        = trim_ghost_endings(text)
            final_plate = text

            if not plausible_plate(final_plate):
                if show_debug and text:
                    print(f"Nicht plausibel: {text!r}")
                show_access("denied" if text else "unknown", text or None)
                continue

            similar = find_similar_plate(final_plate)
            if similar:
                if show_debug and similar != final_plate:
                    print(f"Korrektur: {final_plate!r} -> {similar!r}")
                final_plate = similar

            # FIX: echte DB-Pruefung statt zugelassen = True
            allowed = is_allowed_plate(final_plate)

            print("=" * 40)
            print(f"Kennzeichen : {final_plate}")
            print(f"Berechtigt  : {'Ja' if allowed else 'Nein'}")
            print("=" * 40)

            if _should_log(final_plate):
                log_event(final_plate, "in", allowed)
                print(f"Gespeichert : {final_plate}")
            else:
                print(f"Duplikat uebersprungen : {final_plate}")

            show_access("allowed" if allowed else "denied", final_plate)
            return final_plate

    show_access("unknown")
    return None


if __name__ == "__main__":
    create_tables()
    setup_leds()
    camera = Camera(cam_id=0)
    try:
        while True:
            frame = camera.get_frame()
            if frame is None:
                print("Kein Kamera-Frame."); break
            recognize_license_plate(frame, show_debug=True)
            cv2.imshow("Live Kamera", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            time.sleep(LOOP_DELAY_SECONDS)
    finally:
        cleanup_leds(); camera.release(); cv2.destroyAllWindows()