import cv2
import numpy as np
from pymongo import MongoClient
from datetime import datetime
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from PIL import Image, ImageTk
import threading
import pandas as pd
from bson import ObjectId

# -------------------- MongoDB Setup --------------------
try:
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    client.server_info()
    db = client["gesture_login_db"]
    users_collection = db["users"]
    attendance_collection = db["attendance"]
    DB_CONNECTED = True
except Exception as e:
    DB_CONNECTED = False
    DB_ERROR = str(e)

# -------------------- Custom Face Recognition System --------------------
class SimpleFaceRecognizer:
    def __init__(self, threshold=70):
        self.threshold = threshold
        self.known_faces = {}
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
    
    def add_face(self, face_id, face_image):
        """Add a face to the known faces database"""
        if face_id not in self.known_faces:
            self.known_faces[face_id] = []
        self.known_faces[face_id].append(face_image)
    
    def recognize_face(self, test_image):
        """Recognize a face using template matching"""
        best_match = None
        best_score = float('inf')
        
        gray_test = cv2.cvtColor(test_image, cv2.COLOR_BGR2GRAY) if len(test_image.shape) == 3 else test_image
        gray_test = cv2.resize(gray_test, (200, 200))
        
        for face_id, training_images in self.known_faces.items():
            for train_img in training_images:
                # Resize training image to match test image
                train_resized = cv2.resize(train_img, (200, 200))
                
                # Calculate MSE (Mean Squared Error)
                score = np.mean((gray_test.astype(float) - train_resized.astype(float)) ** 2)
                
                if score < best_score:
                    best_score = score
                    best_match = face_id
        
        # Convert MSE to confidence (lower MSE = higher confidence)
        confidence = max(0, 100 - (best_score / 100))
        
        if confidence > self.threshold:
            return best_match, confidence
        else:
            return None, confidence

# -------------------- Face Recognition System --------------------
class FaceRecognitionSystem:
    def __init__(self, data_dir="data/faces"):
        self.data_dir = data_dir
        self.models_dir = "models"
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        # Use our custom face recognizer instead of cv2.face
        self.face_recognizer = SimpleFaceRecognizer(threshold=60)
        
        self.known_faces = {}
        self.load_known_faces()
        
        self.is_capturing = False
        self.stop_capture = False
        self.gesture_detection_active = False
        self.live_camera_active = False
        self.camera_thread = None

    def load_known_faces(self):
        try:
            users = users_collection.find({"face_registered": True})
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
                
        except Exception as e:
            print(f"Error loading faces: {e}")

    def generate_employee_id(self):
        """Generate automatic employee ID"""
        try:
            last_user = users_collection.find_one({}, sort=[("_id", -1)])
            if last_user and "emp_id" in last_user:
                last_id = last_user["emp_id"]
                if last_id.startswith("EMP"):
                    try:
                        num = int(last_id[3:]) + 1
                        return f"EMP{num:04d}"
                    except:
                        pass
            return "EMP0001"
        except:
            return "EMP0001"

    def register_face(self, emp_id, name, callback):
        self.stop_capture = False
        captured_faces = []
        samples_needed = 30  # Reduced for faster testing
        
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
                    # Add to recognizer
                    self.face_recognizer.add_face(emp_id, face_roi)
                
                callback(False, f"Captured {len(captured_faces)}/{samples_needed}")

        cam.release()
        cv2.destroyAllWindows()

        if self.stop_capture:
            callback(False, "Registration cancelled")
            return

        try:
            users_collection.update_one(
                {"emp_id": emp_id},
                {"$set": {
                    "name": name,
                    "face_registered": True,
                    "registered_on": datetime.now()
                }},
                upsert=True
            )
            self.load_known_faces()
            callback(True, f"Face registered for {name} ({emp_id})")
        except Exception as e:
            callback(False, f"Database error: {e}")

    def delete_user(self, emp_id):
        """Delete user and their face data"""
        try:
            # Delete from database
            result = users_collection.delete_one({"emp_id": emp_id})
            
            # Delete face image
            img_path = os.path.join(self.data_dir, f"{emp_id}.jpg")
            if os.path.exists(img_path):
                os.remove(img_path)
            
            # Reload face recognition model
            self.load_known_faces()
            
            return result.deleted_count > 0
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False

    def start_live_recognition(self, callback):
        """Start continuous face recognition"""
        if len(self.known_faces) == 0:
            callback(None, "No registered users found")
            return False

        self.live_camera_active = True
        self.camera_thread = threading.Thread(target=self._live_recognition_loop, args=(callback,))
        self.camera_thread.daemon = True
        self.camera_thread.start()
        return True

    def stop_live_recognition(self):
        """Stop continuous face recognition"""
        self.live_camera_active = False
        if self.camera_thread and self.camera_thread.is_alive():
            self.camera_thread.join(timeout=2)

    def _live_recognition_loop(self, callback):
        """Continuous face recognition loop"""
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(None, "Cannot access camera")
            return

        recognition_frames = {}
        required_frames = 5
        last_recognition_time = datetime.now()
        recognition_cooldown = 5  # seconds between recognitions

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
                    
                    # Use our custom recognizer
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
                            # Check if user is already logged in
                            recent_login = attendance_collection.find_one(
                                {"emp_id": emp_id, "action": "LOGIN"},
                                sort=[("timestamp", -1)]
                            )
                            recent_logout = attendance_collection.find_one(
                                {"emp_id": emp_id, "action": "LOGOUT", "timestamp": {"$gt": recent_login["timestamp"] if recent_login else datetime.min}}
                            ) if recent_login else None

                            if not recent_login or recent_logout:
                                # User is not logged in, log them in
                                attendance_collection.insert_one({
                                    "emp_id": emp_id,
                                    "name": name,
                                    "action": "LOGIN",
                                    "timestamp": current_time,
                                    "auto": True
                                })
                                callback(emp_id, f"Auto login: {name}")
                            else:
                                # User is already logged in, log them out
                                attendance_collection.insert_one({
                                    "emp_id": emp_id,
                                    "name": name,
                                    "action": "LOGOUT",
                                    "timestamp": current_time,
                                    "auto": True
                                })
                                callback(emp_id, f"Auto logout: {name}")
                            
                            last_recognition_time = current_time
                            recognition_frames.clear()
                    else:
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                        cv2.putText(frame, "Unknown", (x, y-10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                # Display live camera feed
                cv2.imshow("Live Face Recognition - Press Q to stop", frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        except Exception as e:
            callback(None, f"Error in live recognition: {e}")
        finally:
            cam.release()
            cv2.destroyAllWindows()
            self.live_camera_active = False

    def detect_wave_gesture_simple(self, callback):
        """Simple wave gesture detection using motion detection"""
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(False, "Cannot access camera")
            return

        self.stop_capture = False
        motion_count = 0
        motion_threshold = 15
        
        # Initialize background subtractor
        fgbg = cv2.createBackgroundSubtractorMOG2()
        
        try:
            while not self.stop_capture:
                ret, frame = cam.read()
                if not ret:
                    break

                # Flip frame for mirror effect
                frame = cv2.flip(frame, 1)
                
                # Apply background subtraction
                fgmask = fgbg.apply(frame)
                
                # Count non-zero pixels (motion)
                motion_pixels = cv2.countNonZero(fgmask)
                
                if motion_pixels > 1000:  # Threshold for significant motion
                    motion_count += 1
                    cv2.putText(frame, f"Motion detected: {motion_count}/{motion_threshold}", 
                              (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                else:
                    motion_count = max(0, motion_count - 1)
                
                # Display instructions
                cv2.putText(frame, "Wave your hand to login", (50, 100), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, "Press Q to cancel", (50, 130), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                cv2.imshow("Wave Gesture Login", frame)
                
                if motion_count >= motion_threshold:
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

    def detect_fist_gesture_simple(self, callback):
        """Simple fist detection using contour analysis"""
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(False, "Cannot access camera")
            return

        self.stop_capture = False
        fist_frames = 0
        fist_threshold = 20
        
        try:
            while not self.stop_capture:
                ret, frame = cam.read()
                if not ret:
                    break

                # Flip frame for mirror effect
                frame = cv2.flip(frame, 1)
                
                # Convert to HSV for better skin detection
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                
                # Define skin color range
                lower_skin = np.array([0, 20, 70], dtype=np.uint8)
                upper_skin = np.array([20, 255, 255], dtype=np.uint8)
                
                # Create skin mask
                mask = cv2.inRange(hsv, lower_skin, upper_skin)
                
                # Apply morphological operations to clean up the mask
                kernel = np.ones((5,5), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                
                # Find contours
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    # Get the largest contour (likely hand)
                    largest_contour = max(contours, key=cv2.contourArea)
                    
                    # Calculate contour area and hull area
                    area = cv2.contourArea(largest_contour)
                    hull = cv2.convexHull(largest_contour)
                    hull_area = cv2.contourArea(hull)
                    
                    # Simple fist detection: if contour area is close to hull area, it might be a fist
                    if hull_area > 0 and area / hull_area > 0.8 and area > 1000:
                        fist_frames += 1
                        cv2.putText(frame, f"Fist detected: {fist_frames}/{fist_threshold}", 
                                  (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                        cv2.putText(frame, "Keep hand closed for logout", (50, 80), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    else:
                        fist_frames = max(0, fist_frames - 1)
                
                # Display instructions
                cv2.putText(frame, "Make a fist to logout", (50, 120), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, "Press Q to cancel", (50, 150), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                cv2.imshow("Fist Gesture Logout", frame)
                
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


# -------------------- GUI Application --------------------
class AttendanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Employee Hand Gesture Login System")
        self.root.geometry("1400x800")
        self.root.configure(bg="#2c3e50")
        
        if not DB_CONNECTED:
            messagebox.showerror("Database Error", f"MongoDB connection failed:\n{DB_ERROR}\n\nMake sure MongoDB is running.")
        
        self.fr_system = FaceRecognitionSystem()
        self.current_user = None
        self.log_visible = True  # Start with log visible
        self.live_camera_running = False
        
        self.setup_ui()
        self.update_status()
        self.refresh_user_list()
        
        # Start live camera feed
        self.start_live_camera_feed()

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#34495e", height=80)
        header.pack(fill=tk.X)
        
        title = tk.Label(header, text="🔐 Employee Hand Gesture Login System", 
                        font=("Arial", 24, "bold"), bg="#34495e", fg="white")
        title.pack(pady=20)
        
        # Status Bar
        self.status_frame = tk.Frame(self.root, bg="#1abc9c", height=50)
        self.status_frame.pack(fill=tk.X)
        
        self.status_label = tk.Label(self.status_frame, text="Status: Ready", 
                                     font=("Arial", 12), bg="#1abc9c", fg="white")
        self.status_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.user_label = tk.Label(self.status_frame, text="Not logged in", 
                                   font=("Arial", 12, "bold"), bg="#1abc9c", fg="white")
        self.user_label.pack(side=tk.RIGHT, padx=20, pady=10)
        
        # Control Buttons Bar with OptionMenu
        control_frame = tk.Frame(self.root, bg="#2c3e50", height=40)
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
        
        # Main Container
        self.main_container = tk.Frame(self.root, bg="#2c3e50")
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left Panel - User List
        self.left_panel = tk.Frame(self.main_container, bg="#34495e", width=300)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        
        tk.Label(self.left_panel, text="👥 Registered Users", font=("Arial", 16, "bold"), 
                bg="#34495e", fg="white").pack(pady=15)
        
        # User list frame
        user_list_frame = tk.Frame(self.left_panel, bg="#2c3e50")
        user_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Treeview for users
        self.user_tree = ttk.Treeview(user_list_frame, columns=("Name", "Status"), 
                                    show="headings", height=15)
        self.user_tree.pack(fill=tk.BOTH, expand=True)
        
        self.user_tree.heading("Name", text="Name")
        self.user_tree.heading("Status", text="Status")
        
        self.user_tree.column("Name", width=150)
        self.user_tree.column("Status", width=100)
        
        # Manual logout button
        self.manual_logout_btn = tk.Button(self.left_panel, text="🖐️ Manual Logout Selected", 
                                         command=self.manual_logout_selected,
                                         font=("Arial", 11), bg="#e74c3c", fg="white",
                                         cursor="hand2", relief=tk.FLAT, padx=20, pady=10,
                                         state=tk.DISABLED)
        self.manual_logout_btn.pack(pady=10, padx=10, fill=tk.X)
        
        # Refresh button
        tk.Button(self.left_panel, text="🔄 Refresh List", 
                 command=self.refresh_user_list,
                 font=("Arial", 11), bg="#3498db", fg="white",
                 cursor="hand2", relief=tk.FLAT, padx=20, pady=10).pack(pady=(0,10), padx=10, fill=tk.X)
        
        # Center Panel - Live Camera Feed
        self.center_panel = tk.Frame(self.main_container, bg="#ecf0f1")
        self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Camera feed label
        self.camera_label = tk.Label(self.center_panel, bg="#2c3e50")
        self.camera_label.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        # Right Panel - Activity Log
        self.right_panel = tk.Frame(self.main_container, bg="#bdc3c7", width=400)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH)
        
        # Initialize log widgets
        self.create_log_widgets()
        
        # Live Camera Status
        self.camera_status_frame = tk.Frame(self.center_panel, bg="#ecf0f1")
        self.camera_status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.camera_status_label = tk.Label(self.camera_status_frame, 
                                          text="📹 Live Camera: ACTIVE - Auto detecting faces",
                                          font=("Arial", 11, "bold"), 
                                          bg="#27ae60", fg="white", padx=10, pady=5)
        self.camera_status_label.pack(fill=tk.X)
        
        # Actions Panel below camera
        self.actions_panel = tk.Frame(self.center_panel, bg="#ecf0f1")
        self.actions_panel.pack(fill=tk.X, padx=10, pady=10)
        
        self.create_actions_widgets()

    def create_actions_widgets(self):
        """Create action buttons below the camera feed"""
        # Registration Section
        reg_frame = tk.LabelFrame(self.actions_panel, text="Register New User", 
                                 font=("Arial", 12, "bold"), bg="#ecf0f1")
        reg_frame.pack(fill=tk.X, pady=5)
        
        # Auto-generate ID button
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
        
        # Quick Actions Frame
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
        """Create log widgets in the right panel"""
        tk.Label(self.right_panel, text="📋 Activity Log", font=("Arial", 16, "bold"), 
                bg="#34495e", fg="white").pack(pady=15, fill=tk.X)
        
        self.log_text = scrolledtext.ScrolledText(self.right_panel, font=("Courier", 9), 
                                                  bg="#2c3e50", fg="#ecf0f1",
                                                  insertbackground="white",
                                                  relief=tk.FLAT, padx=10, pady=10,
                                                  state=tk.DISABLED)  # Make it non-editable
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0,15))
        
        # Clear log button
        tk.Button(self.right_panel, text="🗑️ Clear Log", 
                 command=self.clear_log,
                 font=("Arial", 10), bg="#e67e22", fg="white",
                 cursor="hand2", relief=tk.FLAT, padx=15, pady=8).pack(pady=(0,15))

    def start_live_camera_feed(self):
        """Start the live camera feed display"""
        self.cap = cv2.VideoCapture(0)
        self.update_frame()
        # Start auto recognition
        self.start_live_camera()

    def update_frame(self):
        """Update the camera feed frame"""
        if hasattr(self, 'cap') and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                # Convert color and resize for Tkinter
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (640, 480))
                
                # Add timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(frame, f"Live: {timestamp}", (10, 30), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.camera_label.imgtk = imgtk
                self.camera_label.configure(image=imgtk)

        self.root.after(50, self.update_frame)  # Update every 50ms

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
            success = self.fr_system.start_live_recognition(self.live_recognition_callback)
            if success:
                self.live_camera_running = True
                self.log("Live face recognition started - Auto detection active")
            else:
                self.log("Failed to start live face recognition")

    def stop_live_camera(self):
        """Stop continuous face recognition"""
        if self.live_camera_running:
            self.fr_system.stop_live_recognition()
            self.live_camera_running = False
            self.log("Live face recognition stopped")

    def live_recognition_callback(self, emp_id, message):
        """Callback for live face recognition"""
        self.root.after(0, lambda: self.log(message))
        if emp_id:
            # Update current user and refresh status
            if "login" in message.lower():
                self.current_user = emp_id
            elif "logout" in message.lower():
                if self.current_user == emp_id:
                    self.current_user = None
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
            # Clear existing items
            for item in self.user_tree.get_children():
                self.user_tree.delete(item)
            
            # Fetch all users
            users = list(users_collection.find({"face_registered": True}))
            
            # Get currently logged in users from attendance records
            recent_logins = attendance_collection.aggregate([
                {"$match": {"action": "LOGIN"}},
                {"$sort": {"timestamp", -1}},
                {"$group": {"_id": "$emp_id", "latest_login": {"$first": "$timestamp"}}}
            ])
            
            logged_in_users = set()
            for login in recent_logins:
                # Check if there's no logout after the latest login
                latest_logout = attendance_collection.find_one(
                    {"emp_id": login["_id"], "action": "LOGOUT", "timestamp": {"$gt": login["latest_login"]}},
                    sort=[("timestamp", -1)]
                )
                if not latest_logout:
                    logged_in_users.add(login["_id"])
            
            # Add users to treeview
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
        
        # Extract emp_id from display text (format: "Name (EMP001)")
        try:
            emp_id = user_display.split("(")[1].split(")")[0]
        except:
            messagebox.showerror("Error", "Could not extract employee ID")
            return
        
        # Get user details
        user = users_collection.find_one({"emp_id": emp_id})
        if not user:
            messagebox.showerror("Error", "User not found")
            return
        
        name = user.get("name", emp_id)
        
        if messagebox.askyesno("Confirm Logout", f"Manually logout {name} ({emp_id})?"):
            try:
                attendance_collection.insert_one({
                    "emp_id": emp_id,
                    "name": name,
                    "action": "LOGOUT",
                    "timestamp": datetime.now(),
                    "manual": True
                })
                
                self.log(f"Manual logout: {name} ({emp_id})")
                messagebox.showinfo("Success", f"{name} logged out manually")
                self.refresh_user_list()
                
                # If current user is logged out, update status
                if self.current_user == emp_id:
                    self.current_user = None
                    self.update_status()
                    
            except Exception as e:
                messagebox.showerror("Error", f"Logout failed: {e}")

    def update_status(self):
        if self.current_user:
            user = users_collection.find_one({"emp_id": self.current_user})
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
        
        # Refresh user list to update status indicators
        self.refresh_user_list()

    def auto_generate_id(self):
        """Auto-generate employee ID"""
        emp_id = self.fr_system.generate_employee_id()
        self.emp_id_entry.delete(0, tk.END)
        self.emp_id_entry.insert(0, emp_id)
        self.log(f"Generated Employee ID: {emp_id}")

    def register_user(self):
        emp_id = self.emp_id_entry.get().strip()
        name = self.name_entry.get().strip()
        
        if not emp_id or not name:
            messagebox.showerror("Error", "Please enter both Employee ID and Name")
            return
        
        # Check if employee ID already exists
        existing_user = users_collection.find_one({"emp_id": emp_id})
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
                self.root.after(0, self.refresh_user_list)
            self.root.after(0, lambda: self.register_btn.config(state=tk.NORMAL))
        
        thread = threading.Thread(target=self.fr_system.register_face, 
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
                # After wave detection, start face recognition
                self.root.after(0, self.face_login)
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", message))
        
        thread = threading.Thread(target=self.fr_system.detect_wave_gesture_simple, 
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
        
        thread = threading.Thread(target=self.fr_system.detect_fist_gesture_simple, 
                                 args=(gesture_callback,))
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
                self.root.after(0, self.update_status)
                self.root.after(0, lambda: messagebox.showinfo("Success", message))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", message))
        
        thread = threading.Thread(target=self.fr_system.recognize_face, 
                                 args=(callback,))
        thread.daemon = True
        thread.start()

    def logout_user(self):
        """Logout current user"""
        if not self.current_user:
            return
        
        try:
            user = users_collection.find_one({"emp_id": self.current_user})
            name = user.get("name", self.current_user) if user else self.current_user
            
            attendance_collection.insert_one({
                "emp_id": self.current_user,
                "name": name,
                "action": "LOGOUT",
                "timestamp": datetime.now(),
                "gesture": True
            })
            
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
        
        # Create Treeview
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
        
        # Fetch records
        try:
            if emp_id:
                records = attendance_collection.find({"emp_id": emp_id}).sort("timestamp", -1).limit(50)
            else:
                records = attendance_collection.find().sort("timestamp", -1).limit(100)
            
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
            # Ask for save location
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                title="Save Excel File As"
            )
            
            if not file_path:
                return
            
            # Fetch all attendance records
            records = list(attendance_collection.find().sort("timestamp", -1))
            
            if not records:
                messagebox.showinfo("Info", "No attendance records to export")
                return
            
            # Prepare data for Excel
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
            
            # Create DataFrame and save to Excel
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
        self.root.destroy()


# -------------------- Main --------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = AttendanceApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()