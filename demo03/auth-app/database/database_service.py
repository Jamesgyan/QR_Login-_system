# database/database_service.py
import sqlite3
import json
from datetime import datetime

class DatabaseService:
    def __init__(self, db_path="auth_app.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                face_encoding TEXT,
                hand_sequence TEXT,
                login_history TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def connect(self):
        """Create database connection"""
        return sqlite3.connect(self.db_path)
    
    def create_user(self, user_data):
        """Create new user"""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO users 
                (username, email, face_encoding, hand_sequence, login_history, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_data['username'],
                user_data['email'],
                json.dumps(user_data.get('face_encoding')),
                json.dumps(user_data.get('hand_sequence')),
                json.dumps(user_data.get('login_history', [])),
                user_data['created_at'],
                user_data['updated_at']
            ))
            
            user_id = cursor.lastrowid
            conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            raise Exception("Username or email already exists")
        finally:
            conn.close()
    
    def find_user_by_id(self, user_id):
        """Find user by ID"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return self._row_to_dict(user)
        return None
    
    def find_user_by_username(self, username):
        """Find user by username"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return self._row_to_dict(user)
        return None
    
    def get_all_users(self):
        """Get all users"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users')
        users = cursor.fetchall()
        conn.close()
        
        return [self._row_to_dict(user) for user in users]
    
    def update_user(self, user_id, updates):
        """Update user data"""
        conn = self.connect()
        cursor = conn.cursor()
        
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values())
        values.append(user_id)
        
        cursor.execute(f'UPDATE users SET {set_clause} WHERE id = ?', values)
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    
    def delete_user(self, user_id):
        """Delete user completely"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    
    def _row_to_dict(self, row):
        """Convert database row to dictionary"""
        columns = ['id', 'username', 'email', 'face_encoding', 'hand_sequence', 
                  'login_history', 'created_at', 'updated_at']
        
        user_dict = dict(zip(columns, row))
        
        # Parse JSON fields
        try:
            if user_dict['face_encoding']:
                user_dict['face_encoding'] = json.loads(user_dict['face_encoding'])
            if user_dict['hand_sequence']:
                user_dict['hand_sequence'] = json.loads(user_dict['hand_sequence'])
            if user_dict['login_history']:
                user_dict['login_history'] = json.loads(user_dict['login_history'])
        except:
            # If JSON parsing fails, keep as string
            pass
        
        return user_dict