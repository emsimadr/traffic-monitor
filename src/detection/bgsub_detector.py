"""
Background-subtraction detector adapter.

Wraps the existing VehicleDetector and presents it via the new Detector interface.
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
        boxes = self._vehicle_detector.detect(frame)
        if boxes is None or len(boxes) == 0:
            return []

        out: List[Detection] = []
        for box in boxes:
            x1, y1, x2, y2 = box[:4]
            out.append(Detection(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2), confidence=1.0))
        return out


