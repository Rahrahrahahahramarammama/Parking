import cv2
from ultralytics import YOLO
import easyocr
import matplotlib.pyplot as plt
import os
import re

model = YOLO('license_plate_detector.pt')
reader = easyocr.Reader(['en', 'de'])

def show_image_matplotlib(img, title="Image"):
    if len(img.shape) == 2:
        plt.imshow(img, cmap='gray')
    else:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        plt.imshow(img_rgb)
    plt.title(title)
    plt.axis('off')
    plt.show()

def preprocess_plate_img(plate_img):
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    eq = cv2.equalizeHist(gray)
    blur = cv2.GaussianBlur(eq, (3,3), 0)
    sharp = cv2.addWeighted(eq, 1.5, blur, -0.5, 0)
    _, binary = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary

def plausible_plate(text):
    # mind. 2 Zeichen, ignoriert "IRL", "PL", "LV", nur Buchstaben und Zahlen erlaubt, muss Zahl enthalten
    text = text.strip().replace(" ", "")
    if len(text) < 4:
        return False
    if text.upper() in ["IRL", "PL", "LV", "EU", "D"]:
        return False
    if not re.search(r'\d', text):
        return False
    if not re.match(r'^[A-Z0-9\-]+$', text, re.I):
        return False
    return True

def recognize_license_plate_with_yolo_easyocr(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"Bild nicht gefunden: {image_path}")
        return

    results = model(img)
    if len(results) == 0 or results[0].boxes is None or len(results[0].boxes) == 0:
        print("Keine Kennzeichen erkannt.")
        return

    candidates = []
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            plate_img = img[y1:y2, x1:x2]
            roi = preprocess_plate_img(plate_img)
            show_image_matplotlib(roi, title="Bearbeitetes Kennzeichen")
            ocr_results = reader.readtext(roi, detail=1)
            for bbox, text, prob in ocr_results:
                text_cleaned = text.replace(" ", "").replace("—", "-")
                if prob > 0.3 and plausible_plate(text_cleaned):
                    candidates.append((text_cleaned, prob))

    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        only_texts = [c[0] for c in candidates]
        # gebe alle plausiblen OCR-Treffer aus, zusammengefügt
        result_string = " | ".join(only_texts)
        print("="*40)
        print(f"Erkanntes Kennzeichen: {result_string}")
        print("="*40)
    else:
        print("- Es wurde kein Kennzeichentext erkannt.")

if __name__ == "__main__":
    folder = r"C:\Dataset_Parking\images"
    files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    for f in files:
        print(f"\nAnalysiere: {f}")
        recognize_license_plate_with_yolo_easyocr(os.path.join(folder, f))
