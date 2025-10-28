class UserService:
    def validate_user_data(self, user_data):
        """Validate user registration data"""
        required_fields = ['username', 'email']
        for field in required_fields:
            if field not in user_data or not user_data[field]:
                return False, f"Missing field: {field}"
        
        # Basic email validation
        if '@' not in user_data['email']:
            return False, "Invalid email format"
        
        return True, "Valid"