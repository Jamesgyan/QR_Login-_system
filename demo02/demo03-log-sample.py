import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from PIL import Image, ImageTk
import cv2
import numpy as np
from pymongo import MongoClient
from datetime import datetime
import os
import threading
import pandas as pd
from bson import ObjectId
import mediapipe as mp

# -------------------- Database Manager --------------------
class DatabaseManager:
    def __init__(self, connection_string="mongodb://localhost:27017/"):
        self.connection_string = connection_string
        self.client = None
        self.db = None
        self.users_collection = None
        self.attendance_collection = None
        self.connected = False
        
    def connect(self):
        try:
            self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=5000)
            self.client.server_info()
            self.db = self.client["gesture_login_db"]
            self.users_collection = self.db["users"]
            self.attendance_collection = self.db["attendance"]
            self.connected = True
            return True
        except Exception as e:
            self.connected = False
            self.error = str(e)
            return False
    
    def get_all_users(self):
        return list(self.users_collection.find({"face_registered": True}))
    
    def get_user(self, emp_id):
        return self.users_collection.find_one({"emp_id": emp_id})
    
    def create_user(self, emp_id, name):
        return self.users_collection.update_one(
            {"emp_id": emp_id},
            {"$set": {
                "name": name,
                "face_registered": True,
                "registered_on": datetime.now()
            }},
            upsert=True
        )
    
    def delete_user(self, emp_id):
        result = self.users_collection.delete_one({"emp_id": emp_id})
        return result.deleted_count > 0
    
    def log_attendance(self, emp_id, name, action, method="face"):
        log_data = {
            "emp_id": emp_id,
            "name": name,
            "action": action,
            "timestamp": datetime.now()
        }
        
        if method == "gesture":
            log_data["gesture"] = True
        elif method == "manual":
            log_data["manual"] = True
        elif method == "auto":
            log_data["auto"] = True
            
        return self.attendance_collection.insert_one(log_data)
    
    def get_attendance_records(self, emp_id=None, limit=100):
        query = {"emp_id": emp_id} if emp_id else {}
        return list(self.attendance_collection.find(query).sort("timestamp", -1).limit(limit))
    
    def get_logged_in_users(self):
        recent_logins = self.attendance_collection.aggregate([
            {"$match": {"action": "LOGIN"}},
            {"$sort": {"timestamp": -1}},
            {"$group": {"_id": "$emp_id", "latest_login": {"$first": "$timestamp"}}}
        ])
        
        logged_in_users = set()
        for login in recent_logins:
            latest_logout = self.attendance_collection.find_one(
                {"emp_id": login["_id"], "action": "LOGOUT", "timestamp": {"$gt": login["latest_login"]}},
                sort=[("timestamp", -1)]
            )
            if not latest_logout:
                logged_in_users.add(login["_id"])
                
        return logged_in_users
    
    def generate_employee_id(self):
        last_user = self.users_collection.find_one({}, sort=[("_id", -1)])
        if last_user and "emp_id" in last_user:
            last_id = last_user["emp_id"]
            if last_id.startswith("ALLY"):
                try:
                    num = int(last_id[4:]) + 1
                    return f"ALLY{num:04d}"
                except:
                    pass
        return "ALLY0001"
    
    def close(self):
        if self.client:
            self.client.close()

# -------------------- Face Recognition System --------------------
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
        samples_needed = 100
        
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

# -------------------- Enhanced Gesture Detector with MediaPipe --------------------
class GestureDetector:
    def __init__(self):
        self.stop_capture = False
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
    def detect_wave_gesture(self, callback):
        """Detect wave gesture using hand landmarks"""
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(False, "Cannot access camera")
            return

        self.stop_capture = False
        wave_count = 0
        wave_threshold = 8
        prev_hand_x = None
        
        try:
            while not self.stop_capture:
                ret, frame = cam.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.hands.process(rgb_frame)
                
                current_hand_x = None
                
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        # Draw hand landmarks
                        self.mp_drawing.draw_landmarks(
                            frame,
                            hand_landmarks,
                            self.mp_hands.HAND_CONNECTIONS,
                            self.mp_drawing_styles.get_default_hand_landmarks_style(),
                            self.mp_drawing_styles.get_default_hand_connections_style()
                        )
                        
                        # Get wrist position (landmark 0)
                        wrist = hand_landmarks.landmark[0]
                        h, w, _ = frame.shape
                        current_hand_x = int(wrist.x * w)
                        
                        # Check for open hand (wave gesture)
                        if self.is_hand_open(hand_landmarks):
                            cv2.putText(frame, "OPEN HAND", (50, 50), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                # Detect horizontal movement for wave
                if prev_hand_x is not None and current_hand_x is not None:
                    movement = abs(current_hand_x - prev_hand_x)
                    if movement > 20:  # Significant horizontal movement
                        wave_count += 1
                        cv2.putText(frame, f"Wave detected: {wave_count}/{wave_threshold}", 
                                  (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    else:
                        wave_count = max(0, wave_count - 1)
                
                prev_hand_x = current_hand_x
                
                cv2.putText(frame, "Wave your hand side to side to login", (50, 150), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, "Press Q to cancel", (50, 180), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                cv2.imshow("Wave Gesture Login - Hand Tracking", frame)
                
                if wave_count >= wave_threshold:
                    cam.release()
                    cv2.destroyAllWindows()
                    callback(True, "Wave gesture detected! Starting face recognition...")
                    return
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_capture = True
                    break

        except Exception as e:
            callback(False, f"Error: {e}")
        finally:
            cam.release()
            cv2.destroyAllWindows()
        
        callback(False, "Wave gesture not detected")

    def detect_fist_gesture(self, callback):
        """Detect fist gesture using hand landmarks"""
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(False, "Cannot access camera")
            return

        self.stop_capture = False
        fist_frames = 0
        fist_threshold = 15
        
        try:
            while not self.stop_capture:
                ret, frame = cam.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.hands.process(rgb_frame)
                
                fist_detected = False
                
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        # Draw hand landmarks
                        self.mp_drawing.draw_landmarks(
                            frame,
                            hand_landmarks,
                            self.mp_hands.HAND_CONNECTIONS,
                            self.mp_drawing_styles.get_default_hand_landmarks_style(),
                            self.mp_drawing_styles.get_default_hand_connections_style()
                        )
                        
                        # Check for fist
                        if self.is_fist(hand_landmarks):
                            fist_detected = True
                            cv2.putText(frame, "FIST DETECTED", (50, 50), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                
                if fist_detected:
                    fist_frames += 1
                    cv2.putText(frame, f"Fist frames: {fist_frames}/{fist_threshold}", 
                              (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                else:
                    fist_frames = max(0, fist_frames - 1)
                
                cv2.putText(frame, "Make a fist to logout", (50, 150), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, "Press Q to cancel", (50, 180), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                cv2.imshow("Fist Gesture Logout - Hand Tracking", frame)
                
                if fist_frames >= fist_threshold:
                    cam.release()
                    cv2.destroyAllWindows()
                    callback(True, "Fist gesture detected! Logging out...")
                    return
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_capture = True
                    break

        except Exception as e:
            callback(False, f"Error: {e}")
        finally:
            cam.release()
            cv2.destroyAllWindows()
        
        callback(False, "Fist gesture not detected")

    def detect_victory_gesture(self, callback):
        """Detect victory gesture (peace sign)"""
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(False, "Cannot access camera")
            return

        self.stop_capture = False
        victory_frames = 0
        victory_threshold = 10
        
        try:
            while not self.stop_capture:
                ret, frame = cam.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.hands.process(rgb_frame)
                
                victory_detected = False
                
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        # Draw hand landmarks
                        self.mp_drawing.draw_landmarks(
                            frame,
                            hand_landmarks,
                            self.mp_hands.HAND_CONNECTIONS,
                            self.mp_drawing_styles.get_default_hand_landmarks_style(),
                            self.mp_drawing_styles.get_default_hand_connections_style()
                        )
                        
                        # Check for victory gesture
                        if self.is_victory_gesture(hand_landmarks):
                            victory_detected = True
                            cv2.putText(frame, "VICTORY GESTURE", (50, 50), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                
                if victory_detected:
                    victory_frames += 1
                    cv2.putText(frame, f"Victory: {victory_frames}/{victory_threshold}", 
                              (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                else:
                    victory_frames = max(0, victory_frames - 1)
                
                cv2.putText(frame, "Show victory sign (peace) for quick login", (50, 150), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, "Press Q to cancel", (50, 180), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                cv2.imshow("Victory Gesture Login - Hand Tracking", frame)
                
                if victory_frames >= victory_threshold:
                    cam.release()
                    cv2.destroyAllWindows()
                    callback(True, "Victory gesture detected! Starting face recognition...")
                    return
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_capture = True
                    break

        except Exception as e:
            callback(False, f"Error: {e}")
        finally:
            cam.release()
            cv2.destroyAllWindows()
        
        callback(False, "Victory gesture not detected")

    def is_hand_open(self, hand_landmarks):
        """Check if hand is open (fingers extended)"""
        # Get tips of fingers (index 4, 8, 12, 16, 20)
        tips = [4, 8, 12, 16, 20]
        mcp_joints = [2, 5, 9, 13, 17]  # Middle joints
        
        open_fingers = 0
        
        # Thumb (special case)
        thumb_tip = hand_landmarks.landmark[4]
        thumb_mcp = hand_landmarks.landmark[2]
        if thumb_tip.x > thumb_mcp.x:  # For right hand
            open_fingers += 1
        
        # Other fingers
        for tip_idx, mcp_idx in zip(tips[1:], mcp_joints[1:]):
            tip = hand_landmarks.landmark[tip_idx]
            mcp = hand_landmarks.landmark[mcp_idx]
            if tip.y < mcp.y:  # Finger is extended
                open_fingers += 1
        
        return open_fingers >= 4  # At least 4 fingers open

    def is_fist(self, hand_landmarks):
        """Check if hand is making a fist"""
        tips = [8, 12, 16, 20]  # Finger tips (excluding thumb)
        pip_joints = [6, 10, 14, 18]  # Middle joints
        
        closed_fingers = 0
        
        for tip_idx, pip_idx in zip(tips, pip_joints):
            tip = hand_landmarks.landmark[tip_idx]
            pip = hand_landmarks.landmark[pip_idx]
            if tip.y > pip.y:  # Finger is closed
                closed_fingers += 1
        
        return closed_fingers >= 3  # At least 3 fingers closed

    def is_victory_gesture(self, hand_landmarks):
        """Check for victory gesture (index and middle finger extended, others closed)"""
        # Tips: 8 (index), 12 (middle), 16 (ring), 20 (pinky)
        # PIP joints: 6 (index), 10 (middle), 14 (ring), 18 (pinky)
        
        index_tip = hand_landmarks.landmark[8]
        index_pip = hand_landmarks.landmark[6]
        middle_tip = hand_landmarks.landmark[12]
        middle_pip = hand_landmarks.landmark[10]
        ring_tip = hand_landmarks.landmark[16]
        ring_pip = hand_landmarks.landmark[14]
        pinky_tip = hand_landmarks.landmark[20]
        pinky_pip = hand_landmarks.landmark[18]
        
        # Index and middle fingers extended
        index_extended = index_tip.y < index_pip.y
        middle_extended = middle_tip.y < middle_pip.y
        
        # Ring and pinky fingers closed
        ring_closed = ring_tip.y > ring_pip.y
        pinky_closed = pinky_tip.y > pinky_pip.y
        
        return index_extended and middle_extended and ring_closed and pinky_closed

    def start_hand_tracking_demo(self, callback):
        """Start a demo showing hand tracking with all gestures"""
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(False, "Cannot access camera")
            return

        self.stop_capture = False
        
        try:
            while not self.stop_capture:
                ret, frame = cam.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.hands.process(rgb_frame)
                
                gesture_text = "No hand detected"
                gesture_color = (255, 255, 255)
                
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        # Draw hand landmarks
                        self.mp_drawing.draw_landmarks(
                            frame,
                            hand_landmarks,
                            self.mp_hands.HAND_CONNECTIONS,
                            self.mp_drawing_styles.get_default_hand_landmarks_style(),
                            self.mp_drawing_styles.get_default_hand_connections_style()
                        )
                        
                        # Detect different gestures
                        if self.is_victory_gesture(hand_landmarks):
                            gesture_text = "VICTORY GESTURE - Quick Login"
                            gesture_color = (255, 255, 0)  # Yellow
                        elif self.is_fist(hand_landmarks):
                            gesture_text = "FIST - Logout"
                            gesture_color = (0, 0, 255)  # Red
                        elif self.is_hand_open(hand_landmarks):
                            gesture_text = "OPEN HAND - Ready for Wave"
                            gesture_color = (0, 255, 0)  # Green
                        else:
                            gesture_text = "HAND DETECTED"
                            gesture_color = (255, 255, 255)  # White
                
                # Display gesture information
                cv2.putText(frame, gesture_text, (50, 50), 
                          cv2.FONT_HERSHEY_SIMPLEX, 1, gesture_color, 2)
                cv2.putText(frame, "Try: Wave, Fist, or Victory gestures", (50, 100), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, "Press Q to close demo", (50, 130), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                cv2.imshow("Hand Gesture Tracking Demo", frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_capture = True
                    break

        except Exception as e:
            callback(False, f"Error: {e}")
        finally:
            cam.release()
            cv2.destroyAllWindows()
        
        callback(True, "Hand tracking demo completed")

# -------------------- Main Application --------------------
class HandGestureLoginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Employee Hand Gesture Login System")
        self.root.geometry("1400x800")
        self.root.configure(bg="#2c3e50")
        
        # Initialize systems
        self.db_manager = DatabaseManager()
        if not self.db_manager.connect():
            messagebox.showerror("Database Error", "MongoDB connection failed!")
            
        self.face_system = FaceRecognitionSystem()
        users = self.db_manager.get_all_users()
        self.face_system.load_known_faces(users)
        
        self.gesture_detector = GestureDetector()
        
        self.current_user = None
        self.log_visible = True
        self.live_camera_running = False
        
        self.setup_ui()
        self.update_status()
        self.refresh_user_list()
        self.start_live_camera_feed()

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def setup_ui(self):
        # Create main frame with scrollbar
        self.main_frame = tk.Frame(self.root, bg="#2c3e50")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self.main_frame, bg="#2c3e50", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#2c3e50")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel to canvas
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.scrollable_frame.bind("<MouseWheel>", self._on_mousewheel)
        
        # Header
        header = tk.Frame(self.scrollable_frame, bg="#34495e", height=80)
        header.pack(fill=tk.X, padx=20, pady=10)
        
        title = tk.Label(header, text="🔐 Employee Hand Gesture Login System", 
                        font=("Arial", 24, "bold"), bg="#34495e", fg="white")
        title.pack(pady=20)

        # Status Bar
        self.status_frame = tk.Frame(self.scrollable_frame, bg="#1abc9c", height=50)
        self.status_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.status_label = tk.Label(self.status_frame, text="Status: Ready", 
                                     font=("Arial", 12), bg="#1abc9c", fg="white")
        self.status_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.user_label = tk.Label(self.status_frame, text="Not logged in", 
                                   font=("Arial", 12, "bold"), bg="#1abc9c", fg="white")
        self.user_label.pack(side=tk.RIGHT, padx=20, pady=10)

        # Control Bar
        control_frame = tk.Frame(self.scrollable_frame, bg="#2c3e50", height=40)
        control_frame.pack(fill=tk.X, padx=20, pady=5)
        
        # Activity Log OptionMenu
        self.log_option_var = tk.StringVar(value="Show Log")
        log_options = ["Show Log", "Hide Log"]
        self.log_option_menu = tk.OptionMenu(control_frame, self.log_option_var, *log_options, command=self.handle_log_option)
        self.log_option_menu.config(font=("Arial", 10), bg="#3498db", fg="white", cursor="hand2", width=10)
        self.log_option_menu.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Live Camera Control
        self.live_camera_btn = tk.Button(control_frame, text="📹 Stop Live Camera", 
                                       command=self.toggle_live_camera,
                                       font=("Arial", 10), bg="#e74c3c", fg="white",
                                       cursor="hand2", relief=tk.FLAT, padx=15, pady=5)
        self.live_camera_btn.pack(side=tk.LEFT, padx=5)

        # Hand Tracking Demo Button
        self.hand_demo_btn = tk.Button(control_frame, text="✋ Hand Tracking Demo", 
                                     command=self.start_hand_tracking_demo,
                                     font=("Arial", 10), bg="#9b59b6", fg="white",
                                     cursor="hand2", relief=tk.FLAT, padx=15, pady=5)
        self.hand_demo_btn.pack(side=tk.LEFT, padx=5)

        # Main Container
        self.main_container = tk.Frame(self.scrollable_frame, bg="#2c3e50")
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left Panel - User List
        self.left_panel = tk.Frame(self.main_container, bg="#34495e", width=300)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        
        tk.Label(self.left_panel, text="👥 Registered Users", font=("Arial", 16, "bold"), 
                bg="#34495e", fg="white").pack(pady=15)
        
        user_list_frame = tk.Frame(self.left_panel, bg="#2c3e50")
        user_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add scrollbar to user treeview
        user_tree_scrollbar = ttk.Scrollbar(user_list_frame)
        user_tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.user_tree = ttk.Treeview(user_list_frame, columns=("Name", "Status"), show="headings", height=15,
                                     yscrollcommand=user_tree_scrollbar.set)
        self.user_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        user_tree_scrollbar.config(command=self.user_tree.yview)
        
        self.user_tree.heading("Name", text="Name")
        self.user_tree.heading("Status", text="Status")
        self.user_tree.column("Name", width=150)
        self.user_tree.column("Status", width=100)
        
        self.manual_logout_btn = tk.Button(self.left_panel, text="🖐️ Manual Logout Selected", 
                                         command=self.manual_logout_selected,
                                         font=("Arial", 11), bg="#e74c3c", fg="white",
                                         cursor="hand2", relief=tk.FLAT, padx=20, pady=10,
                                         state=tk.DISABLED)
        self.manual_logout_btn.pack(pady=10, padx=10, fill=tk.X)
        
        tk.Button(self.left_panel, text="🔄 Refresh List", 
                 command=self.refresh_user_list,
                 font=("Arial", 11), bg="#3498db", fg="white",
                 cursor="hand2", relief=tk.FLAT, padx=20, pady=10).pack(pady=(0,10), padx=10, fill=tk.X)

        # Center Panel - Live Camera
        self.center_panel = tk.Frame(self.main_container, bg="#ecf0f1")
        self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.camera_label = tk.Label(self.center_panel, bg="#2c3e50")
        self.camera_label.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        self.camera_status_frame = tk.Frame(self.center_panel, bg="#ecf0f1")
        self.camera_status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.camera_status_label = tk.Label(self.camera_status_frame, 
                                          text="📹 Live Camera: ACTIVE - Auto detecting faces",
                                          font=("Arial", 11, "bold"), 
                                          bg="#27ae60", fg="white", padx=10, pady=5)
        self.camera_status_label.pack(fill=tk.X)

        # Right Panel - Activity Log
        self.right_panel = tk.Frame(self.main_container, bg="#bdc3c7", width=400)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH)
        
        self.create_log_widgets()

        # Actions Panel
        self.actions_panel = tk.Frame(self.center_panel, bg="#ecf0f1")
        self.actions_panel.pack(fill=tk.X, padx=10, pady=10)
        
        self.create_actions_widgets()

    def handle_log_option(self, selection):
        """Show or hide activity log based on dropdown"""
        if selection == "Show Log":
            self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH)
            self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
            self.log_visible = True
        else:  # Hide Log
            self.right_panel.pack_forget()
            self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
            self.log_visible = False

    def create_log_widgets(self):
        tk.Label(self.right_panel, text="📋 Activity Log", font=("Arial", 16, "bold"), 
                bg="#34495e", fg="white").pack(pady=15, fill=tk.X)
        
        self.log_text = scrolledtext.ScrolledText(self.right_panel, font=("Courier", 9), 
                                                  bg="#2c3e50", fg="#ecf0f1",
                                                  insertbackground="white",
                                                  relief=tk.FLAT, padx=10, pady=10,
                                                  state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0,15))
        
        tk.Button(self.right_panel, text="🗑️ Clear Log", 
                 command=self.clear_log,
                 font=("Arial", 10), bg="#e67e22", fg="white",
                 cursor="hand2", relief=tk.FLAT, padx=15, pady=8).pack(pady=(0,15))

    def create_actions_widgets(self):
        # Registration Section
        reg_frame = tk.LabelFrame(self.actions_panel, text="Register New User", 
                                 font=("Arial", 12, "bold"), bg="#ecf0f1")
        reg_frame.pack(fill=tk.X, pady=5)
        
        id_frame = tk.Frame(reg_frame, bg="#ecf0f1")
        id_frame.pack(fill=tk.X, padx=10, pady=(10,0))
        
        tk.Label(id_frame, text="Employee ID:", bg="#ecf0f1").pack(side=tk.LEFT)
        self.emp_id_entry = tk.Entry(id_frame, font=("Arial", 11), width=15)
        self.emp_id_entry.pack(side=tk.LEFT, padx=5)
        
        self.auto_id_btn = tk.Button(id_frame, text="🆔 Auto Generate", 
                                    command=self.auto_generate_id,
                                    font=("Arial", 9), bg="#f39c12", fg="white",
                                    cursor="hand2", relief=tk.FLAT)
        self.auto_id_btn.pack(side=tk.LEFT, padx=5)
        
        tk.Label(reg_frame, text="Name:", bg="#ecf0f1").pack(anchor=tk.W, padx=10)
        self.name_entry = tk.Entry(reg_frame, font=("Arial", 11), width=30)
        self.name_entry.pack(padx=10, pady=5)
        
        self.register_btn = tk.Button(reg_frame, text="📸 Register Face", 
                                      command=self.register_user,
                                      font=("Arial", 11, "bold"), bg="#27ae60", fg="white",
                                      cursor="hand2", relief=tk.FLAT, padx=20, pady=10)
        self.register_btn.pack(pady=10)

        # Quick Actions
        actions_frame = tk.Frame(self.actions_panel, bg="#ecf0f1")
        actions_frame.pack(fill=tk.X, pady=5)
        
        # Left side - Gestures
        gesture_frame = tk.LabelFrame(actions_frame, text="Quick Actions", 
                                    font=("Arial", 12, "bold"), bg="#ecf0f1")
        gesture_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        tk.Button(gesture_frame, text="👋 Wave to Login", 
                 command=self.wave_login,
                 font=("Arial", 10), bg="#3498db", fg="white",
                 cursor="hand2", relief=tk.FLAT, padx=15, pady=8).pack(pady=5, padx=10, fill=tk.X)
        
        tk.Button(gesture_frame, text="✌️ Victory Login", 
                 command=self.victory_login,
                 font=("Arial", 10), bg="#3498db", fg="white",
                 cursor="hand2", relief=tk.FLAT, padx=15, pady=8).pack(pady=5, padx=10, fill=tk.X)
        
        self.fist_logout_btn = tk.Button(gesture_frame, text="✊ Fist to Logout", 
                                       command=self.fist_logout,
                                       font=("Arial", 10), bg="#e74c3c", fg="white",
                                       cursor="hand2", relief=tk.FLAT, padx=15, pady=8,
                                       state=tk.DISABLED)
        self.fist_logout_btn.pack(pady=5, padx=10, fill=tk.X)
        
        # Right side - Records
        records_frame = tk.LabelFrame(actions_frame, text="Records", 
                                    font=("Arial", 12, "bold"), bg="#ecf0f1")
        records_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        tk.Button(records_frame, text="📋 My Attendance", 
                 command=self.view_my_attendance,
                 font=("Arial", 10), bg="#9b59b6", fg="white",
                 cursor="hand2", relief=tk.FLAT, padx=15, pady=8).pack(pady=5, padx=10, fill=tk.X)
        
        tk.Button(records_frame, text="📊 All Records", 
                 command=self.view_all_attendance,
                 font=("Arial", 10), bg="#9b59b6", fg="white",
                 cursor="hand2", relief=tk.FLAT, padx=15, pady=8).pack(pady=5, padx=10, fill=tk.X)
        
        tk.Button(records_frame, text="📈 Export Excel", 
                 command=self.export_to_excel,
                 font=("Arial", 10), bg="#16a085", fg="white",
                 cursor="hand2", relief=tk.FLAT, padx=15, pady=8).pack(pady=5, padx=10, fill=tk.X)

    def start_live_camera_feed(self):
        """Start the live camera feed display"""
        self.cap = cv2.VideoCapture(0)
        self.update_frame()
        self.start_live_camera()

    def update_frame(self):
        """Update the camera feed frame"""
        if hasattr(self, 'cap') and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (640, 480))
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(frame, f"Live: {timestamp}", (10, 30), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.camera_label.imgtk = imgtk
                self.camera_label.configure(image=imgtk)

        self.root.after(50, self.update_frame)

    def toggle_live_camera(self):
        """Start/stop live camera recognition"""
        if self.live_camera_running:
            self.stop_live_camera()
            self.live_camera_btn.config(text="📹 Start Live Recognition", bg="#27ae60")
            self.camera_status_label.config(text="📹 Live Camera: ACTIVE (No Auto Detection)", bg="#f39c12")
        else:
            self.start_live_camera()
            self.live_camera_btn.config(text="📹 Stop Live Recognition", bg="#e74c3c")
            self.camera_status_label.config(text="📹 Live Camera: ACTIVE - Auto detecting faces", bg="#27ae60")

    def start_live_camera(self):
        """Start continuous face recognition"""
        if not self.live_camera_running:
            success = self.face_system.start_live_recognition(self.live_recognition_callback)
            if success:
                self.live_camera_running = True
                self.log("Live face recognition started - Auto detection active")
            else:
                self.log("Failed to start live face recognition")

    def stop_live_camera(self):
        """Stop continuous face recognition"""
        if self.live_camera_running:
            self.face_system.stop_live_recognition()
            self.live_camera_running = False
            self.log("Live face recognition stopped")

    def live_recognition_callback(self, emp_id, message):
        """Callback for live face recognition"""
        self.root.after(0, lambda: self.log(message))
        if emp_id:
            user = self.db_manager.get_user(emp_id)
            if user:
                name = user.get("name", emp_id)
                logged_in = self.db_manager.get_logged_in_users()
                
                if emp_id not in logged_in:
                    self.db_manager.log_attendance(emp_id, name, "LOGIN", "auto")
                    self.root.after(0, lambda: self.log(f"Auto login: {name} ({emp_id})"))
                    
            self.root.after(0, self.update_status)
            self.root.after(0, self.refresh_user_list)

    def clear_log(self):
        """Clear the activity log"""
        if hasattr(self, 'log_text'):
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state=tk.DISABLED)

    def log(self, message):
        """Add message to activity log"""
        if not hasattr(self, 'log_text'):
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def refresh_user_list(self):
        """Refresh the user list on the left panel"""
        try:
            for item in self.user_tree.get_children():
                self.user_tree.delete(item)
            
            users = self.db_manager.get_all_users()
            logged_in_users = self.db_manager.get_logged_in_users()
            
            for user in users:
                emp_id = user["emp_id"]
                name = user.get("name", "N/A")
                status = "🟢 Online" if emp_id in logged_in_users else "⚫ Offline"
                self.user_tree.insert("", tk.END, values=(f"{name} ({emp_id})", status))
                
        except Exception as e:
            self.log(f"Error refreshing user list: {e}")

    def manual_logout_selected(self):
        """Manually logout selected user"""
        selected = self.user_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a user to logout")
            return
        
        item = selected[0]
        values = self.user_tree.item(item, "values")
        user_display = values[0]
        
        try:
            emp_id = user_display.split("(")[1].split(")")[0]
        except:
            messagebox.showerror("Error", "Could not extract employee ID")
            return
        
        user = self.db_manager.get_user(emp_id)
        if not user:
            messagebox.showerror("Error", "User not found")
            return
        
        name = user.get("name", emp_id)
        
        if messagebox.askyesno("Confirm Logout", f"Manually logout {name} ({emp_id})?"):
            try:
                self.db_manager.log_attendance(emp_id, name, "LOGOUT", "manual")
                self.log(f"Manual logout: {name} ({emp_id})")
                messagebox.showinfo("Success", f"{name} logged out manually")
                self.refresh_user_list()
                
                if self.current_user == emp_id:
                    self.current_user = None
                    self.update_status()
                    
            except Exception as e:
                messagebox.showerror("Error", f"Logout failed: {e}")

    def update_status(self):
        if self.current_user:
            user = self.db_manager.get_user(self.current_user)
            name = user.get("name", self.current_user) if user else self.current_user
            self.user_label.config(text=f"👤 Logged in: {name} ({self.current_user})")
            self.status_frame.config(bg="#27ae60")
            self.user_label.config(bg="#27ae60")
            self.status_label.config(bg="#27ae60", text="Status: User Logged In")
            self.fist_logout_btn.config(state=tk.NORMAL)
            self.manual_logout_btn.config(state=tk.NORMAL)
        else:
            self.user_label.config(text="Not logged in")
            self.status_frame.config(bg="#1abc9c")
            self.user_label.config(bg="#1abc9c")
            self.status_label.config(bg="#1abc9c", text="Status: Ready")
            self.fist_logout_btn.config(state=tk.DISABLED)
            self.manual_logout_btn.config(state=tk.DISABLED)
        
        self.refresh_user_list()

    def auto_generate_id(self):
        """Auto-generate employee ID"""
        emp_id = self.db_manager.generate_employee_id()
        self.emp_id_entry.delete(0, tk.END)
        self.emp_id_entry.insert(0, emp_id)
        self.log(f"Generated Employee ID: {emp_id}")

    def register_user(self):
        emp_id = self.emp_id_entry.get().strip()
        name = self.name_entry.get().strip()
        
        if not emp_id or not name:
            messagebox.showerror("Error", "Please enter both Employee ID and Name")
            return
        
        existing_user = self.db_manager.get_user(emp_id)
        if existing_user:
            messagebox.showerror("Error", f"Employee ID {emp_id} already exists!")
            return
        
        self.register_btn.config(state=tk.DISABLED)
        self.log(f"Starting registration for {name} ({emp_id})...")
        
        def callback(success, message):
            self.root.after(0, lambda: self.log(message))
            if success:
                self.root.after(0, lambda: messagebox.showinfo("Success", message))
                self.root.after(0, lambda: self.emp_id_entry.delete(0, tk.END))
                self.root.after(0, lambda: self.name_entry.delete(0, tk.END))
                self.db_manager.create_user(emp_id, name)
                users = self.db_manager.get_all_users()
                self.face_system.load_known_faces(users)
                self.root.after(0, self.refresh_user_list)
            self.root.after(0, lambda: self.register_btn.config(state=tk.NORMAL))
        
        thread = threading.Thread(target=self.face_system.register_face, 
                                 args=(emp_id, name, callback))
        thread.daemon = True
        thread.start()

    def wave_login(self):
        """Wave gesture login"""
        if self.current_user:
            messagebox.showwarning("Warning", "A user is already logged in. Please logout first.")
            return
        
        self.log("Starting wave gesture detection for login...")
        
        def gesture_callback(success, message):
            self.root.after(0, lambda: self.log(message))
            if success:
                self.root.after(0, self.face_login)
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", message))
        
        thread = threading.Thread(target=self.gesture_detector.detect_wave_gesture, 
                                 args=(gesture_callback,))
        thread.daemon = True
        thread.start()

    def victory_login(self):
        """Victory gesture login"""
        if self.current_user:
            messagebox.showwarning("Warning", "A user is already logged in. Please logout first.")
            return
        
        self.log("Starting victory gesture detection for login...")
        
        def gesture_callback(success, message):
            self.root.after(0, lambda: self.log(message))
            if success:
                self.root.after(0, self.face_login)
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", message))
        
        thread = threading.Thread(target=self.gesture_detector.detect_victory_gesture, 
                                 args=(gesture_callback,))
        thread.daemon = True
        thread.start()

    def fist_logout(self):
        """Fist gesture logout"""
        if not self.current_user:
            messagebox.showwarning("Warning", "No user is currently logged in")
            return
        
        self.log("Starting fist gesture detection for logout...")
        
        def gesture_callback(success, message):
            self.root.after(0, lambda: self.log(message))
            if success:
                self.root.after(0, self.logout_user)
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", message))
        
        thread = threading.Thread(target=self.gesture_detector.detect_fist_gesture, 
                                 args=(gesture_callback,))
        thread.daemon = True
        thread.start()

    def start_hand_tracking_demo(self):
        """Start hand tracking demo"""
        self.log("Starting hand tracking demo...")
        
        def demo_callback(success, message):
            self.root.after(0, lambda: self.log(message))
            if not success:
                self.root.after(0, lambda: messagebox.showerror("Error", message))
        
        thread = threading.Thread(target=self.gesture_detector.start_hand_tracking_demo, 
                                 args=(demo_callback,))
        thread.daemon = True
        thread.start()

    def face_login(self):
        """Face recognition login"""
        if self.current_user:
            messagebox.showwarning("Warning", "A user is already logged in. Please logout first.")
            return
        
        self.log("Starting face recognition login...")
        
        def callback(emp_id, message):
            self.root.after(0, lambda: self.log(message))
            if emp_id:
                self.current_user = emp_id
                user = self.db_manager.get_user(emp_id)
                if user:
                    self.db_manager.log_attendance(emp_id, user.get("name", emp_id), "LOGIN", "face")
                self.root.after(0, self.update_status)
                self.root.after(0, lambda: messagebox.showinfo("Success", message))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", message))
        
        thread = threading.Thread(target=self.face_system.recognize_face, 
                                 args=(callback,))
        thread.daemon = True
        thread.start()

    def logout_user(self):
        """Logout current user"""
        if not self.current_user:
            return
        
        try:
            user = self.db_manager.get_user(self.current_user)
            name = user.get("name", self.current_user) if user else self.current_user
            self.db_manager.log_attendance(self.current_user, name, "LOGOUT", "gesture")
            self.log(f"Gesture logout successful: {name} ({self.current_user})")
            messagebox.showinfo("Success", f"{name} logged out successfully")
            self.current_user = None
            self.update_status()
        except Exception as e:
            messagebox.showerror("Error", f"Logout failed: {e}")

    def view_my_attendance(self):
        if not self.current_user:
            messagebox.showwarning("Warning", "Please login first to view your attendance")
            return
        
        self.show_attendance_window(self.current_user)

    def view_all_attendance(self):
        self.show_attendance_window(None)

    def show_attendance_window(self, emp_id):
        window = tk.Toplevel(self.root)
        window.title(f"Attendance Records - {emp_id if emp_id else 'All Users'}")
        window.geometry("800x500")
        window.configure(bg="#2c3e50")
        
        tk.Label(window, text=f"📋 Attendance Records", 
                font=("Arial", 16, "bold"), bg="#2c3e50", fg="white").pack(pady=15)
        
        tree_frame = tk.Frame(window, bg="#34495e")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0,20))
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree = ttk.Treeview(tree_frame, columns=("Name", "Action", "Timestamp", "Method"), 
                           show="headings", yscrollcommand=scrollbar.set, height=15)
        tree.pack(fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=tree.yview)
        
        tree.heading("Name", text="Name")
        tree.heading("Action", text="Action")
        tree.heading("Timestamp", text="Timestamp")
        tree.heading("Method", text="Method")
        
        tree.column("Name", width=150)
        tree.column("Action", width=100)
        tree.column("Timestamp", width=200)
        tree.column("Method", width=100)
        
        try:
            records = self.db_manager.get_attendance_records(emp_id)
            
            for record in records:
                name = record.get("name", record["emp_id"])
                action = record["action"]
                timestamp = record["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                method = "Gesture" if record.get("gesture") else "Manual" if record.get("manual") else "Auto" if record.get("auto") else "Face"
                tree.insert("", tk.END, values=(name, action, timestamp, method))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch records: {e}")
        
        tk.Button(window, text="Close", command=window.destroy,
                 font=("Arial", 11), bg="#e74c3c", fg="white",
                 cursor="hand2", relief=tk.FLAT, padx=30, pady=10).pack(pady=(0,20))

    def export_to_excel(self):
        """Export attendance data to Excel file"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                title="Save Excel File As"
            )
            
            if not file_path:
                return
            
            records = self.db_manager.get_attendance_records()
            
            if not records:
                messagebox.showinfo("Info", "No attendance records to export")
                return
            
            data = []
            for record in records:
                method = "Gesture" if record.get("gesture") else "Manual" if record.get("manual") else "Auto" if record.get("auto") else "Face"
                data.append({
                    "Employee ID": record["emp_id"],
                    "Name": record.get("name", record["emp_id"]),
                    "Action": record["action"],
                    "Timestamp": record["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                    "Method": method
                })
            
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False, engine='openpyxl')
            
            self.log(f"Exported {len(data)} records to {file_path}")
            messagebox.showinfo("Success", f"Data exported successfully to:\n{file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
            self.log(f"Export error: {e}")

    def on_closing(self):
        """Clean up when application closes"""
        self.stop_live_camera()
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()
        self.db_manager.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HandGestureLoginApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()