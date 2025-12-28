from __future__ import annotations

import time
from typing import Dict, List, Optional

import numpy as np

from analytics.counting import compute_counting_line
from analytics.counter import GateCounter, GateCounterConfig
from domain.models import CountEvent
from detection.tracker import TrackedVehicle
from runtime.context import RuntimeContext


class CountingService:
    """Orchestrates tracking and counting strategies."""

    def __init__(self, ctx: RuntimeContext, counting_cfg: Dict):
        self.ctx = ctx
        self.counting_cfg = counting_cfg or {}
        self.direction_labels = self.counting_cfg.get("direction_labels", {}) or {
            "a_to_b": "northbound",
            "b_to_a": "southbound",
        }
        self.gate_params = self.counting_cfg.get("gate", {}) or {}
        self.counter = None

    def ensure_counter(self, frame_w: int, frame_h: int, fallback_counting_config=None):
        if self.counter is not None:
            return
        line_a_cfg = self.counting_cfg.get("line_a") or fallback_counting_config
        line_b_cfg = self.counting_cfg.get("line_b") or fallback_counting_config
        line_a = compute_counting_line(line_a_cfg, frame_w, frame_h)
        line_b = compute_counting_line(line_b_cfg, frame_w, frame_h)
        self.counter = GateCounter(
            GateCounterConfig(
                line_a=line_a,
                line_b=line_b,
                direction_labels=self.direction_labels,
                max_gap_frames=int(self.gate_params.get("max_gap_frames", 30)),
                min_age_frames=int(self.gate_params.get("min_age_frames", 3)),
                min_displacement_px=float(self.gate_params.get("min_displacement_px", 15.0)),
            )
        )

    def process(self, detections: np.ndarray, frame: np.ndarray, frame_idx: int, counting_config_fallback=None) -> List[CountEvent]:
        # Track detections (tracker no longer counts)
        self.ctx.tracker.update(detections, counting_line=None)

        frame_h, frame_w = frame.shape[:2]
        self.ensure_counter(frame_w, frame_h, fallback_counting_config=counting_config_fallback)

        active_tracks: List[TrackedVehicle] = self.ctx.tracker.get_active_tracks()
        events = self.counter.process(active_tracks, frame_idx)

        # Update aggregates and persistence
        for event in events:
            self._accumulate_counts(event)
            self.ctx.db.add_vehicle_detection(
                timestamp=event.timestamp,
                direction=event.direction,
                direction_label=event.direction_label,
            )

        return events

    def _accumulate_counts(self, event: CountEvent):
        # You can extend this to track per-direction aggregates
        pass


class FrameIngestService:
    """Handles frame ingest, detection, tracking, counting, and ancillary updates."""

    def __init__(self, ctx: RuntimeContext, counting_service: CountingService, counting_config_fallback):
        self.ctx = ctx
        self.counting_service = counting_service
        self.counting_config_fallback = counting_config_fallback
        self.frame_idx = 0

    def handle_frame(self, frame: np.ndarray):
        self.frame_idx += 1
        # Detect
        detections = self.ctx.detector.detect(frame)

        # Update UI frame + stats
        fps = self.ctx.camera.get_fps() if hasattr(self.ctx.camera, 'get_fps') else self.ctx.config['camera']['fps']
        self.ctx.update_frame(frame, fps=fps)

        det_array = np.array([[d.x1, d.y1, d.x2, d.y2] for d in detections], dtype=float) if detections else np.array([])

        # Run counting
        events = self.counting_service.process(det_array, frame, self.frame_idx, counting_config_fallback=self.counting_config_fallback)

        # Recording
        if self.ctx.video_writer is not None:
            self.ctx.video_writer.write(frame)

        return events


