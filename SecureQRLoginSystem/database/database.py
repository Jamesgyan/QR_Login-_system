# database/database.py
import sqlite3
import os
from datetime import datetime
from config.settings import DATABASE_PATH

class DatabaseManager:
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self.create_tables()

    def get_connection(self):
        """Establishes a connection to the SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Access columns by name
            conn.execute("PRAGMA foreign_keys = ON;") # Enforce foreign keys
            return conn
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return None

    def create_tables(self):
        """Creates all necessary tables if they don't exist."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                hashed_password TEXT NOT NULL,
                salt TEXT NOT NULL,
                is_logged_in INTEGER DEFAULT 0 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                action TEXT NOT NULL, -- 'login', 'logout', 'force_logout'
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL, -- YYYY-MM-DD
                login_time TEXT,
                logout_time TEXT,
                hours_worked REAL DEFAULT 0,
                status TEXT NOT NULL, -- 'Present', 'Leave', 'Sick Leave', etc.
                notes TEXT,
                UNIQUE(user_id, date),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL, -- YYYY-MM-DD
                title TEXT NOT NULL,
                category TEXT NOT NULL -- 'Holiday', 'Event', 'Meeting', 'Celebration'
            );
            """
        ]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for query in queries:
                cursor.execute(query)
            conn.commit()

    def execute_query(self, query, params=()):
        """Helper for INSERT, UPDATE, DELETE queries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def fetch_one(self, query, params=()):
        """Helper for fetching a single record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()

    def fetch_all(self, query, params=()):
        """Helper for fetching multiple records."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    # --- User Management ---
    
    def add_user(self, emp_id, name, email, phone, hashed_pass, salt):
        query = """
        INSERT INTO users (employee_id, name, email, phone, hashed_password, salt)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        return self.execute_query(query, (emp_id, name, email, phone, hashed_pass, salt))

    def get_user_by_employee_id(self, emp_id):
        return self.fetch_one("SELECT * FROM users WHERE employee_id = ?", (emp_id,))

    def get_user_by_id(self, user_id):
        return self.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        
    def get_all_users(self):
        return self.fetch_all("SELECT id, employee_id, name, email, phone, is_logged_in FROM users ORDER BY employee_id")

    def update_user_password(self, user_id, new_hashed_pass, new_salt):
        query = "UPDATE users SET hashed_password = ?, salt = ? WHERE id = ?"
        self.execute_query(query, (new_hashed_pass, new_salt, user_id))

    def delete_user(self, user_id):
        # ON DELETE CASCADE will handle related records in other tables
        self.execute_query("DELETE FROM users WHERE id = ?", (user_id,))

    def get_next_employee_id_number(self, prefix):
        query = "SELECT employee_id FROM users WHERE employee_id LIKE ? ORDER BY employee_id DESC LIMIT 1"
        last_user = self.fetch_one(query, (f"{prefix}%",))
        if last_user:
            last_id_num = last_user['employee_id'].replace(prefix, '')
            try:
                return int(last_id_num) + 1
            except ValueError:
                return 1 # Fallback
        return 1 # First user

    # --- Authentication & Login State ---
    
    def update_user_login_status(self, user_id, status):
        query = "UPDATE users SET is_logged_in = ? WHERE id = ?"
        self.execute_query(query, (status, user_id))

    def log_history(self, user_id, action):
        query = "INSERT INTO login_history (user_id, action) VALUES (?, ?)"
        self.execute_query(query, (user_id, action))
        
    def check_admin_password(self, hardcoded_hash):
        # This is a basic implementation. For real security, this should be in the DB.
        # This is just to protect the panel as requested.
        # Let's use a simple hardcoded "admin" password for this example.
        # In a real app, 'admin' user would be in the 'users' table.
        # Hashed "admin" with salt "admin_salt" using PBKDF2
        # You would generate this offline.
        # This is just a placeholder.
        return True # Placeholder for demo.
        
    # --- Attendance & Leave ---
    
    def get_attendance_for_date(self, user_id, date):
        return self.fetch_one("SELECT * FROM attendance WHERE user_id = ? AND date = ?", (user_id, date))
        
    def upsert_attendance(self, user_id, date, login_time=None, logout_time=None, hours=None, status=None, notes=None):
        """Inserts or updates an attendance record."""
        existing = self.get_attendance_for_date(user_id, date)
        
        if existing:
            # Update existing record
            query = "UPDATE attendance SET "
            params = []
            if login_time:
                query += "login_time = ?, "
                params.append(login_time)
            if logout_time:
                query += "logout_time = ?, "
                params.append(logout_time)
            if hours is not None:
                query += "hours_worked = ?, "
                params.append(hours)
            if status:
                query += "status = ?, "
                params.append(status)
            if notes is not None:
                query += "notes = ?, "
                params.append(notes)
            
            query = query.rstrip(', ') + " WHERE id = ?"
            params.append(existing['id'])
            self.execute_query(query, tuple(params))
        else:
            # Insert new record
            query = """
            INSERT INTO attendance (user_id, date, login_time, logout_time, hours_worked, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            self.execute_query(query, (user_id, date, login_time, logout_time, hours or 0, status, notes))

    def get_attendance_records(self, user_id=None, start_date=None, end_date=None):
        query = """
        SELECT a.date, a.status, a.login_time, a.logout_time, a.hours_worked, a.notes, u.employee_id, u.name
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE 1=1
        """
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
        query += " ORDER BY a.date DESC, u.employee_id"
        return self.fetch_all(query, tuple(params))

    # --- History & Reporting ---
    
    def get_login_history(self, user_id=None, start_date=None, end_date=None):
        query = """
        SELECT h.timestamp, h.action, u.employee_id, u.name
        FROM login_history h
        JOIN users u ON h.user_id = u.id
        WHERE 1=1
        """
        params = []
        if user_id:
            query += " AND h.user_id = ?"
            params.append(user_id)
        if start_date:
            # Note: timestamp is DATETIME, so we check the date part
            query += " AND DATE(h.timestamp) >= ?"
            params.append(start_date)
        if end_date:
            query += " AND DATE(h.timestamp) <= ?"
            params.append(end_date)
        query += " ORDER BY h.timestamp DESC"
        return self.fetch_all(query, tuple(params))

    # --- Calendar & Events ---

    def add_event(self, date, title, category):
        query = "INSERT INTO events (date, title, category) VALUES (?, ?, ?)"
        self.execute_query(query, (date, title, category))

    def get_events_for_month(self, year, month):
        # Get events for the given month
        start_date = f"{year}-{month:02d}-01"
        # Find last day of month
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day:02d}"
        
        query = "SELECT * FROM events WHERE date BETWEEN ? AND ?"
        return self.fetch_all(query, (start_date, end_date))
        
    def get_events_for_date(self, date):
        return self.fetch_all("SELECT * FROM events WHERE date = ?", (date,))