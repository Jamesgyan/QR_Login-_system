# database_manager.py

import sqlite3
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._create_tables()

    def _get_connection(self):
        """Establishes and returns a database connection."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Access columns by name
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            return None

    def _create_tables(self):
        """Creates all necessary tables if they don't exist."""
        users_table = """
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            is_logged_in INTEGER DEFAULT 0
        );
        """
        
        login_history_table = """
        CREATE TABLE IF NOT EXISTS LoginHistory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            action TEXT NOT NULL, -- 'login' or 'logout'
            FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
        );
        """
        
        attendance_table = """
        CREATE TABLE IF NOT EXISTS Attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            login_time TEXT,
            logout_time TEXT,
            hours_worked REAL DEFAULT 0,
            status TEXT NOT NULL, -- Present, Leave, Sick Leave, Personal Leave, Absent, Holiday
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE,
            UNIQUE(user_id, date)
        );
        """
        
        events_table = """
        CREATE TABLE IF NOT EXISTS Events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL -- Holiday, Event, Meeting, Celebration
        );
        """

        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_user_employee_id ON Users (employee_id);",
            "CREATE INDEX IF NOT EXISTS idx_history_user_date ON LoginHistory (user_id, timestamp);",
            "CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON Attendance (user_id, date);",
            "CREATE INDEX IF NOT EXISTS idx_events_date ON Events (date);"
        ]
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(users_table)
            cursor.execute(login_history_table)
            cursor.execute(attendance_table)
            cursor.execute(events_table)
            for index in indexes:
                cursor.execute(index)
            conn.commit()

    # --- Generic Helpers ---

    def execute_query(self, query, params=(), commit=False):
        """Executes a query (INSERT, UPDATE, DELETE)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                if commit:
                    conn.commit()
                return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.warning(f"Integrity error: {e}. Query: {query}")
            return None
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}. Query: {query}")
            return None

    def fetch_one(self, query, params=()):
        """Fetches a single record."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchone()
        except sqlite3.Error as e:
            logger.error(f"Database fetch_one error: {e}. Query: {query}")
            return None

    def fetch_all(self, query, params=()):
        """Fetches all matching records."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Database fetch_all error: {e}. Query: {query}")
            return None

    # --- User Management ---

    def add_user(self, employee_id, name, email, phone, password_hash, salt):
        query = """
        INSERT INTO Users (employee_id, name, email, phone, password_hash, salt)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        return self.execute_query(query, (employee_id, name, email, phone, password_hash, salt), commit=True)

    def get_user_by_employee_id(self, employee_id):
        query = "SELECT * FROM Users WHERE employee_id = ?"
        return self.fetch_one(query, (employee_id,))

    def get_user_by_id(self, user_id):
        query = "SELECT * FROM Users WHERE id = ?"
        return self.fetch_one(query, (user_id,))

    def get_last_user(self):
        query = "SELECT employee_id FROM Users ORDER BY id DESC LIMIT 1"
        return self.fetch_one(query)

    def get_all_users(self):
        query = "SELECT id, employee_id, name, email, phone, is_logged_in FROM Users ORDER BY name"
        return self.fetch_all(query)
        
    def update_user_password(self, user_id, new_hash, new_salt):
        query = "UPDATE Users SET password_hash = ?, salt = ? WHERE id = ?"
        self.execute_query(query, (new_hash, new_salt, user_id), commit=True)

    def delete_user(self, user_id):
        # Foreign keys with ON DELETE CASCADE will handle other tables
        query = "DELETE FROM Users WHERE id = ?"
        self.execute_query(query, (user_id,), commit=True)

    # --- Login / Status ---

    def get_user_login_status(self, user_id):
        query = "SELECT is_logged_in FROM Users WHERE id = ?"
        result = self.fetch_one(query, (user_id,))
        return result['is_logged_in'] == 1 if result else False

    def set_user_login_status(self, user_id, status):
        query = "UPDATE Users SET is_logged_in = ? WHERE id = ?"
        self.execute_query(query, (status, user_id), commit=True)

    def force_logout_all(self):
        """Used on application startup to reset all statuses."""
        query = "UPDATE Users SET is_logged_in = 0"
        self.execute_query(query, commit=True)

    def add_login_history(self, user_id, action):
        query = "INSERT INTO LoginHistory (user_id, action) VALUES (?, ?)"
        self.execute_query(query, (user_id, action), commit=True)

    def get_login_history(self, user_id=None, start_date=None, end_date=None):
        query = """
        SELECT h.timestamp, h.action, u.name, u.employee_id
        FROM LoginHistory h
        JOIN Users u ON h.user_id = u.id
        """
        params = []
        conditions = []
        
        if user_id:
            conditions.append("h.user_id = ?")
            params.append(user_id)
        if start_date:
            conditions.append("date(h.timestamp) >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date(h.timestamp) <= ?")
            params.append(end_date)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY h.timestamp DESC"
        return self.fetch_all(query, tuple(params))

    # --- Attendance & Leave ---

    def mark_attendance_login(self, user_id, login_datetime):
        date_str = login_datetime.strftime('%Y-%m-%d')
        time_str = login_datetime.strftime('%H:%M:%S')
        
        query = """
        INSERT INTO Attendance (user_id, date, login_time, status)
        VALUES (?, ?, ?, 'Present')
        ON CONFLICT(user_id, date) DO UPDATE SET
            login_time = COALESCE(excluded.login_time, login_time),
            status = 'Present'
        WHERE status != 'Present'; -- Don't overwrite login time if already 'Present'
        """
        self.execute_query(query, (user_id, date_str, time_str), commit=True)

    def mark_attendance_logout(self, user_id, logout_datetime):
        date_str = logout_datetime.strftime('%Y-%m-%d')
        time_str = logout_datetime.strftime('%H:%M:%S')
        
        # First, update the logout time
        query_update = """
        UPDATE Attendance SET logout_time = ?
        WHERE user_id = ? AND date = ? AND status = 'Present'
        """
        self.execute_query(query_update, (time_str, user_id, date_str), commit=True)
        
        # Now, calculate hours worked
        self._calculate_hours_worked(user_id, date_str)

    def _calculate_hours_worked(self, user_id, date_str):
        record = self.fetch_one(
            "SELECT login_time, logout_time FROM Attendance WHERE user_id = ? AND date = ?",
            (user_id, date_str)
        )
        
        if record and record['login_time'] and record['logout_time']:
            try:
                FMT = '%H:%M:%S'
                t1 = datetime.strptime(record['login_time'], FMT)
                t2 = datetime.strptime(record['logout_time'], FMT)
                duration = t2 - t1
                hours = duration.total_seconds() / 3600
                if hours < 0: hours += 24 # Handle overnight case (though unlikely for this system)
                
                query_hours = "UPDATE Attendance SET hours_worked = ? WHERE user_id = ? AND date = ?"
                self.execute_query(query_hours, (round(hours, 2), user_id, date_str), commit=True)
            except Exception as e:
                logger.error(f"Error calculating hours: {e}")

    def upsert_attendance(self, user_id, date_str, status, notes):
        query = """
        INSERT INTO Attendance (user_id, date, status, notes, login_time, logout_time, hours_worked)
        VALUES (?, ?, ?, ?, NULL, NULL, 0)
        ON CONFLICT(user_id, date) DO UPDATE SET
            status = excluded.status,
            notes = excluded.notes,
            login_time = NULL,
            logout_time = NULL,
            hours_worked = 0
        """
        self.execute_query(query, (user_id, date_str, status, notes), commit=True)

    def get_attendance(self, user_id=None, start_date=None, end_date=None):
        query = """
        SELECT a.date, a.login_time, a.logout_time, a.hours_worked, a.status, a.notes, u.name, u.employee_id
        FROM Attendance a
        JOIN Users u ON a.user_id = u.id
        """
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
            
        query += " ORDER BY u.name, a.date"
        return self.fetch_all(query, tuple(params))
        
    def get_attendance_for_month(self, user_id, month, year):
        query = """
        SELECT date, status FROM Attendance
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
        """
        month_str = f"{year:04d}-{month:02d}"
        return self.fetch_all(query, (user_id, month_str))

    # --- Events & Calendar ---

    def add_event(self, date, title, category):
        query = "INSERT INTO Events (date, title, category) VALUES (?, ?, ?)"
        return self.execute_query(query, (date, title, category), commit=True)
        
    def get_events_for_month(self, month, year):
        query = """
        SELECT date, title, category FROM Events
        WHERE strftime('%Y-%m', date) = ?
        """
        month_str = f"{year:04d}-{month:02d}"
        return self.fetch_all(query, (month_str,))
        
    def get_events_for_day(self, date_str):
        query = "SELECT id, title, category FROM Events WHERE date = ? ORDER BY category"
        return self.fetch_all(query, (date_str,))

    def delete_event(self, event_id):
        query = "DELETE FROM Events WHERE id = ?"
        self.execute_query(query, (event_id,), commit=True)