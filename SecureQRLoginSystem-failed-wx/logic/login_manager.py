# logic/login_manager.py

from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class LoginManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def is_user_logged_in(self, user_id):
        """Checks the database for the user's login status."""
        return self.db.get_user_login_status(user_id)

    def perform_login(self, user_id):
        """Logs a user in and records the event."""
        try:
            if self.is_user_logged_in(user_id):
                user = self.db.get_user_by_id(user_id)
                return 'error', user['name'], "User is already logged in."
                
            self.db.set_user_login_status(user_id, 1)
            self.db.add_login_history(user_id, 'login')
            self.db.mark_attendance_login(user_id, datetime.now())
            
            user = self.db.get_user_by_id(user_id)
            logger.info(f"User {user['employee_id']} logged in.")
            return 'login', user['name'], "Login successful."
        except Exception as e:
            logger.error(f"Error during login for {user_id}: {e}")
            return 'error', '', f"Login error: {e}"

    def perform_logout(self, user_id, forced=False):
        """Logs a user out and records the event."""
        try:
            if not self.is_user_logged_in(user_id) and not forced:
                user = self.db.get_user_by_id(user_id)
                return 'error', user['name'], "User is already logged out."
                
            self.db.set_user_login_status(user_id, 0)
            self.db.add_login_history(user_id, 'logout')
            self.db.mark_attendance_logout(user_id, datetime.now())
            
            user = self.db.get_user_by_id(user_id)
            action = "Forced logout" if forced else "Logout"
            logger.info(f"User {user['employee_id']} logged out (Forced: {forced}).")
            return 'logout', user['name'], f"{action} successful."
        except Exception as e:
            logger.error(f"Error during logout for {user_id}: {e}")
            return 'error', '', f"Logout error: {e}"

    def handle_qr_login(self, user_id):
        """
        Toggles the user's login state based on their QR code.
        Returns (action, name, message)
        """
        user = self.db.get_user_by_id(user_id)
        if not user:
            return 'error', '', "Invalid QR Code: User not found."
            
        if self.is_user_logged_in(user_id):
            return self.perform_logout(user_id)
        else:
            return self.perform_login(user_id)