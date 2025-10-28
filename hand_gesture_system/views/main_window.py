import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from PIL import Image, ImageTk
import cv2
from datetime import datetime
import threading
import pandas as pd

class MainWindow:
    def __init__(self, root, db_manager, face_system, gesture_detector):
        self.root = root
        self.db = db_manager
        self.face_system = face_system
        self.gesture_detector = gesture_detector
        
        self.current_user = None
        self.log_visible = True
        self.live_camera_running = False
        
        self.setup_ui()
        self.update_status()
        self.refresh_user_list()
        self.start_live_camera_feed()

    def setup_ui(self):
        self.root.title("Employee Hand Gesture Login System")
        self.root.geometry("1400x800")
        self.root.configure(bg="#2c3e50")
        
        self.create_header()
        self.create_status_bar()
        self.create_control_bar()
        self.create_main_container()
        self.create_actions_panel()

    def create_header(self):
        header = tk.Frame(self.root, bg="#34495e", height=80)
        header.pack(fill=tk.X)
        
        title = tk.Label(header, text="🔐 Employee Hand Gesture Login System", 
                        font=("Arial", 24, "bold"), bg="#34495e", fg="white")
        title.pack(pady=20)

    def create_status_bar(self):
        self.status_frame = tk.Frame(self.root, bg="#1abc9c", height=50)
        self.status_frame.pack(fill=tk.X)
        
        self.status_label = tk.Label(self.status_frame, text="Status: Ready", 
                                     font=("Arial", 12), bg="#1abc9c", fg="white")
        self.status_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.user_label = tk.Label(self.status_frame, text="Not logged in", 
                                   font=("Arial", 12, "bold"), bg="#1abc9c", fg="white")
        self.user_label.pack(side=tk.RIGHT, padx=20, pady=10)

    def create_control_bar(self):
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

    def create_main_container(self):
        self.main_container = tk.Frame(self.root, bg="#2c3e50")
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.create_left_panel()
        self.create_center_panel()
        self.create_right_panel()

    def create_left_panel(self):
        self.left_panel = tk.Frame(self.main_container, bg="#34495e", width=300)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        
        tk.Label(self.left_panel, text="👥 Registered Users", font=("Arial", 16, "bold"), 
                bg="#34495e", fg="white").pack(pady=15)
        
        user_list_frame = tk.Frame(self.left_panel, bg="#2c3e50")
        user_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.user_tree = ttk.Treeview(user_list_frame, columns=("Name", "Status"), show="headings", height=15)
        self.user_tree.pack(fill=tk.BOTH, expand=True)
        
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

    def create_center_panel(self):
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

    def create_right_panel(self):
        self.right_panel = tk.Frame(self.main_container, bg="#bdc3c7", width=400)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH)
        
        self.create_log_widgets()

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

    def create_actions_panel(self):
        self.actions_panel = tk.Frame(self.center_panel, bg="#ecf0f1")
        self.actions_panel.pack(fill=tk.X, padx=10, pady=10)
        
        self.create_registration_section()
        self.create_quick_actions_section()

    def create_registration_section(self):
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

    def create_quick_actions_section(self):
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

    # All the other methods (start_live_camera_feed, update_frame, toggle_live_camera, etc.)
    # should be copied from the previous working version
    
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
            users = self.db.get_all_users()
            
            # Get currently logged in users
            logged_in_users = self.db.get_logged_in_users()
            
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
        user = self.db.get_user(emp_id)
        if not user:
            messagebox.showerror("Error", "User not found")
            return
        
        name = user.get("name", emp_id)
        
        if messagebox.askyesno("Confirm Logout", f"Manually logout {name} ({emp_id})?"):
            try:
                self.db.log_attendance(emp_id, name, "LOGOUT", "manual")
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
            user = self.db.get_user(self.current_user)
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
        emp_id = self.db.generate_employee_id()
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
        existing_user = self.db.get_user(emp_id)
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
                # Update database and reload faces
                self.db.create_user(emp_id, name)
                users = self.db.get_all_users()
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
                # After wave detection, start face recognition
                self.root.after(0, self.face_login)
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", message))
        
        thread = threading.Thread(target=self.gesture_detector.detect_wave_gesture, 
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
                # Log the attendance
                user = self.db.get_user(emp_id)
                if user:
                    self.db.log_attendance(emp_id, user.get("name", emp_id), "LOGIN", "face")
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
            user = self.db.get_user(self.current_user)
            name = user.get("name", self.current_user) if user else self.current_user
            self.db.log_attendance(self.current_user, name, "LOGOUT", "gesture")
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
            records = self.db.get_attendance_records(emp_id)
            
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
            records = self.db.get_attendance_records()
            
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
        cv2.destroyAllWindows()