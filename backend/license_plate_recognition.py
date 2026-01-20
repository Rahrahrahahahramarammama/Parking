import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cv2
from ultralytics import YOLO
import easyocr
import re
from Levenshtein import distance as levenshtein_distance

from backend.database import (
    auto_add_user_license_plate,
    get_all_license_plates,
    create_tables
)
from backend.camera_module import Camera
from backend.display_control import show_access, setup_leds, cleanup_leds
from backend.status import state  # gemeinsamer Status

# ANPASSEN: Wo liegt dein .pt-File?
# Variante A: Datei liegt in Parking/
model_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'license_plate_detector.pt')
)
# Variante B, falls in backend/:   model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'license_plate_detector.pt'))

reader = easyocr.Reader(['en'], gpu=False)
model = YOLO(model_path)


def crop_eu_blue_strip(plate_img, ratio=0.15):
    h, w = plate_img.shape[:2]
    crop_x = int(w * ratio)
    return plate_img[:, crop_x:]


def scale_plate(img, target_height=180):
    h, w = img.shape[:2]
    scale = target_height / h
    return cv2.resize(img, (int(w * scale), target_height), interpolation=cv2.INTER_CUBIC)


def preprocess_for_ocr(plate_img):
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
    _, binarized = cv2.threshold(
        denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    return binarized


def ocr_easyocr_only(image):
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = reader.readtext(rgb)
    text = ""
    for res in results:
        if res[2] > 0.3:
            text += res[1]
    text = re.sub(r'[^A-Z0-9]', '', text.strip().upper())[:10]
    return text


def plausible_plate(text):
    return 5 <= len(text) <= 10


def trim_ghost_endings(text):
    while len(text) > 6 and text[-1] in "IZ1Q":
        text = text[:-1]
    return text


def find_similar_plate_in_db(plate, max_distance=1):
    plates = get_all_license_plates()
    for known_plate in plates:
        dist = levenshtein_distance(plate, known_plate)
        if dist <= max_distance:
            return known_plate
    return None


def recognize_license_plate(img, show_debug=False):
    results = model(img)
    if len(results) == 0 or results[0].boxes is None or len(results[0].boxes) == 0:
        if show_debug:
            print("Keine Kennzeichen erkannt.")
            show_access("unknown")
        return

    for idx, result in enumerate(results):
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            plate_img = img[y1:y2, x1:x2]
            if show_debug:
                cv2.imshow('YOLO ROI', plate_img)
                cv2.waitKey(1)

            plate_img_no_blue = crop_eu_blue_strip(plate_img)
            plate_img_scaled = scale_plate(plate_img_no_blue)
            plate_img_processed = preprocess_for_ocr(plate_img_scaled)
            if show_debug:
                cv2.imshow('Vorverarbeitet', plate_img_processed)
                cv2.waitKey(1)

            text = ocr_easyocr_only(plate_img_processed)
            text = trim_ghost_endings(text)
            final_plate = text

            if plausible_plate(final_plate):
                similar_plate = find_similar_plate_in_db(final_plate, max_distance=1)
                if similar_plate:
                    if show_debug:
                        print(f"Ähnliches Kennzeichen gefunden, übernehme: {similar_plate}")
                    final_plate = similar_plate

                print("=" * 40)
                print(f"Final erkanntes Kennzeichen: {final_plate}")
                print("=" * 40)
                auto_add_user_license_plate(final_plate)

                zugelassen = True  # vorerst alles OK

                # wichtig: Event für Website
                state.add_event(final_plate, zugelassen)
                print("LOG-EVENT:", final_plate, zugelassen, "Einträge:", len(state.log))

                show_access("allowed" if zugelassen else "denied", final_plate)
            else:
                if show_debug:
                    print("Kein plausibles Kennzeichen erkannt.")
                show_access("denied", text)

                if text:
                    state.add_event(text, False)
                    print("LOG-EVENT (unplausibel):", text, False, "Einträge:", len(state.log))

    if show_debug:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    create_tables()
    setup_leds()
    camera = Camera(cam_id=0)   # hier explizit 0 setzen
    try:
        while True:
            frame = camera.get_frame()
            if frame is None:
                print("Kamera-Frame konnte nicht gelesen werden")
                break
            recognize_license_plate(frame, show_debug=True)
            cv2.imshow("Live Kamera", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            time.sleep(1)
    finally:
        cleanup_leds()
        camera.release()
        cv2.destroyAllWindows()

