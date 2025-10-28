# core/auth_manager.py
import json
from datetime import datetime

class AuthManager:
    def __init__(self, db_manager, security_manager):
        self.db = db_manager
        self.sec = security_manager

    def handle_manual_login(self, employee_id, password):
        """Handles manual login with ID and password."""
        user = self.db.get_user_by_employee_id(employee_id)
        
        if not user:
            return "Error: Employee ID not found."
            
        if self.sec.verify_password(user['hashed_password'], user['salt'], password):
            if user['is_logged_in']:
                return "Error: User is already logged in."
            return self._perform_login(user['id'], user['name'])
        else:
            return "Error: Invalid password."

    # --- ADD THIS NEW FUNCTION ---
    def handle_manual_logout(self, employee_id, password):
        """Handles manual logout with ID and password."""
        user = self.db.get_user_by_employee_id(employee_id)
        
        if not user:
            return "Error: Employee ID not found."
            
        if not self.sec.verify_password(user['hashed_password'], user['salt'], password):
            return "Error: Invalid password."

        if not user['is_logged_in']:
            return "Error: User is already logged out."
        
        # All checks passed, perform logout
        return self._perform_logout(user['id'], user['name'])
    # --- END OF NEW FUNCTION ---

    def handle_qr_login_toggle(self, qr_data_str):
        """Handles the QR toggle logic."""
        try:
            data = json.loads(qr_data_str)
            employee_id = data.get('employee_id')
        except json.JSONDecodeError:
            return "Error: Invalid QR code data."
            
        if not employee_id:
            return "Error: QR code does not contain an employee ID."
            
        user = self.db.get_user_by_employee_id(employee_id)
        if not user:
            return f"Error: No user found for {employee_id}."
            
        # Toggle logic
        if user['is_logged_in']:
            return self._perform_logout(user['id'], user['name'])
        else:
            return self._perform_login(user['id'], user['name'])

    def _perform_login(self, user_id, user_name="User"):
        """Internal login helper."""
        now = datetime.now()
        current_date = now.strftime('%Y-%m-%d')
        current_time = now.strftime('%H:%M:%S')
        
        try:
            self.db.update_user_login_status(user_id, 1)
            self.db.log_history(user_id, 'login')
            
            # Upsert attendance: Mark as present and set login time
            self.db.upsert_attendance(
                user_id=user_id,
                date=current_date,
                login_time=current_time,
                status="Present"
            )
            return f"Success: {user_name} logged in at {current_time}."
        except Exception as e:
            return f"Login Error: {e}"

    def _perform_logout(self, user_id, user_name="User", action='logout'):
        """Internal logout helper."""
        now = datetime.now()
        current_date = now.strftime('%Y-%m-%d')
        current_time = now.strftime('%H:%M:%S')
        
        try:
            self.db.update_user_login_status(user_id, 0)
            self.db.log_history(user_id, action)
            
            # Update attendance: Set logout time and calculate hours
            record = self.db.get_attendance_for_date(user_id, current_date)
            hours_worked = 0
            
            if record and record['login_time']:
                try:
                    login_dt = datetime.strptime(record['login_time'], '%H:%M:%S')
                    logout_dt = datetime.strptime(current_time, '%H:%M:%S')
                    duration = logout_dt - login_dt
                    hours_worked = round(duration.total_seconds() / 3600, 2)
                except Exception as e:
                    print(f"Hour calculation error: {e}")
            
            self.db.upsert_attendance(
                user_id=user_id,
                date=current_date,
                logout_time=current_time,
                hours=hours_worked
            )
            
            return f"Success: {user_name} logged out at {current_time}."
        except Exception as e:
            return f"Logout Error: {e}"

    def force_logout(self, user_id):
        """Forces a user to log out (admin action)."""
        user = self.db.get_user_by_id(user_id)
        if not user:
            return "Error: User not found."
        if not user['is_logged_in']:
            return "Info: User is already logged out."
            
        return self._perform_logout(user_id, user['name'], action='force_logout')

    def mark_leave(self, user_id, start_date, end_date, leave_type, notes):
        """Marks leave for a user over a date range."""
        from datetime import timedelta
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if start_dt > end_dt:
                return "Error: Start date must be before end date."

            current_dt = start_dt
            count = 0
            while current_dt <= end_dt:
                self.db.upsert_attendance(
                    user_id=user_id,
                    date=current_dt.strftime('%Y-%m-%d'),
                    status=leave_type,
                    notes=notes,
                    login_time=None,
                    logout_time=None,
                    hours=0
                )
                count += 1
                current_dt += timedelta(days=1)
            
            return f"Success: Marked {leave_type} for {count} days."
        except Exception as e:
            return f"Error marking leave: {e}"