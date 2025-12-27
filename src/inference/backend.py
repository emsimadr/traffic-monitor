"""
Inference backend interface.

Backends return pixel-space detections in the original frame coordinate system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol

import numpy as np


@dataclass(frozen=True)
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float = 1.0
    class_id: Optional[int] = None
    class_name: Optional[str] = None


class InferenceBackend(Protocol):
    def detect(self, frame: np.ndarray) -> List[Detection]:
        ...


