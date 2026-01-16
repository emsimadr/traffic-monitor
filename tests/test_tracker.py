"""
Smoke tests for VehicleTracker stability across synthetic sequences.
"""

import numpy as np
import pytest
from tracking.tracker import VehicleTracker, TrackedVehicle


class TestTrackerBasics:
    """Basic tracker functionality tests."""

    def test_tracker_init(self):
        """Tracker initializes with default parameters."""
        tracker = VehicleTracker()
        
        assert tracker.max_frames_since_seen == 10
        assert tracker.min_trajectory_length == 3
        assert tracker.iou_threshold == 0.3
        assert len(tracker.tracked_vehicles) == 0
        assert tracker.next_vehicle_id == 0

    def test_tracker_custom_params(self):
        """Tracker accepts custom parameters."""
        tracker = VehicleTracker(
            max_frames_since_seen=5,
            min_trajectory_length=2,
            iou_threshold=0.5
        )
        
        assert tracker.max_frames_since_seen == 5
        assert tracker.min_trajectory_length == 2
        assert tracker.iou_threshold == 0.5

    def test_empty_detections(self):
        """Tracker handles empty detection array."""
        tracker = VehicleTracker()
        
        result = tracker.update(np.array([]))
        
        assert result == []
        assert len(tracker.tracked_vehicles) == 0


class TestTrackerSequence:
    """Tests for tracker stability across synthetic detection sequences."""

    def test_single_object_tracked(self):
        """Single object is tracked across frames."""
        tracker = VehicleTracker(iou_threshold=0.3)
        
        # Frame 1: Object appears at (100, 100, 150, 150)
        det1 = np.array([[100, 100, 150, 150]])
        tracker.update(det1)
        
        assert len(tracker.tracked_vehicles) == 1
        track = list(tracker.tracked_vehicles.values())[0]
        assert track.vehicle_id == 0
        assert track.bbox == (100, 100, 150, 150)

    def test_object_moves_smoothly(self):
        """Object moving smoothly maintains same track ID."""
        tracker = VehicleTracker(iou_threshold=0.2)
        
        # Simulate object moving right across 5 frames
        positions = [
            [100, 100, 150, 150],
            [120, 100, 170, 150],
            [140, 100, 190, 150],
            [160, 100, 210, 150],
            [180, 100, 230, 150],
        ]
        
        for pos in positions:
            tracker.update(np.array([pos]))
        
        # Should still be single track
        assert len(tracker.tracked_vehicles) == 1
        track = list(tracker.tracked_vehicles.values())[0]
        assert track.vehicle_id == 0
        
        # Trajectory should have 5 points
        assert len(track.trajectory) == 5

    def test_object_disappears_and_removed(self):
        """Object disappearing is removed after max_frames_since_seen."""
        tracker = VehicleTracker(max_frames_since_seen=3)
        
        # Object appears
        tracker.update(np.array([[100, 100, 150, 150]]))
        assert len(tracker.tracked_vehicles) == 1
        
        # Object disappears for max_frames_since_seen + 1 frames
        for _ in range(4):
            tracker.update(np.array([]))
        
        # Track should be removed
        assert len(tracker.tracked_vehicles) == 0

    def test_two_objects_tracked_independently(self):
        """Two objects are tracked with separate IDs."""
        tracker = VehicleTracker(iou_threshold=0.3)
        
        # Two objects appear far apart
        det = np.array([
            [100, 100, 150, 150],
            [300, 300, 350, 350],
        ])
        tracker.update(det)
        
        assert len(tracker.tracked_vehicles) == 2
        ids = [v.vehicle_id for v in tracker.tracked_vehicles.values()]
        assert 0 in ids
        assert 1 in ids

    def test_trajectory_accumulates(self):
        """Trajectory accumulates center points over frames."""
        tracker = VehicleTracker(iou_threshold=0.2)
        
        # Object moves slowly so boxes overlap (IoU > threshold)
        # Each step moves 10px, with 50px box, gives good overlap
        for i in range(5):
            x = 100 + i * 10
            y = 100 + i * 10
            tracker.update(np.array([[x, y, x + 50, y + 50]]))
        
        # Should still be single track with accumulated trajectory
        assert len(tracker.tracked_vehicles) == 1
        track = list(tracker.tracked_vehicles.values())[0]
        
        # Should have 5 trajectory points
        assert len(track.trajectory) == 5
        
        # Centers should be at (125, 125), (135, 135), (145, 145), (155, 155), (165, 165)
        centers = list(track.trajectory)
        assert centers[0] == (125.0, 125.0)
        assert centers[-1] == (165.0, 165.0)

    def test_get_active_tracks(self):
        """get_active_tracks returns only uncounted tracks."""
        tracker = VehicleTracker()
        
        tracker.update(np.array([[100, 100, 150, 150]]))
        
        active = tracker.get_active_tracks()
        assert len(active) == 1
        assert active[0].has_been_counted is False
        
        # Mark as counted
        active[0].has_been_counted = True
        
        active = tracker.get_active_tracks()
        assert len(active) == 0

    def test_get_all_tracks(self):
        """get_all_tracks returns all tracks including counted ones."""
        tracker = VehicleTracker()
        
        tracker.update(np.array([[100, 100, 150, 150]]))
        track = list(tracker.tracked_vehicles.values())[0]
        track.has_been_counted = True
        
        all_tracks = tracker.get_all_tracks()
        assert len(all_tracks) == 1
        assert all_tracks[0].has_been_counted is True


class TestTrackerMetadata:
    """Tests for detection metadata preservation."""
    
    def test_metadata_stored_on_new_track(self):
        """Detection metadata is stored when creating new track."""
        tracker = VehicleTracker()
        
        det = np.array([[100, 100, 150, 150]])
        metadata = [{'class_id': 2, 'class_name': 'car', 'confidence': 0.87}]
        
        tracker.update(det, detection_metadata=metadata)
        
        assert len(tracker.tracked_vehicles) == 1
        track = list(tracker.tracked_vehicles.values())[0]
        assert track.class_id == 2
        assert track.class_name == 'car'
        assert track.confidence == 0.87
    
    def test_metadata_updated_on_existing_track(self):
        """Detection metadata is updated when track is matched."""
        tracker = VehicleTracker(iou_threshold=0.3)
        
        # Create track without metadata
        det1 = np.array([[100, 100, 150, 150]])
        tracker.update(det1)
        
        track = list(tracker.tracked_vehicles.values())[0]
        assert track.class_id is None
        
        # Update with metadata
        det2 = np.array([[105, 105, 155, 155]])  # Slight movement
        metadata = [{'class_id': 2, 'class_name': 'car', 'confidence': 0.9}]
        tracker.update(det2, detection_metadata=metadata)
        
        # Same track should now have metadata
        track = list(tracker.tracked_vehicles.values())[0]
        assert track.class_id == 2
        assert track.class_name == 'car'
        assert track.confidence == 0.9
    
    def test_no_metadata_defaults(self):
        """Tracks without metadata have default values."""
        tracker = VehicleTracker()
        
        det = np.array([[100, 100, 150, 150]])
        tracker.update(det)  # No metadata provided
        
        track = list(tracker.tracked_vehicles.values())[0]
        assert track.class_id is None
        assert track.class_name is None
        assert track.confidence == 1.0


class TestIoUCalculation:
    """Tests for IoU calculation helper."""

    def test_iou_identical_boxes(self):
        """Identical boxes have IoU of 1.0."""
        tracker = VehicleTracker()
        
        iou = tracker._calculate_iou(
            (100, 100, 200, 200),
            (100, 100, 200, 200)
        )
        
        assert iou == 1.0

    def test_iou_no_overlap(self):
        """Non-overlapping boxes have IoU of 0.0."""
        tracker = VehicleTracker()
        
        iou = tracker._calculate_iou(
            (0, 0, 50, 50),
            (100, 100, 150, 150)
        )
        
        assert iou == 0.0

    def test_iou_partial_overlap(self):
        """Partially overlapping boxes have IoU between 0 and 1."""
        tracker = VehicleTracker()
        
        # 50% overlap in x direction
        iou = tracker._calculate_iou(
            (0, 0, 100, 100),
            (50, 0, 150, 100)
        )
        
        # Intersection: 50x100 = 5000
        # Union: 100x100 + 100x100 - 5000 = 15000
        # IoU = 5000/15000 = 0.333...
        assert 0.3 < iou < 0.4

