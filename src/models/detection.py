"""
Detection models for object detection results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

import numpy as np


@dataclass(frozen=True)
class BoundingBox:
    """
    A bounding box in pixel coordinates.
    
    Attributes:
        x1: Left edge x coordinate.
        y1: Top edge y coordinate.
        x2: Right edge x coordinate.
        y2: Bottom edge y coordinate.
    """
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def area(self) -> float:
        return self.width * self.height

    def as_tuple(self) -> Tuple[float, float, float, float]:
        """Return as (x1, y1, x2, y2) tuple."""
        return (self.x1, self.y1, self.x2, self.y2)

    def as_int_tuple(self) -> Tuple[int, int, int, int]:
        """Return as integer (x1, y1, x2, y2) tuple."""
        return (int(self.x1), int(self.y1), int(self.x2), int(self.y2))

    @classmethod
    def from_tuple(cls, t: Tuple[float, float, float, float]) -> "BoundingBox":
        """Create from (x1, y1, x2, y2) tuple."""
        return cls(x1=t[0], y1=t[1], x2=t[2], y2=t[3])

    @classmethod
    def from_xywh(cls, x: float, y: float, w: float, h: float) -> "BoundingBox":
        """Create from (x, y, width, height) format."""
        return cls(x1=x, y1=y, x2=x + w, y2=y + h)


@dataclass(frozen=True)
class Detection:
    """
    A single detection from an object detector.
    
    Attributes:
        bbox: Bounding box in pixel coordinates.
        confidence: Detection confidence score (0-1).
        class_id: Optional class ID from the detector.
        class_name: Optional human-readable class name.
        timestamp: Optional timestamp of detection.
    """
    bbox: BoundingBox
    confidence: float = 1.0
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    timestamp: Optional[float] = None

    @property
    def x1(self) -> float:
        return self.bbox.x1

    @property
    def y1(self) -> float:
        return self.bbox.y1

    @property
    def x2(self) -> float:
        return self.bbox.x2

    @property
    def y2(self) -> float:
        return self.bbox.y2

    @property
    def center(self) -> Tuple[float, float]:
        return self.bbox.center

    @classmethod
    def from_xyxy(
        cls,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        confidence: float = 1.0,
        class_id: Optional[int] = None,
        class_name: Optional[str] = None,
    ) -> "Detection":
        """Create Detection from x1, y1, x2, y2 coordinates."""
        return cls(
            bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
            confidence=confidence,
            class_id=class_id,
            class_name=class_name,
        )

    @classmethod
    def from_base_detection(cls, det) -> "Detection":
        """
        Adapter: Convert from detection.base.Detection to models.Detection.
        
        Args:
            det: A detection.base.Detection instance with x1, y1, x2, y2, confidence, etc.
        """
        return cls(
            bbox=BoundingBox(x1=det.x1, y1=det.y1, x2=det.x2, y2=det.y2),
            confidence=getattr(det, "confidence", 1.0),
            class_id=getattr(det, "class_id", None),
            class_name=getattr(det, "class_name", None),
        )

    @classmethod
    def from_domain_detection(cls, det) -> "Detection":
        """
        Adapter: Convert from domain.models.Detection (bbox tuple) to models.Detection.
        
        Args:
            det: A domain.models.Detection instance with bbox as (x1, y1, x2, y2).
        """
        bbox = det.bbox
        return cls(
            bbox=BoundingBox(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3]),
            confidence=det.score if det.score is not None else 1.0,
            class_id=det.class_id,
            timestamp=det.timestamp,
        )

    @classmethod
    def from_numpy_row(cls, row: np.ndarray) -> "Detection":
        """
        Adapter: Convert from numpy array row [x1, y1, x2, y2, ...] to Detection.
        """
        return cls(
            bbox=BoundingBox(
                x1=float(row[0]),
                y1=float(row[1]),
                x2=float(row[2]),
                y2=float(row[3]),
            ),
            confidence=float(row[4]) if len(row) > 4 else 1.0,
            class_id=int(row[5]) if len(row) > 5 else None,
        )

    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array [x1, y1, x2, y2, confidence, class_id]."""
        return np.array([
            self.x1, self.y1, self.x2, self.y2,
            self.confidence,
            self.class_id if self.class_id is not None else -1,
        ])


def detections_from_numpy(arr: np.ndarray) -> List[Detection]:
    """
    Adapter: Convert numpy array of detections to list of Detection objects.
    
    Args:
        arr: Array of shape (N, 4+) where each row is [x1, y1, x2, y2, ...].
    """
    if arr is None or len(arr) == 0:
        return []
    return [Detection.from_numpy_row(row) for row in arr]


def detections_to_numpy(detections: List[Detection]) -> np.ndarray:
    """
    Adapter: Convert list of Detection objects to numpy array.
    
    Returns:
        Array of shape (N, 6) with [x1, y1, x2, y2, confidence, class_id].
    """
    if not detections:
        return np.array([])
    return np.array([d.to_numpy() for d in detections])

