"""
Camera capture module for accessing and managing the webcam.
"""

import cv2
import logging
import time
import os
from typing import Tuple, Optional, Union
import numpy as np

class VideoCapture:
    """Class for managing video capture from a webcam or IP camera."""
    
    def __init__(
        self,
        device_id: Union[int, str] = 0,
        resolution: Tuple[int, int] = (640, 480),
        fps: int = 30,
        buffer_size: int = 1,
        max_retries: int = 3,
        rtsp_transport: str = "tcp"
    ) -> None:
        """
        Initialize the video capture device.
        
        Args:
            device_id: Camera device ID (int) or stream URL (str)
            resolution: Tuple of (width, height) for capture resolution
            fps: Target frames per second
            buffer_size: Size of the frame buffer (1 = no buffering)
            max_retries: Maximum number of retry attempts for initialization
            rtsp_transport: RTSP transport protocol ("tcp" or "udp")
        """
        self.device_id = device_id
        self.resolution = resolution
        self.fps = fps
        self.buffer_size = buffer_size
        self.max_retries = max_retries
        self.rtsp_transport = rtsp_transport
        self.consecutive_failures = 0
        
        # Initialize the capture device
        self.cap = None
        self.initialize()
        
        logging.info(f"Camera initialized (ID: {device_id}, Resolution: {resolution}, FPS: {fps})")
    
    def initialize(self, retry_count: int = 0) -> None:
        """
        Initialize or reinitialize the capture device with retry logic.
        
        Args:
            retry_count: Current retry attempt number
        """
        # Release existing capture if it exists
        if self.cap is not None:
            self.release()
        
        # Wait before retry (exponential backoff)
        if retry_count > 0:
            wait_time = min(2 ** retry_count, 10)  # Max 10 seconds
            logging.info(f"Retrying camera initialization (attempt {retry_count + 1}/{self.max_retries}) after {wait_time}s")
            time.sleep(wait_time)
        
        # Create new capture
        # Set RTSP transport protocol
        if isinstance(self.device_id, str) and (self.device_id.startswith("rtsp://") or self.device_id.startswith("rtsps://")):
            logging.info(f"Setting RTSP transport to: {self.rtsp_transport}")
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{self.rtsp_transport}"
            
        self.cap = cv2.VideoCapture(self.device_id)
        
        if not self.cap.isOpened():
            if retry_count < self.max_retries - 1:
                logging.warning(f"Failed to open camera device {self.device_id}, retrying...")
                return self.initialize(retry_count + 1)
            else:
                logging.error(f"Failed to open camera device {self.device_id} after {self.max_retries} attempts")
                raise RuntimeError(f"Failed to open camera device {self.device_id} after {self.max_retries} attempts")
        
        # Only set properties for USB cameras (integers), not IP streams
        if isinstance(self.device_id, int):
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
            
            # Verify settings were applied
            actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            logging.info(f"Camera actual settings - Resolution: ({actual_width}x{actual_height}), FPS: {actual_fps}")
        else:
            logging.info(f"IP Camera initialized: {self.device_id}")
        
        # Wait for camera to initialize
        time.sleep(1.0)
        self.consecutive_failures = 0
    
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read a frame from the camera with automatic retry on failure.
        
        Returns:
            Tuple of (success, frame)
        """
        if self.cap is None or not self.cap.isOpened():
            logging.warning("Camera not opened, attempting to reinitialize")
            try:
                self.initialize()
            except RuntimeError:
                return False, None
        
        # Read frame
        ret, frame = self.cap.read()
        
        # Handle read failure with retry
        if not ret:
            self.consecutive_failures += 1
            if self.consecutive_failures <= 3:
                logging.warning(f"Failed to read frame (consecutive failures: {self.consecutive_failures}), attempting to reinitialize camera")
                try:
                    self.initialize()
                    ret, frame = self.cap.read()
                    if ret:
                        self.consecutive_failures = 0
                except RuntimeError:
                    logging.error("Camera reinitialization failed")
                    return False, None
            else:
                logging.error("Too many consecutive camera read failures")
                return False, None
        
        return ret, frame
    
    def release(self) -> None:
        """Release the camera resources."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            logging.info("Camera released")
    
    def is_opened(self) -> bool:
        """Check if the camera is open."""
        return self.cap is not None and self.cap.isOpened()
    
    def get_resolution(self) -> Tuple[int, int]:
        """Get the current resolution."""
        if self.cap is None:
            return self.resolution
        
        width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        return (int(width), int(height))
    
    def get_fps(self) -> float:
        """Get the current FPS setting."""
        if self.cap is None:
            return self.fps
        
        return self.cap.get(cv2.CAP_PROP_FPS)