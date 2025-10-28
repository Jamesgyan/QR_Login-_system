# gui/user_panel.py
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2
import threading
import time
from gui.gui_utils import show_info, show_error

class UserPanel(ttk.Frame):
    def __init__(self, master, auth_manager, qr_handler):
        super().__init__(master)
        self.auth_manager = auth_manager
        self.qr_handler = qr_handler
        
        self.cap = None
        self.camera_running = False
        self.last_scan_time = 0
        self.scan_cooldown = 3 # 3 seconds cooldown
        
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(expand=True, fill='both')
        
        # --- Left Side: QR Camera ---
        qr_frame = ttk.LabelFrame(main_frame, text="QR Code Scanner", padding=10)
        qr_frame.pack(side='left', fill='both', expand=True, padx=10)
        
        self.camera_label = ttk.Label(qr_frame, text="Camera is Off",
                                      anchor='center', relief='solid',
                                      background='black', foreground='white')
        self.camera_label.pack(fill='both', expand=True, pady=5)
        
        cam_btn_frame = ttk.Frame(qr_frame)
        cam_btn_frame.pack(fill='x', pady=5)
        
        self.start_btn = ttk.Button(cam_btn_frame, text="Start Camera", command=self.start_camera)
        self.start_btn.pack(side='left', expand=True, fill='x', padx=5)
        
        self.stop_btn = ttk.Button(cam_btn_frame, text="Stop Camera", command=self.stop_camera, state='disabled')
        self.stop_btn.pack(side='left', expand=True, fill='x', padx=5)

        # --- Right Side: Manual Login ---
        manual_frame = ttk.LabelFrame(main_frame, text="Manual Login / Logout", padding=10)
        manual_frame.pack(side='right', fill='y', padx=10)

        ttk.Label(manual_frame, text="Employee ID:").grid(row=0, column=0, sticky='w', pady=5)
        self.emp_id_entry = ttk.Entry(manual_frame, width=30)
        self.emp_id_entry.grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(manual_frame, text="Password:").grid(row=1, column=0, sticky='w', pady=5)
        self.pass_entry = ttk.Entry(manual_frame, width=30, show='*')
        self.pass_entry.grid(row=1, column=1, pady=5, padx=5)

        # --- BUTTONS UPDATED ---
        login_btn = ttk.Button(manual_frame, text="Login", command=self.manual_login)
        login_btn.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(10, 5)) # Added padding
        
        # New Logout Button
        logout_btn = ttk.Button(manual_frame, text="Logout", command=self.manual_logout)
        logout_btn.grid(row=3, column=0, columnspan=2, sticky='ew', pady=5)
        
        # Clear button moved down
        clear_btn = ttk.Button(manual_frame, text="Clear", command=self.clear_form)
        clear_btn.grid(row=4, column=0, columnspan=2, sticky='ew', pady=5)
        # --- END OF BUTTON UPDATES ---

    def manual_login(self):
        emp_id = self.emp_id_entry.get()
        password = self.pass_entry.get()
        
        if not emp_id or not password:
            show_error("Login Error", "Please enter both Employee ID and Password.")
            return
            
        result = self.auth_manager.handle_manual_login(emp_id, password)
        
        if result.startswith("Success"):
            show_info("Login Success", result)
            self.clear_form()
        else:
            show_error("Login Failed", result)

    # --- ADD THIS NEW FUNCTION ---
    def manual_logout(self):
        emp_id = self.emp_id_entry.get()
        password = self.pass_entry.get()
        
        if not emp_id or not password:
            show_error("Logout Error", "Please enter both Employee ID and Password to log out.")
            return
            
        result = self.auth_manager.handle_manual_logout(emp_id, password)
        
        if result.startswith("Success"):
            show_info("Logout Success", result)
            self.clear_form()
        else:
            show_error("Logout Failed", result)
    # --- END OF NEW FUNCTION ---

    def clear_form(self):
        self.emp_id_entry.delete(0, 'end')
        self.pass_entry.delete(0, 'end')

    def start_camera(self):
        if self.camera_running:
            return
            
        try:
            self.cap = cv2.VideoCapture(0) # 0 is default webcam
            if not self.cap.isOpened():
                raise Exception("Cannot open webcam.")
            self.camera_running = True
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='normal')
            
            # Start camera feed in a new thread
            self.thread = threading.Thread(target=self.update_camera_feed, daemon=True)
            self.thread.start()
        except Exception as e:
            show_error("Camera Error", f"Failed to start camera: {e}")
            self.cap = None

    def stop_camera(self):
        self.camera_running = False
        if self.cap:
            self.cap.release()
        self.cap = None
        
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.camera_label.config(image=None, text="Camera is Off", background='black')
        self.camera_label.image = None

    def update_camera_feed(self):
        while self.camera_running and self.cap:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue
                
                # --- QR Scanning Logic ---
                current_time = time.time()
                if current_time - self.last_scan_time > self.scan_cooldown:
                    qr_data = self.qr_handler.scan_qr_from_frame(frame)
                    if qr_data:
                        self.last_scan_time = current_time
                        self.handle_scanned_qr(qr_data)
                # --- End Scanning Logic ---

                # Convert frame for Tkinter
                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(img_rgb)
                img_tk = ImageTk.PhotoImage(image=img_pil)
                
                # Update label in main thread
                self.camera_label.after(0, self.update_label_image, img_tk)
                
                time.sleep(1/30) # ~30 fps

            except Exception as e:
                print(f"Camera feed error: {e}")
                self.stop_camera()
                break
        
        # Ensure camera stops properly when loop exits
        if not self.camera_running:
            self.camera_label.after(0, self.stop_camera)

    def update_label_image(self, img_tk):
        """Safely updates the camera label from the main thread."""
        if self.camera_running:
            self.camera_label.config(image=img_tk, text="")
            self.camera_label.image = img_tk # Keep a reference
            
    def handle_scanned_qr(self, qr_data):
        """Handles the QR data; shows popup in main thread."""
        result = self.auth_manager.handle_qr_login_toggle(qr_data)
        
        if result.startswith("Success"):
            self.camera_label.after(0, show_info, "QR Scan Success", result)
        else:
            self.camera_label.after(0, show_error, "QR Scan Failed", result)