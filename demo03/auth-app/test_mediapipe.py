# test_mediapipe.py
try:
    import mediapipe as mp
    print("✅ MediaPipe imported successfully!")
    print(f"MediaPipe version: {mp.__version__}")
    
    # Test hand detection initialization
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(static_image_mode=True)
    print("✅ Hand detection initialized successfully!")
    hands.close()
    
except ImportError as e:
    print(f"❌ MediaPipe import failed: {e}")
except Exception as e:
    print(f"❌ MediaPipe test failed: {e}")

try:
    import cv2
    print("✅ OpenCV imported successfully!")
except ImportError as e:
    print(f"❌ OpenCV import failed: {e}")