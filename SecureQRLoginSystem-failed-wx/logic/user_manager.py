# logic/user_manager.py

import os  
import validation_utils as vutils
import logging

logger = logging.getLogger(__name__)

class UserManager:
    def __init__(self, db_manager, security_manager, qr_handler, login_manager):
        self.db = db_manager
        self.sec = security_manager
        self.qr = qr_handler
        self.login_m = login_manager # Used for force logout

    def _generate_employee_id(self):
        """Generates a new employee ID, e.g., ALLY001, ALLY002."""
        last_user = self.db.get_last_user()
        if not last_user:
            return "ALLY001"
        
        try:
            last_id_num = int(last_user['employee_id'][4:])
            new_id_num = last_id_num + 1
            return f"ALLY{new_id_num:03d}"
        except (ValueError, TypeError):
            logger.error("Could not parse last employee ID. Defaulting.")
            # Fallback (should not happen with good data)
            count_result = self.db.fetch_one('SELECT COUNT(*) as count FROM Users')
            count = count_result['count'] if count_result else 0
            return f"ALLY{count + 1:03d}"

    def add_user(self, name, email, phone, password):
        """
        Validates data, hashes password, adds user to DB, and generates QR code.
        Returns (success_bool, message_or_data)
        """
        if not (name and email and password):
            return False, "Name, Email, and Password are required."
        if not vutils.validate_email(email):
            return False, "Invalid email format."
        if not vutils.validate_phone(phone):
            return False, "Invalid phone format (must be 10 digits or empty)."
            
        # Check if email exists
        if self.db.fetch_one("SELECT id FROM Users WHERE email = ?", (email,)):
            return False, f"Email '{email}' already exists."

        try:
            employee_id = self._generate_employee_id()
            hashed_pw, salt = self.sec.hash_password(password)
            
            user_id = self.db.add_user(employee_id, name, email, phone, hashed_pw, salt)
            
            if user_id:
                qr_path = self.qr.generate_qr_code(user_id, employee_id)
                logger.info(f"Added user {employee_id} with ID {user_id}. QR at {qr_path}")
                return True, {"id": user_id, "employee_id": employee_id}
            else:
                return False, "Failed to add user to database (possibly duplicate)."
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False, f"An unexpected error occurred: {e}"

    def authenticate_user(self, employee_id, password):
        """Authenticates a user via manual login."""
        user = self.db.get_user_by_employee_id(employee_id)
        if not user:
            return None
        
        if self.sec.verify_password(user['password_hash'], user['salt'], password):
            return user # Returns the full user row (as a dict)
        
        return None
        
    def get_all_users_with_status(self):
        """Fetches all users for the admin panel list."""
        return self.db.get_all_users()

    def reset_password(self, user_id, new_password):
        """Resets a user's password."""
        try:
            new_hash, new_salt = self.sec.hash_password(new_password)
            self.db.update_user_password(user_id, new_hash, new_salt)
            return True, "Password reset successfully."
        except Exception as e:
            logger.error(f"Error resetting password for {user_id}: {e}")
            return False, "Failed to reset password."

    def force_logout(self, user_id):
        """Forces a user to log out."""
        if self.db.get_user_login_status(user_id):
            # Use LoginManager to ensure attendance is also handled
            self.login_m.perform_logout(user_id, forced=True)
            return True, "User forced to log out."
        else:
            return False, "User is already logged out."
            
    def delete_user(self, user_id):
        """Deletes a user and their associated data (via CASCADE)."""
        try:
            # First, get user details to delete QR code
            user = self.db.get_user_by_id(user_id)
            if not user:
                return False, "User not found."
                
            # Delete user from DB (CASCADE handles history, attendance)
            self.db.delete_user(user_id)
            
            # Delete QR code file
            qr_file = self.qr.qr_dir / f"{user['employee_id']}.png"
            if qr_file.exists():
                os.remove(qr_file)
                
            return True, f"User {user['employee_id']} deleted successfully."
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False, f"Error deleting user: {e}"