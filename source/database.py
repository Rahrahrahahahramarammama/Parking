import sqlite3

DB_NAME = 'smartpark.db'

def create_tables():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Users table: alle Kennzeichen im System + Passwort
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            license_plate TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    # Reservations table (optional für Park-Reservationen)
    c.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY (license_plate) REFERENCES users (license_plate)
        )
    ''')
    # Parking spots table (optional für belegte Plätze)
    c.execute('''
        CREATE TABLE IF NOT EXISTS parking_spots (
            spot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate TEXT,
            occupied INTEGER DEFAULT 0,
            FOREIGN KEY (license_plate) REFERENCES users (license_plate)
        )
    ''')
    conn.commit()
    conn.close()

def add_user(license_plate, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('INSERT OR IGNORE INTO users (license_plate, password) VALUES (?, ?)', (license_plate, password))
        conn.commit()
        if c.rowcount == 0:
            print(f"Kennzeichen {license_plate} war bereits im System.")
        else:
            print(f"Kennzeichen {license_plate} wurde registriert.")
    except sqlite3.Error as e:
        print("Fehler beim Speichern:", e)
    finally:
        conn.close()

def auto_add_user_license_plate(plate, default_password="autogen"):
    add_user(plate, default_password)

def check_user(license_plate):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE license_plate = ?', (license_plate,))
    user = c.fetchone()
    conn.close()
    return user is not None

def get_all_license_plates():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT license_plate FROM users')
    plates = [row[0] for row in c.fetchall()]
    conn.close()
    return plates

# Optional: Weitere Funktionen für Reservationen und Parkplätze etc. möglich

if __name__ == "__main__":
    create_tables()
    print("DB-Struktur angelegt oder geprüft. Beispiel-Platteneintrag:")
    add_user("TEST123", "autogen")
    print("Alle gespeicherten Kennzeichen:", get_all_license_plates())
