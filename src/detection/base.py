"""
Detection interfaces.

We keep this lightweight so the project can support multiple backends:
- classical CV (background subtraction)
- YOLO (CPU/ONNX for dev)
- YOLO on accelerator (e.g., Hailo) for deployment
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass(frozen=True)
class Detection:
    """
    A single detection.

    bbox is in pixel coordinates in the original frame.
    """

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float = 1.0
    class_id: Optional[int] = None
    class_name: Optional[str] = None


class Detector:
    """Detector interface returning detections in pixel-space."""

    def detect(self, frame: np.ndarray) -> List[Detection]:
        raise NotImplementedError


