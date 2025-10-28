"""
Secure QR Login System with Attendance Tracking
Complete implementation with all features
"""

import wx
import cv2
import qrcode
import sqlite3
import hashlib
import secrets
import json
import os
import sys
import csv
from datetime import datetime, timedelta
from pathlib import Path
import calendar as cal
from pyzbar.pyzbar import decode
import re

# ============================================================================
# Database Manager
# ============================================================================
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                is_logged_in INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Login history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Attendance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                status TEXT NOT NULL,
                login_time TEXT,
                logout_time TEXT,
                hours_worked REAL DEFAULT 0,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, date)
            )
        ''')
        
        # Events/Holidays table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_login_history_user ON login_history(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance(user_id, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_date ON events(date)')
        
        conn.commit()
        conn.close()

# ============================================================================
# Security Manager
# ============================================================================
class SecurityManager:
    @staticmethod
    def hash_password(password, salt=None):
        if salt is None:
            salt = secrets.token_hex(32)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return pwd_hash.hex(), salt
    
    @staticmethod
    def verify_password(password, password_hash, salt):
        pwd_hash, _ = SecurityManager.hash_password(password, salt)
        return pwd_hash == password_hash
    
    @staticmethod
    def validate_email(email):
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_phone(phone):
        return len(phone) == 10 and phone.isdigit()

# ============================================================================
# User Manager
# ============================================================================
class UserManager:
    def __init__(self, db_manager):
        self.db = db_manager
    
    def generate_employee_id(self, prefix="ALLY"):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT employee_id FROM users WHERE employee_id LIKE ? ORDER BY employee_id DESC LIMIT 1", (f"{prefix}%",))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            last_id = result[0]
            num = int(last_id[len(prefix):]) + 1
        else:
            num = 1
        
        return f"{prefix}{num:03d}"
    
    def add_user(self, name, email, phone, password):
        if not SecurityManager.validate_email(email):
            raise ValueError("Invalid email format")
        if not SecurityManager.validate_phone(phone):
            raise ValueError("Phone must be exactly 10 digits")
        
        employee_id = self.generate_employee_id()
        pwd_hash, salt = SecurityManager.hash_password(password)
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (employee_id, name, email, phone, password_hash, salt)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (employee_id, name, email, phone, pwd_hash, salt))
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            return employee_id, user_id
        except sqlite3.IntegrityError as e:
            conn.close()
            raise ValueError(f"User with this email already exists: {e}")
    
    def get_all_users(self):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, employee_id, name, email, phone, is_logged_in FROM users")
        users = cursor.fetchall()
        conn.close()
        return users
    
    def get_user_by_employee_id(self, employee_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE employee_id = ?", (employee_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    def reset_password(self, employee_id, new_password):
        pwd_hash, salt = SecurityManager.hash_password(new_password)
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = ?, salt = ? WHERE employee_id = ?", 
                      (pwd_hash, salt, employee_id))
        conn.commit()
        conn.close()
    
    def delete_user(self, employee_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE employee_id = ?", (employee_id,))
        conn.commit()
        conn.close()

# ============================================================================
# Login Manager
# ============================================================================
class LoginManager:
    def __init__(self, db_manager):
        self.db = db_manager
    
    def authenticate(self, employee_id, password):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash, salt FROM users WHERE employee_id = ?", (employee_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            user_id, pwd_hash, salt = result
            if SecurityManager.verify_password(password, pwd_hash, salt):
                return user_id
        return None
    
    def is_user_logged_in(self, user_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_logged_in FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] == 1 if result else False
    
    def login(self, user_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Update user status
        cursor.execute("UPDATE users SET is_logged_in = 1 WHERE id = ?", (user_id,))
        
        # Log the action
        cursor.execute("INSERT INTO login_history (user_id, action) VALUES (?, ?)", (user_id, "LOGIN"))
        
        # Mark attendance
        today = datetime.now().strftime("%Y-%m-%d")
        login_time = datetime.now().strftime("%H:%M:%S")
        cursor.execute('''
            INSERT OR REPLACE INTO attendance (user_id, date, status, login_time)
            VALUES (?, ?, ?, ?)
        ''', (user_id, today, "Present", login_time))
        
        conn.commit()
        conn.close()
    
    def logout(self, user_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Update user status
        cursor.execute("UPDATE users SET is_logged_in = 0 WHERE id = ?", (user_id,))
        
        # Log the action
        cursor.execute("INSERT INTO login_history (user_id, action) VALUES (?, ?)", (user_id, "LOGOUT"))
        
        # Update attendance
        today = datetime.now().strftime("%Y-%m-%d")
        logout_time = datetime.now().strftime("%H:%M:%S")
        
        cursor.execute("SELECT login_time FROM attendance WHERE user_id = ? AND date = ?", (user_id, today))
        result = cursor.fetchone()
        
        if result and result[0]:
            login_time = datetime.strptime(result[0], "%H:%M:%S")
            logout_dt = datetime.strptime(logout_time, "%H:%M:%S")
            hours_worked = (logout_dt - login_time).total_seconds() / 3600
            
            cursor.execute('''
                UPDATE attendance SET logout_time = ?, hours_worked = ?
                WHERE user_id = ? AND date = ?
            ''', (logout_time, hours_worked, user_id, today))
        
        conn.commit()
        conn.close()
    
    def force_logout(self, employee_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE employee_id = ?", (employee_id,))
        result = cursor.fetchone()
        if result:
            self.logout(result[0])
        conn.close()
    
    def get_login_history(self, user_id=None, start_date=None, end_date=None):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT lh.id, u.employee_id, u.name, lh.action, lh.timestamp
            FROM login_history lh
            JOIN users u ON lh.user_id = u.id
            WHERE 1=1
        '''
        params = []
        
        if user_id:
            query += " AND lh.user_id = ?"
            params.append(user_id)
        
        if start_date:
            query += " AND DATE(lh.timestamp) >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND DATE(lh.timestamp) <= ?"
            params.append(end_date)
        
        query += " ORDER BY lh.timestamp DESC"
        
        cursor.execute(query, params)
        history = cursor.fetchall()
        conn.close()
        return history

# ============================================================================
# QR Handler
# ============================================================================
class QRHandler:
    def __init__(self, qr_dir):
        self.qr_dir = Path(qr_dir)
        self.qr_dir.mkdir(exist_ok=True)
    
    def generate_qr(self, user_id, employee_id):
        data = json.dumps({"user_id": user_id, "employee_id": employee_id})
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        qr_path = self.qr_dir / f"{employee_id}.png"
        img.save(str(qr_path))
        return str(qr_path)
    
    def scan_qr(self, frame):
        decoded_objects = decode(frame)
        for obj in decoded_objects:
            try:
                data = json.loads(obj.data.decode('utf-8'))
                return data
            except:
                pass
        return None

# ============================================================================
# Attendance Manager
# ============================================================================
class AttendanceManager:
    def __init__(self, db_manager):
        self.db = db_manager
    
    def mark_leave(self, user_id, start_date, end_date, leave_type, notes=""):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            cursor.execute('''
                INSERT OR REPLACE INTO attendance (user_id, date, status, notes)
                VALUES (?, ?, ?, ?)
            ''', (user_id, date_str, leave_type, notes))
            current += timedelta(days=1)
        
        conn.commit()
        conn.close()
    
    def get_attendance(self, user_id=None, start_date=None, end_date=None):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT a.id, u.employee_id, u.name, a.date, a.status, 
                   a.login_time, a.logout_time, a.hours_worked, a.notes
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            WHERE 1=1
        '''
        params = []
        
        if user_id:
            query += " AND a.user_id = ?"
            params.append(user_id)
        
        if start_date:
            query += " AND a.date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND a.date <= ?"
            params.append(end_date)
        
        query += " ORDER BY a.date DESC"
        
        cursor.execute(query, params)
        attendance = cursor.fetchall()
        conn.close()
        return attendance
    
    def get_attendance_summary(self, user_id, month, year):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        start_date = f"{year}-{month:02d}-01"
        _, last_day = cal.monthrange(year, month)
        end_date = f"{year}-{month:02d}-{last_day}"
        
        cursor.execute('''
            SELECT status, COUNT(*) FROM attendance
            WHERE user_id = ? AND date BETWEEN ? AND ?
            GROUP BY status
        ''', (user_id, start_date, end_date))
        
        summary = dict(cursor.fetchall())
        conn.close()
        return summary

# ============================================================================
# Event Manager
# ============================================================================
class EventManager:
    def __init__(self, db_manager):
        self.db = db_manager
    
    def add_event(self, date, title, category, description=""):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO events (date, title, category, description)
            VALUES (?, ?, ?, ?)
        ''', (date, title, category, description))
        conn.commit()
        conn.close()
    
    def get_events(self, month=None, year=None):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        if month and year:
            start_date = f"{year}-{month:02d}-01"
            _, last_day = cal.monthrange(year, month)
            end_date = f"{year}-{month:02d}-{last_day}"
            cursor.execute("SELECT * FROM events WHERE date BETWEEN ? AND ?", (start_date, end_date))
        else:
            cursor.execute("SELECT * FROM events")
        
        events = cursor.fetchall()
        conn.close()
        return events
    
    def delete_event(self, event_id):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()

# ============================================================================
# User Panel
# ============================================================================
class UserPanel(wx.Panel):
    def __init__(self, parent, db_manager, login_manager, qr_handler):
        super().__init__(parent)
        self.db = db_manager
        self.login_manager = login_manager
        self.qr_handler = qr_handler
        self.camera = None
        self.camera_running = False
        
        self.init_ui()
    
    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Manual Login Section
        login_box = wx.StaticBox(self, label="Manual Login")
        login_sizer = wx.StaticBoxSizer(login_box, wx.VERTICAL)
        
        grid = wx.FlexGridSizer(3, 2, 10, 10)
        grid.AddGrowableCol(1)
        
        grid.Add(wx.StaticText(self, label="Employee ID:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.employee_id_ctrl = wx.TextCtrl(self)
        grid.Add(self.employee_id_ctrl, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(self, label="Password:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.password_ctrl = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        grid.Add(self.password_ctrl, 1, wx.EXPAND)
        
        login_sizer.Add(grid, 0, wx.ALL|wx.EXPAND, 10)
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.login_btn = wx.Button(self, label="Login")
        self.logout_btn = wx.Button(self, label="Logout")
        self.clear_btn = wx.Button(self, label="Clear")
        btn_sizer.Add(self.login_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.logout_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.clear_btn)
        login_sizer.Add(btn_sizer, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        main_sizer.Add(login_sizer, 0, wx.ALL|wx.EXPAND, 10)
        
        # QR Scanner Section
        qr_box = wx.StaticBox(self, label="QR Code Scanner")
        qr_sizer = wx.StaticBoxSizer(qr_box, wx.VERTICAL)
        
        self.camera_display = wx.StaticBitmap(self, size=(640, 480))
        qr_sizer.Add(self.camera_display, 1, wx.ALL|wx.EXPAND, 10)
        
        cam_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_cam_btn = wx.Button(self, label="Start Camera")
        self.stop_cam_btn = wx.Button(self, label="Stop Camera")
        self.stop_cam_btn.Enable(False)
        cam_btn_sizer.Add(self.start_cam_btn, 0, wx.RIGHT, 5)
        cam_btn_sizer.Add(self.stop_cam_btn)
        qr_sizer.Add(cam_btn_sizer, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        main_sizer.Add(qr_sizer, 1, wx.ALL|wx.EXPAND, 10)
        
        # Status Display
        self.status_text = wx.TextCtrl(self, style=wx.TE_MULTILINE|wx.TE_READONLY, size=(-1, 100))
        main_sizer.Add(self.status_text, 0, wx.ALL|wx.EXPAND, 10)
        
        self.SetSizer(main_sizer)
        
        # Bind events
        self.login_btn.Bind(wx.EVT_BUTTON, self.on_login)
        self.logout_btn.Bind(wx.EVT_BUTTON, self.on_logout)
        self.clear_btn.Bind(wx.EVT_BUTTON, self.on_clear)
        self.start_cam_btn.Bind(wx.EVT_BUTTON, self.on_start_camera)
        self.stop_cam_btn.Bind(wx.EVT_BUTTON, self.on_stop_camera)
    
    def on_login(self, event):
        employee_id = self.employee_id_ctrl.GetValue().strip()
        password = self.password_ctrl.GetValue()
        
        if not employee_id or not password:
            wx.MessageBox("Please enter both Employee ID and Password", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        user_id = self.login_manager.authenticate(employee_id, password)
        if user_id:
            if self.login_manager.is_user_logged_in(user_id):
                wx.MessageBox("You are already logged in!", "Info", wx.OK|wx.ICON_INFORMATION)
            else:
                self.login_manager.login(user_id)
                self.status_text.SetValue(f"Successfully logged in as {employee_id}")
                wx.MessageBox("Login successful!", "Success", wx.OK|wx.ICON_INFORMATION)
        else:
            wx.MessageBox("Invalid credentials", "Error", wx.OK|wx.ICON_ERROR)
    
    def on_logout(self, event):
        employee_id = self.employee_id_ctrl.GetValue().strip()
        
        if not employee_id:
            wx.MessageBox("Please enter Employee ID", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        user_manager = UserManager(self.db)
        user = user_manager.get_user_by_employee_id(employee_id)
        
        if user:
            user_id = user[0]
            if self.login_manager.is_user_logged_in(user_id):
                self.login_manager.logout(user_id)
                self.status_text.SetValue(f"Successfully logged out: {employee_id}")
                wx.MessageBox("Logout successful!", "Success", wx.OK|wx.ICON_INFORMATION)
            else:
                wx.MessageBox("You are not logged in!", "Info", wx.OK|wx.ICON_INFORMATION)
        else:
            wx.MessageBox("Invalid Employee ID", "Error", wx.OK|wx.ICON_ERROR)
    
    def on_clear(self, event):
        self.employee_id_ctrl.Clear()
        self.password_ctrl.Clear()
        self.status_text.Clear()
    
    def on_start_camera(self, event):
        try:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                raise Exception("Cannot open camera")
            
            self.camera_running = True
            self.start_cam_btn.Enable(False)
            self.stop_cam_btn.Enable(True)
            self.camera_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.on_camera_timer)
            self.camera_timer.Start(30)
        except Exception as e:
            wx.MessageBox(f"Camera error: {str(e)}", "Error", wx.OK|wx.ICON_ERROR)
    
    def on_stop_camera(self, event):
        self.camera_running = False
        if hasattr(self, 'camera_timer'):
            self.camera_timer.Stop()
        if self.camera:
            self.camera.release()
        self.camera_display.SetBitmap(wx.NullBitmap)
        self.start_cam_btn.Enable(True)
        self.stop_cam_btn.Enable(False)
    
    def on_camera_timer(self, event):
        if self.camera and self.camera_running:
            ret, frame = self.camera.read()
            if ret:
                # Scan for QR code
                qr_data = self.qr_handler.scan_qr(frame)
                if qr_data:
                    self.handle_qr_login(qr_data)
                
                # Display frame
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = frame.shape[:2]
                image = wx.Image(w, h, frame.tobytes())
                self.camera_display.SetBitmap(wx.Bitmap(image))
    
    def handle_qr_login(self, qr_data):
        try:
            user_id = qr_data.get('user_id')
            employee_id = qr_data.get('employee_id')
            
            if self.login_manager.is_user_logged_in(user_id):
                self.login_manager.logout(user_id)
                self.status_text.SetValue(f"QR Logout: {employee_id}")
            else:
                self.login_manager.login(user_id)
                self.status_text.SetValue(f"QR Login: {employee_id}")
        except Exception as e:
            self.status_text.SetValue(f"QR Error: {str(e)}")

# ============================================================================
# Admin Panel
# ============================================================================
class AdminPanel(wx.Panel):
    def __init__(self, parent, db_manager, login_manager, qr_handler):
        super().__init__(parent)
        self.db = db_manager
        self.login_manager = login_manager
        self.qr_handler = qr_handler
        self.user_manager = UserManager(db_manager)
        self.attendance_manager = AttendanceManager(db_manager)
        self.event_manager = EventManager(db_manager)
        
        self.init_ui()
    
    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.notebook = wx.Notebook(self)
        
        # User Management Tab
        self.user_mgmt_panel = self.create_user_mgmt_panel()
        self.notebook.AddPage(self.user_mgmt_panel, "User Management")
        
        # Leave Management Tab
        self.leave_mgmt_panel = self.create_leave_mgmt_panel()
        self.notebook.AddPage(self.leave_mgmt_panel, "Leave Management")
        
        main_sizer.Add(self.notebook, 1, wx.ALL|wx.EXPAND, 10)
        self.SetSizer(main_sizer)
    
    def create_user_mgmt_panel(self):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Add User Section
        add_box = wx.StaticBox(panel, label="Add New User")
        add_sizer = wx.StaticBoxSizer(add_box, wx.VERTICAL)
        
        grid = wx.FlexGridSizer(5, 2, 10, 10)
        grid.AddGrowableCol(1)
        
        grid.Add(wx.StaticText(panel, label="Name:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.name_ctrl = wx.TextCtrl(panel)
        grid.Add(self.name_ctrl, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(panel, label="Email:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.email_ctrl = wx.TextCtrl(panel)
        grid.Add(self.email_ctrl, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(panel, label="Phone:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.phone_ctrl = wx.TextCtrl(panel)
        grid.Add(self.phone_ctrl, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(panel, label="Password:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.new_password_ctrl = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        grid.Add(self.new_password_ctrl, 1, wx.EXPAND)
        
        add_sizer.Add(grid, 0, wx.ALL|wx.EXPAND, 10)
        
        self.add_user_btn = wx.Button(panel, label="Add User")
        self.add_user_btn.Bind(wx.EVT_BUTTON, self.on_add_user)
        add_sizer.Add(self.add_user_btn, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        sizer.Add(add_sizer, 0, wx.ALL|wx.EXPAND, 10)
        
        # User List Section
        list_box = wx.StaticBox(panel, label="All Users")
        list_sizer = wx.StaticBoxSizer(list_box, wx.VERTICAL)
        
        self.user_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        self.user_list.InsertColumn(0, "Employee ID", width=100)
        self.user_list.InsertColumn(1, "Name", width=150)
        self.user_list.InsertColumn(2, "Email", width=200)
        self.user_list.InsertColumn(3, "Phone", width=100)
        self.user_list.InsertColumn(4, "Status", width=80)
        list_sizer.Add(self.user_list, 1, wx.ALL|wx.EXPAND, 10)
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_btn = wx.Button(panel, label="Refresh")
        self.reset_pwd_btn = wx.Button(panel, label="Reset Password")
        self.force_logout_btn = wx.Button(panel, label="Force Logout")
        self.view_qr_btn = wx.Button(panel, label="View QR Code")
        self.delete_user_btn = wx.Button(panel, label="Delete User")
        
        btn_sizer.Add(self.refresh_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.reset_pwd_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.force_logout_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.view_qr_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.delete_user_btn)
        
        list_sizer.Add(btn_sizer, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        sizer.Add(list_sizer, 1, wx.ALL|wx.EXPAND, 10)
        
        panel.SetSizer(sizer)
        
        # Bind events
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh_users)
        self.reset_pwd_btn.Bind(wx.EVT_BUTTON, self.on_reset_password)
        self.force_logout_btn.Bind(wx.EVT_BUTTON, self.on_force_logout)
        self.view_qr_btn.Bind(wx.EVT_BUTTON, self.on_view_qr)
        self.delete_user_btn.Bind(wx.EVT_BUTTON, self.on_delete_user)
        
        self.on_refresh_users(None)
        return panel
    
    def create_leave_mgmt_panel(self):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        leave_notebook = wx.Notebook(panel)
        
        # Mark Leave Tab
        mark_leave_panel = self.create_mark_leave_panel(leave_notebook)
        leave_notebook.AddPage(mark_leave_panel, "Mark Leave")
        
        # View Attendance Tab
        view_attendance_panel = self.create_view_attendance_panel(leave_notebook)
        leave_notebook.AddPage(view_attendance_panel, "View Attendance")
        
        # Calendar Tab
        calendar_panel = self.create_calendar_panel(leave_notebook)
        leave_notebook.AddPage(calendar_panel, "Company Calendar")
        
        # Summary Tab
        summary_panel = self.create_summary_panel(leave_notebook)
        leave_notebook.AddPage(summary_panel, "Attendance Summary")
        
        sizer.Add(leave_notebook, 1, wx.ALL|wx.EXPAND, 10)
        panel.SetSizer(sizer)
        return panel
    
    def create_mark_leave_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        form_box = wx.StaticBox(panel, label="Mark Leave")
        form_sizer = wx.StaticBoxSizer(form_box, wx.VERTICAL)
        
        grid = wx.FlexGridSizer(5, 2, 10, 10)
        grid.AddGrowableCol(1)
        
        grid.Add(wx.StaticText(panel, label="Employee ID:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.leave_emp_id = wx.TextCtrl(panel)
        grid.Add(self.leave_emp_id, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(panel, label="Start Date (YYYY-MM-DD):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.leave_start_date = wx.TextCtrl(panel)
        grid.Add(self.leave_start_date, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(panel, label="End Date (YYYY-MM-DD):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.leave_end_date = wx.TextCtrl(panel)
        grid.Add(self.leave_end_date, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(panel, label="Leave Type:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.leave_type = wx.Choice(panel, choices=["Leave", "Sick Leave", "Personal Leave", "Absent", "Holiday"])
        self.leave_type.SetSelection(0)
        grid.Add(self.leave_type, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(panel, label="Notes:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.leave_notes = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 60))
        grid.Add(self.leave_notes, 1, wx.EXPAND)
        
        form_sizer.Add(grid, 0, wx.ALL|wx.EXPAND, 10)
        
        self.mark_leave_btn = wx.Button(panel, label="Mark Leave")
        self.mark_leave_btn.Bind(wx.EVT_BUTTON, self.on_mark_leave)
        form_sizer.Add(self.mark_leave_btn, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        sizer.Add(form_sizer, 0, wx.ALL|wx.EXPAND, 10)
        panel.SetSizer(sizer)
        return panel
    
    def create_view_attendance_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        filter_box = wx.StaticBox(panel, label="Filters")
        filter_sizer = wx.StaticBoxSizer(filter_box, wx.HORIZONTAL)
        
        filter_sizer.Add(wx.StaticText(panel, label="Employee ID:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.att_emp_id = wx.TextCtrl(panel, size=(100, -1))
        filter_sizer.Add(self.att_emp_id, 0, wx.RIGHT, 10)
        
        filter_sizer.Add(wx.StaticText(panel, label="Start Date:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.att_start_date = wx.TextCtrl(panel, size=(100, -1))
        filter_sizer.Add(self.att_start_date, 0, wx.RIGHT, 10)
        
        filter_sizer.Add(wx.StaticText(panel, label="End Date:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.att_end_date = wx.TextCtrl(panel, size=(100, -1))
        filter_sizer.Add(self.att_end_date, 0, wx.RIGHT, 10)
        
        self.view_att_btn = wx.Button(panel, label="View Attendance")
        self.view_att_btn.Bind(wx.EVT_BUTTON, self.on_view_attendance)
        filter_sizer.Add(self.view_att_btn)
        
        sizer.Add(filter_sizer, 0, wx.ALL|wx.EXPAND, 10)
        
        self.attendance_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        self.attendance_list.InsertColumn(0, "Employee ID", width=100)
        self.attendance_list.InsertColumn(1, "Name", width=120)
        self.attendance_list.InsertColumn(2, "Date", width=100)
        self.attendance_list.InsertColumn(3, "Status", width=100)
        self.attendance_list.InsertColumn(4, "Login", width=80)
        self.attendance_list.InsertColumn(5, "Logout", width=80)
        self.attendance_list.InsertColumn(6, "Hours", width=60)
        self.attendance_list.InsertColumn(7, "Notes", width=150)
        
        sizer.Add(self.attendance_list, 1, wx.ALL|wx.EXPAND, 10)
        panel.SetSizer(sizer)
        return panel
    
    def create_calendar_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Navigation
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.prev_month_btn = wx.Button(panel, label="< Previous")
        self.next_month_btn = wx.Button(panel, label="Next >")
        self.month_year_label = wx.StaticText(panel, label="")
        
        nav_sizer.Add(self.prev_month_btn, 0, wx.RIGHT, 10)
        nav_sizer.Add(self.month_year_label, 1, wx.ALIGN_CENTER_VERTICAL)
        nav_sizer.Add(self.next_month_btn)
        
        sizer.Add(nav_sizer, 0, wx.ALL|wx.EXPAND, 10)
        
        # Calendar Grid
        self.calendar_grid = wx.grid.Grid(panel)
        self.calendar_grid.CreateGrid(6, 7)
        self.calendar_grid.SetRowLabelSize(0)
        
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            self.calendar_grid.SetColLabelValue(i, day)
        
        sizer.Add(self.calendar_grid, 1, wx.ALL|wx.EXPAND, 10)
        
        # Add Event Section
        event_box = wx.StaticBox(panel, label="Add Event")
        event_sizer = wx.StaticBoxSizer(event_box, wx.HORIZONTAL)
        
        event_sizer.Add(wx.StaticText(panel, label="Date:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.event_date = wx.TextCtrl(panel, size=(100, -1))
        event_sizer.Add(self.event_date, 0, wx.RIGHT, 10)
        
        event_sizer.Add(wx.StaticText(panel, label="Title:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.event_title = wx.TextCtrl(panel, size=(150, -1))
        event_sizer.Add(self.event_title, 0, wx.RIGHT, 10)
        
        event_sizer.Add(wx.StaticText(panel, label="Category:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.event_category = wx.Choice(panel, choices=["Holiday", "Event", "Meeting", "Celebration"])
        self.event_category.SetSelection(0)
        event_sizer.Add(self.event_category, 0, wx.RIGHT, 10)
        
        self.add_event_btn = wx.Button(panel, label="Add Event")
        self.add_event_btn.Bind(wx.EVT_BUTTON, self.on_add_event)
        event_sizer.Add(self.add_event_btn)
        
        sizer.Add(event_sizer, 0, wx.ALL|wx.EXPAND, 10)
        
        panel.SetSizer(sizer)
        
        # Initialize calendar
        self.current_month = datetime.now().month
        self.current_year = datetime.now().year
        self.prev_month_btn.Bind(wx.EVT_BUTTON, self.on_prev_month)
        self.next_month_btn.Bind(wx.EVT_BUTTON, self.on_next_month)
        self.refresh_calendar()
        
        return panel
    
    def create_summary_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        filter_box = wx.StaticBox(panel, label="Generate Summary")
        filter_sizer = wx.StaticBoxSizer(filter_box, wx.HORIZONTAL)
        
        filter_sizer.Add(wx.StaticText(panel, label="Employee ID:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.summary_emp_id = wx.TextCtrl(panel, size=(100, -1))
        filter_sizer.Add(self.summary_emp_id, 0, wx.RIGHT, 10)
        
        filter_sizer.Add(wx.StaticText(panel, label="Month:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.summary_month = wx.SpinCtrl(panel, value="1", min=1, max=12)
        self.summary_month.SetValue(datetime.now().month)
        filter_sizer.Add(self.summary_month, 0, wx.RIGHT, 10)
        
        filter_sizer.Add(wx.StaticText(panel, label="Year:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.summary_year = wx.SpinCtrl(panel, value="2025", min=2020, max=2100)
        self.summary_year.SetValue(datetime.now().year)
        filter_sizer.Add(self.summary_year, 0, wx.RIGHT, 10)
        
        self.gen_summary_btn = wx.Button(panel, label="Generate Summary")
        self.gen_summary_btn.Bind(wx.EVT_BUTTON, self.on_generate_summary)
        filter_sizer.Add(self.gen_summary_btn)
        
        sizer.Add(filter_sizer, 0, wx.ALL|wx.EXPAND, 10)
        
        self.summary_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE|wx.TE_READONLY)
        sizer.Add(self.summary_text, 1, wx.ALL|wx.EXPAND, 10)
        
        panel.SetSizer(sizer)
        return panel
    
    def on_add_user(self, event):
        name = self.name_ctrl.GetValue().strip()
        email = self.email_ctrl.GetValue().strip()
        phone = self.phone_ctrl.GetValue().strip()
        password = self.new_password_ctrl.GetValue()
        
        if not all([name, email, phone, password]):
            wx.MessageBox("All fields are required", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        try:
            employee_id, user_id = self.user_manager.add_user(name, email, phone, password)
            self.qr_handler.generate_qr(user_id, employee_id)
            wx.MessageBox(f"User added successfully!\nEmployee ID: {employee_id}", "Success", wx.OK|wx.ICON_INFORMATION)
            
            # Clear form
            self.name_ctrl.Clear()
            self.email_ctrl.Clear()
            self.phone_ctrl.Clear()
            self.new_password_ctrl.Clear()
            
            self.on_refresh_users(None)
        except ValueError as e:
            wx.MessageBox(str(e), "Error", wx.OK|wx.ICON_ERROR)
    
    def on_refresh_users(self, event):
        self.user_list.DeleteAllItems()
        users = self.user_manager.get_all_users()
        
        for user in users:
            idx = self.user_list.InsertItem(self.user_list.GetItemCount(), user[1])
            self.user_list.SetItem(idx, 1, user[2])
            self.user_list.SetItem(idx, 2, user[3])
            self.user_list.SetItem(idx, 3, user[4])
            status = "Logged In" if user[5] else "Logged Out"
            self.user_list.SetItem(idx, 4, status)
            
            if user[5]:
                self.user_list.SetItemTextColour(idx, wx.Colour(0, 150, 0))
    
    def on_reset_password(self, event):
        selected = self.user_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Please select a user", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        employee_id = self.user_list.GetItemText(selected, 0)
        
        dlg = wx.TextEntryDialog(self, "Enter new password:", "Reset Password")
        if dlg.ShowModal() == wx.ID_OK:
            new_password = dlg.GetValue()
            if new_password:
                self.user_manager.reset_password(employee_id, new_password)
                wx.MessageBox("Password reset successfully", "Success", wx.OK|wx.ICON_INFORMATION)
        dlg.Destroy()
    
    def on_force_logout(self, event):
        selected = self.user_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Please select a user", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        employee_id = self.user_list.GetItemText(selected, 0)
        self.login_manager.force_logout(employee_id)
        wx.MessageBox("User logged out successfully", "Success", wx.OK|wx.ICON_INFORMATION)
        self.on_refresh_users(None)
    
    def on_view_qr(self, event):
        selected = self.user_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Please select a user", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        employee_id = self.user_list.GetItemText(selected, 0)
        qr_path = self.qr_handler.qr_dir / f"{employee_id}.png"
        
        if qr_path.exists():
            img = wx.Image(str(qr_path), wx.BITMAP_TYPE_PNG)
            img = img.Scale(400, 400, wx.IMAGE_QUALITY_HIGH)
            bitmap = wx.Bitmap(img)
            
            dlg = wx.Dialog(self, title=f"QR Code - {employee_id}", size=(450, 500))
            sizer = wx.BoxSizer(wx.VERTICAL)
            static_bitmap = wx.StaticBitmap(dlg, bitmap=bitmap)
            sizer.Add(static_bitmap, 0, wx.ALL|wx.ALIGN_CENTER, 20)
            dlg.SetSizer(sizer)
            dlg.ShowModal()
            dlg.Destroy()
        else:
            wx.MessageBox("QR code not found", "Error", wx.OK|wx.ICON_ERROR)
    
    def on_delete_user(self, event):
        selected = self.user_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Please select a user", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        employee_id = self.user_list.GetItemText(selected, 0)
        name = self.user_list.GetItemText(selected, 1)
        
        dlg = wx.MessageDialog(self, 
                              f"Are you sure you want to delete user {name} ({employee_id})?\n\nThis will also delete all associated attendance records and login history.",
                              "Confirm Delete",
                              wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
        
        if dlg.ShowModal() == wx.ID_YES:
            try:
                self.user_manager.delete_user(employee_id)
                
                # Delete QR code file
                qr_path = self.qr_handler.qr_dir / f"{employee_id}.png"
                if qr_path.exists():
                    qr_path.unlink()
                
                wx.MessageBox("User deleted successfully", "Success", wx.OK|wx.ICON_INFORMATION)
                self.on_refresh_users(None)
            except Exception as e:
                wx.MessageBox(f"Error deleting user: {str(e)}", "Error", wx.OK|wx.ICON_ERROR)
        
        dlg.Destroy()
    
    def on_mark_leave(self, event):
        employee_id = self.leave_emp_id.GetValue().strip()
        start_date = self.leave_start_date.GetValue().strip()
        end_date = self.leave_end_date.GetValue().strip()
        leave_type = self.leave_type.GetStringSelection()
        notes = self.leave_notes.GetValue().strip()
        
        if not all([employee_id, start_date, end_date]):
            wx.MessageBox("Please fill all required fields", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        user = self.user_manager.get_user_by_employee_id(employee_id)
        if not user:
            wx.MessageBox("Invalid Employee ID", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            wx.MessageBox("Invalid date format. Use YYYY-MM-DD", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        try:
            self.attendance_manager.mark_leave(user[0], start_date, end_date, leave_type, notes)
            wx.MessageBox("Leave marked successfully", "Success", wx.OK|wx.ICON_INFORMATION)
            
            self.leave_emp_id.Clear()
            self.leave_start_date.Clear()
            self.leave_end_date.Clear()
            self.leave_notes.Clear()
        except Exception as e:
            wx.MessageBox(f"Error: {str(e)}", "Error", wx.OK|wx.ICON_ERROR)
    
    def on_view_attendance(self, event):
        self.attendance_list.DeleteAllItems()
        
        employee_id = self.att_emp_id.GetValue().strip()
        start_date = self.att_start_date.GetValue().strip() or None
        end_date = self.att_end_date.GetValue().strip() or None
        
        user_id = None
        if employee_id:
            user = self.user_manager.get_user_by_employee_id(employee_id)
            if user:
                user_id = user[0]
        
        attendance = self.attendance_manager.get_attendance(user_id, start_date, end_date)
        
        for record in attendance:
            idx = self.attendance_list.InsertItem(self.attendance_list.GetItemCount(), record[1])
            self.attendance_list.SetItem(idx, 1, record[2])
            self.attendance_list.SetItem(idx, 2, record[3])
            self.attendance_list.SetItem(idx, 3, record[4])
            self.attendance_list.SetItem(idx, 4, record[5] or "")
            self.attendance_list.SetItem(idx, 5, record[6] or "")
            self.attendance_list.SetItem(idx, 6, f"{record[7]:.2f}" if record[7] else "0.00")
            self.attendance_list.SetItem(idx, 7, record[8] or "")
            
            # Color coding
            if record[4] == "Present":
                self.attendance_list.SetItemTextColour(idx, wx.Colour(0, 150, 0))
            elif record[4] in ["Leave", "Sick Leave", "Personal Leave"]:
                self.attendance_list.SetItemTextColour(idx, wx.Colour(255, 140, 0))
            elif record[4] == "Absent":
                self.attendance_list.SetItemTextColour(idx, wx.Colour(200, 0, 0))
            elif record[4] == "Holiday":
                self.attendance_list.SetItemTextColour(idx, wx.Colour(0, 0, 200))
    
    def refresh_calendar(self):
        month_name = cal.month_name[self.current_month]
        self.month_year_label.SetLabel(f"{month_name} {self.current_year}")
        
        # Get calendar data
        month_cal = cal.monthcalendar(self.current_year, self.current_month)
        
        # Get events for this month
        events = self.event_manager.get_events(self.current_month, self.current_year)
        event_dict = {}
        for event in events:
            date = event[1]
            if date not in event_dict:
                event_dict[date] = []
            event_dict[date].append(event[2])
        
        # Clear grid
        for row in range(6):
            for col in range(7):
                self.calendar_grid.SetCellValue(row, col, "")
                self.calendar_grid.SetCellBackgroundColour(row, col, wx.WHITE)
        
        # Fill calendar
        today = datetime.now().date()
        for week_idx, week in enumerate(month_cal):
            for day_idx, day in enumerate(week):
                if day != 0:
                    date_str = f"{self.current_year}-{self.current_month:02d}-{day:02d}"
                    cell_text = str(day)
                    
                    if date_str in event_dict:
                        cell_text += f"\n{', '.join(event_dict[date_str][:2])}"
                        self.calendar_grid.SetCellBackgroundColour(week_idx, day_idx, wx.Colour(255, 255, 200))
                    
                    self.calendar_grid.SetCellValue(week_idx, day_idx, cell_text)
                    
                    # Highlight today
                    if date_str == today.strftime("%Y-%m-%d"):
                        self.calendar_grid.SetCellBackgroundColour(week_idx, day_idx, wx.Colour(200, 230, 255))
    
    def on_prev_month(self, event):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.refresh_calendar()
    
    def on_next_month(self, event):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.refresh_calendar()
    
    def on_add_event(self, event):
        date = self.event_date.GetValue().strip()
        title = self.event_title.GetValue().strip()
        category = self.event_category.GetStringSelection()
        
        if not all([date, title]):
            wx.MessageBox("Please enter date and title", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        try:
            datetime.strptime(date, "%Y-%m-%d")
            self.event_manager.add_event(date, title, category)
            wx.MessageBox("Event added successfully", "Success", wx.OK|wx.ICON_INFORMATION)
            
            self.event_date.Clear()
            self.event_title.Clear()
            self.refresh_calendar()
        except ValueError:
            wx.MessageBox("Invalid date format. Use YYYY-MM-DD", "Error", wx.OK|wx.ICON_ERROR)
    
    def on_generate_summary(self, event):
        employee_id = self.summary_emp_id.GetValue().strip()
        month = self.summary_month.GetValue()
        year = self.summary_year.GetValue()
        
        if not employee_id:
            wx.MessageBox("Please enter Employee ID", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        user = self.user_manager.get_user_by_employee_id(employee_id)
        if not user:
            wx.MessageBox("Invalid Employee ID", "Error", wx.OK|wx.ICON_ERROR)
            return
        
        summary = self.attendance_manager.get_attendance_summary(user[0], month, year)
        
        total_days = sum(summary.values())
        
        summary_text = f"Attendance Summary for {user[2]} ({employee_id})\n"
        summary_text += f"Month: {cal.month_name[month]} {year}\n"
        summary_text += "=" * 50 + "\n\n"
        
        for status, count in summary.items():
            percentage = (count / total_days * 100) if total_days > 0 else 0
            summary_text += f"{status}: {count} days ({percentage:.1f}%)\n"
        
        summary_text += f"\nTotal Days Recorded: {total_days}\n"
        
        self.summary_text.SetValue(summary_text)

# ============================================================================
# History Panel
# ============================================================================
class HistoryPanel(wx.Panel):
    def __init__(self, parent, db_manager, login_manager):
        super().__init__(parent)
        self.db = db_manager
        self.login_manager = login_manager
        self.user_manager = UserManager(db_manager)
        self.attendance_manager = AttendanceManager(db_manager)
        
        self.init_ui()
    
    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Filter Section
        filter_box = wx.StaticBox(self, label="Filters")
        filter_sizer = wx.StaticBoxSizer(filter_box, wx.HORIZONTAL)
        
        filter_sizer.Add(wx.StaticText(self, label="Employee ID:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.filter_emp_id = wx.TextCtrl(self, size=(100, -1))
        filter_sizer.Add(self.filter_emp_id, 0, wx.RIGHT, 10)
        
        filter_sizer.Add(wx.StaticText(self, label="Start Date:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.filter_start_date = wx.TextCtrl(self, size=(100, -1))
        filter_sizer.Add(self.filter_start_date, 0, wx.RIGHT, 10)
        
        filter_sizer.Add(wx.StaticText(self, label="End Date:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.filter_end_date = wx.TextCtrl(self, size=(100, -1))
        filter_sizer.Add(self.filter_end_date, 0, wx.RIGHT, 10)
        
        self.filter_btn = wx.Button(self, label="Filter")
        self.refresh_btn = wx.Button(self, label="Refresh")
        self.export_btn = wx.Button(self, label="Export CSV")
        
        filter_sizer.Add(self.filter_btn, 0, wx.RIGHT, 5)
        filter_sizer.Add(self.refresh_btn, 0, wx.RIGHT, 5)
        filter_sizer.Add(self.export_btn)
        
        main_sizer.Add(filter_sizer, 0, wx.ALL|wx.EXPAND, 10)
        
        # History List
        self.history_list = wx.ListCtrl(self, style=wx.LC_REPORT)
        self.history_list.InsertColumn(0, "Employee ID", width=100)
        self.history_list.InsertColumn(1, "Name", width=150)
        self.history_list.InsertColumn(2, "Action", width=100)
        self.history_list.InsertColumn(3, "Timestamp", width=200)
        
        main_sizer.Add(self.history_list, 1, wx.ALL|wx.EXPAND, 10)
        
        self.SetSizer(main_sizer)
        
        # Bind events
        self.filter_btn.Bind(wx.EVT_BUTTON, self.on_filter)
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        self.export_btn.Bind(wx.EVT_BUTTON, self.on_export)
        
        self.on_refresh(None)
    
    def on_filter(self, event):
        self.history_list.DeleteAllItems()
        
        employee_id = self.filter_emp_id.GetValue().strip()
        start_date = self.filter_start_date.GetValue().strip() or None
        end_date = self.filter_end_date.GetValue().strip() or None
        
        user_id = None
        if employee_id:
            user = self.user_manager.get_user_by_employee_id(employee_id)
            if user:
                user_id = user[0]
            else:
                wx.MessageBox("Invalid Employee ID", "Error", wx.OK|wx.ICON_ERROR)
                return
        
        history = self.login_manager.get_login_history(user_id, start_date, end_date)
        
        for record in history:
            idx = self.history_list.InsertItem(self.history_list.GetItemCount(), record[1])
            self.history_list.SetItem(idx, 1, record[2])
            self.history_list.SetItem(idx, 2, record[3])
            self.history_list.SetItem(idx, 3, record[4])
            
            # Color coding
            if record[3] == "LOGIN":
                self.history_list.SetItemTextColour(idx, wx.Colour(0, 150, 0))
            else:
                self.history_list.SetItemTextColour(idx, wx.Colour(200, 0, 0))
    
    def on_refresh(self, event):
        self.filter_emp_id.Clear()
        self.filter_start_date.Clear()
        self.filter_end_date.Clear()
        self.on_filter(None)
    
    def on_export(self, event):
        dlg = wx.FileDialog(self, "Save CSV file", wildcard="CSV files (*.csv)|*.csv",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            try:
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Employee ID", "Name", "Action", "Timestamp"])
                    
                    for i in range(self.history_list.GetItemCount()):
                        row = [
                            self.history_list.GetItemText(i, 0),
                            self.history_list.GetItemText(i, 1),
                            self.history_list.GetItemText(i, 2),
                            self.history_list.GetItemText(i, 3)
                        ]
                        writer.writerow(row)
                
                wx.MessageBox("Data exported successfully", "Success", wx.OK|wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Export failed: {str(e)}", "Error", wx.OK|wx.ICON_ERROR)
        
        dlg.Destroy()

# ============================================================================
# Main Application Frame
# ============================================================================
class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Secure QR Login System", size=(1200, 800))
        
        # Initialize paths
        self.app_dir = self.get_app_data_dir()
        self.db_path = self.app_dir / "database" / "secure_qr_login.db"
        self.qr_dir = self.app_dir / "qr_codes"
        
        # Create directories
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.qr_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize managers
        self.db_manager = DatabaseManager(str(self.db_path))
        self.login_manager = LoginManager(self.db_manager)
        self.qr_handler = QRHandler(self.qr_dir)
        
        # Check admin password
        if not self.check_admin_password():
            self.Close()
            return
        
        self.init_ui()
        self.Centre()
    
    def get_app_data_dir(self):
        """Get cross-platform application data directory"""
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", os.path.expanduser("~")))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path.home() / ".config"
        
        return base / "SecureQRLoginSystem"
    
    def check_admin_password(self):
        """Admin authentication"""
        dlg = wx.PasswordEntryDialog(self, "Enter admin password:", "Admin Authentication")
        
        if dlg.ShowModal() == wx.ID_OK:
            password = dlg.GetValue()
            dlg.Destroy()
            
            # Simple admin password check (in production, use secure storage)
            if password == "admin123":
                return True
            else:
                wx.MessageBox("Invalid admin password", "Error", wx.OK|wx.ICON_ERROR)
                return False
        else:
            dlg.Destroy()
            return False
    
    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create notebook
        notebook = wx.Notebook(panel)
        
        # User Panel
        user_panel = UserPanel(notebook, self.db_manager, self.login_manager, self.qr_handler)
        notebook.AddPage(user_panel, "User Login")
        
        # Admin Panel
        admin_panel = AdminPanel(notebook, self.db_manager, self.login_manager, self.qr_handler)
        notebook.AddPage(admin_panel, "Admin")
        
        # History Panel
        history_panel = HistoryPanel(notebook, self.db_manager, self.login_manager)
        notebook.AddPage(history_panel, "History")
        
        sizer.Add(notebook, 1, wx.ALL|wx.EXPAND, 5)
        panel.SetSizer(sizer)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Status bar
        self.CreateStatusBar()
        self.SetStatusText("Secure QR Login System - Ready")
    
    def create_menu_bar(self):
        menubar = wx.MenuBar()
        
        # File menu
        file_menu = wx.Menu()
        exit_item = file_menu.Append(wx.ID_EXIT, "E&xit", "Exit the application")
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        
        # Help menu
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "&About", "About this application")
        self.Bind(wx.EVT_MENU, self.on_about, about_item)
        
        menubar.Append(file_menu, "&File")
        menubar.Append(help_menu, "&Help")
        
        self.SetMenuBar(menubar)
    
    def on_exit(self, event):
        dlg = wx.MessageDialog(self, "Are you sure you want to exit?", "Confirm Exit",
                              wx.YES_NO | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            self.Close(True)
        dlg.Destroy()
    
    def on_about(self, event):
        info = wx.adv.AboutDialogInfo()
        info.SetName("Secure QR Login System")
        info.SetVersion("1.0")
        info.SetDescription("A comprehensive attendance tracking system with QR code authentication,\n"
                           "leave management, and calendar functionality.")
        info.SetWebSite("https://github.com/yourusername/secure-qr-login")
        info.AddDeveloper("Your Name")
        
        wx.adv.AboutBox(info)

# ============================================================================
# Application Entry Point
# ============================================================================
class SecureQRLoginApp(wx.App):
    def OnInit(self):
        self.frame = MainFrame()
        self.frame.Show()
        return True

def main():
    app = SecureQRLoginApp()
    app.MainLoop()

if __name__ == "__main__":
    main()