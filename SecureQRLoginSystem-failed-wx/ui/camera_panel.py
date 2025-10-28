# ui/camera_panel.py

import wx
import cv2
import numpy as np

class CameraPanel(wx.Panel):
    def __init__(self, parent, qr_handler, on_qr_decoded):
        wx.Panel.__init__(self, parent, -1)
        
        self.qr_handler = qr_handler
        self.on_qr_decoded = on_qr_decoded # Callback function
        
        self.capture = None
        self.is_camera_running = False
        
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetSize((320, 240))
        self.SetMinSize((320, 240))

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)

    def on_erase_background(self, event):
        # Do nothing to prevent flickering
        pass

    def start_camera(self):
        if self.is_camera_running:
            return True # Already running
            
        try:
            # Try to open the default camera
            self.capture = cv2.VideoCapture(0) 
            if not self.capture.isOpened():
                raise IOError("Cannot open webcam")
            
            # Set a smaller resolution for faster processing
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                
            self.is_camera_running = True
            self.timer.Start(1000 // 30)  # 30 FPS
            print("Camera started")
            return True
        except Exception as e:
            print(f"Camera start error: {e}")
            wx.MessageBox(f"Failed to start camera: {e}", "Camera Error", wx.OK | wx.ICON_ERROR)
            self.capture = None
            return False

    def stop_camera(self):
        if not self.is_camera_running:
            return
            
        try:
            self.timer.Stop()
            if self.capture:
                self.capture.release()
            self.capture = None
            self.is_camera_running = False
            # Clear the panel
            dc = wx.ClientDC(self)
            dc.Clear()
            print("Camera stopped")
        except Exception as e:
            print(f"Camera stop error: {e}")

    def on_timer(self, event):
        if not self.is_camera_running or not self.capture:
            return
            
        ret, frame = self.capture.read()
        if ret:
            # Process frame for QR code
            qr_data = self.qr_handler.decode_qr_code(frame)
            if qr_data:
                # Found a QR code, stop the camera and notify the parent
                self.stop_camera()
                self.on_qr_decoded(qr_data)
                return

            # Convert to RGB for wx.Bitmap
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Resize frame to fit panel
            h, w = self.GetSize()
            frame_resized = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)

            # Create bitmap
            self.bmp = wx.Bitmap.FromBuffer(w, h, frame_resized.tobytes())
            self.Refresh(False) # Refresh without erasing background

    def on_paint(self, event):
        if self.is_camera_running and hasattr(self, 'bmp'):
            try:
                # Use BufferedPaintDC for flicker-free drawing
                dc = wx.BufferedPaintDC(self)
                dc.DrawBitmap(self.bmp, 0, 0)
            except Exception as e:
                # This can happen if the panel is destroyed while painting
                print(f"Paint error: {e}")
        else:
            # Draw a placeholder if camera is off
            dc = wx.PaintDC(self)
            dc.Clear()
            dc.SetPen(wx.Pen(wx.BLACK))
            dc.SetBrush(wx.Brush(wx.LIGHT_GREY))
            dc.DrawRectangle(0, 0, *self.GetSize())
            w, h = self.GetSize()
            text = "Camera Offline"
            tw, th = dc.GetTextExtent(text)
            dc.DrawText(text, (w - tw) // 2, (h - th) // 2)