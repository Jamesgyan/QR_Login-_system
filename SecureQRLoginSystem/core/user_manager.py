# core/user_manager.py
from config.settings import ID_PREFIX
from utils.validators import validate_email, validate_phone

class UserManager:
    def __init__(self, db_manager, security_manager, qr_handler):
        self.db = db_manager
        self.sec = security_manager
        self.qr = qr_handler
        self.prefix = ID_PREFIX

    def generate_employee_id(self):
        """Generates the next available employee ID (e.g., ALLY001)."""
        next_num = self.db.get_next_employee_id_number(self.prefix)
        return f"{self.prefix}{next_num:03d}"

    def add_user(self, name, email, phone, password):
        """Validates and adds a new user to the system."""
        if not (name and email and phone and password):
            return "All fields are required."
        if not validate_email(email):
            return "Invalid email format."
            
        if not validate_phone(phone):
            return "Phone number must be exactly 10 digits."
            
        # Check if email is unique
        if self.db.fetch_one("SELECT id FROM users WHERE email = ?", (email,)):
            return "Email already exists."

        try:
            salt = self.sec.get_salt()
            hashed_pass = self.sec.hash_password(password, salt)
            emp_id = self.generate_employee_id()
            
            user_id = self.db.add_user(emp_id, name, email, phone, hashed_pass, salt)
            
            if user_id:
                self.qr.generate_qr(emp_id)
                return f"User {emp_id} created successfully."
            else:
                return "Failed to create user in database."
        except Exception as e:
            return f"An error occurred: {e}"

    def reset_password(self, user_id, new_password):
        """Resets a user's password."""
        if len(new_password) < 6:
            return "Password must be at least 6 characters."
        try:
            salt = self.sec.get_salt()
            hashed_pass = self.sec.hash_password(new_password, salt)
            self.db.update_user_password(user_id, hashed_pass, salt)
            return "Password reset successfully."
        except Exception as e:
            return f"Failed to reset password: {e}"

    def delete_user(self, user_id):
        """Deletes a user and all their associated data."""
        try:
            # Foreign key constraints with ON DELETE CASCADE will handle
            # related history and attendance.
            self.db.delete_user(user_id)
            return "User deleted successfully."
        except Exception as e:
            return f"Failed to delete user: {e}"
            
    def get_all_users_for_display(self):
        """Gets all users with a readable login status."""
        users = self.db.get_all_users()
        return [
            {**user, 'status': "Logged In" if user['is_logged_in'] else "Logged Out"}
            for user in users
        ]