# ui/main_frame.py

import wx
from .user_panel import UserPanel
from .admin_panel import AdminPanel
from .history_panel import HistoryPanel

# A simple hardcoded admin password.
# In a real app, this should be hashed/salted in the database.
ADMIN_PASSWORD = "admin"

class MainFrame(wx.Frame):
    def __init__(self, parent, title, user_m, login_m, att_m, db_m, qr_h):
        wx.Frame.__init__(self, parent, title=title, size=(800, 700))
        
        self.db = db_m
        self.admin_locked = True
        
        # --- Reset all login statuses on startup ---
        self.db.force_logout_all()
        
        # --- Create Notebook (Tabbed Interface) ---
        self.notebook = wx.Notebook(self)
        
        # --- Panel 1: User Login ---
        self.user_panel = UserPanel(self.notebook, user_m, login_m, qr_h)
        self.notebook.AddPage(self.user_panel, "Login")
        
        # --- Panel 2: Login History ---
        self.history_panel = HistoryPanel(self.notebook, db_m, att_m)
        self.notebook.AddPage(self.history_panel, "History")
        
        # --- Panel 3: Admin Panel ---
        self.admin_panel = AdminPanel(self.notebook, user_m, att_m, db_m, qr_h)
        self.notebook.AddPage(self.admin_panel, "Admin")
        
        # --- Sizer ---
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)
        
        # --- Bindings ---
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGING, self.on_tab_changing)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        self.CreateStatusBar()
        self.SetStatusText("Welcome to the Secure QR Login System")

    def on_tab_changing(self, event):
        old_sel = event.GetOldSelection()
        new_sel = event.GetSelection()
        
        # --- Stop camera if leaving User Panel ---
        if old_sel == 0 and self.user_panel:
            self.user_panel.stop_panel_camera()
            
        # --- Admin Panel Protection ---
        if new_sel == 2: # Index 2 is Admin
            if self.admin_locked:
                dlg = wx.PasswordEntryDialog(self, "Enter Admin Password:", "Admin Access")
                
                if dlg.ShowModal() == wx.ID_OK:
                    password = dlg.GetValue()
                    if password == ADMIN_PASSWORD:
                        self.admin_locked = False
                        self.SetStatusText("Admin access granted.")
                        event.Skip() # Allow tab change
                    else:
                        wx.MessageBox("Incorrect Password", "Access Denied", wx.OK | wx.ICON_ERROR)
                        event.Veto() # Prevent tab change
                else:
                    event.Veto() # User cancelled
                
                dlg.Destroy()
            else:
                event.Skip() # Already unlocked
                
    def on_close(self, event):
        """Ensure camera is off before closing."""
        try:
            self.user_panel.stop_panel_camera()
        except Exception as e:
            print(f"Error stopping camera on close: {e}")
        finally:
            self.Destroy()