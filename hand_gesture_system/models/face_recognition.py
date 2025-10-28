import cv2
import numpy as np
import os
from datetime import datetime
import threading

class SimpleFaceRecognizer:
    def __init__(self, threshold=70):
        self.threshold = threshold
        self.known_faces = {}
    
    def add_face(self, face_id, face_image):
        if face_id not in self.known_faces:
            self.known_faces[face_id] = []
        self.known_faces[face_id].append(face_image)
    
    def recognize_face(self, test_image):
        best_match = None
        best_score = float('inf')
        
        gray_test = cv2.cvtColor(test_image, cv2.COLOR_BGR2GRAY) if len(test_image.shape) == 3 else test_image
        gray_test = cv2.resize(gray_test, (200, 200))
        
        for face_id, training_images in self.known_faces.items():
            for train_img in training_images:
                train_resized = cv2.resize(train_img, (200, 200))
                score = np.mean((gray_test.astype(float) - train_resized.astype(float)) ** 2)
                
                if score < best_score:
                    best_score = score
                    best_match = face_id
        
        confidence = max(0, 100 - (best_score / 100))
        
        if confidence > self.threshold:
            return best_match, confidence
        else:
            return None, confidence

class FaceRecognitionSystem:
    def __init__(self, data_dir="data/faces"):
        self.data_dir = data_dir
        self.models_dir = "models"
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Correct way to load cascade classifier
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.face_recognizer = SimpleFaceRecognizer(threshold=60)
        
        self.known_faces = {}
        self.is_capturing = False
        self.stop_capture = False
        self.live_camera_active = False
        self.camera_thread = None

    def load_known_faces(self, users):
        self.known_faces = {}
        for user in users:
            emp_id = user["emp_id"]
            self.known_faces[emp_id] = {
                "name": user.get("name", emp_id),
                "_id": user.get("_id")
            }
            
            img_path = os.path.join(self.data_dir, f"{emp_id}.jpg")
            if os.path.exists(img_path):
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    img = cv2.resize(img, (200, 200))
                    self.face_recognizer.add_face(emp_id, img)

    def register_face(self, emp_id, name, callback):
        self.stop_capture = False
        captured_faces = []
        samples_needed = 30
        
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(False, "Cannot access camera")
            return

        while len(captured_faces) < samples_needed and not self.stop_capture:
            ret, frame = cam.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, f"Samples: {len(captured_faces)}/{samples_needed}", 
                          (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            cv2.imshow("Registration - Press Q to cancel", frame)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                self.stop_capture = True
                break
            
            if len(faces) == 1:
                x, y, w, h = faces[0]
                face_roi = gray[y:y+h, x:x+w]
                face_roi = cv2.resize(face_roi, (200, 200))
                captured_faces.append(face_roi)
                
                if len(captured_faces) == 1:
                    image_path = os.path.join(self.data_dir, f"{emp_id}.jpg")
                    cv2.imwrite(image_path, face_roi)
                    self.face_recognizer.add_face(emp_id, face_roi)
                
                callback(False, f"Captured {len(captured_faces)}/{samples_needed}")

        cam.release()
        cv2.destroyAllWindows()

        if self.stop_capture:
            callback(False, "Registration cancelled")
            return

        callback(True, f"Face registered for {name} ({emp_id})")

    def start_live_recognition(self, callback):
        if len(self.known_faces) == 0:
            callback(None, "No registered users found")
            return False

        self.live_camera_active = True
        self.camera_thread = threading.Thread(target=self._live_recognition_loop, args=(callback,))
        self.camera_thread.daemon = True
        self.camera_thread.start()
        return True

    def stop_live_recognition(self):
        self.live_camera_active = False
        if self.camera_thread and self.camera_thread.is_alive():
            self.camera_thread.join(timeout=2)

    def _live_recognition_loop(self, callback):
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(None, "Cannot access camera")
            return

        recognition_frames = {}
        required_frames = 5
        last_recognition_time = datetime.now()
        recognition_cooldown = 5

        try:
            while self.live_camera_active:
                ret, frame = cam.read()
                if not ret:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
                
                current_time = datetime.now()
                time_since_last_recognition = (current_time - last_recognition_time).total_seconds()
                
                for (x, y, w, h) in faces:
                    face_roi = gray[y:y+h, x:x+w]
                    emp_id, confidence = self.face_recognizer.recognize_face(face_roi)
                    
                    if emp_id and time_since_last_recognition >= recognition_cooldown:
                        name = self.known_faces[emp_id]["name"]
                        
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        cv2.putText(frame, f"{name}", (x, y-30), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        cv2.putText(frame, f"Confidence: {int(confidence)}%", (x, y-10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
                        recognition_frames[emp_id] = recognition_frames.get(emp_id, 0) + 1
                        
                        if recognition_frames[emp_id] >= required_frames:
                            callback(emp_id, f"Face detected: {name}")
                            last_recognition_time = current_time
                            recognition_frames.clear()
                    else:
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                        cv2.putText(frame, "Unknown", (x, y-10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                cv2.imshow("Live Face Recognition - Press Q to stop", frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        except Exception as e:
            callback(None, f"Error in live recognition: {e}")
        finally:
            cam.release()
            cv2.destroyAllWindows()
            self.live_camera_active = False

    def recognize_face(self, callback):
        if len(self.known_faces) == 0:
            callback(None, "No registered users found")
            return

        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(None, "Cannot access camera")
            return

        recognition_frames = {}
        required_frames = 5
        self.stop_capture = False

        try:
            while not self.stop_capture:
                ret, frame = cam.read()
                if not ret:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
                
                for (x, y, w, h) in faces:
                    face_roi = gray[y:y+h, x:x+w]
                    emp_id, confidence = self.face_recognizer.recognize_face(face_roi)
                    
                    if emp_id:
                        name = self.known_faces[emp_id]["name"]
                        
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        cv2.putText(frame, f"{name}", (x, y-30), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        cv2.putText(frame, f"Confidence: {int(confidence)}%", (x, y-10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
                        recognition_frames[emp_id] = recognition_frames.get(emp_id, 0) + 1
                        
                        if recognition_frames[emp_id] >= required_frames:
                            cam.release()
                            cv2.destroyAllWindows()
                            callback(emp_id, f"Login successful: {name}")
                            return
                    else:
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                        cv2.putText(frame, "Unknown", (x, y-10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        recognition_frames.clear()

                cv2.imshow("Face Recognition - Press Q to cancel", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_capture = True
                    break

        except Exception as e:
            callback(None, f"Error: {e}")
        finally:
            cam.release()
            cv2.destroyAllWindows()
        
        callback(None, "No registered face recognized")