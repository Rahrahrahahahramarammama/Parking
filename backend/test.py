import cv2

cap = cv2.VideoCapture(0)
print ("opened:", cap.isOpened())
ret, frame = cap.read()
print("Frame:", ret)
