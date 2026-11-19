"""Behavioural analysis with OpenCV Haar cascades (face presence, eye alignment, posture)."""
import base64
import cv2
import numpy as np

_face = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_eye = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")


def analyze(data_url: str) -> dict:
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1])
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
        h, w = img.shape
        faces = _face.detectMultiScale(img, 1.2, 5, minSize=(80, 80))
        if len(faces) == 0:
            return {"face": False, "eyes": False, "posture": "No face"}
        x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        eyes = _eye.detectMultiScale(img[y:y + fh // 2, x:x + fw])
        cx, cy = (x + fw / 2) / w, (y + fh / 2) / h
        centered = 0.3 < cx < 0.7 and cy < 0.65
        return {"face": True, "eyes": len(eyes) >= 2, "posture": "Good" if centered else "Off-center"}
    except Exception:
        return {"face": False, "eyes": False, "posture": "Unknown"}


def summarize(s: dict) -> dict:
    n = max(s.get("n", 0), 1)
    pct = lambda k: round(100 * s.get(k, 0) / n)
    return {"frames": s.get("n", 0), "face_presence": pct("face"),
            "eye_contact": pct("eyes"), "good_posture": pct("good")}
