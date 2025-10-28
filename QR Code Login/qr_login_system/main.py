import wx
import cv2
import qrcode
import json
import datetime
import re
import hashlib
import secrets
import sqlite3
import os
from pathlib import Path
import csv
import sys
import shutil
from datetime import timedelta
import calendar

def get_database_path():
    """Get the appropriate database path for both development and bundled environments"""
    # Detect if running from PyInstaller bundle
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    # Use writable path for the DB (AppData on Windows, ~/.config on Linux, ~/Library/Application Support on macOS)
    if sys.platform == "win32":
        appdata_path = os.path.join(os.getenv('APPDATA'), 'SecureQRLoginSystem')
    elif sys.platform == "darwin":  # macOS
        appdata_path = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'SecureQRLoginSystem')
    else:  # Linux and other Unix-like
        appdata_path = os.path.join(os.path.expanduser('~'), '.config', 'SecureQRLoginSystem')
    
    os.makedirs(appdata_path, exist_ok=True)

    db_path = os.path.join(appdata_path, 'secure_qr_login.db')
    return db_path

def get_qr_codes_path():
    """Get the appropriate path for storing QR code images"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    # Use writable path for QR codes
    if sys.platform == "win32":
        appdata_path = os.path.join(os.getenv('APPDATA'), 'SecureQRLoginSystem', 'qr_codes')
    elif sys.platform == "darwin":  # macOS
        appdata_path = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'SecureQRLoginSystem', 'qr_codes')
    else:  # Linux and other Unix-like
        appdata_path = os.path.join(os.path.expanduser('~'), '.config', 'SecureQRLoginSystem', 'qr_codes')
    
    os.makedirs(appdata_path, exist_ok=True)
    return appdata_path

class DatabaseManager:
    def __init__(self, db_path=None):
        if db_path is None:
            self.db_path = get_database_path()
        else:
            self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables with proper error handling"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # First, try to get table info to check current schema
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            table_exists = cursor.fetchone()
            
            if table_exists:
                # Table exists, check schema
                cursor.execute("PRAGMA table_info(users)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'adress' in columns and 'address' not in columns:
                    # Need to migrate from old schema
                    print("Migrating database schema from 'adress' to 'address'...")
                    self.migrate_database(conn, cursor)
                elif 'address' not in columns:
                    # Table exists but missing address column, add it
                    print("Adding missing 'address' column...")
                    cursor.execute("ALTER TABLE users ADD COLUMN address TEXT NOT NULL DEFAULT ''")
                # If 'address' already exists, do nothing
            else:
                # Table doesn't exist, create with correct schema
                self.create_tables(conn, cursor)
                
        except Exception as e:
            print(f"Error during database initialization: {e}")
            # If anything fails, try to create fresh tables
            try:
                cursor.execute("DROP TABLE IF EXISTS users")
                cursor.execute("DROP TABLE IF EXISTS login_history")
                cursor.execute("DROP TABLE IF EXISTS attendance")
                cursor.execute("DROP TABLE IF EXISTS holidays")
                cursor.execute("DROP TABLE IF EXISTS events")
                self.create_tables(conn, cursor)
            except Exception as e2:
                print(f"Failed to create fresh tables: {e2}")
        
        conn.commit()
        conn.close()
    
    def create_tables(self, conn, cursor):
        """Create database tables with correct schema"""
        # Users table - corrected schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                qr_code_data TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Login history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                method TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Attendance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                date DATE NOT NULL,
                status TEXT NOT NULL, -- 'present', 'leave', 'holiday', 'absent'
                login_time TIMESTAMP,
                logout_time TIMESTAMP,
                hours_worked DECIMAL(4,2),
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, date)
            )
        ''')
        
        # Holidays table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS holidays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                event_date DATE NOT NULL,
                event_type TEXT NOT NULL, -- 'holiday', 'event', 'meeting', 'celebration'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON users(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_phone ON users(phone)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_timestamp ON login_history(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_user_id ON login_history(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance(user_id, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_holidays_date ON holidays(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date)')
    
    def migrate_database(self, conn, cursor):
        """Migrate from old schema to new schema"""
        try:
            # Create temporary table with new schema
            cursor.execute('''
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    address TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    qr_code_data TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Copy data from old table to new table
            cursor.execute('''
                INSERT INTO users_new 
                (id, user_id, name, address, email, phone, password_hash, salt, qr_code_data, is_active, created_at)
                SELECT id, user_id, name, adress, email, phone, password_hash, salt, qr_code_data, is_active, created_at
                FROM users
            ''')
            
            # Drop old table and rename new table
            cursor.execute('DROP TABLE users')
            cursor.execute('ALTER TABLE users_new RENAME TO users')
            
            # Recreate indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON users(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_email ON users(email)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_phone ON users(phone)')
            
            print("Database migration completed successfully")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            # If migration fails, try the simpler approach
            try:
                cursor.execute("ALTER TABLE users RENAME COLUMN adress TO address")
                print("Successfully renamed column using ALTER TABLE")
            except Exception as e2:
                print(f"Column rename also failed: {e2}")
                raise
    
    def add_user(self, user_data):
        """Add a new user to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (user_id, name, address, email, phone, password_hash, salt, qr_code_data, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_data['user_id'],
                user_data['name'],
                user_data['address'],
                user_data['email'],
                user_data['phone'],
                user_data['password_hash'],
                user_data['salt'],
                user_data['qr_code_data'],
                user_data.get('is_active', True)
            ))
            conn.commit()
            return True, "User added successfully"
        except sqlite3.IntegrityError as e:
            return False, f"User with this ID, email or phone already exists: {str(e)}"
        except Exception as e:
            return False, f"Database error: {str(e)}"
        finally:
            conn.close()
    
    def update_user_password(self, user_id, new_password_hash, new_salt):
        """Update user password"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE users 
                SET password_hash = ?, salt = ?
                WHERE user_id = ?
            ''', (new_password_hash, new_salt, user_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            return False
        finally:
            conn.close()
    
    def get_user_by_id(self, user_id):
        """Get user by user ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                'id': user[0],
                'user_id': user[1],
                'name': user[2],
                'address': user[3],
                'email': user[4],
                'phone': user[5],
                'password_hash': user[6],
                'salt': user[7],
                'qr_code_data': user[8],
                'is_active': bool(user[9]),
                'created_at': user[10]
            }
        return None
    
    def get_user_by_qr_data(self, qr_data):
        """Get user by QR code data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE qr_code_data = ?', (qr_data,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                'id': user[0],
                'user_id': user[1],
                'name': user[2],
                'address': user[3],
                'email': user[4],
                'phone': user[5],
                'password_hash': user[6],
                'salt': user[7],
                'qr_code_data': user[8],
                'is_active': bool(user[9]),
                'created_at': user[10]
            }
        return None
    
    def get_all_users(self):
        """Get all users from database (excluding sensitive data)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT user_id, name, address, email, phone, is_active, created_at 
                FROM users 
                ORDER BY user_id
            ''')
        except sqlite3.OperationalError as e:
            if "no such column: address" in str(e):
                # Fallback for old schema
                cursor.execute('''
                    SELECT user_id, name, adress, email, phone, is_active, created_at 
                    FROM users 
                    ORDER BY user_id
                ''')
            else:
                raise
        
        users = cursor.fetchall()
        conn.close()
        
        user_list = []
        for user in users:
            user_list.append({
                'user_id': user[0],
                'name': user[1],
                'address': user[2],
                'email': user[3],
                'phone': user[4],
                'is_active': bool(user[5]),
                'created_at': user[6]
            })
        return user_list
    
    def user_exists(self, user_id, email, phone):
        """Check if user with given ID, email or phone already exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id FROM users 
            WHERE user_id = ? OR email = ? OR phone = ?
        ''', (user_id, email, phone))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def get_last_user_id(self, prefix="EMP"):
        """Get the last user ID with the given prefix"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id FROM users 
            WHERE user_id LIKE ? 
            ORDER BY user_id DESC 
            LIMIT 1
        ''', (f"{prefix}%",))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def add_login_record(self, user_id, action, method):
        """Add login/logout record to history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO login_history (user_id, action, method)
            VALUES (?, ?, ?)
        ''', (user_id, action, method))
        conn.commit()
        conn.close()
    
    def get_login_history(self, user_id=None, start_date=None, end_date=None):
        """Get login history with optional filters"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT lh.user_id, u.name, lh.action, lh.timestamp, lh.method
            FROM login_history lh
            JOIN users u ON lh.user_id = u.user_id
        '''
        params = []
        
        conditions = []
        if user_id:
            conditions.append("lh.user_id = ?")
            params.append(user_id)
        
        if start_date:
            conditions.append("DATE(lh.timestamp) >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("DATE(lh.timestamp) <= ?")
            params.append(end_date)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY lh.timestamp DESC"
        
        cursor.execute(query, params)
        history = cursor.fetchall()
        conn.close()
        
        return history

    # Attendance and Leave Management Methods
    def mark_attendance(self, user_id, date, status, login_time=None, logout_time=None, hours_worked=0, notes=""):
        """Mark attendance for a user on a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO attendance 
                (user_id, date, status, login_time, logout_time, hours_worked, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, date, status, login_time, logout_time, hours_worked, notes))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error marking attendance: {e}")
            return False
        finally:
            conn.close()
    
    def get_attendance(self, user_id=None, start_date=None, end_date=None):
        """Get attendance records with optional filters"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT a.user_id, u.name, a.date, a.status, a.login_time, a.logout_time, a.hours_worked, a.notes
            FROM attendance a
            JOIN users u ON a.user_id = u.user_id
        '''
        params = []
        
        conditions = []
        if user_id:
            conditions.append("a.user_id = ?")
            params.append(user_id)
        
        if start_date:
            conditions.append("a.date >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("a.date <= ?")
            params.append(end_date)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY a.date DESC, u.name"
        
        cursor.execute(query, params)
        attendance = cursor.fetchall()
        conn.close()
        
        return attendance
    
    def get_attendance_summary(self, start_date, end_date):
        """Get attendance summary for all users in date range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                u.user_id,
                u.name,
                COUNT(a.date) as total_days,
                SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present_days,
                SUM(CASE WHEN a.status = 'leave' THEN 1 ELSE 0 END) as leave_days,
                SUM(CASE WHEN a.status = 'holiday' THEN 1 ELSE 0 END) as holiday_days,
                SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) as absent_days
            FROM users u
            LEFT JOIN attendance a ON u.user_id = a.user_id AND a.date BETWEEN ? AND ?
            WHERE u.is_active = 1
            GROUP BY u.user_id, u.name
            ORDER BY u.name
        '''
        
        cursor.execute(query, (start_date, end_date))
        summary = cursor.fetchall()
        conn.close()
        
        return summary
    
    def add_holiday(self, date, description):
        """Add a holiday"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO holidays (date, description)
                VALUES (?, ?)
            ''', (date, description))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding holiday: {e}")
            return False
        finally:
            conn.close()
    
    def get_holidays(self, start_date=None, end_date=None):
        """Get holidays with optional date range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT date, description FROM holidays"
        params = []
        
        if start_date and end_date:
            query += " WHERE date BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        elif start_date:
            query += " WHERE date >= ?"
            params.append(start_date)
        elif end_date:
            query += " WHERE date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date"
        
        cursor.execute(query, params)
        holidays = cursor.fetchall()
        conn.close()
        
        return holidays
    
    def is_holiday(self, date):
        """Check if a date is a holiday"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT date FROM holidays WHERE date = ?', (date,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def mark_unmarked_dates_as_leave(self, user_id, start_date, end_date, leave_type="leave"):
        """Mark unmarked dates in range as leave for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get all dates in range
            current_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
            
            while current_date <= end_date_obj:
                date_str = current_date.strftime('%Y-%m-%d')
                
                # Check if date is already marked
                cursor.execute('SELECT id FROM attendance WHERE user_id = ? AND date = ?', (user_id, date_str))
                existing = cursor.fetchone()
                
                # Check if date is holiday
                is_holiday = self.is_holiday(date_str)
                
                if not existing and not is_holiday:
                    # Mark as leave
                    cursor.execute('''
                        INSERT INTO attendance (user_id, date, status, notes)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, date_str, leave_type, "Auto-marked as leave"))
                
                current_date += timedelta(days=1)
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error marking unmarked dates as leave: {e}")
            return False
        finally:
            conn.close()

    # Events Management Methods
    def add_event(self, title, description, event_date, event_type):
        """Add an event to the calendar"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO events (title, description, event_date, event_type)
                VALUES (?, ?, ?, ?)
            ''', (title, description, event_date, event_type))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding event: {e}")
            return False
        finally:
            conn.close()
    
    def get_events(self, start_date=None, end_date=None, event_type=None):
        """Get events with optional filters"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT id, title, description, event_date, event_type FROM events"
        params = []
        
        conditions = []
        if start_date and end_date:
            conditions.append("event_date BETWEEN ? AND ?")
            params.extend([start_date, end_date])
        elif start_date:
            conditions.append("event_date >= ?")
            params.append(start_date)
        elif end_date:
            conditions.append("event_date <= ?")
            params.append(end_date)
        
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY event_date"
        
        cursor.execute(query, params)
        events = cursor.fetchall()
        conn.close()
        
        return events
    
    def delete_event(self, event_id):
        """Delete an event"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting event: {e}")
            return False
        finally:
            conn.close()
    
    def get_calendar_data(self, year, month):
        """Get all holidays and events for a specific month"""
        # Calculate start and end dates for the month
        start_date = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day:02d}"
        
        holidays = self.get_holidays(start_date, end_date)
        events = self.get_events(start_date, end_date)
        
        return {
            'holidays': holidays,
            'events': events
        }

class PasswordResetDialog(wx.Dialog):
    def __init__(self, parent, user_name, user_id):
        super().__init__(parent, title=f"Reset Password for {user_name}", size=(400, 200))
        self.user_id = user_id
        self.user_name = user_name
        self.init_ui()

    def init_ui(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        instruction = wx.StaticText(self, label=f"Reset password for {self.user_name} ({self.user_id}):")
        vbox.Add(instruction, 0, wx.ALL | wx.EXPAND, 10)
        
        vbox.Add(wx.StaticText(self, label="New Password:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.new_password = wx.TextCtrl(self, style=wx.TE_PASSWORD, size=(300, -1))
        vbox.Add(self.new_password, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        
        vbox.Add(wx.StaticText(self, label="Confirm Password:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.confirm_password = wx.TextCtrl(self, style=wx.TE_PASSWORD, size=(300, -1))
        vbox.Add(self.confirm_password, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.ok_btn = wx.Button(self, label="OK", id=wx.ID_OK)
        self.cancel_btn = wx.Button(self, label="Cancel", id=wx.ID_CANCEL)

        # ✅ Set OK button as default when pressing Enter
        self.SetDefaultItem(self.ok_btn)

        
        self.ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)
        
        btn_sizer.Add(self.ok_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)
        
        vbox.Add(btn_sizer, 0, wx.CENTER | wx.ALL, 10)
        
        self.SetSizer(vbox)
        self.Centre()
    
    def on_ok(self, event):
        new_pwd = self.new_password.GetValue()
        confirm_pwd = self.confirm_password.GetValue()
        
        if not new_pwd:
            wx.MessageBox("Password cannot be empty", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        if new_pwd != confirm_pwd:
            wx.MessageBox("Passwords do not match", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        self.EndModal(wx.ID_OK)
    
    def on_cancel(self, event):
        self.EndModal(wx.ID_CANCEL)
    
    def get_password(self):
        return self.new_password.GetValue()

class DebugAuthDialog(wx.Dialog):
    def __init__(self, parent, user_manager):
        super().__init__(parent, title="Debug Authentication", size=(400, 250))
        self.user_manager = user_manager
        self.init_ui()
    
    def init_ui(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        vbox.Add(wx.StaticText(self, label="Enter Employee ID to debug:"), 0, wx.ALL, 10)
        self.user_id_input = wx.TextCtrl(self)
        vbox.Add(self.user_id_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        vbox.Add(wx.StaticText(self, label="Optional Test Password:"), 0, wx.ALL | wx.TOP, 10)
        self.password_input = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        vbox.Add(self.password_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(self, wx.ID_OK)
        cancel_btn = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        vbox.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.SetSizer(vbox)
        self.SetDefaultItem(ok_btn)  # ✅ Press Enter to trigger OK
        
        # Bind OK button
        ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
    
    def on_ok(self, event):
        user_id = self.user_id_input.GetValue().strip()
        password = self.password_input.GetValue().strip() or None
        if not user_id:
            wx.MessageBox("Please enter Employee ID", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Run debug auth
        self.user_manager.debug_user_authentication(user_id, password)
        wx.MessageBox("Debug information printed in console/log.", "Debug Complete", wx.OK | wx.ICON_INFORMATION)
        self.EndModal(wx.ID_OK)

class SecurityManager:
    @staticmethod
    def hash_password(password, salt=None):
        """Hash password with salt - FIXED VERSION"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        # FIX: Use consistent encoding
        password_bytes = password.encode('utf-8')
        salt_bytes = bytes.fromhex(salt)
        
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password_bytes,
            salt_bytes,
            100000  # Number of iterations
        ).hex()
        
        return password_hash, salt

    @staticmethod
    def verify_password(password, stored_hash, salt):
        """Verify password against stored hash - FIXED VERSION"""
        password_bytes = password.encode('utf-8')
        salt_bytes = bytes.fromhex(salt)  # ✅ FIXED: decode hex back to bytes

        new_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password_bytes,
            salt_bytes,
            100000
        ).hex()

        return secrets.compare_digest(new_hash, stored_hash)

    @staticmethod
    def validate_phone(phone):
        """Validate phone number - exactly 10 digits"""
        return re.match(r'^\d{10}$', phone) is not None
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None

class IDGenerator:
    @staticmethod
    def generate_employee_id(db_manager, prefix="ALLY"):
        """Generate automatic employee ID"""
        last_id = db_manager.get_last_user_id(prefix)
        
        if last_id:
            # Extract the numeric part and increment
            match = re.match(rf"^{prefix}(\d+)$", last_id)
            if match:
                number = int(match.group(1))
                new_number = number + 1
            else:
                new_number = 1
        else:
            new_number = 1
        
        return f"{prefix}{new_number:03d}"  # 3-digit number with leading zeros

class QRHandler:
    @staticmethod
    def generate_qr_code(user_id, name, address, email, phone):
        """Generate QR code data and image for a user"""
        qr_data = json.dumps({
            "user_id": user_id,
            "name": name,
            "address": address,
            "email": email,
            "phone": phone,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # Generate QR code image
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        return qr_data, img
    
    @staticmethod
    def scan_qr_code(frame):
        """Scan QR code from camera frame using OpenCV's QRCodeDetector"""
        try:
            qr_decoder = cv2.QRCodeDetector()
            data, bbox, _ = qr_decoder.detectAndDecode(frame)
            
            if data and len(data) > 0:
                try:
                    qr_data = json.loads(data)
                    return qr_data
                except json.JSONDecodeError:
                    return data
            return None
        except Exception as e:
            print(f"QR scanning error: {e}")
            return None

class CalendarPanel(wx.Panel):
    def __init__(self, parent, db_manager):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_date = datetime.datetime.now()
        self.selected_date = None
        self.init_ui()
        self.refresh_calendar()
    
    def init_ui(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, label="Company Calendar", style=wx.ALIGN_CENTER)
        title_font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        vbox.Add(title, 0, wx.ALL | wx.CENTER, 10)
        
        # Navigation controls
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.prev_month_btn = wx.Button(self, label="← Previous")
        self.month_label = wx.StaticText(self, label="", style=wx.ALIGN_CENTER)
        self.next_month_btn = wx.Button(self, label="Next →")
        self.today_btn = wx.Button(self, label="Today")
        
        self.prev_month_btn.Bind(wx.EVT_BUTTON, self.on_prev_month)
        self.next_month_btn.Bind(wx.EVT_BUTTON, self.on_next_month)
        self.today_btn.Bind(wx.EVT_BUTTON, self.on_today)
        
        nav_sizer.Add(self.prev_month_btn, 0, wx.RIGHT, 10)
        nav_sizer.Add(self.month_label, 1, wx.ALIGN_CENTER)
        nav_sizer.Add(self.next_month_btn, 0, wx.LEFT, 10)
        nav_sizer.Add(self.today_btn, 0, wx.LEFT, 20)
        
        vbox.Add(nav_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Calendar grid
        self.calendar_grid = wx.GridSizer(7, 7, 5, 5)  # 7x7 for days header + 6 weeks
        vbox.Add(self.calendar_grid, 1, wx.EXPAND | wx.ALL, 10)
        
        # Event management section
        event_box = wx.StaticBox(self, label="Add Event/Holiday")
        event_sizer = wx.StaticBoxSizer(event_box, wx.VERTICAL)
        
        event_grid = wx.FlexGridSizer(4, 2, 10, 10)
        event_grid.AddGrowableCol(1, 1)
        
        event_grid.Add(wx.StaticText(self, label="Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.event_date = wx.TextCtrl(self, size=(120, -1))
        event_grid.Add(self.event_date, 0, wx.EXPAND)
        
        event_grid.Add(wx.StaticText(self, label="Title:*"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.event_title = wx.TextCtrl(self, size=(200, -1))
        event_grid.Add(self.event_title, 0, wx.EXPAND)
        
        event_grid.Add(wx.StaticText(self, label="Type:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.event_type = wx.ComboBox(self, choices=["Holiday", "Event", "Meeting", "Celebration"], style=wx.CB_READONLY)
        self.event_type.SetSelection(0)
        event_grid.Add(self.event_type, 0, wx.EXPAND)
        
        event_grid.Add(wx.StaticText(self, label="Description:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.event_desc = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 60))
        event_grid.Add(self.event_desc, 0, wx.EXPAND)
        
        event_sizer.Add(event_grid, 0, wx.EXPAND | wx.ALL, 10)
        
        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_event_btn = wx.Button(self, label="Add Event/Holiday", size=(150, 35))
        self.delete_event_btn = wx.Button(self, label="Delete Selected", size=(120, 35))
        
        self.add_event_btn.Bind(wx.EVT_BUTTON, self.on_add_event)
        self.delete_event_btn.Bind(wx.EVT_BUTTON, self.on_delete_event)
        
        btn_sizer.Add(self.add_event_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.delete_event_btn, 0, wx.ALL, 5)
        
        event_sizer.Add(btn_sizer, 0, wx.CENTER)
        vbox.Add(event_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Events list for the month
        events_box = wx.StaticBox(self, label="Events This Month")
        events_sizer = wx.StaticBoxSizer(events_box, wx.VERTICAL)
        
        self.events_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.events_list.InsertColumn(0, "Date", width=80)
        self.events_list.InsertColumn(1, "Type", width=80)
        self.events_list.InsertColumn(2, "Title", width=150)
        self.events_list.InsertColumn(3, "Description", width=200)
        
        events_sizer.Add(self.events_list, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(events_sizer, 1, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(vbox)
    
    def refresh_calendar(self):
        """Refresh the calendar display"""
        # Clear existing calendar
        self.calendar_grid.Clear()
        
        # Update month label
        self.month_label.SetLabel(self.current_date.strftime("%B %Y"))
        
        # Add day headers
        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        for day in days:
            header = wx.StaticText(self, label=day, style=wx.ALIGN_CENTER)
            header.SetBackgroundColour(wx.Colour(200, 200, 200))
            header.SetMinSize((80, 25))
            self.calendar_grid.Add(header, 0, wx.EXPAND)
        
        # Get first day of month and number of days
        year = self.current_date.year
        month = self.current_date.month
        first_day = datetime.date(year, month, 1)
        last_day = datetime.date(year, month, calendar.monthrange(year, month)[1])
        
        # Get calendar data
        calendar_data = self.db_manager.get_calendar_data(year, month)
        holidays = {holiday[0]: holiday[1] for holiday in calendar_data['holidays']}
        events = {}
        for event in calendar_data['events']:
            events[event[3]] = event  # event[3] is event_date
        
        # Fill in blank days before first day of month
        start_weekday = first_day.weekday()  # Monday=0, Sunday=6
        # Convert to Sunday=0, Monday=1, ..., Saturday=6
        start_weekday = (start_weekday + 1) % 7
        
        for _ in range(start_weekday):
            self.calendar_grid.Add(wx.StaticText(self, label=""), 0, wx.EXPAND)
        
        # Add days of the month
        current_day = first_day
        while current_day <= last_day:
            day_str = str(current_day.day)
            date_str = current_day.strftime("%Y-%m-%d")
            
            # Create day button
            day_btn = wx.Button(self, label=day_str, size=(80, 60))
            day_btn.date = date_str
            day_btn.Bind(wx.EVT_BUTTON, self.on_day_click)
            
            # Color coding
            if current_day == datetime.date.today():
                day_btn.SetBackgroundColour(wx.Colour(173, 216, 230))  # Light blue for today
            
            # Check if it's a holiday
            if date_str in holidays:
                day_btn.SetBackgroundColour(wx.Colour(255, 200, 200))  # Light red for holidays
                day_btn.SetToolTip(f"Holiday: {holidays[date_str]}")
            
            # Check if there are events
            if date_str in events:
                event = events[date_str]
                day_btn.SetBackgroundColour(wx.Colour(200, 230, 200))  # Light green for events
                day_btn.SetToolTip(f"{event[4]}: {event[1]}")
            
            self.calendar_grid.Add(day_btn, 0, wx.EXPAND)
            
            current_day += timedelta(days=1)
        
        # Fill remaining empty cells
        while self.calendar_grid.GetItemCount() < 49:  # 7x7 grid
            self.calendar_grid.Add(wx.StaticText(self, label=""), 0, wx.EXPAND)
        
        self.Layout()
        
        # Refresh events list
        self.refresh_events_list()
    
    def refresh_events_list(self):
        """Refresh the events list for the current month"""
        self.events_list.DeleteAllItems()
        
        year = self.current_date.year
        month = self.current_date.month
        start_date = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day:02d}"
        
        events = self.db_manager.get_events(start_date, end_date)
        
        for event in events:
            index = self.events_list.InsertItem(self.events_list.GetItemCount(), event[3])  # date
            self.events_list.SetItem(index, 1, event[4])  # type
            self.events_list.SetItem(index, 2, event[1])  # title
            self.events_list.SetItem(index, 3, event[2] or "")  # description
            self.events_list.SetItemData(index, event[0])  # store event ID
            
            # Color code based on event type
            if event[4] == "Holiday":
                self.events_list.SetItemTextColour(index, wx.Colour(255, 0, 0))
            elif event[4] == "Event":
                self.events_list.SetItemTextColour(index, wx.Colour(0, 0, 255))
            elif event[4] == "Meeting":
                self.events_list.SetItemTextColour(index, wx.Colour(128, 0, 128))
    
    def on_prev_month(self, event):
        """Go to previous month"""
        self.current_date = self.current_date.replace(day=1)
        self.current_date -= timedelta(days=1)
        self.current_date = self.current_date.replace(day=1)
        self.refresh_calendar()
    
    def on_next_month(self, event):
        """Go to next month"""
        self.current_date = self.current_date.replace(day=28) + timedelta(days=4)
        self.current_date = self.current_date.replace(day=1)
        self.refresh_calendar()
    
    def on_today(self, event):
        """Go to current month"""
        self.current_date = datetime.datetime.now()
        self.refresh_calendar()
    
    def on_day_click(self, event):
        """Handle day button click"""
        btn = event.GetEventObject()
        self.selected_date = btn.date
        self.event_date.SetValue(self.selected_date)
        
        # Highlight selected day
        for i in range(self.calendar_grid.GetItemCount()):
            item = self.calendar_grid.GetItem(i)
            if item.GetWindow() and hasattr(item.GetWindow(), 'date'):
                if item.GetWindow().date == self.selected_date:
                    item.GetWindow().SetBackgroundColour(wx.Colour(255, 255, 0))  # Yellow for selected
                else:
                    # Reset to original colors
                    if item.GetWindow().date == datetime.date.today().strftime("%Y-%m-%d"):
                        item.GetWindow().SetBackgroundColour(wx.Colour(173, 216, 230))
                    elif self.db_manager.is_holiday(item.GetWindow().date):
                        item.GetWindow().SetBackgroundColour(wx.Colour(255, 200, 200))
                    else:
                        item.GetWindow().SetBackgroundColour(wx.NullColour)
    
    def on_add_event(self, event):
        """Add a new event or holiday"""
        date = self.event_date.GetValue().strip()
        title = self.event_title.GetValue().strip()
        event_type = self.event_type.GetStringSelection()
        description = self.event_desc.GetValue().strip()
        
        if not date or not title:
            wx.MessageBox("Please enter both date and title", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        if not self.validate_date_format(date):
            wx.MessageBox("Please enter a valid date in YYYY-MM-DD format", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # If it's a holiday, add to holidays table as well
        if event_type == "Holiday":
            success = self.db_manager.add_holiday(date, title)
            if not success:
                wx.MessageBox("Error adding holiday", "Error", wx.OK | wx.ICON_ERROR)
                return
        
        # Add to events table
        success = self.db_manager.add_event(title, description, date, event_type)
        if success:
            wx.MessageBox(f"{event_type} added successfully", "Success", wx.OK | wx.ICON_INFORMATION)
            self.event_title.Clear()
            self.event_desc.Clear()
            self.refresh_calendar()
        else:
            wx.MessageBox(f"Error adding {event_type.lower()}", "Error", wx.OK | wx.ICON_ERROR)
    
    def on_delete_event(self, event):
        """Delete selected event"""
        selected_index = self.events_list.GetFirstSelected()
        if selected_index == -1:
            wx.MessageBox("Please select an event to delete", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        event_id = self.events_list.GetItemData(selected_index)
        event_date = self.events_list.GetItemText(selected_index)
        event_type = self.events_list.GetItemText(selected_index, 1)
        event_title = self.events_list.GetItemText(selected_index, 2)
        
        confirm = wx.MessageBox(
            f"Are you sure you want to delete the {event_type.lower()} '{event_title}' on {event_date}?",
            "Confirm Delete",
            wx.YES_NO | wx.ICON_QUESTION
        )
        
        if confirm == wx.YES:
            # If it's a holiday, remove from holidays table as well
            if event_type == "Holiday":
                conn = sqlite3.connect(self.db_manager.db_path)
                cursor = conn.cursor()
                try:
                    cursor.execute('DELETE FROM holidays WHERE date = ? AND description = ?', (event_date, event_title))
                    conn.commit()
                except Exception as e:
                    print(f"Error deleting holiday: {e}")
                finally:
                    conn.close()
            
            # Delete from events table
            success = self.db_manager.delete_event(event_id)
            if success:
                wx.MessageBox("Event deleted successfully", "Success", wx.OK | wx.ICON_INFORMATION)
                self.refresh_calendar()
            else:
                wx.MessageBox("Error deleting event", "Error", wx.OK | wx.ICON_ERROR)
    
    def validate_date_format(self, date_str):
        """Validate YYYY-MM-DD date format"""
        try:
            datetime.datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False

class UserManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logged_in_users = set()
    
    def add_user(self, name, address, email, phone, password, prefix="ALLY"):
        """Add a new user with validation"""
        # Validate inputs
        if not all([name, address, email, phone, password]):
            return False, None, "All fields are required"
        
        if not SecurityManager.validate_email(email):
            return False, None, "Invalid email format"
        
        if not SecurityManager.validate_phone(phone):
            return False, None, "Phone number must be exactly 10 digits"
        
        # Generate user ID
        user_id = IDGenerator.generate_employee_id(self.db_manager, prefix)
        
        # Check for existing user
        if self.db_manager.user_exists(user_id, email, phone):
            return False, None, "User with this ID, email or phone already exists"
        
        # Hash password
        password_hash, salt = SecurityManager.hash_password(password)
        
        # Generate QR code
        qr_data, qr_image = QRHandler.generate_qr_code(user_id, name, address, email, phone)
        
        # Prepare user data
        user_data = {
            "user_id": user_id,
            "name": name,
            "address": address,
            "email": email,
            "phone": phone,
            "password_hash": password_hash,
            "salt": salt,
            "qr_code_data": qr_data,
            "is_active": True
        }
        
        # Save to database
        success, message = self.db_manager.add_user(user_data)
        if success:
            # Save QR code image to appropriate location
            qr_dir = Path(get_qr_codes_path())
            qr_image.save(qr_dir / f"{user_id}.png")
            return True, user_id, f"User {name} added successfully with ID: {user_id}"
        else:
            return False, None, f"Failed to add user: {message}"
    
    def reset_user_password(self, user_id, new_password):
        """Reset user password (admin function)"""
        user = self.db_manager.get_user_by_id(user_id)
        if not user:
            return False, "User not found"
        
        # Hash new password
        password_hash, salt = SecurityManager.hash_password(new_password)
        
        # Update in database
        success = self.db_manager.update_user_password(user_id, password_hash, salt)
        if success:
            return True, f"Password reset successfully for {user['name']} ({user_id})"
        else:
            return False, "Failed to reset password"
    
    def verify_manual_login(self, user_id, password):
        """Verify manual login credentials - FIXED VERSION"""
        print(f"🔐 Verifying login for user_id: {user_id}")
        
        # Get user from database
        user = self.db_manager.get_user_by_id(user_id)
        if not user:
            print(f"❌ User {user_id} not found in database")
            return False, "Invalid user ID or password"
        
        if not user.get('is_active', True):
            print(f"❌ User {user_id} is inactive")
            return False, "User account is disabled"
        
        print(f"📝 Stored hash: {user['password_hash'][:20]}...")
        print(f"🧂 Stored salt: {user['salt']}")
        print(f"🔑 Password length: {len(password)}")
        
        # Verify password with improved error handling
        try:
            is_valid = SecurityManager.verify_password(password, user['password_hash'], user['salt'])

            print(f"✅ Password verification result: {is_valid}")
            
            if is_valid:
                return True, "Credentials verified"
            else:
                print("❌ Password hash mismatch")
                return False, "Invalid user ID or password"
                
        except Exception as e:
            print(f"❌ Error during password verification: {e}")
            return False, "Authentication error"
    
    def debug_user_authentication(self, user_id, test_password=None):
        """Debug method to check user authentication issues"""
        print(f"\n🔍 DEBUG AUTHENTICATION FOR USER: {user_id}")
        
        user = self.db_manager.get_user_by_id(user_id)
        if not user:
            print("❌ USER NOT FOUND IN DATABASE")
            return
        
        print(f"✅ User found: {user['name']}")
        print(f"📧 Email: {user['email']}")
        print(f"📞 Phone: {user['phone']}")
        print(f"🟢 Active: {user.get('is_active', True)}")
        print(f"🔐 Password hash: {user['password_hash'][:30]}...")
        print(f"🧂 Salt: {user['salt']}")
        print(f"📅 Created: {user['created_at']}")
        
        if test_password:
            print(f"\n🧪 Testing password: '{test_password}'")
            is_valid = SecurityManager.verify_password(test_password, user['password_hash'], user['salt'])
            print(f"🔑 Password test result: {is_valid}")
            
            # Test hash generation
            test_hash, test_salt = SecurityManager.hash_password(test_password, user['salt'])
            print(f"🔑 Test hash: {test_hash[:30]}...")
            print(f"🧂 Using same salt: {test_salt == user['salt']}")
            print(f"🔍 Hash match: {test_hash == user['password_hash']}")
        
        print(f"📱 Logged in status: {user_id in self.logged_in_users}")
        print("--- DEBUG COMPLETE ---\n")
    
    def get_all_users(self):
        """Get all users with login status"""
        try:
            users = self.db_manager.get_all_users()
            user_list = []
            for user in users:
                status = "Logged In" if user['user_id'] in self.logged_in_users else "Logged Out"
                user_list.append({
                    'user_id': user['user_id'],
                    'name': user['name'],
                    'address': user['address'],
                    'email': user['email'],
                    'phone': user['phone'],
                    'status': status,
                    'created_at': user['created_at']
                })
            return user_list
        except Exception as e:
            print(f"Error getting users: {e}")
            return []
    
    def is_user_logged_in(self, user_id):
        """Check if user is currently logged in"""
        return user_id in self.logged_in_users
    
    def get_user_by_id(self, user_id):
        """Get user details by user ID"""
        return self.db_manager.get_user_by_id(user_id)
    
    def logout_user(self, user_id):
        """Logout user without password verification"""
        if user_id in self.logged_in_users:
            self.logged_in_users.remove(user_id)
            self.db_manager.add_login_record(user_id, "logout", "manual_admin")
            return True, f"User {user_id} logged out successfully"
        else:
            return False, f"User {user_id} is not logged in"

class LoginManager:
    def __init__(self, db_manager, user_manager):
        self.db_manager = db_manager
        self.user_manager = user_manager
    
    def handle_qr_login(self, qr_data):
        """Handle login/logout via QR code scanning - FIXED VERSION"""
        print(f"📱 Processing QR login data: {qr_data}")
        
        # Handle both string and dict QR data
        if isinstance(qr_data, str):
            try:
                qr_data = json.loads(qr_data)
            except json.JSONDecodeError:
                print("❌ Invalid QR code format - not JSON")
                return False, "Invalid QR code format"
        
        user_id = qr_data.get('user_id')
        if not user_id:
            print("❌ No user_id found in QR data")
            return False, "Invalid QR code: missing user ID"
        
        print(f"👤 Looking up user by ID: {user_id}")
        
        # FIX: Get user by ID instead of QR data for better reliability
        user = self.db_manager.get_user_by_id(user_id)
        if not user:
            print(f"❌ User {user_id} not found in database")
            return False, "Unknown user"
        
        # Alternative: Also try to verify QR data matches
        try:
            expected_qr_data = json.loads(user['qr_code_data'])
            if expected_qr_data.get('user_id') != user_id:
                print("⚠️ QR data mismatch")
        except:
            print("⚠️ Could not verify QR data integrity")
        
        if not user.get('is_active', True):
            print(f"❌ User {user_id} account is disabled")
            return False, "User account is disabled"
        
        current_time = datetime.datetime.now()
        today = current_time.strftime('%Y-%m-%d')
        
        if self.user_manager.is_user_logged_in(user_id):
            # Logout user
            print(f"🚪 Logging out user: {user_id}")
            logout_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Calculate hours worked
            login_record = self.get_last_login_record(user_id)
            hours_worked = 0
            if login_record:
                try:
                    login_time = datetime.datetime.strptime(login_record[3], '%Y-%m-%d %H:%M:%S')
                    hours_worked = round((current_time - login_time).total_seconds() / 3600, 2)
                    print(f"⏰ Hours worked: {hours_worked}")
                except Exception as e:
                    print(f"⚠️ Error calculating hours: {e}")
            
            # Update attendance record
            success = self.db_manager.mark_attendance(
                user_id, today, "present", 
                login_time=login_record[3] if login_record else None,
                logout_time=logout_time,
                hours_worked=hours_worked
            )
            
            if success:
                self.user_manager.logged_in_users.remove(user_id)
                self.db_manager.add_login_record(user_id, "logout", "qr_code")
                print(f"✅ Successfully logged out: {user['name']} ({user_id})")
                return True, f"{user['name']} ({user_id}) logged out successfully"
            else:
                print(f"❌ Failed to update attendance for logout")
                return False, "Error updating attendance record"
        else:
            # Login user
            print(f"🔐 Logging in user: {user_id}")
            login_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Check if today is holiday
            if self.db_manager.is_holiday(today):
                status = "holiday"
                print("🎉 Today is a holiday")
            else:
                status = "present"
            
            # Create attendance record
            success = self.db_manager.mark_attendance(
                user_id, today, status, 
                login_time=login_time
            )
            
            if success:
                self.user_manager.logged_in_users.add(user_id)
                self.db_manager.add_login_record(user_id, "login", "qr_code")
                print(f"✅ Successfully logged in: {user['name']} ({user_id})")
                return True, f"{user['name']} ({user_id}) logged in successfully"
            else:
                print(f"❌ Failed to update attendance for login")
                return False, "Error updating attendance record"
    
    def get_last_login_record(self, user_id):
        """Get the last login record for a user"""
        conn = sqlite3.connect(self.db_manager.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, action, timestamp 
            FROM login_history 
            WHERE user_id = ? AND action = 'login' 
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (user_id,))
        record = cursor.fetchone()
        conn.close()
        return record
    
    def handle_manual_login(self, user_id, password):
        """Handle manual login - IMPROVED DEBUG VERSION"""
        print(f"🔐 Attempting manual login for: {user_id}")
        print(f"🔑 Password provided: {'*' * len(password)} (length: {len(password)})")
        
        # Basic validation
        if not user_id or not password:
            print("❌ Missing user ID or password")
            return False, "Please enter both Employee ID and Password"
        
        success, message = self.user_manager.verify_manual_login(user_id, password)
        print(f"📊 Login verification result: {success}, {message}")
        
        if success:
            if not self.user_manager.is_user_logged_in(user_id):
                self.user_manager.logged_in_users.add(user_id)
                self.db_manager.add_login_record(user_id, "login", "manual")
                
                # Mark attendance
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                login_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if self.db_manager.is_holiday(today):
                    status = "holiday"
                else:
                    status = "present"
                
                attendance_success = self.db_manager.mark_attendance(
                    user_id, today, status, login_time=login_time
                )
                
                if attendance_success:
                    print(f"✅ Manual login successful for {user_id}")
                    return True, f"Login successful for {user_id}"
                else:
                    print(f"⚠️ Login successful but attendance update failed for {user_id}")
                    return True, f"Login successful for {user_id} (attendance note failed)"
            else:
                print(f"⚠️ User {user_id} is already logged in")
                return False, "User is already logged in"
        else:
            print(f"❌ Manual login failed for {user_id}: {message}")
            return False, message
    
    def handle_manual_logout(self, user_id, password):
        """Handle manual logout - IMPROVED DEBUG VERSION"""
        print(f"🚪 Attempting manual logout for: {user_id}")
        print(f"🔑 Password provided: {'*' * len(password)} (length: {len(password)})")
        
        # Basic validation
        if not user_id or not password:
            print("❌ Missing user ID or password")
            return False, "Please enter both Employee ID and Password"
        
        success, message = self.user_manager.verify_manual_login(user_id, password)
        print(f"📊 Logout verification result: {success}, {message}")
        
        if success:
            if self.user_manager.is_user_logged_in(user_id):
                current_time = datetime.datetime.now()
                today = current_time.strftime('%Y-%m-%d')
                logout_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
                
                # Calculate hours worked
                login_record = self.get_last_login_record(user_id)
                hours_worked = 0
                if login_record:
                    try:
                        login_time = datetime.datetime.strptime(login_record[3], '%Y-%m-%d %H:%M:%S')
                        hours_worked = round((current_time - login_time).total_seconds() / 3600, 2)
                        print(f"⏰ Hours worked: {hours_worked}")
                    except Exception as e:
                        print(f"⚠️ Error calculating hours: {e}")
                
                # Update attendance record
                attendance_success = self.db_manager.mark_attendance(
                    user_id, today, "present", 
                    login_time=login_record[3] if login_record else None,
                    logout_time=logout_time,
                    hours_worked=hours_worked
                )
                
                if attendance_success:
                    self.user_manager.logged_in_users.remove(user_id)
                    self.db_manager.add_login_record(user_id, "logout", "manual")
                    print(f"✅ Manual logout successful for {user_id}")
                    return True, f"Logout successful for {user_id}"
                else:
                    print(f"⚠️ Logout successful but attendance update failed for {user_id}")
                    return True, f"Logout successful for {user_id} (attendance note failed)"
            else:
                print(f"⚠️ User {user_id} is not logged in")
                return False, "User is not logged in"
        else:
            print(f"❌ Manual logout failed for {user_id}: {message}")
            return False, message
    
    def admin_logout_user(self, user_id):
        """Admin can logout any user without password"""
        return self.user_manager.logout_user(user_id)

class UserPanel(wx.Panel):
    def __init__(self, parent, login_manager):
        super().__init__(parent)
        self.login_manager = login_manager
        self.init_ui()
    
    def init_ui(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, label="User Login/Logout Panel", style=wx.ALIGN_CENTER)
        title_font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        vbox.Add(title, 0, wx.ALL | wx.CENTER, 10)
        
        # Manual login section
        manual_box = wx.StaticBox(self, label="Manual Login/Logout")
        manual_sizer = wx.StaticBoxSizer(manual_box, wx.VERTICAL)
        
        grid = wx.FlexGridSizer(3, 2, 10, 10)
        grid.AddGrowableCol(1, 1)
        
        grid.Add(wx.StaticText(self, label="Employee ID:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.manual_id_input = wx.TextCtrl(self, size=(200, -1))
        grid.Add(self.manual_id_input, 0, wx.EXPAND)
        
        grid.Add(wx.StaticText(self, label="Password:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.manual_password_input = wx.TextCtrl(self, style=wx.TE_PASSWORD, size=(200, -1))
        grid.Add(self.manual_password_input, 0, wx.EXPAND)
        
        manual_sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 15)
        
        # Login/Logout buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.login_btn = wx.Button(self, label="Login", size=(100, 35))
        self.logout_btn = wx.Button(self, label="Logout", size=(100, 35))
        self.clear_btn = wx.Button(self, label="Clear", size=(80, 35))
        
        self.login_btn.Bind(wx.EVT_BUTTON, self.on_manual_login)
        self.logout_btn.Bind(wx.EVT_BUTTON, self.on_manual_logout)
        self.clear_btn.Bind(wx.EVT_BUTTON, self.on_clear_manual)
        
        btn_sizer.Add(self.login_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.logout_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.clear_btn, 0, wx.ALL, 5)
        
        manual_sizer.Add(btn_sizer, 0, wx.CENTER)
        vbox.Add(manual_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # QR Code section
        qr_box = wx.StaticBox(self, label="QR Code Login/Logout")
        qr_sizer = wx.StaticBoxSizer(qr_box, wx.VERTICAL)
        
        self.camera_display = wx.StaticBitmap(self, size=(400, 300))
        qr_sizer.Add(self.camera_display, 0, wx.ALL | wx.CENTER, 10)
        
        # Camera controls
        cam_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_cam_btn = wx.Button(self, label="Start Camera", size=(120, 35))
        self.stop_cam_btn = wx.Button(self, label="Stop Camera", size=(120, 35))
        self.stop_cam_btn.Disable()
        
        self.start_cam_btn.Bind(wx.EVT_BUTTON, self.on_start_camera)
        self.stop_cam_btn.Bind(wx.EVT_BUTTON, self.on_stop_camera)
        
        cam_btn_sizer.Add(self.start_cam_btn, 0, wx.ALL, 5)
        cam_btn_sizer.Add(self.stop_cam_btn, 0, wx.ALL, 5)
        
        qr_sizer.Add(cam_btn_sizer, 0, wx.CENTER)
        vbox.Add(qr_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(vbox)
        
        # Camera variables
        self.camera = None
        self.timer = wx.Timer(self)
        self.is_scanning = False
        self.last_scanned = None
        self.Bind(wx.EVT_TIMER, self.on_update_camera, self.timer)
    
    def on_manual_login(self, event):
        user_id = self.manual_id_input.GetValue().strip()
        password = self.manual_password_input.GetValue()
        
        if not user_id or not password:
            wx.MessageBox("Please enter both Employee ID and Password", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        success, message = self.login_manager.handle_manual_login(user_id, password)
        if success:
            wx.MessageBox(message, "Success", wx.OK | wx.ICON_INFORMATION)
            self.on_clear_manual()
        else:
            wx.MessageBox(message, "Login Failed", wx.OK | wx.ICON_ERROR)
    
    def on_manual_logout(self, event):
        user_id = self.manual_id_input.GetValue().strip()
        password = self.manual_password_input.GetValue()
        
        if not user_id or not password:
            wx.MessageBox("Please enter both Employee ID and Password", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        success, message = self.login_manager.handle_manual_logout(user_id, password)
        if success:
            wx.MessageBox(message, "Success", wx.OK | wx.ICON_INFORMATION)
            self.on_clear_manual()
        else:
            wx.MessageBox(message, "Logout Failed", wx.OK | wx.ICON_ERROR)
    
    def on_clear_manual(self, event=None):
        self.manual_id_input.Clear()
        self.manual_password_input.Clear()
    
    def on_start_camera(self, event):
        self.camera = cv2.VideoCapture(0)
        if not self.camera.isOpened():
            self.camera = cv2.VideoCapture(1)
            if not self.camera.isOpened():
                wx.MessageBox("Cannot open camera. Please check camera connection.", "Error", wx.OK | wx.ICON_ERROR)
                return
        
        self.is_scanning = True
        self.start_cam_btn.Disable()
        self.stop_cam_btn.Enable()
        self.timer.Start(100)
    
    def on_stop_camera(self, event):
        self.is_scanning = False
        self.timer.Stop()
        if self.camera:
            self.camera.release()
        self.start_cam_btn.Enable()
        self.stop_cam_btn.Disable()
        # Display blank image
        blank_bitmap = wx.Bitmap(400, 300)
        self.camera_display.SetBitmap(blank_bitmap)
    
    def on_update_camera(self, event):
        if self.camera and self.is_scanning:
            ret, frame = self.camera.read()
            if ret:
                # Convert frame for display
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_resized = cv2.resize(frame_rgb, (400, 300))
                height, width = frame_resized.shape[:2]
                image = wx.Bitmap.FromBuffer(width, height, frame_resized)
                self.camera_display.SetBitmap(image)
                
                # Scan for QR codes
                qr_data = QRHandler.scan_qr_code(frame)
                if qr_data and qr_data != self.last_scanned:
                    self.last_scanned = qr_data
                    success, message = self.login_manager.handle_qr_login(qr_data)
                    if success:
                        wx.MessageBox(message, "QR Scan Result", wx.OK | wx.ICON_INFORMATION)
                    else:
                        wx.MessageBox(message, "QR Scan Error", wx.OK | wx.ICON_WARNING)
                    
                    wx.CallLater(2000, self.reset_scan)
    
    def reset_scan(self):
        self.last_scanned = None

class HistoryPanel(wx.Panel):
    def __init__(self, parent, db_manager, user_manager):
        super().__init__(parent)
        self.db_manager = db_manager
        self.user_manager = user_manager
        self.init_ui()
        wx.CallAfter(self.refresh_history)
    
    def init_ui(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, label="Login/Logout History", style=wx.ALIGN_CENTER)
        title_font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        vbox.Add(title, 0, wx.ALL | wx.CENTER, 10)
        
        # Filters
        filter_box = wx.StaticBox(self, label="Filter History")
        filter_sizer = wx.StaticBoxSizer(filter_box, wx.VERTICAL)
        
        filter_grid = wx.FlexGridSizer(2, 4, 10, 10)
        
        filter_grid.Add(wx.StaticText(self, label="User:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.user_filter = wx.ComboBox(self, style=wx.CB_READONLY, size=(200, -1))
        self.user_filter.Append("All Users", None)
        
        # Load users asynchronously to avoid database issues
        wx.CallAfter(self.load_users)
        
        self.user_filter.SetSelection(0)
        self.user_filter.Bind(wx.EVT_COMBOBOX, self.on_filter_change)
        
        filter_grid.Add(self.user_filter, 0, wx.EXPAND)
        
        # Date filters using text inputs instead of DatePickerCtrl
        filter_grid.Add(wx.StaticText(self, label="Start Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_date_input = wx.TextCtrl(self, size=(100, -1))
        self.start_date_input.SetToolTip("YYYY-MM-DD format")
        date_sizer.Add(self.start_date_input, 0, wx.RIGHT, 5)
        date_sizer.Add(wx.StaticText(self, label="(YYYY-MM-DD)"), 0, wx.ALIGN_CENTER_VERTICAL)
        filter_grid.Add(date_sizer, 0, wx.EXPAND)
        
        filter_grid.Add(wx.StaticText(self, label="End Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        date_sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.end_date_input = wx.TextCtrl(self, size=(100, -1))
        self.end_date_input.SetToolTip("YYYY-MM-DD format")
        date_sizer2.Add(self.end_date_input, 0, wx.RIGHT, 5)
        date_sizer2.Add(wx.StaticText(self, label="(YYYY-MM-DD)"), 0, wx.ALIGN_CENTER_VERTICAL)
        filter_grid.Add(date_sizer2, 0, wx.EXPAND)
        
        filter_sizer.Add(filter_grid, 0, wx.EXPAND | wx.ALL, 10)
        
        # Filter buttons
        filter_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.apply_filter_btn = wx.Button(self, label=" Refresh ", size=(120, 30))
        self.clear_filter_btn = wx.Button(self, label="Clear Filters", size=(120, 30))
        self.export_btn = wx.Button(self, label="Export to CSV", size=(120, 30))
        
        self.apply_filter_btn.Bind(wx.EVT_BUTTON, self.on_apply_filters)
        self.clear_filter_btn.Bind(wx.EVT_BUTTON, self.on_clear_filters)
        self.export_btn.Bind(wx.EVT_BUTTON, self.on_export_csv)
        
        filter_btn_sizer.Add(self.apply_filter_btn, 0, wx.ALL, 5)
        filter_btn_sizer.Add(self.clear_filter_btn, 0, wx.ALL, 5)
        filter_btn_sizer.Add(self.export_btn, 0, wx.ALL, 5)
        
        filter_sizer.Add(filter_btn_sizer, 0, wx.CENTER)
        vbox.Add(filter_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # History list
        history_box = wx.StaticBox(self, label="Login/Logout Records")
        history_sizer = wx.StaticBoxSizer(history_box, wx.VERTICAL)
        
        self.history_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.history_list.InsertColumn(0, "Employee ID", width=100)
        self.history_list.InsertColumn(1, "Name", width=150)
        self.history_list.InsertColumn(2, "Action", width=80)
        self.history_list.InsertColumn(3, "Timestamp", width=150)
        self.history_list.InsertColumn(4, "Method", width=100)
        
        history_sizer.Add(self.history_list, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(history_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(vbox)
    
    def load_users(self):
        """Load users for the filter dropdown"""
        try:
            users = self.user_manager.get_all_users()
            self.user_filter.Clear()
            self.user_filter.Append("All Users", None)
            
            for user in users:
                self.user_filter.Append(f"{user['name']} ({user['user_id']})", user['user_id'])
            
            self.user_filter.SetSelection(0)
        except Exception as e:
            print(f"Error loading users: {e}")
    
    def on_apply_filters(self, event):
        self.refresh_history()
    
    def on_clear_filters(self, event):
        self.user_filter.SetSelection(0)
        self.start_date_input.Clear()
        self.end_date_input.Clear()
        self.refresh_history()
    
    def refresh_history(self):
        self.history_list.DeleteAllItems()
        
        # Get filter values
        selected_user = self.user_filter.GetClientData(self.user_filter.GetSelection())
        
        start_date = self.start_date_input.GetValue().strip()
        end_date = self.end_date_input.GetValue().strip()
        
        # Validate date formats
        if start_date and not self.validate_date_format(start_date):
            wx.MessageBox("Start date must be in YYYY-MM-DD format", "Invalid Date", wx.OK | wx.ICON_WARNING)
            return
        
        if end_date and not self.validate_date_format(end_date):
            wx.MessageBox("End date must be in YYYY-MM-DD format", "Invalid Date", wx.OK | wx.ICON_WARNING)
            return
        
        # Get history
        try:
            history = self.db_manager.get_login_history(selected_user, start_date, end_date)
            
            for record in history:
                index = self.history_list.InsertItem(self.history_list.GetItemCount(), record[0])  # user_id
                self.history_list.SetItem(index, 1, record[1])  # name
                self.history_list.SetItem(index, 2, record[2].upper())  # action
                self.history_list.SetItem(index, 3, record[3])  # timestamp
                self.history_list.SetItem(index, 4, record[4].title())  # method
                
                # Color code based on action
                if record[2].lower() == "login":
                    self.history_list.SetItemTextColour(index, wx.Colour(0, 128, 0))  # Green
                else:
                    self.history_list.SetItemTextColour(index, wx.Colour(128, 0, 0))  # Red
        except Exception as e:
            wx.MessageBox(f"Error loading history: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
    
    def validate_date_format(self, date_str):
        """Validate YYYY-MM-DD date format"""
        try:
            datetime.datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def on_filter_change(self, event):
        self.refresh_history()
    
    def on_export_csv(self, event):
        with wx.FileDialog(self, "Save CSV file", wildcard="CSV files (*.csv)|*.csv",
                          style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            
            filename = dialog.GetPath()
            try:
                # Get current filter values
                selected_user = self.user_filter.GetClientData(self.user_filter.GetSelection())
                start_date = self.start_date_input.GetValue().strip()
                end_date = self.end_date_input.GetValue().strip()
                
                history = self.db_manager.get_login_history(selected_user, start_date, end_date)
                
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Employee ID', 'Name', 'Action', 'Timestamp', 'Method'])
                    
                    for record in history:
                        writer.writerow([
                            record[0],  # user_id
                            record[1],  # name
                            record[2].upper(),  # action
                            record[3],  # timestamp
                            record[4].title()  # method
                        ])
                
                wx.MessageBox(f"History exported to {filename}", "Success", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Error exporting CSV: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

class LeaveManagementPanel(wx.Panel):
    def __init__(self, parent, db_manager, user_manager):
        super().__init__(parent)
        self.db_manager = db_manager
        self.user_manager = user_manager
        self.init_ui()
        wx.CallAfter(self.refresh_data)
    
    def init_ui(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, label="Leave and Attendance Management", style=wx.ALIGN_CENTER)
        title_font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        vbox.Add(title, 0, wx.ALL | wx.CENTER, 10)
        
        # Create notebook for tabs
        notebook = wx.Notebook(self)
        
        # Mark Leave tab
        self.mark_leave_tab = wx.Panel(notebook)
        self.init_mark_leave_tab()
        notebook.AddPage(self.mark_leave_tab, "Mark Leave")
        
        # View Attendance tab
        self.view_attendance_tab = wx.Panel(notebook)
        self.init_view_attendance_tab()
        notebook.AddPage(self.view_attendance_tab, "View Attendance")
        
        # Calendar tab
        self.calendar_tab = CalendarPanel(notebook, self.db_manager)
        notebook.AddPage(self.calendar_tab, "Company Calendar")
        
        # Attendance Summary tab
        self.summary_tab = wx.Panel(notebook)
        self.init_summary_tab()
        notebook.AddPage(self.summary_tab, "Attendance Summary")
        
        vbox.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(vbox)
    
    def init_mark_leave_tab(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # User selection
        user_sizer = wx.BoxSizer(wx.HORIZONTAL)
        user_sizer.Add(wx.StaticText(self.mark_leave_tab, label="Select User:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.user_combo = wx.ComboBox(self.mark_leave_tab, style=wx.CB_READONLY, size=(200, -1))
        user_sizer.Add(self.user_combo, 0, wx.RIGHT, 10)
        
        vbox.Add(user_sizer, 0, wx.ALL, 10)
        
        # Date range
        date_box = wx.StaticBox(self.mark_leave_tab, label="Date Range")
        date_sizer = wx.StaticBoxSizer(date_box, wx.VERTICAL)
        
        date_grid = wx.FlexGridSizer(2, 2, 10, 10)
        date_grid.AddGrowableCol(1, 1)
        
        date_grid.Add(wx.StaticText(self.mark_leave_tab, label="Start Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        start_date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_date = wx.TextCtrl(self.mark_leave_tab, size=(120, -1))
        self.start_date.SetValue(datetime.datetime.now().strftime('%Y-%m-%d'))
        start_date_sizer.Add(self.start_date, 0, wx.RIGHT, 5)
        start_date_sizer.Add(wx.StaticText(self.mark_leave_tab, label="(YYYY-MM-DD)"), 0, wx.ALIGN_CENTER_VERTICAL)
        date_grid.Add(start_date_sizer, 0, wx.EXPAND)
        
        date_grid.Add(wx.StaticText(self.mark_leave_tab, label="End Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        end_date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.end_date = wx.TextCtrl(self.mark_leave_tab, size=(120, -1))
        self.end_date.SetValue(datetime.datetime.now().strftime('%Y-%m-%d'))
        end_date_sizer.Add(self.end_date, 0, wx.RIGHT, 5)
        end_date_sizer.Add(wx.StaticText(self.mark_leave_tab, label="(YYYY-MM-DD)"), 0, wx.ALIGN_CENTER_VERTICAL)
        date_grid.Add(end_date_sizer, 0, wx.EXPAND)
        
        date_sizer.Add(date_grid, 0, wx.EXPAND | wx.ALL, 10)
        vbox.Add(date_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Leave type
        type_box = wx.StaticBox(self.mark_leave_tab, label="Leave Type")
        type_sizer = wx.StaticBoxSizer(type_box, wx.VERTICAL)
        
        self.leave_type = wx.RadioBox(self.mark_leave_tab, choices=["Leave", "Sick Leave", "Personal Leave", "Absent"], majorDimension=2, style=wx.RA_SPECIFY_ROWS)
        type_sizer.Add(self.leave_type, 0, wx.EXPAND | wx.ALL, 10)
        vbox.Add(type_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Notes
        notes_box = wx.StaticBox(self.mark_leave_tab, label="Notes (Optional)")
        notes_sizer = wx.StaticBoxSizer(notes_box, wx.VERTICAL)
        self.notes_input = wx.TextCtrl(self.mark_leave_tab, style=wx.TE_MULTILINE, size=(-1, 60))
        notes_sizer.Add(self.notes_input, 1, wx.EXPAND | wx.ALL, 10)
        vbox.Add(notes_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.mark_leave_btn = wx.Button(self.mark_leave_tab, label="Mark Leave", size=(120, 35))
        self.mark_unmarked_btn = wx.Button(self.mark_leave_tab, label="Mark Unmarked as Leave", size=(180, 35))
        
        self.mark_leave_btn.Bind(wx.EVT_BUTTON, self.on_mark_leave)
        self.mark_unmarked_btn.Bind(wx.EVT_BUTTON, self.on_mark_unmarked_as_leave)
        
        btn_sizer.Add(self.mark_leave_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.mark_unmarked_btn, 0, wx.ALL, 5)
        
        vbox.Add(btn_sizer, 0, wx.CENTER | wx.ALL, 10)
        
        self.mark_leave_tab.SetSizer(vbox)
    
    def init_view_attendance_tab(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Filters
        filter_box = wx.StaticBox(self.view_attendance_tab, label="Filters")
        filter_sizer = wx.StaticBoxSizer(filter_box, wx.VERTICAL)
        
        filter_grid = wx.FlexGridSizer(2, 4, 10, 10)
        filter_grid.AddGrowableCol(1, 1)
        
        filter_grid.Add(wx.StaticText(self.view_attendance_tab, label="User:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.attendance_user_filter = wx.ComboBox(self.view_attendance_tab, style=wx.CB_READONLY, size=(200, -1))
        self.attendance_user_filter.Append("All Users", None)
        filter_grid.Add(self.attendance_user_filter, 0, wx.EXPAND)
        
        filter_grid.Add(wx.StaticText(self.view_attendance_tab, label="Start Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        start_date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.attendance_start_date = wx.TextCtrl(self.view_attendance_tab, size=(120, -1))
        # Default to first day of current month
        first_day = datetime.datetime.now().replace(day=1).strftime('%Y-%m-%d')
        self.attendance_start_date.SetValue(first_day)
        start_date_sizer.Add(self.attendance_start_date, 0, wx.RIGHT, 5)
        start_date_sizer.Add(wx.StaticText(self.view_attendance_tab, label="(YYYY-MM-DD)"), 0, wx.ALIGN_CENTER_VERTICAL)
        filter_grid.Add(start_date_sizer, 0, wx.EXPAND)
        
        filter_grid.Add(wx.StaticText(self.view_attendance_tab, label="End Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        end_date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.attendance_end_date = wx.TextCtrl(self.view_attendance_tab, size=(120, -1))
        self.attendance_end_date.SetValue(datetime.datetime.now().strftime('%Y-%m-%d'))
        end_date_sizer.Add(self.attendance_end_date, 0, wx.RIGHT, 5)
        end_date_sizer.Add(wx.StaticText(self.view_attendance_tab, label="(YYYY-MM-DD)"), 0, wx.ALIGN_CENTER_VERTICAL)
        filter_grid.Add(end_date_sizer, 0, wx.EXPAND)
        
        filter_sizer.Add(filter_grid, 0, wx.EXPAND | wx.ALL, 10)
        
        # Filter buttons
        filter_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_attendance_btn = wx.Button(self.view_attendance_tab, label="Refresh", size=(100, 30))
        self.export_attendance_btn = wx.Button(self.view_attendance_tab, label="Export to CSV", size=(120, 30))
        
        self.refresh_attendance_btn.Bind(wx.EVT_BUTTON, self.on_refresh_attendance)
        self.export_attendance_btn.Bind(wx.EVT_BUTTON, self.on_export_attendance)
        
        filter_btn_sizer.Add(self.refresh_attendance_btn, 0, wx.ALL, 5)
        filter_btn_sizer.Add(self.export_attendance_btn, 0, wx.ALL, 5)
        
        filter_sizer.Add(filter_btn_sizer, 0, wx.CENTER)
        vbox.Add(filter_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Attendance list
        attendance_box = wx.StaticBox(self.view_attendance_tab, label="Attendance Records")
        attendance_sizer = wx.StaticBoxSizer(attendance_box, wx.VERTICAL)
        
        self.attendance_list = wx.ListCtrl(self.view_attendance_tab, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.attendance_list.InsertColumn(0, "Employee ID", width=100)
        self.attendance_list.InsertColumn(1, "Name", width=150)
        self.attendance_list.InsertColumn(2, "Date", width=100)
        self.attendance_list.InsertColumn(3, "Status", width=100)
        self.attendance_list.InsertColumn(4, "Login Time", width=120)
        self.attendance_list.InsertColumn(5, "Logout Time", width=120)
        self.attendance_list.InsertColumn(6, "Hours Worked", width=100)
        self.attendance_list.InsertColumn(7, "Notes", width=200)
        
        attendance_sizer.Add(self.attendance_list, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(attendance_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        self.view_attendance_tab.SetSizer(vbox)
    
    def init_summary_tab(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Date range for summary
        summary_filter_box = wx.StaticBox(self.summary_tab, label="Summary Period")
        summary_filter_sizer = wx.StaticBoxSizer(summary_filter_box, wx.VERTICAL)
        
        summary_grid = wx.FlexGridSizer(2, 2, 10, 10)
        summary_grid.AddGrowableCol(1, 1)
        
        summary_grid.Add(wx.StaticText(self.summary_tab, label="Start Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        start_date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.summary_start_date = wx.TextCtrl(self.summary_tab, size=(120, -1))
        # Default to first day of current month
        first_day = datetime.datetime.now().replace(day=1).strftime('%Y-%m-%d')
        self.summary_start_date.SetValue(first_day)
        start_date_sizer.Add(self.summary_start_date, 0, wx.RIGHT, 5)
        start_date_sizer.Add(wx.StaticText(self.summary_tab, label="(YYYY-MM-DD)"), 0, wx.ALIGN_CENTER_VERTICAL)
        summary_grid.Add(start_date_sizer, 0, wx.EXPAND)
        
        summary_grid.Add(wx.StaticText(self.summary_tab, label="End Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        end_date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.summary_end_date = wx.TextCtrl(self.summary_tab, size=(120, -1))
        self.summary_end_date.SetValue(datetime.datetime.now().strftime('%Y-%m-%d'))
        end_date_sizer.Add(self.summary_end_date, 0, wx.RIGHT, 5)
        end_date_sizer.Add(wx.StaticText(self.summary_tab, label="(YYYY-MM-DD)"), 0, wx.ALIGN_CENTER_VERTICAL)
        summary_grid.Add(end_date_sizer, 0, wx.EXPAND)
        
        summary_filter_sizer.Add(summary_grid, 0, wx.EXPAND | wx.ALL, 10)
        
        # Generate button
        self.generate_summary_btn = wx.Button(self.summary_tab, label="Generate Summary", size=(140, 35))
        self.generate_summary_btn.Bind(wx.EVT_BUTTON, self.on_generate_summary)
        summary_filter_sizer.Add(self.generate_summary_btn, 0, wx.ALL | wx.CENTER, 10)
        
        vbox.Add(summary_filter_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Summary list
        summary_box = wx.StaticBox(self.summary_tab, label="Attendance Summary")
        summary_sizer = wx.StaticBoxSizer(summary_box, wx.VERTICAL)
        
        self.summary_list = wx.ListCtrl(self.summary_tab, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.summary_list.InsertColumn(0, "Employee ID", width=100)
        self.summary_list.InsertColumn(1, "Name", width=150)
        self.summary_list.InsertColumn(2, "Total Days", width=80)
        self.summary_list.InsertColumn(3, "Present", width=80)
        self.summary_list.InsertColumn(4, "Leave", width=80)
        self.summary_list.InsertColumn(5, "Holiday", width=80)
        self.summary_list.InsertColumn(6, "Absent", width=80)
        self.summary_list.InsertColumn(7, "Attendance %", width=100)
        
        summary_sizer.Add(self.summary_list, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(summary_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        self.summary_tab.SetSizer(vbox)
    
    def refresh_data(self):
        """Refresh all data in the panel"""
        self.load_users()
        self.refresh_attendance()
    
    def load_users(self):
        """Load users for dropdowns"""
        try:
            users = self.user_manager.get_all_users()
            
            # Clear and populate user combo in mark leave tab
            self.user_combo.Clear()
            for user in users:
                self.user_combo.Append(f"{user['name']} ({user['user_id']})", user['user_id'])
            
            # Clear and populate user filter in view attendance tab
            self.attendance_user_filter.Clear()
            self.attendance_user_filter.Append("All Users", None)
            for user in users:
                self.attendance_user_filter.Append(f"{user['name']} ({user['user_id']})", user['user_id'])
            self.attendance_user_filter.SetSelection(0)
            
        except Exception as e:
            print(f"Error loading users: {e}")
    
    def on_mark_leave(self, event):
        user_id = self.user_combo.GetClientData(self.user_combo.GetSelection())
        start_date = self.start_date.GetValue().strip()
        end_date = self.end_date.GetValue().strip()
        leave_type = self.leave_type.GetStringSelection().lower().replace(" ", "_")
        notes = self.notes_input.GetValue().strip()
        
        if not user_id:
            wx.MessageBox("Please select a user", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        if not self.validate_date_format(start_date) or not self.validate_date_format(end_date):
            wx.MessageBox("Please enter valid dates in YYYY-MM-DD format", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Mark leave for each day in the range
        current_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
        days_marked = 0
        
        while current_date <= end_date_obj:
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Skip if it's a holiday
            if not self.db_manager.is_holiday(date_str):
                success = self.db_manager.mark_attendance(user_id, date_str, leave_type, notes=notes)
                if success:
                    days_marked += 1
            
            current_date += timedelta(days=1)
        
        wx.MessageBox(f"Leave marked successfully for {days_marked} days", "Success", wx.OK | wx.ICON_INFORMATION)
        self.refresh_attendance()
    
    def on_mark_unmarked_as_leave(self, event):
        user_id = self.user_combo.GetClientData(self.user_combo.GetSelection())
        start_date = self.start_date.GetValue().strip()
        end_date = self.end_date.GetValue().strip()
        leave_type = self.leave_type.GetStringSelection().lower().replace(" ", "_")
        
        if not user_id:
            wx.MessageBox("Please select a user", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        if not self.validate_date_format(start_date) or not self.validate_date_format(end_date):
            wx.MessageBox("Please enter valid dates in YYYY-MM-DD format", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        success = self.db_manager.mark_unmarked_dates_as_leave(user_id, start_date, end_date, leave_type)
        if success:
            wx.MessageBox("Unmarked dates successfully marked as leave", "Success", wx.OK | wx.ICON_INFORMATION)
            self.refresh_attendance()
        else:
            wx.MessageBox("Error marking unmarked dates as leave", "Error", wx.OK | wx.ICON_ERROR)
    
    def on_refresh_attendance(self, event=None):
        self.refresh_attendance()
    
    def refresh_attendance(self):
        """Refresh attendance list"""
        self.attendance_list.DeleteAllItems()
        
        selected_user = self.attendance_user_filter.GetClientData(self.attendance_user_filter.GetSelection())
        start_date = self.attendance_start_date.GetValue().strip()
        end_date = self.attendance_end_date.GetValue().strip()
        
        # Validate dates
        if start_date and not self.validate_date_format(start_date):
            wx.MessageBox("Start date must be in YYYY-MM-DD format", "Invalid Date", wx.OK | wx.ICON_WARNING)
            return
        
        if end_date and not self.validate_date_format(end_date):
            wx.MessageBox("End date must be in YYYY-MM-DD format", "Invalid Date", wx.OK | wx.ICON_WARNING)
            return
        
        try:
            attendance = self.db_manager.get_attendance(selected_user, start_date, end_date)
            
            for record in attendance:
                index = self.attendance_list.InsertItem(self.attendance_list.GetItemCount(), record[0])  # user_id
                self.attendance_list.SetItem(index, 1, record[1])  # name
                self.attendance_list.SetItem(index, 2, record[2])  # date
                self.attendance_list.SetItem(index, 3, record[3].title())  # status
                self.attendance_list.SetItem(index, 4, record[4] or "")  # login_time
                self.attendance_list.SetItem(index, 5, record[5] or "")  # logout_time
                self.attendance_list.SetItem(index, 6, str(record[6]) if record[6] else "")  # hours_worked
                self.attendance_list.SetItem(index, 7, record[7] or "")  # notes
                
                # Color code based on status
                if record[3] == "present":
                    self.attendance_list.SetItemTextColour(index, wx.Colour(0, 128, 0))  # Green
                elif record[3] == "leave":
                    self.attendance_list.SetItemTextColour(index, wx.Colour(255, 165, 0))  # Orange
                elif record[3] == "holiday":
                    self.attendance_list.SetItemTextColour(index, wx.Colour(0, 0, 255))  # Blue
                elif record[3] == "absent":
                    self.attendance_list.SetItemTextColour(index, wx.Colour(255, 0, 0))  # Red
                    
        except Exception as e:
            wx.MessageBox(f"Error loading attendance: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
    
    def on_export_attendance(self, event):
        with wx.FileDialog(self, "Save CSV file", wildcard="CSV files (*.csv)|*.csv",
                          style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            
            filename = dialog.GetPath()
            try:
                selected_user = self.attendance_user_filter.GetClientData(self.attendance_user_filter.GetSelection())
                start_date = self.attendance_start_date.GetValue().strip()
                end_date = self.attendance_end_date.GetValue().strip()
                
                attendance = self.db_manager.get_attendance(selected_user, start_date, end_date)
                
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Employee ID', 'Name', 'Date', 'Status', 'Login Time', 'Logout Time', 'Hours Worked', 'Notes', 'Holidays/Events'])
                    
                    # Get holidays and events for the date range
                    holidays = self.db_manager.get_holidays(start_date, end_date)
                    events = self.db_manager.get_events(start_date, end_date)
                    
                    holiday_dict = {holiday[0]: holiday[1] for holiday in holidays}
                    event_dict = {}
                    for event in events:
                        if event[3] not in event_dict:
                            event_dict[event[3]] = []
                        event_dict[event[3]].append(f"{event[4]}: {event[1]}")
                    
                    for record in attendance:
                        date_str = record[2]
                        holiday_event_info = ""
                        
                        if date_str in holiday_dict:
                            holiday_event_info = f"Holiday: {holiday_dict[date_str]}"
                        elif date_str in event_dict:
                            holiday_event_info = "; ".join(event_dict[date_str])
                        
                        writer.writerow([
                            record[0],  # user_id
                            record[1],  # name
                            record[2],  # date
                            record[3].title(),  # status
                            record[4] or "",  # login_time
                            record[5] or "",  # logout_time
                            record[6] or "",  # hours_worked
                            record[7] or "",  # notes
                            holiday_event_info  # holidays and events
                        ])
                
                wx.MessageBox(f"Attendance exported to {filename}\n\nHolidays and events are included in the export.", "Success", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Error exporting CSV: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
    
    def on_generate_summary(self, event):
        """Generate attendance summary"""
        self.summary_list.DeleteAllItems()
        
        start_date = self.summary_start_date.GetValue().strip()
        end_date = self.summary_end_date.GetValue().strip()
        
        if not self.validate_date_format(start_date) or not self.validate_date_format(end_date):
            wx.MessageBox("Please enter valid dates in YYYY-MM-DD format", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        try:
            summary = self.db_manager.get_attendance_summary(start_date, end_date)
            
            for record in summary:
                user_id, name, total_days, present, leave, holiday, absent = record
                
                # Calculate attendance percentage (excluding holidays)
                working_days = total_days - holiday
                if working_days > 0:
                    attendance_pct = (present / working_days) * 100
                else:
                    attendance_pct = 0
                
                index = self.summary_list.InsertItem(self.summary_list.GetItemCount(), user_id)
                self.summary_list.SetItem(index, 1, name)
                self.summary_list.SetItem(index, 2, str(total_days))
                self.summary_list.SetItem(index, 3, str(present))
                self.summary_list.SetItem(index, 4, str(leave))
                self.summary_list.SetItem(index, 5, str(holiday))
                self.summary_list.SetItem(index, 6, str(absent))
                self.summary_list.SetItem(index, 7, f"{attendance_pct:.1f}%")
                
                # Color code based on attendance percentage
                if attendance_pct >= 90:
                    self.summary_list.SetItemTextColour(index, wx.Colour(0, 128, 0))  # Green
                elif attendance_pct >= 75:
                    self.summary_list.SetItemTextColour(index, wx.Colour(255, 165, 0))  # Orange
                else:
                    self.summary_list.SetItemTextColour(index, wx.Colour(255, 0, 0))  # Red
                    
        except Exception as e:
            wx.MessageBox(f"Error generating summary: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
    
    def validate_date_format(self, date_str):
        """Validate YYYY-MM-DD date format"""
        try:
            datetime.datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False

class AdminPanel(wx.Panel):
    def __init__(self, parent, user_manager, login_manager, db_manager):
        super().__init__(parent)
        self.user_manager = user_manager
        self.login_manager = login_manager
        self.db_manager = db_manager
        self.init_ui()
        wx.CallAfter(self.refresh_user_list)
    
    def init_ui(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Create notebook for tabs
        notebook = wx.Notebook(self)
        
        # User Management tab
        self.user_management_tab = wx.Panel(notebook)
        self.init_user_management_tab()
        notebook.AddPage(self.user_management_tab, "User Management")
        
        # Leave Management tab
        self.leave_management_tab = LeaveManagementPanel(notebook, self.db_manager, self.user_manager)
        notebook.AddPage(self.leave_management_tab, "Leave Management")
        
        vbox.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(vbox)
    
    def init_user_management_tab(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self.user_management_tab, label="Admin Panel - User Management", style=wx.ALIGN_CENTER)
        title_font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        vbox.Add(title, 0, wx.ALL | wx.CENTER, 10)
        
        # Add user section
        add_user_box = wx.StaticBox(self.user_management_tab, label="Add New User")
        add_user_sizer = wx.StaticBoxSizer(add_user_box, wx.VERTICAL)
        
        grid = wx.FlexGridSizer(6, 2, 10, 10)
        grid.AddGrowableCol(1, 1)
        
        # Name field
        grid.Add(wx.StaticText(self.user_management_tab, label="Full Name:*"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.name_input = wx.TextCtrl(self.user_management_tab, size=(250, -1))
        grid.Add(self.name_input, 0, wx.EXPAND)
        
        # Address field
        grid.Add(wx.StaticText(self.user_management_tab, label="Address:*"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.address_input = wx.TextCtrl(self.user_management_tab, size=(250, -1))
        grid.Add(self.address_input, 0, wx.EXPAND)

        # Email field
        grid.Add(wx.StaticText(self.user_management_tab, label="Email:*"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.email_input = wx.TextCtrl(self.user_management_tab, size=(250, -1))
        grid.Add(self.email_input, 0, wx.EXPAND)
        
        # Phone field
        grid.Add(wx.StaticText(self.user_management_tab, label="Phone:*"), 0, wx.ALIGN_CENTER_VERTICAL)
        phone_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.phone_input = wx.TextCtrl(self.user_management_tab, size=(150, -1))
        phone_sizer.Add(self.phone_input, 0, wx.RIGHT, 5)
        phone_sizer.Add(wx.StaticText(self.user_management_tab, label="(10 digits)"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(phone_sizer, 0, wx.EXPAND)
        
        # Password field
        grid.Add(wx.StaticText(self.user_management_tab, label="Password:*"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.password_input = wx.TextCtrl(self.user_management_tab, style=wx.TE_PASSWORD, size=(200, -1))
        grid.Add(self.password_input, 0, wx.EXPAND)
        
        # ID Prefix
        grid.Add(wx.StaticText(self.user_management_tab, label="ID Prefix:"), 0, wx.ALIGN_CENTER_VERTICAL)
        prefix_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.prefix_input = wx.TextCtrl(self.user_management_tab, value="ALLY", size=(60, -1))
        prefix_sizer.Add(self.prefix_input, 0, wx.RIGHT, 5)
        prefix_sizer.Add(wx.StaticText(self.user_management_tab, label="(e.g.,ALLY, EMP, USR, ADM)"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(prefix_sizer, 0, wx.EXPAND)
        
        add_user_sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 15)
        
        # Add user button
        self.add_user_btn = wx.Button(self.user_management_tab, label="Add User & Generate QR Code", size=(220, 40))
        self.add_user_btn.Bind(wx.EVT_BUTTON, self.on_add_user)
        add_user_sizer.Add(self.add_user_btn, 0, wx.ALL | wx.CENTER, 10)
        
        vbox.Add(add_user_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # User management section
        user_mgmt_box = wx.StaticBox(self.user_management_tab, label="User Management")
        user_mgmt_sizer = wx.StaticBoxSizer(user_mgmt_box, wx.VERTICAL)
        
        # User list
        self.user_list = wx.ListCtrl(self.user_management_tab, style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SINGLE_SEL)
        self.user_list.InsertColumn(0, "Employee ID", width=100)
        self.user_list.InsertColumn(1, "Name", width=150)
        self.user_list.InsertColumn(2, "Address", width=150)
        self.user_list.InsertColumn(3, "Email", width=200)
        self.user_list.InsertColumn(4, "Phone", width=120)
        self.user_list.InsertColumn(5, "Status", width=100)
        self.user_list.InsertColumn(6, "Created", width=120)
        
        user_mgmt_sizer.Add(self.user_list, 1, wx.EXPAND | wx.ALL, 5)
        
        # Management buttons
        mgmt_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.refresh_btn = wx.Button(self.user_management_tab, label="Refresh List", size=(100, 35))
        self.reset_password_btn = wx.Button(self.user_management_tab, label="Reset Password", size=(120, 35))
        self.force_logout_btn = wx.Button(self.user_management_tab, label="Force Logout", size=(120, 35))
        self.view_qr_btn = wx.Button(self.user_management_tab, label="View QR Code", size=(120, 35))
        self.debug_auth_btn = wx.Button(self.user_management_tab, label="Debug Auth", size=(100, 35))
        
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        self.reset_password_btn.Bind(wx.EVT_BUTTON, self.on_reset_password)
        self.force_logout_btn.Bind(wx.EVT_BUTTON, self.on_force_logout)
        self.view_qr_btn.Bind(wx.EVT_BUTTON, self.on_view_qr)
        self.debug_auth_btn.Bind(wx.EVT_BUTTON, self.on_debug_auth)
        
        mgmt_btn_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        mgmt_btn_sizer.Add(self.reset_password_btn, 0, wx.ALL, 5)
        mgmt_btn_sizer.Add(self.force_logout_btn, 0, wx.ALL, 5)
        mgmt_btn_sizer.Add(self.view_qr_btn, 0, wx.ALL, 5)
        mgmt_btn_sizer.Add(self.debug_auth_btn, 0, wx.ALL, 5)
        
        user_mgmt_sizer.Add(mgmt_btn_sizer, 0, wx.CENTER)
        vbox.Add(user_mgmt_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        self.user_management_tab.SetSizer(vbox)
    
    def get_selected_user(self):
        """Get selected user ID from list"""
        selected_index = self.user_list.GetFirstSelected()
        if selected_index == -1:
            return None
        return self.user_list.GetItemText(selected_index)
    
    def on_add_user(self, event):
        name = self.name_input.GetValue().strip()
        address = self.address_input.GetValue().strip()
        email = self.email_input.GetValue().strip()
        phone = self.phone_input.GetValue().strip()
        password = self.password_input.GetValue()
        prefix = self.prefix_input.GetValue().strip().upper()
        
        if not prefix:
            prefix = "ALLY"
        
        # Validate required fields
        if not all([name, address, email, phone, password]):
            wx.MessageBox("Please fill in all required fields (*)", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Validate phone number
        if not SecurityManager.validate_phone(phone):
            wx.MessageBox("Phone number must be exactly 10 digits", "Validation Error", wx.OK | wx.ICON_WARNING)
            return
        
        # Add user
        success, user_id, message = self.user_manager.add_user(name, address, email, phone, password, prefix)
        
        if success:
            wx.MessageBox(f"{message}\n\nEmployee ID: {user_id}", "Success", wx.OK | wx.ICON_INFORMATION)
            self.clear_form()
            self.refresh_user_list()
        else:
            wx.MessageBox(message, "Error", wx.OK | wx.ICON_ERROR)
    
    def on_reset_password(self, event):
        user_id = self.get_selected_user()
        if not user_id:
            wx.MessageBox("Please select a user from the list", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        user = self.user_manager.get_user_by_id(user_id)
        if not user:
            wx.MessageBox("Selected user not found", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Passes both the name (for the dialog title/instruction) and the ID
        dialog = PasswordResetDialog(self, user['name'], user_id) 
        
        if dialog.ShowModal() == wx.ID_OK:
            new_password = dialog.get_password()
            
            # This relies on self.user_manager having a method that handles hashing and DB update.
            success, message = self.user_manager.reset_user_password(user_id, new_password)
            if success:
                wx.MessageBox(message, "Success", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox(message, "Error", wx.OK | wx.ICON_ERROR)
        
        dialog.Destroy() # Crucial: always destroy wx.Dialogs
    
    def on_force_logout(self, event):
        user_id = self.get_selected_user()
        if not user_id:
            wx.MessageBox("Please select a user from the list", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        user = self.user_manager.get_user_by_id(user_id)
        if not user:
            wx.MessageBox("Selected user not found", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Confirm force logout
        confirm = wx.MessageBox(
            f"Are you sure you want to force logout {user['name']} ({user_id})?",
            "Confirm Force Logout",
            wx.YES_NO | wx.ICON_QUESTION
        )
        
        if confirm == wx.YES:
            success, message = self.login_manager.admin_logout_user(user_id)
            if success:
                wx.MessageBox(message, "Success", wx.OK | wx.ICON_INFORMATION)
                self.refresh_user_list()
            else:
                wx.MessageBox(message, "Info", wx.OK | wx.ICON_INFORMATION)
    
    def on_view_qr(self, event):
        user_id = self.get_selected_user()
        if not user_id:
            wx.MessageBox("Please select a user from the list", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        user = self.user_manager.get_user_by_id(user_id)
        if not user:
            wx.MessageBox("Selected user not found", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        qr_path = Path(get_qr_codes_path()) / f"{user_id}.png"
        if not qr_path.exists():
            wx.MessageBox(f"QR code not found for {user_id}", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Display QR code in a dialog
        dialog = wx.Dialog(self, title=f"QR Code - {user['name']} ({user_id})", size=(400, 450))
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # User info
        info_text = wx.StaticText(dialog, label=f"Name: {user['name']}\nID: {user_id}\nEmail: {user['email']}\nAddress: {user['address']}")
        vbox.Add(info_text, 0, wx.ALL | wx.CENTER, 10)
        
        # QR code image
        image = wx.Image(str(qr_path), wx.BITMAP_TYPE_PNG)
        image = image.Scale(300, 300, wx.IMAGE_QUALITY_HIGH)
        bitmap = wx.Bitmap(image)
        qr_display = wx.StaticBitmap(dialog, bitmap=bitmap)
        vbox.Add(qr_display, 0, wx.ALL | wx.CENTER, 10)
        
        # Close button
        close_btn = wx.Button(dialog, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: dialog.EndModal(wx.ID_OK))
        vbox.Add(close_btn, 0, wx.ALL | wx.CENTER, 10)
        
        dialog.SetSizer(vbox)
        dialog.Centre()
        dialog.ShowModal()
    
    def on_debug_auth(self, event):
        """Debug authentication for selected user"""
        user_id = self.get_selected_user()
        if not user_id:
            wx.MessageBox("Please select a user first", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Get test password from user
        dialog = wx.TextEntryDialog(self, f"Enter test password for {user_id}:", "Debug Authentication", style=wx.TE_PASSWORD)
        if dialog.ShowModal() == wx.ID_OK:
            test_password = dialog.GetValue()
            self.user_manager.debug_user_authentication(user_id, test_password)
            wx.MessageBox("Check console for debug output", "Debug Info", wx.OK | wx.ICON_INFORMATION)
        dialog.Destroy()
    
    def clear_form(self):
        """Clear the add user form"""
        self.name_input.Clear()
        self.address_input.Clear()
        self.email_input.Clear()
        self.phone_input.Clear()
        self.password_input.Clear()
        self.prefix_input.SetValue("ALLY")
    
    def on_refresh(self, event):
        """Handle refresh button click by refreshing the user list."""
        self.refresh_user_list()
        
        # Optionally, refresh other AdminPanel tabs if they exist and have a refresh method
        if hasattr(self, 'leave_management_tab'):
            self.leave_management_tab.refresh_data()
        
        wx.MessageBox("User data refreshed.", "Success", wx.OK | wx.ICON_INFORMATION)

    def refresh_user_list(self):
        """Refreshes the list of users displayed in the User Management list control."""
        try:
            # Clear the current list control content
            self.user_list.DeleteAllItems()
            
            # Fetch the latest user data
            users = self.user_manager.get_all_users()

            # Populate the list control
            for i, user in enumerate(users):
                index = self.user_list.InsertItem(i, user['user_id'])
                self.user_list.SetItem(index, 1, user['name'])
                self.user_list.SetItem(index, 2, user['address'])
                self.user_list.SetItem(index, 3, user['email'])
                self.user_list.SetItem(index, 4, user['phone'])
                self.user_list.SetItem(index, 5, user['status'])
                self.user_list.SetItem(index, 6, str(user['created_at']))

        except Exception as e:
            wx.MessageBox(f"Failed to refresh user list: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

class LoginDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Admin Login", size=(300, 200))
        self.init_ui()
    
    def init_ui(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        vbox.Add(wx.StaticText(self, label="Admin Authentication Required"), 0, wx.ALL | wx.CENTER, 10)
        
        grid = wx.FlexGridSizer(2, 2, 10, 10)
        grid.AddGrowableCol(1, 1)
        
        grid.Add(wx.StaticText(self, label="Password:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.password_input = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        grid.Add(self.password_input, 0, wx.EXPAND)
        
        vbox.Add(grid, 0, wx.EXPAND | wx.ALL, 15)
        
        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        login_btn = wx.Button(self, label="Login")
        cancel_btn = wx.Button(self, label="Cancel")
        
        login_btn.Bind(wx.EVT_BUTTON, self.on_login)
        cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)
        
        btn_sizer.Add(login_btn, 0, wx.ALL, 5)
        btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
        
        vbox.Add(btn_sizer, 0, wx.CENTER)
        
        self.SetSizer(vbox)
        self.Centre()
    
    def on_login(self, event):
        # For demo purposes, using a simple password check
        # In production, this should be properly secured
        if self.password_input.GetValue() == "admin123":
            self.EndModal(wx.ID_OK)
        else:
            wx.MessageBox("Invalid admin password", "Error", wx.OK | wx.ICON_ERROR)
    
    def on_cancel(self, event):
        self.EndModal(wx.ID_CANCEL)

class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Secure QR Login System", size=(1200, 800))
        
        # Initialize managers
        self.db_manager = DatabaseManager()
        self.user_manager = UserManager(self.db_manager)
        self.login_manager = LoginManager(self.db_manager, self.user_manager)
        
        self.init_ui()
        self.Centre()
    
    def init_ui(self):
        # Create notebook for tabs
        notebook = wx.Notebook(self)
        
        # Add tabs
        self.user_tab = UserPanel(notebook, self.login_manager)
        self.history_tab = HistoryPanel(notebook, self.db_manager, self.user_manager)
        
        notebook.AddPage(self.user_tab, "User Panel")
        notebook.AddPage(self.history_tab, "Login History")
        
        # Admin panel is protected and now includes leave management
        self.admin_tab = AdminPanel(notebook, self.user_manager, self.login_manager, self.db_manager)
        notebook.AddPage(self.admin_tab, "Admin Panel")
        
        # Create sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)
        
        # Create status bar
        self.CreateStatusBar()
        self.update_status_bar()
        
        # Bind events
        self.Bind(wx.EVT_CLOSE, self.on_close)
        notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_change)
    
    def on_tab_change(self, event):
        if event.GetSelection() == 2:  # Admin panel tab
            if not self.authenticate_admin():
                # Switch back to first tab if authentication fails
                event.GetEventObject().SetSelection(0)
            else:
                # Refresh data in admin panel
                if hasattr(self.admin_tab, 'refresh_user_list'):
                    self.admin_tab.refresh_user_list()
                if hasattr(self.admin_tab, 'leave_management_tab'):
                    self.admin_tab.leave_management_tab.refresh_data()
        else:
            self.update_status_bar()
    
    def authenticate_admin(self):
        """Authenticate admin access"""
        dialog = LoginDialog(self)
        result = dialog.ShowModal()
        dialog.Destroy()
        return result == wx.ID_OK
    
    def update_status_bar(self):
        """Update status bar with current statistics"""
        try:
            users = self.user_manager.get_all_users()
            total_users = len(users)
            logged_in = sum(1 for user in users if user['status'] == "Logged In")
            self.SetStatusText(f"Total Users: {total_users} | Logged In: {logged_in} | Logged Out: {total_users - logged_in}")
        except Exception as e:
            self.SetStatusText(f"Error loading user statistics: {str(e)}")
    
    def on_close(self, event):
        # Stop camera if running
        if hasattr(self.user_tab, 'camera') and self.user_tab.camera:
            self.user_tab.camera.release()
        self.Destroy()

def main():
    app = wx.App()
    frame = MainFrame()
    frame.Show()
    app.MainLoop()

if __name__ == "__main__":
    main()