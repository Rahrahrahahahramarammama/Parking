import time

# Falls auf Raspberry Pi: Importiere RPi.GPIO
try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False
    print("GPIO Modul nicht gefunden – nur Simulation möglich.")

# Pin-Zuweisungen ändern je nach Wiring!
GREEN_LED_PIN = 21
RED_LED_PIN = 20

def setup_leds():
    if HAS_GPIO:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GREEN_LED_PIN, GPIO.OUT)
        GPIO.setup(RED_LED_PIN, GPIO.OUT)
        GPIO.output(GREEN_LED_PIN, GPIO.LOW)
        GPIO.output(RED_LED_PIN, GPIO.LOW)

def show_access(status, plate=None):
    """
    Zeigt Status und steuert LEDs.
    status: "allowed", "denied", "unknown"
    plate: optional (Kennzeichen)
    """
    if status == "allowed":
        msg = "Eintritt erlaubt"
        set_leds(green=True, red=False)
    elif status == "denied":
        msg = "Eintritt verweigert"
        set_leds(green=False, red=True)
    else:
        msg = "Unbekanntes Fahrzeug"
        set_leds(green=False, red=False)

    if plate:
        print(f"[{plate}] - {msg}")
    else:
        print(msg)
    show_lcd(msg)  # Ausgabe auch auf LCD/Display

def set_leds(green: bool, red: bool):
    if HAS_GPIO:
        GPIO.output(GREEN_LED_PIN, GPIO.HIGH if green else GPIO.LOW)
        GPIO.output(RED_LED_PIN, GPIO.HIGH if red else GPIO.LOW)
    else:
        print(f"[LED SIMULIERT] Grün: {green}, Rot: {red}")

def show_lcd(msg):
    # lcd.message(msg)  # Erweiterbar für echtes LCD
    print(f"[LCD] {msg}")

def cleanup_leds():
    if HAS_GPIO:
        GPIO.output(GREEN_LED_PIN, GPIO.LOW)
        GPIO.output(RED_LED_PIN, GPIO.LOW)
        GPIO.cleanup()

# Beispiel/Test
if __name__ == "__main__":
    setup_leds()
    show_access("allowed", "AB123CD")
    time.sleep(2)
    show_access("denied", "XY987ZY")
    time.sleep(2)
    show_access("unknown", "PK999PK")
    cleanup_leds()
