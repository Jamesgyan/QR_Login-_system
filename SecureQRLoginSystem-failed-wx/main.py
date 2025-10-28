# main.py

import wx
import config_manager as cfg
from database_manager import DatabaseManager
from security_manager import SecurityManager
from qr_handler import QRHandler
from logic.user_manager import UserManager
from logic.login_manager import LoginManager
from logic.attendance_manager import AttendanceManager
from ui.main_frame import MainFrame

class MainApp(wx.App):
    def OnInit(self):
        # 1. Set up directories
        try:
            cfg.setup_directories()
        except Exception as e:
            wx.MessageBox(f"Fatal Error: Could not create application directories.\n{e}",
                          "Initialization Error", wx.OK | wx.ICON_ERROR)
            return False

        # 2. Initialize all managers (the "backend")
        try:
            db_m = DatabaseManager(cfg.DB_PATH)
            sec_m = SecurityManager()
            qr_h = QRHandler(cfg.QR_DIR)
            login_m = LoginManager(db_m)
            att_m = AttendanceManager(db_m)
            user_m = UserManager(db_m, sec_m, qr_h, login_m)
        except Exception as e:
            wx.MessageBox(f"Fatal Error: Could not initialize managers.\n{e}",
                          "Initialization Error", wx.OK | wx.ICON_ERROR)
            return False

        # 3. Initialize the Main UI Frame
        self.frame = MainFrame(
            parent=None, 
            title="Secure QR Login & Attendance System",
            user_m=user_m,
            login_m=login_m,
            att_m=att_m,
            db_m=db_m,
            qr_h=qr_h
        )
        
        self.frame.SetMinSize((800, 700))
        self.frame.Center()
        self.frame.Show(True)
        return True

if __name__ == "__main__":
    app = MainApp()
    app.MainLoop()