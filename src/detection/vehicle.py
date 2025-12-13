"""
Vehicle detection module for identifying vehicles in video frames.
This is a basic implementation using background subtraction and contour analysis.
"""

import cv2
import numpy as np
import logging
from typing import List, Tuple, Optional

class VehicleDetector:
    """Detect vehicles using background subtraction and contour analysis."""
    
    def __init__(
        self,
        min_contour_area: int = 1000,
        detect_shadows: bool = True,
        history: int = 100,
        var_threshold: int = 40,
        min_width: int = 30,
        min_height: int = 30,
        max_width_ratio: float = 0.8,
        max_height_ratio: float = 0.8
    ) -> None:
        """
        Initialize the vehicle detector.
        
        Args:
            min_contour_area: Minimum contour area to be considered a vehicle
            detect_shadows: Whether to detect shadows in background subtraction
            history: History length for background subtraction
            var_threshold: Variance threshold for background subtraction
            min_width: Minimum bounding box width in pixels
            min_height: Minimum bounding box height in pixels
            max_width_ratio: Maximum width as ratio of frame width (filters oversized detections)
            max_height_ratio: Maximum height as ratio of frame height (filters oversized detections)
        """
        self.min_contour_area = min_contour_area
        self.min_width = min_width
        self.min_height = min_height
        self.max_width_ratio = max_width_ratio
        self.max_height_ratio = max_height_ratio
        
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
        
        # Track previous detections to filter stationary objects
        self.previous_detections = []
        self.stationary_threshold = 5  # Pixels movement threshold
        
        logging.info("Vehicle detector initialized")
    
    def detect(self, frame: np.ndarray) -> np.ndarray:
        """
        Detect vehicles in the frame.
        
        Args:
            frame: Input frame
        
        Returns:
            Array of vehicle bounding boxes [x1, y1, x2, y2]
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
        frame_height, frame_width = frame.shape[0], frame.shape[1]
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter based on area
            if area < self.min_contour_area or area > self.max_contour_area:
                continue
            
            # Get bounding box
            x_cont, y_cont, w_cont, h_cont = cv2.boundingRect(contour)
            
            # Size-based filtering
            if w_cont < self.min_width or h_cont < self.min_height:
                continue
            
            # Filter oversized detections (likely false positives)
            if w_cont > frame_width * self.max_width_ratio:
                continue
            if h_cont > frame_height * self.max_height_ratio:
                continue
            
            # Calculate aspect ratio (width/height)
            aspect_ratio = float(w_cont) / h_cont if h_cont > 0 else 0
            
            # Most vehicles have aspect ratio between 0.5 and 4.0
            if not (0.5 <= aspect_ratio <= 4.0):
                continue
            
            # Adjust coordinates to original frame
            x1 = x + x_cont
            y1 = y + y_cont
            x2 = x1 + w_cont
            y2 = y1 + h_cont
            
            # Calculate center for position-based filtering
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            # Position-based filtering: focus on road area (middle to bottom of frame)
            # This helps filter out detections in sky or other non-road areas
            road_y_min = frame_height * 0.2  # Start road area at 20% from top
            road_y_max = frame_height * 0.95  # End road area at 95% from top
            
            if center_y < road_y_min or center_y > road_y_max:
                continue
            
            vehicles.append([x1, y1, x2, y2])
        
        # Filter stationary objects by comparing with previous frame
        vehicles = self._filter_stationary_objects(vehicles)
        
        # Merge overlapping/nearby boxes to reduce fragmentation
        vehicles = self._merge_boxes(vehicles)
        
        # Update previous detections
        self.previous_detections = vehicles.copy()
        
        return np.array(vehicles) if vehicles else np.array([])
    
    def _merge_boxes(self, boxes: List[List[int]], overlap_thresh: float = 0.1, distance_thresh: int = 20) -> List[List[int]]:
        """
        Merge bounding boxes that overlap or are very close to each other.
        
        Args:
            boxes: List of bounding boxes [x1, y1, x2, y2]
            overlap_thresh: Minimum overlap ratio to merge
            distance_thresh: Minimum distance between boxes to merge (pixels)
            
        Returns:
            List of merged bounding boxes
        """
        if not boxes:
            return []
            
        # Convert to numpy for easier handling
        # Using a loop for simplicity and to handle the iterative merging
        merged_boxes = list(boxes)
        
        while True:
            new_boxes = []
            merged_indices = set()
            has_merged = False
            
            for i in range(len(merged_boxes)):
                if i in merged_indices:
                    continue
                    
                current_box = merged_boxes[i]
                
                for j in range(i + 1, len(merged_boxes)):
                    if j in merged_indices:
                        continue
                        
                    other_box = merged_boxes[j]
                    
                    # Check for overlap or proximity
                    if self._should_merge(current_box, other_box, distance_thresh):
                        # Merge boxes: x1, y1, x2, y2
                        current_box = [
                            min(current_box[0], other_box[0]),
                            min(current_box[1], other_box[1]),
                            max(current_box[2], other_box[2]),
                            max(current_box[3], other_box[3])
                        ]
                        merged_indices.add(j)
                        has_merged = True
                
                new_boxes.append(current_box)
            
            merged_boxes = new_boxes
            if not has_merged:
                break
                
        return merged_boxes

    def _should_merge(self, box1: List[int], box2: List[int], distance: int) -> bool:
        """Check if two boxes should be merged based on proximity."""
        x1_a, y1_a, x2_a, y2_a = box1
        x1_b, y1_b, x2_b, y2_b = box2
        
        # Check if boxes intersect (with distance buffer)
        # We expand box1 by 'distance' pixels in all directions
        if (x1_a - distance < x2_b and x2_a + distance > x1_b and
            y1_a - distance < y2_b and y2_a + distance > y1_b):
            return True
        return False

    def _filter_stationary_objects(self, current_detections: List[List[int]]) -> List[List[int]]:
        """
        Filter out detections that haven't moved significantly (likely stationary objects).
        
        Args:
            current_detections: List of current detections [x1, y1, x2, y2]
            
        Returns:
            Filtered list of detections
        """
        if not self.previous_detections or not current_detections:
            return current_detections
        
        filtered = []
        for curr in current_detections:
            curr_center = ((curr[0] + curr[2]) / 2, (curr[1] + curr[3]) / 2)
            
            # Check if this detection is close to any previous detection
            is_stationary = False
            for prev in self.previous_detections:
                prev_center = ((prev[0] + prev[2]) / 2, (prev[1] + prev[3]) / 2)
                
                # Calculate distance between centers
                distance = np.sqrt(
                    (curr_center[0] - prev_center[0]) ** 2 +
                    (curr_center[1] - prev_center[1]) ** 2
                )
                
                # If very close, likely the same stationary object
                if distance < self.stationary_threshold:
                    is_stationary = True
                    break
            
            if not is_stationary:
                filtered.append(curr)
        
        return filtered
    
    def set_roi(self, x: int, y: int, width: int, height: int) -> None:
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
    
    def reset_background_model(self) -> None:
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