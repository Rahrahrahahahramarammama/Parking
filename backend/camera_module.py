import cv2

class Camera:
    def __init__(self, cam_id=0, width=640, height=480):
        self.cam_id = cam_id
        self.cap = cv2.VideoCapture(self.cam_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def get_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            print("Fehler beim Kamera-Frame!")
            return None
        return frame

    def release(self):
        self.cap.release()
        cv2.destroyAllWindows()

# Beispiel-Nutzung:
if __name__ == "__main__":
    camera = Camera()
    while True:
        frame = camera.get_frame()
        if frame is None:
            break
        cv2.imshow("Kamera Modul Vorschau", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    camera.release()

