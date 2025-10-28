# ui/user_panel.py

import wx
from .camera_panel import CameraPanel

class UserPanel(wx.Panel):
    def __init__(self, parent, user_manager, login_manager, qr_handler):
        wx.Panel.__init__(self, parent)
        
        self.user_m = user_manager
        self.login_m = login_manager
        
        # --- Main Sizer ---
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # --- QR Code Section ---
        qr_box = wx.StaticBox(self, label="QR Code Login")
        qr_sizer = wx.StaticBoxSizer(qr_box, wx.VERTICAL)
        
        self.camera_panel = CameraPanel(self, qr_handler, self.on_qr_decoded)
        qr_sizer.Add(self.camera_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        qr_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_cam_btn = wx.Button(self, label="Start Camera")
        self.stop_cam_btn = wx.Button(self, label="Stop Camera")
        self.stop_cam_btn.Disable()
        qr_btn_sizer.Add(self.start_cam_btn, 1, wx.RIGHT, 5)
        qr_btn_sizer.Add(self.stop_cam_btn, 1, wx.LEFT, 5)
        qr_sizer.Add(qr_btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(qr_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # --- Manual Login Section ---
        manual_box = wx.StaticBox(self, label="Manual Login")
        manual_sizer = wx.StaticBoxSizer(manual_box, wx.VERTICAL)
        
        grid_sizer = wx.FlexGridSizer(2, 2, 5, 5) # 2 rows, 2 cols, 5px gaps
        grid_sizer.AddGrowableCol(1)
        
        grid_sizer.Add(wx.StaticText(self, label="Employee ID:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.emp_id_ctrl = wx.TextCtrl(self)
        grid_sizer.Add(self.emp_id_ctrl, 1, wx.EXPAND)
        
        grid_sizer.Add(wx.StaticText(self, label="Password:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.pw_ctrl = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        grid_sizer.Add(self.pw_ctrl, 1, wx.EXPAND)
        
        manual_sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        manual_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.login_btn = wx.Button(self, label="Login")
        self.logout_btn = wx.Button(self, label="Logout")
        self.clear_btn = wx.Button(self, label="Clear")
        manual_btn_sizer.Add(self.login_btn, 1, wx.RIGHT, 5)
        manual_btn_sizer.Add(self.logout_btn, 1, wx.RIGHT, 5)
        manual_btn_sizer.Add(self.clear_btn, 1)
        manual_sizer.Add(manual_btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        main_sizer.Add(manual_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # --- Status Section ---
        status_box = wx.StaticBox(self, label="Status")
        status_sizer = wx.StaticBoxSizer(status_box, wx.VERTICAL)
        
        self.status_text = wx.StaticText(self, label="Status: Ready. Please scan QR or log in manually.")
        font = self.status_text.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.status_text.SetFont(font)
        status_sizer.Add(self.status_text, 1, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(status_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # --- Bindings ---
        self.start_cam_btn.Bind(wx.EVT_BUTTON, self.on_start_camera)
        self.stop_cam_btn.Bind(wx.EVT_BUTTON, self.on_stop_camera)
        self.login_btn.Bind(wx.EVT_BUTTON, self.on_manual_login)
        self.logout_btn.Bind(wx.EVT_BUTTON, self.on_manual_logout)
        self.clear_btn.Bind(wx.EVT_BUTTON, self.on_clear)
        
        self.SetSizer(main_sizer)

    def on_start_camera(self, event):
        if self.camera_panel.start_camera():
            self.start_cam_btn.Disable()
            self.stop_cam_btn.Enable()
            self.set_status("Camera started. Please scan your QR code.", "blue")

    def on_stop_camera(self, event):
        self.camera_panel.stop_camera()
        self.start_cam_btn.Enable()
        self.stop_cam_btn.Disable()
        self.set_status("Camera stopped.", "black")
        
    def on_qr_decoded(self, qr_data):
        """Callback from CameraPanel when a QR is successfully decoded."""
        self.start_cam_btn.Enable()
        self.stop_cam_btn.Disable()
        
        user_id = qr_data.get('user_id')
        emp_id = qr_data.get('employee_id')
        
        if not user_id:
            self.set_status("Invalid QR Code.", "red")
            return
            
        action, name, message = self.login_m.handle_qr_login(user_id)
        
        if action == 'login':
            self.set_status(f"Welcome, {name}! You are now logged in.", "green")
        elif action == 'logout':
            self.set_status(f"Goodbye, {name}! You are now logged out.", "orange")
        else: # Error
            self.set_status(f"Error for {name}: {message}", "red")

    def on_manual_login(self, event):
        emp_id = self.emp_id_ctrl.GetValue().strip()
        password = self.pw_ctrl.GetValue()
        
        if not emp_id or not password:
            self.set_status("Employee ID and Password are required.", "red")
            return
            
        user = self.user_m.authenticate_user(emp_id, password)
        
        if not user:
            self.set_status("Invalid Employee ID or Password.", "red")
            return
            
        # User is valid, now try to log them in
        action, name, message = self.login_m.perform_login(user['id'])
        
        if action == 'login':
            self.set_status(f"Welcome, {name}! You are now logged in.", "green")
        else: # Error (e.g., already logged in)
            self.set_status(f"Error: {message}", "red")

    def on_manual_logout(self, event):
        emp_id = self.emp_id_ctrl.GetValue().strip()
        password = self.pw_ctrl.GetValue()
        
        if not emp_id or not password:
            self.set_status("Employee ID and Password are required to log out.", "red")
            return
            
        # We must authenticate before logging out for security
        user = self.user_m.authenticate_user(emp_id, password)
        
        if not user:
            self.set_status("Invalid Employee ID or Password.", "red")
            return

        # User is valid, now try to log them out
        action, name, message = self.login_m.perform_logout(user['id'])
        
        if action == 'logout':
            self.set_status(f"Goodbye, {name}! You are now logged out.", "orange")
        else: # Error (e.g., already logged out)
            self.set_status(f"Error: {message}", "red")
            
    def on_clear(self, event):
        self.emp_id_ctrl.Clear()
        self.pw_ctrl.Clear()
        self.set_status("Fields cleared.", "black")

    def set_status(self, text, color):
        """Updates the status text with a given color."""
        self.status_text.SetLabel(text)
        color_map = {
            "red": wx.Colour(200, 0, 0),
            "green": wx.Colour(0, 150, 0),
            "blue": wx.Colour(0, 0, 150),
            "orange": wx.Colour(255, 100, 0),
            "black": wx.SystemSettings.GetColour(wx.SYS_COLOUR_STATICTEXT)
        }
        self.status_text.SetForegroundColour(color_map.get(color, "black"))
        
    def stop_panel_camera(self):
        """Public method for MainFrame to call when tab changes."""
        self.camera_panel.stop_camera()
        self.start_cam_btn.Enable()
        self.stop_cam_btn.Disable()