import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import cv2
from PIL import Image, ImageTk
from datetime import datetime
import numpy as np

class HandGestureLoginSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("Employee Hand Gesture Login System")
        self.root.geometry("1000x700")

        self.setup_ui()
        self.start_live_camera()

    def setup_ui(self):
        # Left panel - Live camera feed
        self.center_panel = tk.Frame(self.root, bg="#ecf0f1")
        self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.camera_label = tk.Label(self.center_panel)
        self.camera_label.pack(padx=10, pady=10)

        # Right panel - Activity log
        self.right_panel = tk.Frame(self.root, width=300, bg="#bdc3c7")
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH)

        # Top panel - Controls
        control_frame = tk.Frame(self.root, bg="#2c3e50", height=50)
        control_frame.pack(side=tk.TOP, fill=tk.X)

        # Activity Log OptionMenu
        self.log_option_var = tk.StringVar(value="Show Log")
        log_options = ["Show Log", "Hide Log"]
        self.log_option_menu = tk.OptionMenu(control_frame, self.log_option_var, *log_options, command=self.handle_log_option)
        self.log_option_menu.config(font=("Arial", 10), bg="#3498db", fg="white", cursor="hand2")
        self.log_option_menu.pack(side=tk.LEFT, padx=5, pady=5)

        # Initialize log widgets
        self.create_log_widgets()

    def create_log_widgets(self):
        self.log_text = scrolledtext.ScrolledText(self.right_panel, width=40, height=40, state=tk.DISABLED, font=("Arial", 10))
        self.log_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    def handle_log_option(self, selection):
        """Show or hide activity log based on dropdown"""
        if selection == "Show Log":
            self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH)
            self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        else:  # Hide Log
            self.right_panel.pack_forget()
            self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

    def start_live_camera(self):
        self.cap = cv2.VideoCapture(0)
        self.update_frame()

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            # Convert color and resize for Tkinter
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (640, 480))
            img = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.camera_label.imgtk = imgtk
            self.camera_label.configure(image=imgtk)

            # Here you can integrate your hand gesture detection for login/logout
            # Example: detect_fist_sign(frame) -> log login/logout
            # self.log("Detected login") or self.log("Detected logout")

        self.root.after(10, self.update_frame)  # Keep updating frames

    def log(self, message):
        """Append a message to activity log"""
        if not hasattr(self, 'log_text'):
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def __del__(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()

if __name__ == "__main__":
    root = tk.Tk()
    app = HandGestureLoginSystem(root)
    root.mainloop()
