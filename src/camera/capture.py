"""
Camera capture module for accessing and managing the webcam.
"""

import cv2
import logging
import time

class VideoCapture:
    """Class for managing video capture from a webcam."""
    
    def __init__(self, device_id=0, resolution=(640, 480), fps=30, buffer_size=1):
        """
        Initialize the video capture device.
        
        Args:
            device_id: Camera device ID (usually 0 for the first camera)
            resolution: Tuple of (width, height) for capture resolution
            fps: Target frames per second
            buffer_size: Size of the frame buffer (1 = no buffering)
        """
        self.device_id = device_id
        self.resolution = resolution
        self.fps = fps
        self.buffer_size = buffer_size
        
        # Initialize the capture device
        self.cap = None
        self.initialize()
        
        logging.info(f"Camera initialized (ID: {device_id}, Resolution: {resolution}, FPS: {fps})")
    
    def initialize(self):
        """Initialize or reinitialize the capture device."""
        # Release existing capture if it exists
        if self.cap is not None:
            self.release()
        
        # Create new capture
        self.cap = cv2.VideoCapture(self.device_id)
        
        if not self.cap.isOpened():
            logging.error(f"Failed to open camera device {self.device_id}")
            raise RuntimeError(f"Failed to open camera device {self.device_id}")
        
        # Set camera properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
        
        # Verify settings were applied
        actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        logging.info(f"Camera actual settings - Resolution: ({actual_width}x{actual_height}), FPS: {actual_fps}")
        
        # Wait for camera to initialize
        time.sleep(1.0)
    
    def read(self):
        """
        Read a frame from the camera.
        
        Returns:
            Tuple of (success, frame)
        """
        if self.cap is None or not self.cap.isOpened():
            logging.error("Attempted to read from closed camera")
            return False, None
        
        # Read frame
        ret, frame = self.cap.read()
        
        # Handle read failure
        if not ret:
            logging.warning("Failed to read frame, attempting to reinitialize camera")
            self.initialize()
            ret, frame = self.cap.read()
            
            if not ret:
                logging.error("Camera reinitialization failed")
                return False, None
        
        return ret, frame
    
    def release(self):
        """Release the camera resources."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            logging.info("Camera released")
    
    def is_opened(self):
        """Check if the camera is open."""
        return self.cap is not None and self.cap.isOpened()
    
    def get_resolution(self):
        """Get the current resolution."""
        if self.cap is None:
            return self.resolution
        
        width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        return (int(width), int(height))
    
    def get_fps(self):
        """Get the current FPS setting."""
        if self.cap is None:
            return self.fps
        
        return self.cap.get(cv2.CAP_PROP_FPS)