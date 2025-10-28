import cv2
import mediapipe as mp
import numpy as np

class HandDetector:
    def __init__(self, max_hands=1, detection_confidence=0.7, tracking_confidence=0.7):
        self.max_hands = max_hands
        self.detection_confidence = detection_confidence
        self.tracking_confidence = tracking_confidence

        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=self.max_hands,
            min_detection_confidence=self.detection_confidence,
            min_tracking_confidence=self.tracking_confidence
        )
        self.mp_drawing = mp.solutions.drawing_utils
        print("✅ HandDetector initialized with MediaPipe")

    def detect_hands(self, frame):
        """Detect hands and return landmarks + image"""
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(image_rgb)

        hand_landmarks = []
        if results.multi_hand_landmarks:
            for landmarks in results.multi_hand_landmarks:
                hand_landmarks.append(landmarks)
                self.mp_drawing.draw_landmarks(frame, landmarks, self.mp_hands.HAND_CONNECTIONS)

        return hand_landmarks, frame  # Always return a list + image

    def extract_landmarks(self, hand_landmarks):
        """Extract normalized landmark coordinates"""
        # ✅ FIX: handle if tuple is passed accidentally
        if isinstance(hand_landmarks, tuple):
            if len(hand_landmarks) > 0:
                hand_landmarks = hand_landmarks[0]  # take first detected hand
            else:
                return []

        # ✅ Also handle empty input safely
        if not hasattr(hand_landmarks, "landmark"):
            return []

        landmarks = []
        for lm in hand_landmarks.landmark:
            landmarks.append([lm.x, lm.y, lm.z])
        return np.array(landmarks).flatten()

    def get_hand_box(self, hand_landmarks, frame_shape):
        """Get bounding box from landmarks"""
        h, w, _ = frame_shape
        landmarks = np.array([[lm.x * w, lm.y * h] for lm in hand_landmarks.landmark])
        x_min, y_min = np.min(landmarks, axis=0)
        x_max, y_max = np.max(landmarks, axis=0)
        return int(x_min), int(y_min), int(x_max), int(y_max)
