# gui/main_app.py
import tkinter as tk
from tkinter import ttk
from gui.user_panel import UserPanel
from gui.admin_panel import AdminPanel
from gui.history_panel import HistoryPanel
from gui.gui_utils import setup_style

class MainApplication(tk.Tk):
    def __init__(self, db_manager, user_manager, auth_manager, qr_handler):
        super().__init__()
        
        self.title("Secure QR Login & Attendance System")
        self.geometry("1000x700")
        
        # Set the custom style
        setup_style()
        
        # --- Create main notebook ---
        notebook = ttk.Notebook(self)
        
        # --- Create tabs ---
        self.user_panel = UserPanel(notebook, auth_manager, qr_handler)
        self.admin_panel = AdminPanel(notebook, db_manager, user_manager, auth_manager)
        self.history_panel = HistoryPanel(notebook, db_manager)
        
        # --- Add tabs to notebook ---
        notebook.add(self.user_panel, text="User Panel")
        notebook.add(self.admin_panel, text="Admin Panel")
        notebook.add(self.history_panel, text="Login History")
        
        notebook.pack(expand=True, fill='both', padx=10, pady=10)
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """Handle window close event."""
        # Stop camera if it's running
        if self.user_panel.camera_running:
            self.user_panel.stop_camera()
        
        # Clean up QR window if open
        if self.admin_panel.qr_window and self.admin_panel.qr_window.winfo_exists():
            self.admin_panel.qr_window.destroy()
            
        self.destroy()