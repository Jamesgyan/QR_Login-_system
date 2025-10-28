# main_gui.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import cv2
from PIL import Image, ImageTk
import numpy as np
import json
from datetime import datetime
import os
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from face_recognition.face_detector import FaceDetector
from hand_sign_recognition.hand_detector import HandDetector
from user_management.user_controller import UserController
from database.database_service import DatabaseService
from utils.camera_utils import CameraUtils, CameraManager


class AuthApplicationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("BioAuth - Face & Hand Sign Authentication")
        self.root.geometry("1000x700")
        
        # Initialize services
        self.db_service = DatabaseService()
        self.user_controller = UserController(self.db_service)
        self.face_detector = FaceDetector()
        self.hand_detector = HandDetector()
        self.camera_manager = None
        
        # Camera setup
        self.current_frame = None
        self.is_capturing = False
        
        # Data storage
        self.captured_face_images = []
        self.captured_hand_images = []
        self.current_hand_sequence = []
        
        self.setup_gui()
        self.start_camera()
    
    def setup_gui(self):
        # Create main notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tabs
        self.login_tab = ttk.Frame(self.notebook)
        self.register_tab = ttk.Frame(self.notebook)
        self.manage_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.login_tab, text='🔐 Login')
        self.notebook.add(self.register_tab, text='👤 Register')
        self.notebook.add(self.manage_tab, text='⚙️ Manage Users')
        
        self.setup_login_tab()
        self.setup_register_tab()
        self.setup_manage_tab()
    
    def setup_login_tab(self):
        # Login tab layout
        left_frame = ttk.Frame(self.login_tab)
        left_frame.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        
        right_frame = ttk.Frame(self.login_tab)
        right_frame.pack(side='right', fill='both', expand=True, padx=10, pady=10)
        
        # Camera feed
        ttk.Label(left_frame, text="Camera Feed", font=('Arial', 12, 'bold')).pack(pady=5)
        
        self.login_video_frame = ttk.Label(left_frame)
        self.login_video_frame.pack(pady=10)
        
        # Login controls
        login_controls = ttk.LabelFrame(right_frame, text="Login Controls", padding=10)
        login_controls.pack(fill='x', pady=10)
        
        self.login_status = ttk.Label(login_controls, text="Status: Ready", foreground='blue')
        self.login_status.pack(pady=5)
        
        ttk.Button(login_controls, text="Start Face Recognition", 
                  command=self.start_face_login).pack(pady=5, fill='x')
        
        ttk.Button(login_controls, text="Verify Hand Sequence", 
                  command=self.start_hand_login).pack(pady=5, fill='x')
        
        ttk.Button(login_controls, text="Full Authentication", 
                  command=self.full_authentication).pack(pady=5, fill='x')
        
        # Login history
        history_frame = ttk.LabelFrame(right_frame, text="Login History", padding=10)
        history_frame.pack(fill='both', expand=True, pady=10)
        
        self.login_history_text = scrolledtext.ScrolledText(history_frame, height=15)
        self.login_history_text.pack(fill='both', expand=True)
    
    def setup_register_tab(self):
        # Registration tab layout
        main_frame = ttk.Frame(self.register_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Top section - camera and controls
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill='x', pady=10)
        
        # Camera feed
        camera_frame = ttk.LabelFrame(top_frame, text="Registration Camera", padding=10)
        camera_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        self.register_video_frame = ttk.Label(camera_frame)
        self.register_video_frame.pack(pady=10)
        
        # Registration controls
        controls_frame = ttk.LabelFrame(top_frame, text="Registration Controls", padding=10)
        controls_frame.pack(side='right', fill='both', expand=True, padx=5)
        
        # User info
        ttk.Label(controls_frame, text="Username:").pack(anchor='w')
        self.username_entry = ttk.Entry(controls_frame, width=30)
        self.username_entry.pack(fill='x', pady=5)
        
        ttk.Label(controls_frame, text="Email:").pack(anchor='w')
        self.email_entry = ttk.Entry(controls_frame, width=30)
        self.email_entry.pack(fill='x', pady=5)
        
        # Face registration
        face_frame = ttk.Frame(controls_frame)
        face_frame.pack(fill='x', pady=10)
        
        ttk.Button(face_frame, text="Capture Face Image", 
                  command=self.capture_face_image).pack(side='left', padx=5)
        
        self.face_count_label = ttk.Label(face_frame, text="Faces: 0/3")
        self.face_count_label.pack(side='right', padx=5)
        
        # Hand sequence registration
        hand_frame = ttk.Frame(controls_frame)
        hand_frame.pack(fill='x', pady=10)
        
        ttk.Button(hand_frame, text="Capture Hand Sign", 
                  command=self.capture_hand_image).pack(side='left', padx=5)
        
        self.hand_count_label = ttk.Label(hand_frame, text="Signs: 0/3")
        self.hand_count_label.pack(side='right', padx=5)
        
        self.hand_sequence_label = ttk.Label(controls_frame, text="Sequence: []")
        self.hand_sequence_label.pack(pady=5)
        
        # Register button
        ttk.Button(controls_frame, text="Complete Registration", 
                  command=self.complete_registration).pack(pady=10, fill='x')
        
        # Status
        self.reg_status = ttk.Label(controls_frame, text="Status: Ready")
        self.reg_status.pack(pady=5)
        
        # Bottom section - preview frames
        bottom_frame = ttk.LabelFrame(main_frame, text="Captured Images Preview", padding=10)
        bottom_frame.pack(fill='both', expand=True, pady=10)
        
        # Face preview
        face_preview_frame = ttk.Frame(bottom_frame)
        face_preview_frame.pack(fill='x', pady=5)
        
        ttk.Label(face_preview_frame, text="Face Images:").pack(anchor='w')
        self.face_preview_container = ttk.Frame(face_preview_frame)
        self.face_preview_container.pack(fill='x', pady=5)
        
        # Hand preview
        hand_preview_frame = ttk.Frame(bottom_frame)
        hand_preview_frame.pack(fill='x', pady=5)
        
        ttk.Label(hand_preview_frame, text="Hand Sign Images:").pack(anchor='w')
        self.hand_preview_container = ttk.Frame(hand_preview_frame)
        self.hand_preview_container.pack(fill='x', pady=5)
    
    def setup_manage_tab(self):
        # User management tab
        main_frame = ttk.Frame(self.manage_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # User list
        list_frame = ttk.LabelFrame(main_frame, text="Registered Users", padding=10)
        list_frame.pack(fill='both', expand=True, pady=10)
        
        # Treeview for users
        columns = ('ID', 'Username', 'Email', 'Registered')
        self.user_tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        for col in columns:
            self.user_tree.heading(col, text=col)
            self.user_tree.column(col, width=100)
        
        self.user_tree.pack(fill='both', expand=True)
        
        # Management controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill='x', pady=10)
        
        ttk.Button(controls_frame, text="Refresh List", 
                  command=self.refresh_user_list).pack(side='left', padx=5)
        
        ttk.Button(controls_frame, text="Export User Data", 
                  command=self.export_user_data).pack(side='left', padx=5)
        
        ttk.Button(controls_frame, text="Delete User", 
                  command=self.delete_user).pack(side='right', padx=5)
        
        # Export area
        export_frame = ttk.LabelFrame(main_frame, text="Exported Data", padding=10)
        export_frame.pack(fill='both', expand=True, pady=10)
        
        self.export_text = scrolledtext.ScrolledText(export_frame, height=8)
        self.export_text.pack(fill='both', expand=True)
        
        # Load initial user list
        self.refresh_user_list()

    def start_camera(self):
        """Start camera using CameraManager"""
        self.camera_manager = CameraManager()
        if self.camera_manager.start_camera():
            self.is_capturing = True
            self.show_camera_feed()
        else:
            messagebox.showerror("Camera Error", "Could not start camera. Please check if camera is connected.")
            self.is_capturing = False

    def show_camera_feed(self):
        """Show camera feed using CameraUtils"""
        if self.is_capturing and self.camera_manager:
            frame = self.camera_manager.get_frame_with_overlay()
            
            if frame is not None:
                # Convert frame for display using CameraUtils
                tk_image = CameraUtils.frame_to_tk_image(frame, width=400, height=300)
                
                if tk_image:
                    # Update both camera feeds
                    self.login_video_frame.configure(image=tk_image)
                    self.login_video_frame.image = tk_image  # Keep reference
                    
                    self.register_video_frame.configure(image=tk_image)
                    self.register_video_frame.image = tk_image  # Keep reference
                    
                    self.current_frame = frame
            
            self.root.after(10, self.show_camera_feed)

    def capture_face_image(self):
        """Capture face image with preprocessing"""
        if self.current_frame is not None and len(self.captured_face_images) < 3:
            # Preprocess the image for better face recognition
            processed_frame = CameraUtils.preprocess_face_image(self.current_frame)
            self.captured_face_images.append(processed_frame)
            self.face_count_label.config(text=f"Faces: {len(self.captured_face_images)}/3")
            self.update_face_previews()
            messagebox.showinfo("Success", f"Face image {len(self.captured_face_images)} captured!")
        else:
            messagebox.showwarning("Warning", "Maximum 3 face images allowed")

    def capture_hand_image(self):
        """Capture hand image with preprocessing"""
        if self.current_frame is not None and len(self.captured_hand_images) < 3:
            # Preprocess the image for better hand detection
            processed_frame = CameraUtils.preprocess_hand_image(self.current_frame)
            
            # Detect hand and recognize gesture
            hand_landmarks_list = self.hand_detector.detect_hands(processed_frame)
            if hand_landmarks_list:
                landmarks = self.hand_detector.extract_landmarks(hand_landmarks_list[0])
                gesture = self.hand_detector.recognize_gesture(landmarks)
                
                self.captured_hand_images.append(processed_frame)
                self.current_hand_sequence.append(gesture)
                
                self.hand_count_label.config(text=f"Signs: {len(self.captured_hand_images)}/3")
                self.hand_sequence_label.config(text=f"Sequence: {self.current_hand_sequence}")
                self.update_hand_previews()
                
                messagebox.showinfo("Success", 
                                  f"Hand sign captured: {gesture}\nSequence: {self.current_hand_sequence}")
            else:
                messagebox.showerror("Error", "No hand detected in the frame")
        else:
            messagebox.showwarning("Warning", "Maximum 3 hand signs allowed")

    def update_face_previews(self):
        """Update face image previews in the GUI"""
        # Clear existing previews
        for widget in self.face_preview_container.winfo_children():
            widget.destroy()
        
        # Show captured face images as thumbnails
        for i, img in enumerate(self.captured_face_images):
            # Create thumbnail
            thumbnail = CameraUtils.resize_frame(img, width=80, height=80)
            if thumbnail is not None:
                tk_image = CameraUtils.frame_to_tk_image(thumbnail)
                if tk_image:
                    frame = ttk.Frame(self.face_preview_container)
                    frame.pack(side='left', padx=5)
                    
                    label = ttk.Label(frame, image=tk_image)
                    label.image = tk_image  # Keep reference
                    label.pack()
                    
                    # Add image number
                    ttk.Label(frame, text=f"Face {i+1}").pack()

    def update_hand_previews(self):
        """Update hand image previews in the GUI"""
        # Clear existing previews
        for widget in self.hand_preview_container.winfo_children():
            widget.destroy()
        
        # Show captured hand images as thumbnails
        for i, (img, gesture) in enumerate(zip(self.captured_hand_images, self.current_hand_sequence)):
            # Create thumbnail
            thumbnail = CameraUtils.resize_frame(img, width=80, height=80)
            if thumbnail is not None:
                tk_image = CameraUtils.frame_to_tk_image(thumbnail)
                if tk_image:
                    frame = ttk.Frame(self.hand_preview_container)
                    frame.pack(side='left', padx=5)
                    
                    label = ttk.Label(frame, image=tk_image)
                    label.image = tk_image  # Keep reference
                    label.pack()
                    
                    # Add gesture label
                    ttk.Label(frame, text=f"Sign {i+1}: {gesture}").pack()

    def complete_registration(self):
        username = self.username_entry.get()
        email = self.email_entry.get()
        
        if not username or not email:
            messagebox.showerror("Error", "Please enter username and email")
            return
        
        if len(self.captured_face_images) < 1:
            messagebox.showerror("Error", "Please capture at least 1 face image")
            return
        
        if len(self.captured_hand_images) < 3:
            messagebox.showerror("Error", "Please capture 3 hand signs")
            return
        
        try:
            # Process face registration
            face_encoding = None
            if self.captured_face_images:
                face_encoding = self.face_detector.extract_features(self.captured_face_images[0])
                if face_encoding is not None:
                    self.face_detector.register_face(username, [self.captured_face_images[0]])
            
            # Register user
            user_data = {"username": username, "email": email}
            user_id = self.user_controller.create_user(user_data, face_encoding, self.current_hand_sequence)
            
            messagebox.showinfo("Success", f"User {username} registered successfully!\nUser ID: {user_id}")
            
            # Reset form
            self.reset_registration_form()
            self.refresh_user_list()
            
        except Exception as e:
            messagebox.showerror("Error", f"Registration failed: {str(e)}")

    def reset_registration_form(self):
        self.username_entry.delete(0, tk.END)
        self.email_entry.delete(0, tk.END)
        self.captured_face_images = []
        self.captured_hand_images = []
        self.current_hand_sequence = []
        self.face_count_label.config(text="Faces: 0/3")
        self.hand_count_label.config(text="Signs: 0/3")
        self.hand_sequence_label.config(text="Sequence: []")
        
        # Clear previews
        for widget in self.face_preview_container.winfo_children():
            widget.destroy()
        for widget in self.hand_preview_container.winfo_children():
            widget.destroy()

    def start_face_login(self):
        if self.current_frame is not None:
            self.login_status.config(text="Status: Scanning face...", foreground='orange')
            self.root.update()
            
            # Preprocess frame for better face detection
            processed_frame = CameraUtils.preprocess_face_image(self.current_frame)
            
            # Detect and recognize face
            face_locations, face_encodings = self.face_detector.detect_faces(processed_frame)
            
            if face_encodings:
                user_id = self.face_detector.match_face(face_encodings[0])
                if user_id:
                    self.login_status.config(text=f"Status: Face recognized - User: {user_id}", 
                                           foreground='green')
                    self.add_login_history(f"Face recognition successful for user {user_id}")
                else:
                    self.login_status.config(text="Status: Face not recognized", 
                                           foreground='red')
                    self.add_login_history("Face recognition failed - unknown user")
            else:
                self.login_status.config(text="Status: No face detected", 
                                       foreground='red')
                self.add_login_history("No face detected")

    def start_hand_login(self):
        if self.current_frame is not None:
            self.login_status.config(text="Status: Verifying hand sequence...", foreground='orange')
            self.root.update()
            
            # Preprocess frame for better hand detection
            processed_frame = CameraUtils.preprocess_hand_image(self.current_frame)
            
            hand_landmarks_list = self.hand_detector.detect_hands(processed_frame)
            if hand_landmarks_list:
                landmarks = self.hand_detector.extract_landmarks(hand_landmarks_list[0])
                gesture = self.hand_detector.recognize_gesture(landmarks)
                
                self.login_status.config(text=f"Status: Hand sign detected: {gesture}", 
                                       foreground='blue')
                self.add_login_history(f"Hand sign detected: {gesture}")
            else:
                self.login_status.config(text="Status: No hand detected", 
                                       foreground='red')
                self.add_login_history("No hand detected")

    def full_authentication(self):
        """Perform both face and hand authentication"""
        self.login_status.config(text="Status: Starting full authentication...", foreground='orange')
        self.add_login_history("Starting full authentication...")
        
        # Perform face authentication first
        self.start_face_login()
        
        # Then perform hand authentication after a delay
        self.root.after(2000, self.start_hand_login)

    def add_login_history(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.login_history_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.login_history_text.see(tk.END)

    def refresh_user_list(self):
        # Clear existing items
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        
        # Fetch users from database
        users = self.db_service.get_all_users()
        for user in users:
            self.user_tree.insert('', tk.END, values=(
                user['id'], 
                user['username'], 
                user['email'],
                user['created_at'][:10] if 'created_at' in user else 'N/A'
            ))

    def export_user_data(self):
        selected = self.user_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a user to export")
            return
        
        user_id = self.user_tree.item(selected[0])['values'][0]
        
        try:
            exported_data = self.user_controller.export_user_data(user_id, "json")
            self.export_text.delete(1.0, tk.END)
            self.export_text.insert(tk.END, exported_data)
            messagebox.showinfo("Success", f"User {user_id} data exported successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def delete_user(self):
        selected = self.user_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a user to delete")
            return
        
        user_id = self.user_tree.item(selected[0])['values'][0]
        username = self.user_tree.item(selected[0])['values'][1]
        
        if messagebox.askyesno("Confirm Delete", 
                             f"Are you sure you want to delete user '{username}'? This action cannot be undone."):
            try:
                success = self.user_controller.delete_user(user_id)
                if success:
                    messagebox.showinfo("Success", f"User {username} deleted successfully!")
                    self.refresh_user_list()
                else:
                    messagebox.showerror("Error", "Failed to delete user")
            except Exception as e:
                messagebox.showerror("Error", f"Delete failed: {str(e)}")

    def __del__(self):
        if self.camera_manager:
            self.camera_manager.stop_camera()

if __name__ == "__main__":
    root = tk.Tk()
    app = AuthApplicationGUI(root)
    root.mainloop()