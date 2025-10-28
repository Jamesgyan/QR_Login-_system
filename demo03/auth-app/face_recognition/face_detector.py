# face_recognition/face_detector.py
import cv2
import face_recognition
import numpy as np

class FaceDetector:
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_ids = []
    
    def detect_faces(self, image):
        """Detect faces in image"""
        try:
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_image)
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            return face_locations, face_encodings
        except Exception as e:
            print(f"Face detection error: {e}")
            return [], []
    
    def extract_features(self, face_image):
        """Extract face embeddings"""
        try:
            rgb_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
            encodings = face_recognition.face_encodings(rgb_image)
            return encodings[0] if encodings else None
        except Exception as e:
            print(f"Feature extraction error: {e}")
            return None
    
    def match_face(self, face_encoding, threshold=0.6):
        """Match face against known faces"""
        if len(self.known_face_encodings) == 0:
            return None
        
        try:
            face_distances = face_recognition.face_distance(
                self.known_face_encodings, face_encoding
            )
            best_match_index = np.argmin(face_distances)
            
            if face_distances[best_match_index] < threshold:
                return self.known_face_ids[best_match_index]
            return None
        except Exception as e:
            print(f"Face matching error: {e}")
            return None
    
    def register_face(self, user_id, face_images):
        """Register face for a user"""
        encodings = []
        for image in face_images:
            encoding = self.extract_features(image)
            if encoding is not None:
                encodings.append(encoding)
        
        if encodings:
            avg_encoding = np.mean(encodings, axis=0)
            self.known_face_encodings.append(avg_encoding)
            self.known_face_ids.append(user_id)
            return avg_encoding
        return None