# core/qr_handler.py
import qrcode
import cv2
import os
import json
from config.settings import QR_CODE_DIR

class QRHandler:
    def __init__(self):
        self.qr_detector = cv2.QRCodeDetector()
        self.qr_dir = QR_CODE_DIR

    def generate_qr(self, employee_id):
        """Generates a QR code for a user and saves it."""
        data = {"employee_id": employee_id}
        json_data = json.dumps(data)
        
        img = qrcode.make(json_data)
        filepath = os.path.join(self.qr_dir, f"{employee_id}.png")
        img.save(filepath)
        return filepath

    def scan_qr_from_frame(self, frame):
        """
        Scans a single OpenCV frame for a QR code.
        Returns the decoded data (JSON string) or None.
        """
        try:
            # detectAndDecode returns data, bbox, straight_qrcode
            data, _, _ = self.qr_detector.detectAndDecode(frame)
            if data:
                return data
        except Exception as e:
            print(f"Error during QR scan: {e}")
        return None