#sign_registration.py file
class HandDetector:
    def __init__(self, hand_detector):
        self.hand_detector = hand_detector
        self.user_sequences = {}  # user_id -> sequence_pattern
    
    def delete_sign_data(self, user_id):
        """Remove hand sign data for user"""
        self.user_sequences.pop(user_id, None)
        return True