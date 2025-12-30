"""
ObservationSource interface for pluggable video/image sources.

This defines the contract that all observation sources must implement,
enabling the processing pipeline to work with any video source:
- USB/CSI cameras
- RTSP/IP cameras
- Video files
- Image sequences
- Remote streams
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional

from models.frame import FrameData


@dataclass
class ObservationConfig:
    """
    Base configuration for observation sources.
    
    Attributes:
        source_id: Unique identifier for this source (e.g., "cam-01", "traffic-feed").
        resolution: Target resolution as (width, height). None = use source default.
        fps: Target frames per second. None = use source default.
        metadata: Additional source-specific configuration.
    """
    source_id: str = "default"
    resolution: Optional[tuple[int, int]] = None
    fps: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ObservationSource(ABC):
    """
    Abstract base class for observation sources.
    
    An observation source provides video frames from any input:
    cameras, video files, image sequences, or remote streams.
    
    Lifecycle:
        1. Create instance with config
        2. Call open() to initialize the source
        3. Call read() repeatedly to get frames
        4. Call close() to release resources
    
    Can also be used as a context manager:
        with OpenCVSource(config) as source:
            for frame_data in source:
                process(frame_data)
    """

    def __init__(self, config: ObservationConfig):
        self._config = config
        self._is_open = False
        self._frame_index = 0

    @property
    def source_id(self) -> str:
        """Unique identifier for this source."""
        return self._config.source_id

    @property
    def is_open(self) -> bool:
        """Whether the source is currently open and ready to read."""
        return self._is_open

    @property
    def frame_index(self) -> int:
        """Current frame index (number of frames read since open)."""
        return self._frame_index

    @abstractmethod
    def open(self) -> None:
        """
        Open/initialize the observation source.
        
        Must be called before read(). May raise exceptions if the source
        cannot be opened (e.g., camera not found, file doesn't exist).
        
        Raises:
            RuntimeError: If the source cannot be opened.
        """
        pass

    @abstractmethod
    def read(self) -> Optional[FrameData]:
        """
        Read the next frame from the source.
        
        Returns:
            FrameData containing the frame, timestamp, frame_id, and source_id.
            Returns None if no frame is available (e.g., end of video, camera error).
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close/release the observation source.
        
        Releases any resources held by the source (camera handle, file handle, etc.).
        Safe to call multiple times.
        """
        pass

    def __enter__(self) -> "ObservationSource":
        """Context manager entry - opens the source."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - closes the source."""
        self.close()

    def __iter__(self) -> Iterator[FrameData]:
        """
        Iterate over frames from the source.
        
        Yields FrameData objects until the source is exhausted or closed.
        The source must be open before iterating.
        """
        if not self._is_open:
            raise RuntimeError("Source must be open before iterating")
        
        while True:
            frame_data = self.read()
            if frame_data is None:
                break
            yield frame_data

