# qr_handler.py

import qrcode
import json
import os
from pyzbar import pyzbar

class QRHandler:
    def __init__(self, qr_dir):
        self.qr_dir = qr_dir
        if not os.path.exists(self.qr_dir):
            os.makedirs(self.qr_dir)
            
    def generate_qr_code(self, user_id, employee_id):
        """
        Generates a QR code containing user ID and employee ID in JSON format.
        """
        data = {
            "user_id": user_id,
            "employee_id": employee_id
        }
        json_data = json.dumps(data)
        
        img = qrcode.make(json_data)
        filepath = self.qr_dir / f"{employee_id}.png"
        
        try:
            img.save(str(filepath))
            return str(filepath)
        except Exception as e:
            print(f"Error saving QR code: {e}")
            return None

    def decode_qr_code(self, frame):
        """
        Decodes a QR code from a single OpenCV frame.
        Returns the parsed JSON data if successful, else None.
        """
        try:
            decoded_objects = pyzbar.decode(frame)
            if decoded_objects:
                # Get the data from the first decoded object
                data_str = decoded_objects[0].data.decode('utf-8')
                # Parse the JSON data
                data = json.loads(data_str)
                if "user_id" in data and "employee_id" in data:
                    return data
        except (json.JSONDecodeError, UnicodeDecodeError, Exception) as e:
            print(f"Error decoding QR: {e}")
            
        return None