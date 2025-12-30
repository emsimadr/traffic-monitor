"""
Observation layer for pluggable video/image sources.

This layer abstracts the source of frames (camera, video file, remote stream)
from the processing pipeline. Each source implements the ObservationSource
interface and returns FrameData objects.
"""

from .base import ObservationSource, ObservationConfig
from .opencv_source import OpenCVSource, OpenCVSourceConfig

__all__ = [
    "ObservationSource",
    "ObservationConfig",
    "OpenCVSource",
    "OpenCVSourceConfig",
]

