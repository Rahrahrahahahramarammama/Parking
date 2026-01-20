import cv2
import time


class Camera:
    def __init__(self, cam_id=0, width=1280, height=720, fps=30):
        # cam_id = 0, weil dein Test gezeigt hat, dass Index 0 funktioniert
        self.cam_id = cam_id
        
        self.cap = cv2.VideoCapture(self.cam_id)
                
        if not self.cap.isOpened():
            raise RuntimeError(f"kann kamera /dev/video0 nicht öffnen")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        
        time.sleep(0.3)
        for _ in range(5):
            self.cap.read()

    def get_frame(self):
        ret, frame = self.cap.read()
        if not ret or frame is None:
            print("Fehler beim Kamera-Frame!")
            return None
        return frame

    def release(self):
        if self.cap is not None:
            self.cap.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    # einfacher Kameratest
    camera = Camera(cam_id=0)
    while True:
        frame = camera.get_frame()
        if frame is None:
            break
        cv2.imshow("Kamera Modul Vorschau", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    camera.release()
