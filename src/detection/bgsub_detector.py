"""
Background-subtraction detector adapter.

Wraps the existing VehicleDetector and presents it via the new Detector interface.

CLASSIFICATION BEHAVIOR:
- This detector produces UNCLASSIFIED detections (motion blobs).
- All detections have class_id=None, class_name=None, confidence=1.0.
- For multi-class detection (person, bicycle, car, motorcycle, bus, truck),
  use detection.backend='yolo' or detection.backend='hailo'.
- Background subtraction is a single-class fallback for when AI acceleration
  is not available or not needed.
"""

from __future__ import annotations

from typing import List

import numpy as np

from .base import Detector, Detection
from .vehicle import VehicleDetector


class BgSubDetector(Detector):
    def __init__(self, vehicle_detector: VehicleDetector):
        self._vehicle_detector = vehicle_detector

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Detect motion blobs via background subtraction.
        
        Returns:
            List of Detection objects with:
            - bbox: bounding box in pixel coordinates
            - confidence: 1.0 (background subtraction doesn't produce confidence scores)
            - class_id: None (no object classification)
            - class_name: None (no object classification)
        """
        boxes = self._vehicle_detector.detect(frame)
        if boxes is None or len(boxes) == 0:
            return []

        out: List[Detection] = []
        for box in boxes:
            x1, y1, x2, y2 = box[:4]
            # Note: class_id and class_name are left as None (single-class detection)
            out.append(Detection(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2), confidence=1.0))
        return out


