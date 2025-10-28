# utils/camera_utils.py
import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk

class CameraUtils:
    @staticmethod
    def resize_frame(frame, width=None, height=None):
        """Resize frame while maintaining aspect ratio"""
        if frame is None:
            return None
            
        h, w = frame.shape[:2]
        
        if width is None and height is None:
            return frame
            
        if width is None:
            ratio = height / float(h)
            width = int(w * ratio)
        elif height is None:
            ratio = width / float(w)
            height = int(h * ratio)
            
        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    
    @staticmethod
    def draw_face_rectangles(frame, face_locations):
        """Draw rectangles around detected faces"""
        if face_locations is None:
            return frame
            
        for (top, right, bottom, left) in face_locations:
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, 'Face', (left, top-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        return frame
    
    @staticmethod
    def draw_hand_landmarks(frame, hand_landmarks):
        """Draw hand landmarks on frame"""
        if hand_landmarks is None:
            return frame
            
        for landmark in hand_landmarks.landmark:
            h, w, c = frame.shape
            cx, cy = int(landmark.x * w), int(landmark.y * h)
            cv2.circle(frame, (cx, cy), 5, (255, 0, 0), cv2.FILLED)
        
        return frame
    
    @staticmethod
    def frame_to_tk_image(frame, width=None, height=None):
        """Convert OpenCV frame to Tkinter PhotoImage"""
        if frame is None:
            return None
            
        # Resize if dimensions provided
        if width or height:
            frame = CameraUtils.resize_frame(frame, width, height)
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert to PIL Image
        pil_image = Image.fromarray(rgb_frame)
        
        # Convert to Tkinter PhotoImage
        tk_image = ImageTk.PhotoImage(image=pil_image)
        
        return tk_image
    
    @staticmethod
    def test_camera():
        """Test if camera is working"""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return False, "Camera not found"
        
        ret, frame = cap.read()
        cap.release()
        
        if ret and frame is not None:
            return True, "Camera working properly"
        else:
            return False, "Camera found but cannot read frames"
    
    @staticmethod
    def get_available_cameras(max_test=5):
        """Get list of available cameras"""
        available_cameras = []
        for i in range(max_test):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    available_cameras.append(i)
                cap.release()
        return available_cameras
    
    @staticmethod
    def capture_high_quality_image(camera_index=0, delay=2):
        """
        Capture a high-quality image by allowing camera to adjust
        """
        cap = cv2.VideoCapture(camera_index)
        
        # Allow camera to adjust
        for _ in range(30):  # Read some frames to adjust
            cap.read()
        
        # Capture frame
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            return frame
        return None
    
    @staticmethod
    def preprocess_face_image(image):
        """Preprocess image for face recognition"""
        if image is None:
            return None
            
        # Convert to RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Enhance image quality
        # Apply mild sharpening
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(rgb_image, -1, kernel)
        
        # Normalize brightness
        lab = cv2.cvtColor(sharpened, cv2.COLOR_RGB2LAB)
        lab[:,:,0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(lab[:,:,0])
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        
        return enhanced
    
    @staticmethod
    def preprocess_hand_image(image):
        """Preprocess image for hand detection"""
        if image is None:
            return None
            
        # Convert to RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Enhance contrast for better hand detection
        lab = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2LAB)
        lab[:,:,0] = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8)).apply(lab[:,:,0])
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        
        return enhanced
    
    @staticmethod
    def add_overlay_text(frame, text, position=(10, 30), color=(0, 255, 0)):
        """Add text overlay to frame"""
        cv2.putText(frame, text, position, 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        return frame
    
    @staticmethod
    def create_composite_frame(images, grid_size=(2, 2)):
        """Create a composite frame from multiple images"""
        if not images:
            return None
            
        h, w = images[0].shape[:2]
        composite = np.zeros((h * grid_size[0], w * grid_size[1], 3), dtype=np.uint8)
        
        for idx, img in enumerate(images):
            if idx >= grid_size[0] * grid_size[1]:
                break
            row = idx // grid_size[1]
            col = idx % grid_size[1]
            composite[row*h:(row+1)*h, col*w:(col+1)*w] = img
            
        return composite


class CameraManager:
    """Manager for camera operations"""
    
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None
        self.is_running = False
    
    def start_camera(self):
        """Start camera capture"""
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            self.is_running = self.cap.isOpened()
            return self.is_running
        except Exception as e:
            print(f"Error starting camera: {e}")
            return False
    
    def stop_camera(self):
        """Stop camera capture"""
        self.is_running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
    
    def get_frame(self):
        """Get current frame from camera"""
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                return frame
        return None
    
    def get_frame_with_overlay(self, overlay_text=None):
        """Get frame with optional overlay text"""
        frame = self.get_frame()
        if frame is not None and overlay_text:
            frame = CameraUtils.add_overlay_text(frame, overlay_text)
        return frame
    
    def __del__(self):
        self.stop_camera()