from datetime import datetime

class ParkingState:
    def __init__(self):
        self.zufahrt_erlaubt = True
        self.letztes_kennzeichen = ""
        self.log = []  # Liste aus dicts: {"kennzeichen":..., "zeit":..., "erlaubt":...}

    def add_event(self, kennzeichen: str, erlaubt: bool):
        """Neues Ereignis (erkannte Nummerntafel) speichern."""
        self.letztes_kennzeichen = kennzeichen
        self.zufahrt_erlaubt = erlaubt
        self.log.append({
            "kennzeichen": kennzeichen,
            "zeit": datetime.now().strftime("%H:%M:%S"),
            "erlaubt": erlaubt
        })

# globaler Status, von Backend + Web-App gemeinsam genutzt
state = ParkingState()
