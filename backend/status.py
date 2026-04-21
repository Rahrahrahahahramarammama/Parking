from datetime import datetime
from collections import deque

MAX_LOG_ENTRIES = 500   # FIX: Ring-Buffer – verhindert unbegrenztes RAM-Wachstum


class ParkingState:
    def __init__(self):
        self.zufahrt_erlaubt     = True
        self.letztes_kennzeichen = ""
        self.log: deque = deque(maxlen=MAX_LOG_ENTRIES)

    def add_event(self, kennzeichen: str, erlaubt: bool) -> None:
        self.letztes_kennzeichen = kennzeichen
        self.zufahrt_erlaubt     = erlaubt
        self.log.append({
            "kennzeichen": kennzeichen,
            "zeit":        datetime.now().strftime("%H:%M:%S"),
            "erlaubt":     erlaubt,
        })

    @property
    def log_list(self) -> list:
        """Log als normale Liste, neueste Eintraege zuerst."""
        return list(reversed(self.log))


# Globaler Status – von Backend + Web-App gemeinsam genutzt
state = ParkingState()