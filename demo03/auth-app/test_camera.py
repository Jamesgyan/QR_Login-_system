# test_camera.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.camera_utils import CameraUtils

def test_camera_utils():
    print("Testing Camera Utilities...")
    
    # Test camera availability
    success, message = CameraUtils.test_camera()
    print(f"Camera Test: {message}")
    
    # List available cameras
    cameras = CameraUtils.get_available_cameras()
    print(f"Available cameras: {cameras}")
    
    if success:
        print("✅ Camera utilities are working properly!")
    else:
        print("❌ Camera utilities test failed!")

if __name__ == "__main__":
    test_camera_utils()