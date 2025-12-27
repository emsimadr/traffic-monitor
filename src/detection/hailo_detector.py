"""
Hailo (AI HAT+) detector backend placeholder.

Why this exists:
- We want the codebase structured so swapping from CPU YOLO → Hailo YOLO
  does not require rewriting `main.py` or the tracker/storage pipeline.

What is NOT implemented here:
- Loading/compiling HEF models
- Hailo runtime pipeline (hailort / TAPPAS / GStreamer)

When we implement this for real on the Pi, this class should:
- accept a compiled model artifact reference (e.g., HEF path)
- run inference on frames (likely resized/letterboxed)
- return a list of Detection objects with pixel-space bboxes in the original frame
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .base import Detector, Detection


@dataclass(frozen=True)
class HailoConfig:
    hef_path: str
    # Add fields later: input_size, labels, postprocess config, etc.


class HailoYoloDetector(Detector):
    def __init__(self, cfg: HailoConfig):
        self.cfg = cfg
        raise NotImplementedError(
            "Hailo backend is not implemented yet. "
            "Use detection.backend='yolo' for CPU dev, or 'bgsub' fallback."
        )

    def detect(self, frame: np.ndarray) -> List[Detection]:  # pragma: no cover
        return []


