class FaceRegistration:
    def __init__(self, face_detector):
        self.face_detector = face_detector
    
    def delete_face_data(self, user_id):
        """Remove face data for user"""
        if user_id in self.face_detector.known_face_ids:
            index = self.face_detector.known_face_ids.index(user_id)
            self.face_detector.known_face_encodings.pop(index)
            self.face_detector.known_face_ids.pop(index)
            return True
        return False