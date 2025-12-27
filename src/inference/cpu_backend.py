"""
CPU inference backend (development path).

Uses Ultralytics if installed. This keeps the project runnable on non-Pi dev
machines while we build out the Hailo backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

from .backend import Detection, InferenceBackend


@dataclass(frozen=True)
class CpuYoloConfig:
    model: str
    conf_threshold: float = 0.25
    iou_threshold: float = 0.45
    classes: Optional[Sequence[int]] = None
    class_name_overrides: Optional[Dict[int, str]] = None


class UltralyticsCpuBackend(InferenceBackend):
    def __init__(self, cfg: CpuYoloConfig):
        self.cfg = cfg
        try:
            from ultralytics import YOLO  # type: ignore
        except Exception as e:  # pragma: no cover
            raise ImportError(
                "Ultralytics is not installed. Install with `pip install ultralytics` "
                "or switch detection.backend to 'bgsub'."
            ) from e

        self._model = YOLO(cfg.model)

    def detect(self, frame: np.ndarray) -> List[Detection]:
        results = self._model.predict(
            source=frame,
            conf=self.cfg.conf_threshold,
            iou=self.cfg.iou_threshold,
            classes=list(self.cfg.classes) if self.cfg.classes is not None else None,
            verbose=False,
        )
        if not results:
            return []

        r0 = results[0]
        names = getattr(r0, "names", None) or {}
        boxes = getattr(r0, "boxes", None)
        if boxes is None:
            return []

        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else np.asarray(boxes.xyxy)
        conf = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else np.asarray(boxes.conf)
        cls = boxes.cls.cpu().numpy() if hasattr(boxes.cls, "cpu") else np.asarray(boxes.cls)

        out: List[Detection] = []
        for (x1, y1, x2, y2), c, k in zip(xyxy, conf, cls):
            class_id = int(k) if k is not None else None
            class_name = None
            if class_id is not None:
                class_name = (
                    (self.cfg.class_name_overrides or {}).get(class_id)
                    or names.get(class_id)
                    or str(class_id)
                )
            out.append(
                Detection(
                    x1=float(x1),
                    y1=float(y1),
                    x2=float(x2),
                    y2=float(y2),
                    confidence=float(c),
                    class_id=class_id,
                    class_name=class_name,
                )
            )

        return out


