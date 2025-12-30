"""
Typed models for the traffic monitor application.

These models provide strong typing and validation without changing existing behavior.
Use the adapter functions to convert from existing dicts/tuples.
"""

from .frame import FrameData
from .detection import Detection, BoundingBox
from .track import Track, TrackState
from .count_event import CountEvent
from .status import Status, DiskUsage, SystemStats
from .health import Health
from .config import (
    Config,
    CameraConfig,
    DetectionConfig,
    YoloConfig,
    CountingConfig,
    GateConfig,
    StorageConfig,
    TrackingConfig,
)

__all__ = [
    # Frame
    "FrameData",
    # Detection
    "Detection",
    "BoundingBox",
    # Tracking
    "Track",
    "TrackState",
    # Counting
    "CountEvent",
    # Status/Health
    "Status",
    "DiskUsage",
    "SystemStats",
    "Health",
    # Config
    "Config",
    "CameraConfig",
    "DetectionConfig",
    "YoloConfig",
    "CountingConfig",
    "GateConfig",
    "StorageConfig",
    "TrackingConfig",
]

