import cv2
import numpy as np

class GestureDetector:
    def __init__(self):
        self.stop_capture = False

    def detect_wave_gesture(self, callback):
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(False, "Cannot access camera")
            return

        self.stop_capture = False
        motion_count = 0
        motion_threshold = 15
        fgbg = cv2.createBackgroundSubtractorMOG2()
        
        try:
            while not self.stop_capture:
                ret, frame = cam.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                fgmask = fgbg.apply(frame)
                motion_pixels = cv2.countNonZero(fgmask)
                
                if motion_pixels > 1000:
                    motion_count += 1
                    cv2.putText(frame, f"Motion detected: {motion_count}/{motion_threshold}", 
                              (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                else:
                    motion_count = max(0, motion_count - 1)
                
                cv2.putText(frame, "Wave your hand to login", (50, 100), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, "Press Q to cancel", (50, 130), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                cv2.imshow("Wave Gesture Login", frame)
                
                if motion_count >= motion_threshold:
                    cam.release()
                    cv2.destroyAllWindows()
                    callback(True, "Wave gesture detected! Starting face recognition...")
                    return
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_capture = True
                    break

        except Exception as e:
            callback(False, f"Error: {e}")
        finally:
            cam.release()
            cv2.destroyAllWindows()
        
        callback(False, "Wave gesture not detected")

    def detect_fist_gesture(self, callback):
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            callback(False, "Cannot access camera")
            return

        self.stop_capture = False
        fist_frames = 0
        fist_threshold = 20
        
        try:
            while not self.stop_capture:
                ret, frame = cam.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                
                lower_skin = np.array([0, 20, 70], dtype=np.uint8)
                upper_skin = np.array([20, 255, 255], dtype=np.uint8)
                
                mask = cv2.inRange(hsv, lower_skin, upper_skin)
                kernel = np.ones((5,5), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    area = cv2.contourArea(largest_contour)
                    hull = cv2.convexHull(largest_contour)
                    hull_area = cv2.contourArea(hull)
                    
                    if hull_area > 0 and area / hull_area > 0.8 and area > 1000:
                        fist_frames += 1
                        cv2.putText(frame, f"Fist detected: {fist_frames}/{fist_threshold}", 
                                  (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                        cv2.putText(frame, "Keep hand closed for logout", (50, 80), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    else:
                        fist_frames = max(0, fist_frames - 1)
                
                cv2.putText(frame, "Make a fist to logout", (50, 120), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, "Press Q to cancel", (50, 150), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                cv2.imshow("Fist Gesture Logout", frame)
                
                if fist_frames >= fist_threshold:
                    cam.release()
                    cv2.destroyAllWindows()
                    callback(True, "Fist gesture detected! Logging out...")
                    return
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_capture = True
                    break

        except Exception as e:
            callback(False, f"Error: {e}")
        finally:
            cam.release()
            cv2.destroyAllWindows()
        
        callback(False, "Fist gesture not detected")