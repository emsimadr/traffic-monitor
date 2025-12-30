"""
FrameData model for captured video frames.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass
class FrameData:
    """
    Metadata and payload for a captured video frame.
    
    Attributes:
        frame: The raw frame data as a numpy array (BGR format).
        width: Frame width in pixels.
        height: Frame height in pixels.
        timestamp: Unix timestamp when frame was captured.
        frame_index: Sequential frame number since start.
        source: Identifier for the camera/video source.
    """
    frame: np.ndarray
    width: int
    height: int
    timestamp: float
    frame_index: int = 0
    source: Optional[str] = None

    @classmethod
    def from_numpy(
        cls,
        frame: np.ndarray,
        timestamp: float,
        frame_index: int = 0,
        source: Optional[str] = None,
    ) -> "FrameData":
        """Create FrameData from a numpy array."""
        h, w = frame.shape[:2]
        return cls(
            frame=frame,
            width=w,
            height=h,
            timestamp=timestamp,
            frame_index=frame_index,
            source=source,
        )

    @property
    def shape(self) -> Tuple[int, int, int]:
        """Return (height, width, channels)."""
        return self.frame.shape

    @property
    def size(self) -> Tuple[int, int]:
        """Return (width, height)."""
        return (self.width, self.height)

