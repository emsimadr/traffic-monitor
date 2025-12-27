"""
Hailo AI HAT+ inference backend (placeholder).

This file exists so the repo structure matches the target architecture.
We'll implement it on-device once we pick the exact Hailo pipeline/toolchain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from .backend import Detection, InferenceBackend


@dataclass(frozen=True)
class HailoConfig:
    hef_path: str


class HailoBackend(InferenceBackend):
    def __init__(self, cfg: HailoConfig):
        self.cfg = cfg
        raise NotImplementedError(
            "Hailo backend not implemented yet. Use Cpu YOLO backend for dev or bgsub fallback."
        )

    def detect(self, frame: np.ndarray) -> List[Detection]:  # pragma: no cover
        return []


