"""
Vehicle tracking module for tracking vehicles across video frames.

This module implements a simple tracking system to prevent double-counting
by tracking vehicles across frames and counting them only once when they
cross the counting line.
"""

import logging
import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from collections import deque


@dataclass
class TrackedVehicle:
    """Represents a tracked vehicle across frames."""
    vehicle_id: int
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    center: Tuple[float, float]  # (cx, cy)
    frames_since_seen: int
    direction: Optional[str]  # "northbound", "southbound", or None
    has_been_counted: bool
    trajectory: deque  # History of center positions


class VehicleTracker:
    """
    Tracks vehicles across frames to prevent double-counting.
    
    Uses IoU (Intersection over Union) to match detections across frames
    and tracks vehicle movement to determine direction and count vehicles
    only once when they cross the counting line.
    """
    
    def __init__(
        self,
        max_frames_since_seen: int = 10,
        min_trajectory_length: int = 3,
        iou_threshold: float = 0.3
    ):
        """
        Initialize the vehicle tracker.
        
        Args:
            max_frames_since_seen: Maximum frames a vehicle can be missing
                                   before being removed from tracking
            min_trajectory_length: Minimum trajectory points needed to
                                   determine direction
            iou_threshold: Minimum IoU value to match detections across frames
        """
        self.max_frames_since_seen = max_frames_since_seen
        self.min_trajectory_length = min_trajectory_length
        self.iou_threshold = iou_threshold
        
        self.tracked_vehicles: Dict[int, TrackedVehicle] = {}
        self.next_vehicle_id = 0
        self.counting_line: Optional[List[Tuple[int, int]]] = None
        
        logging.info("Vehicle tracker initialized")
    
    def set_counting_line(self, line: List[Tuple[int, int]]):
        """
        Set the counting line as a list of two points [(x1, y1), (x2, y2)].
        
        Args:
            line: List of two points defining the line
        """
        self.counting_line = line
        logging.debug(f"Counting line set to {line}")
    
    def update(self, detections: np.ndarray, counting_line: List[Tuple[int, int]]) -> List[Tuple[int, str]]:
        """
        Update tracker with new detections and return vehicles that crossed the line.
        
        Args:
            detections: Array of detections, each as [x1, y1, x2, y2]
            counting_line: List of two points [(x1, y1), (x2, y2)]
            
        Returns:
            List of tuples (vehicle_id, direction) for vehicles that just crossed
            the counting line and should be counted
        """
        if self.counting_line != counting_line:
            self.set_counting_line(counting_line)
        
        # Update existing tracked vehicles
        self._update_existing_tracks(detections)
        
        # Add new detections as new tracks
        self._add_new_tracks(detections)
        
        # Remove old tracks
        self._remove_old_tracks()
        
        # Check for vehicles crossing the counting line
        vehicles_to_count = self._check_line_crossings()
        
        return vehicles_to_count
    
    def _calculate_iou(
        self,
        bbox1: Tuple[int, int, int, int],
        bbox2: Tuple[int, int, int, int]
    ) -> float:
        """
        Calculate Intersection over Union (IoU) between two bounding boxes.
        
        Args:
            bbox1: First bounding box (x1, y1, x2, y2)
            bbox2: Second bounding box (x1, y1, x2, y2)
            
        Returns:
            IoU value between 0 and 1
        """
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i <= x1_i or y2_i <= y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        
        # Calculate union
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _calculate_center(self, bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
        """Calculate center point of a bounding box."""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    
    def _update_existing_tracks(self, detections: np.ndarray):
        """Update existing tracked vehicles with new detections."""
        if len(detections) == 0:
            # No detections, increment frames_since_seen for all tracks
            for vehicle in self.tracked_vehicles.values():
                vehicle.frames_since_seen += 1
            return
        
        # Match detections to existing tracks using IoU
        matched_detections = set()
        
        for vehicle_id, vehicle in self.tracked_vehicles.items():
            if vehicle.has_been_counted:
                vehicle.frames_since_seen += 1
                continue
            
            best_iou = 0.0
            best_detection_idx = None
            
            for idx, detection in enumerate(detections):
                if idx in matched_detections:
                    continue
                
                iou = self._calculate_iou(vehicle.bbox, tuple(detection[:4]))
                if iou > best_iou and iou >= self.iou_threshold:
                    best_iou = iou
                    best_detection_idx = idx
            
            if best_detection_idx is not None:
                # Update vehicle with new detection
                detection = detections[best_detection_idx]
                vehicle.bbox = tuple(detection[:4])
                vehicle.center = self._calculate_center(vehicle.bbox)
                vehicle.frames_since_seen = 0
                vehicle.trajectory.append(vehicle.center)
                
                # Limit trajectory length
                if len(vehicle.trajectory) > 20:
                    vehicle.trajectory.popleft()
                
                matched_detections.add(best_detection_idx)
            else:
                # No match found, increment frames_since_seen
                vehicle.frames_since_seen += 1
    
    def _add_new_tracks(self, detections: np.ndarray):
        """Add new detections as new tracked vehicles."""
        if len(detections) == 0:
            return
        
        # Find detections that weren't matched to existing tracks
        matched_indices = set()
        for vehicle in self.tracked_vehicles.values():
            if vehicle.has_been_counted:
                continue
            
            for idx, detection in enumerate(detections):
                if idx in matched_indices:
                    continue
                
                iou = self._calculate_iou(vehicle.bbox, tuple(detection[:4]))
                if iou >= self.iou_threshold:
                    matched_indices.add(idx)
        
        # Create new tracks for unmatched detections
        for idx, detection in enumerate(detections):
            if idx not in matched_indices:
                bbox = tuple(detection[:4])
                center = self._calculate_center(bbox)
                
                vehicle = TrackedVehicle(
                    vehicle_id=self.next_vehicle_id,
                    bbox=bbox,
                    center=center,
                    frames_since_seen=0,
                    direction=None,
                    has_been_counted=False,
                    trajectory=deque([center], maxlen=20)
                )
                
                self.tracked_vehicles[self.next_vehicle_id] = vehicle
                self.next_vehicle_id += 1
    
    def _remove_old_tracks(self):
        """Remove tracked vehicles that haven't been seen for too long."""
        to_remove = []
        for vehicle_id, vehicle in self.tracked_vehicles.items():
            if vehicle.frames_since_seen > self.max_frames_since_seen:
                to_remove.append(vehicle_id)
        
        for vehicle_id in to_remove:
            del self.tracked_vehicles[vehicle_id]
    
    def _check_line_crossings(self) -> List[Tuple[int, str]]:
        """
        Check for vehicles crossing the counting line based on side switching.
        
        Returns:
            List of (vehicle_id, direction) tuples for vehicles that just crossed
        """
        if not self.counting_line:
            return []
            
        vehicles_to_count = []
        p1, p2 = self.counting_line
        
        for vehicle in self.tracked_vehicles.values():
            if vehicle.has_been_counted or len(vehicle.trajectory) < 2:
                continue
            
            # Get current and previous position
            curr_pos = vehicle.center
            prev_pos = vehicle.trajectory[-2]
            
            # Check which side of the line the points are on
            prev_side = self._get_line_side(prev_pos, p1, p2)
            curr_side = self._get_line_side(curr_pos, p1, p2)
            
            # If sides are different (and not 0 which means on the line), a crossing occurred
            if prev_side != 0 and curr_side != 0 and prev_side != curr_side:
                # Direction is determined by the transition
                # +1 to -1: Direction A (e.g., Northbound)
                # -1 to +1: Direction B (e.g., Southbound)
                
                if prev_side > 0 and curr_side < 0:
                    vehicle.direction = "northbound" # Arbitrary mapping, can be swapped
                else:
                    vehicle.direction = "southbound"
                
                # Mark as counted and add to list
                vehicle.has_been_counted = True
                vehicles_to_count.append((vehicle.vehicle_id, vehicle.direction))
                logging.debug(f"Vehicle {vehicle.vehicle_id} crossed line: {vehicle.direction}")
        
        return vehicles_to_count

    def _get_line_side(self, p: Tuple[float, float], line_start: Tuple[int, int], line_end: Tuple[int, int]) -> int:
        """
        Determine which side of the line a point is on using the cross product.
        
        Returns:
            1 if on one side, -1 if on the other, 0 if on the line
        """
        # Vector for the line
        line_vec_x = line_end[0] - line_start[0]
        line_vec_y = line_end[1] - line_start[1]
        
        # Vector from line start to point
        point_vec_x = p[0] - line_start[0]
        point_vec_y = p[1] - line_start[1]
        
        # Cross product (2D analog)
        cross_product = (line_vec_x * point_vec_y) - (line_vec_y * point_vec_x)
        
        if cross_product > 0:
            return 1
        elif cross_product < 0:
            return -1
        else:
            return 0

    def _determine_direction(self, vehicle: TrackedVehicle) -> Optional[str]:
        """Deprecated: Direction is now determined during line crossing."""
        return vehicle.direction
    
    def get_active_tracks(self) -> List[TrackedVehicle]:
        """Get list of currently active tracked vehicles."""
        return [v for v in self.tracked_vehicles.values() if not v.has_been_counted]

