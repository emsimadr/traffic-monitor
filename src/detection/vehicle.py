"""
Vehicle detection module for identifying vehicles in video frames.
This is a basic implementation using background subtraction and contour analysis.
"""

import cv2
import numpy as np
import logging

class VehicleDetector:
    """Detect vehicles using background subtraction and contour analysis."""
    
    def __init__(self, min_contour_area=1000, detect_shadows=True, 
                 history=100, var_threshold=40):
        """
        Initialize the vehicle detector.
        
        Args:
            min_contour_area: Minimum contour area to be considered a vehicle
            detect_shadows: Whether to detect shadows in background subtraction
            history: History length for background subtraction
            var_threshold: Variance threshold for background subtraction
        """
        self.min_contour_area = min_contour_area
        
        # Create background subtractor
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=var_threshold,
            detectShadows=detect_shadows
        )
        
        # Maximum contour area (to filter out very large detections)
        self.max_contour_area = 100000
        
        # ROI for detection (will be set based on first frame)
        self.roi = None
        
        # Counter for frame processing
        self.frame_count = 0
        
        # Kernel for morphological operations
        self.kernel = np.ones((5, 5), np.uint8)
        
        logging.info("Vehicle detector initialized")
    
    def detect(self, frame):
        """
        Detect vehicles in the frame.
        
        Args:
            frame: Input frame
        
        Returns:
            List of vehicle bounding boxes [x1, y1, x2, y2]
        """
        self.frame_count += 1
        
        # Set ROI if not already set
        if self.roi is None:
            self.roi = (0, 0, frame.shape[1], frame.shape[0])
        
        # Extract ROI from frame
        x, y, w, h = self.roi
        roi_frame = frame[y:y+h, x:x+w]
        
        # Apply background subtraction
        fg_mask = self.bg_subtractor.apply(roi_frame)
        
        # Apply morphological operations to remove noise
        opening = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.kernel)
        closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, self.kernel)
        
        # Threshold to remove shadows (gray pixels)
        _, thresholded = cv2.threshold(closing, 200, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter and process contours
        vehicles = []
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter based on area
            if area < self.min_contour_area or area > self.max_contour_area:
                continue
            
            # Get bounding box
            x_cont, y_cont, w_cont, h_cont = cv2.boundingRect(contour)
            
            # Calculate aspect ratio (width/height)
            aspect_ratio = float(w_cont) / h_cont if h_cont > 0 else 0
            
            # Most vehicles have aspect ratio between 0.5 and 4.0
            if 0.5 <= aspect_ratio <= 4.0:
                # Adjust coordinates to original frame
                x1 = x + x_cont
                y1 = y + y_cont
                x2 = x1 + w_cont
                y2 = y1 + h_cont
                
                vehicles.append([x1, y1, x2, y2])
        
        return np.array(vehicles)
    
    def set_roi(self, x, y, width, height):
        """
        Set region of interest for detection.
        
        Args:
            x: X-coordinate of top-left corner
            y: Y-coordinate of top-left corner
            width: Width of ROI
            height: Height of ROI
        """
        self.roi = (x, y, width, height)
        logging.info(f"Detection ROI set to ({x}, {y}, {width}, {height})")
    
    def reset_background_model(self):
        """Reset the background model."""
        history = self.bg_subtractor.getHistory()
        var_threshold = self.bg_subtractor.getVarThreshold()
        detect_shadows = self.bg_subtractor.getDetectShadows()
        
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=var_threshold,
            detectShadows=detect_shadows
        )
        
        logging.info("Background model reset")