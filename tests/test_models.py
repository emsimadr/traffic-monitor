"""
Smoke tests for typed models and adapters.
"""

import time
import pytest
import numpy as np
from collections import deque

from models.frame import FrameData
from models.detection import Detection, BoundingBox, detections_from_numpy, detections_to_numpy
from models.track import Track, TrackState
from models.count_event import CountEvent
from models.status import Status, StatusLevel, DiskUsage, SystemStats
from models.health import Health
from models.config import (
    Config,
    CameraConfig,
    DetectionConfig,
    CountingConfig,
    StorageConfig,
    TrackingConfig,
)


class TestBoundingBox:
    def test_properties(self):
        bbox = BoundingBox(x1=100, y1=100, x2=200, y2=150)
        assert bbox.width == 100
        assert bbox.height == 50
        assert bbox.center == (150.0, 125.0)
        assert bbox.area == 5000

    def test_as_tuple(self):
        bbox = BoundingBox(x1=10.5, y1=20.5, x2=30.5, y2=40.5)
        assert bbox.as_tuple() == (10.5, 20.5, 30.5, 40.5)
        assert bbox.as_int_tuple() == (10, 20, 30, 40)

    def test_from_xywh(self):
        bbox = BoundingBox.from_xywh(x=100, y=100, w=50, h=30)
        assert bbox.x1 == 100
        assert bbox.x2 == 150
        assert bbox.y2 == 130


class TestDetection:
    def test_from_xyxy(self):
        det = Detection.from_xyxy(10, 20, 30, 40, confidence=0.9, class_id=2)
        assert det.x1 == 10
        assert det.confidence == 0.9
        assert det.class_id == 2

    def test_from_numpy_row(self):
        row = np.array([100, 100, 200, 200, 0.85, 1])
        det = Detection.from_numpy_row(row)
        assert det.x1 == 100
        assert det.confidence == 0.85
        assert det.class_id == 1

    def test_to_numpy(self):
        det = Detection.from_xyxy(10, 20, 30, 40, confidence=0.5, class_id=3)
        arr = det.to_numpy()
        assert arr[0] == 10
        assert arr[4] == 0.5
        assert arr[5] == 3


class TestDetectionAdapters:
    def test_detections_from_numpy_empty(self):
        result = detections_from_numpy(np.array([]))
        assert result == []

    def test_detections_roundtrip(self):
        arr = np.array([
            [10, 20, 30, 40, 0.9, 1],
            [50, 60, 70, 80, 0.8, 2],
        ])
        detections = detections_from_numpy(arr)
        assert len(detections) == 2
        
        back = detections_to_numpy(detections)
        assert back.shape == (2, 6)
        np.testing.assert_array_almost_equal(arr, back)


class TestFrameData:
    def test_from_numpy(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        ts = time.time()
        fd = FrameData.from_numpy(frame, timestamp=ts, frame_index=42)
        
        assert fd.width == 640
        assert fd.height == 480
        assert fd.frame_index == 42
        assert fd.size == (640, 480)


class TestTrack:
    def test_basic_track(self):
        track = Track(
            track_id=1,
            bbox=BoundingBox(100, 100, 150, 150),
            center=(125.0, 125.0),
            trajectory=deque([(125.0, 125.0)]),
        )
        assert track.age == 1
        assert track.is_active is True

    def test_track_with_metadata(self):
        track = Track(
            track_id=2,
            bbox=BoundingBox(100, 100, 150, 150),
            center=(125.0, 125.0),
            trajectory=deque([(125.0, 125.0)]),
            class_id=2,
            class_name="car",
            confidence=0.87,
        )
        assert track.class_id == 2
        assert track.class_name == "car"
        assert track.confidence == 0.87

    def test_track_state_from_track(self):
        track = Track(
            track_id=5,
            bbox=BoundingBox(10, 20, 30, 40),
            center=(20.0, 30.0),
            direction="A_TO_B",
            class_id=2,
            class_name="car",
            confidence=0.9,
        )
        state = TrackState.from_track(track)
        assert state.track_id == 5
        assert state.bbox == (10, 20, 30, 40)
        assert state.direction == "A_TO_B"
        assert state.class_id == 2
        assert state.class_name == "car"
        assert state.confidence == 0.9


class TestCountEvent:
    def test_to_dict(self):
        event = CountEvent(
            track_id=1,
            direction="A_TO_B",
            direction_label="northbound",
            timestamp=1234567890.0,
            counting_mode="gate",
        )
        d = event.to_dict()
        assert d["track_id"] == 1
        assert d["direction"] == "A_TO_B"
        assert d["direction_label"] == "northbound"
    
    def test_to_dict_with_metadata(self):
        event = CountEvent(
            track_id=1,
            direction="A_TO_B",
            direction_label="northbound",
            timestamp=1234567890.0,
            counting_mode="gate",
            class_id=2,
            class_name="car",
            confidence=0.87,
            detection_backend="yolo",
            platform="Windows-10",
            process_pid=12345,
        )
        d = event.to_dict()
        assert d["track_id"] == 1
        assert d["direction"] == "A_TO_B"
        assert d["class_id"] == 2
        assert d["class_name"] == "car"
        assert d["confidence"] == 0.87
        assert d["detection_backend"] == "yolo"
        assert d["platform"] == "Windows-10"
        assert d["process_pid"] == 12345


class TestStatus:
    def test_from_dict(self):
        d = {
            "status": "running",
            "alerts": [],
            "last_frame_age": 0.5,
            "fps": 30.0,
            "uptime_seconds": 3600,
            "disk": {"total_bytes": 1000, "free_bytes": 500, "pct_free": 50.0},
            "temp_c": 45.0,
            "timestamp": 1234567890.0,
        }
        status = Status.from_dict(d)
        assert status.status == StatusLevel.RUNNING
        assert status.is_healthy is True
        assert status.fps == 30.0
        assert status.disk.pct_free == 50.0

    def test_degraded_status(self):
        status = Status(
            status=StatusLevel.DEGRADED,
            alerts=["camera_stale"],
        )
        assert status.is_healthy is False


class TestHealth:
    def test_from_dict(self):
        d = {
            "timestamp": 123.0,
            "platform": "Linux-5.4",
            "python": "3.11.0",
            "cwd": "/home/user",
            "storage_db_path": "data/db.sqlite",
        }
        health = Health.from_dict(d)
        assert health.platform == "Linux-5.4"
        assert health.python == "3.11.0"


class TestConfig:
    def test_from_dict_minimal(self):
        d = {
            "camera": {"device_id": 0},
            "detection": {"backend": "bgsub"},
            "storage": {"local_database_path": "test.db"},
            "log_path": "test.log",
            "log_level": "DEBUG",
        }
        cfg = Config.from_dict(d)
        assert cfg.camera.device_id == 0
        assert cfg.detection.backend == "bgsub"
        assert cfg.log_level == "DEBUG"

    def test_roundtrip(self):
        d = {
            "camera": {
                "backend": "opencv",
                "device_id": 0,
                "resolution": [1920, 1080],
                "fps": 60,
            },
            "detection": {
                "backend": "yolo",
                "yolo": {"model": "yolov8n.pt", "conf_threshold": 0.5},
            },
            "counting": {
                "line_a": [[0.1, 0.5], [0.9, 0.5]],
                "direction_labels": {"a_to_b": "north"},
            },
            "storage": {"local_database_path": "db.sqlite"},
            "tracking": {"max_frames_since_seen": 15},
            "log_path": "app.log",
            "log_level": "INFO",
        }
        cfg = Config.from_dict(d)
        back = cfg.to_dict()
        
        assert back["camera"]["fps"] == 60
        assert back["detection"]["yolo"]["model"] == "yolov8n.pt"
        assert back["counting"]["line_a"] == [[0.1, 0.5], [0.9, 0.5]]
        assert back["tracking"]["max_frames_since_seen"] == 15

