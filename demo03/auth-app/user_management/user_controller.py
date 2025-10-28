# user_management/user_controller.py
from datetime import datetime
import json

class UserController:
    def __init__(self, db_service):
        self.db_service = db_service
    
    def create_user(self, user_data, face_encoding, hand_sequence):
        """Create new user with biometric data"""
        user = {
            "username": user_data["username"],
            "email": user_data["email"],
            "face_encoding": face_encoding.tolist() if face_encoding is not None else None,
            "hand_sequence": hand_sequence,
            "login_history": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        return self.db_service.create_user(user)
    
    def get_user(self, user_id):
        """Get user by ID"""
        return self.db_service.find_user_by_id(user_id)
    
    def get_user_by_username(self, username):
        """Get user by username"""
        return self.db_service.find_user_by_username(username)
    
    def update_user(self, user_id, updates):
        """Update user information"""
        updates["updated_at"] = datetime.now().isoformat()
        return self.db_service.update_user(user_id, updates)
    
    def delete_user(self, user_id):
        """Completely remove user and their biometric data"""
        return self.db_service.delete_user(user_id)
    
    def export_user_data(self, user_id, format="json"):
        """Export user data in specified format"""
        user_data = self.get_user(user_id)
        if not user_data:
            return None
        
        # Remove binary data for export
        export_data = user_data.copy()
        export_data.pop('face_encoding', None)
        
        if format == "json":
            return json.dumps(export_data, indent=2)
        else:
            return str(export_data)