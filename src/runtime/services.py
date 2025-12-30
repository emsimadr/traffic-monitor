from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

import cv2
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
        self._line_a: Optional[List[Tuple[int, int]]] = None
        self._line_b: Optional[List[Tuple[int, int]]] = None

    def ensure_counter(self, frame_w: int, frame_h: int, fallback_counting_config=None):
        if self.counter is not None:
            return
        line_a_cfg = self.counting_cfg.get("line_a") or fallback_counting_config
        line_b_cfg = self.counting_cfg.get("line_b") or fallback_counting_config
        self._line_a = compute_counting_line(line_a_cfg, frame_w, frame_h)
        self._line_b = compute_counting_line(line_b_cfg, frame_w, frame_h)
        self.counter = GateCounter(
            GateCounterConfig(
                line_a=self._line_a,
                line_b=self._line_b,
                direction_labels=self.direction_labels,
                max_gap_frames=int(self.gate_params.get("max_gap_frames", 30)),
                min_age_frames=int(self.gate_params.get("min_age_frames", 3)),
                min_displacement_px=float(self.gate_params.get("min_displacement_px", 15.0)),
            )
        )

    def get_gate_lines(self) -> Tuple[Optional[List[Tuple[int, int]]], Optional[List[Tuple[int, int]]]]:
        """Return the computed gate lines (A, B) in pixel coordinates."""
        return self._line_a, self._line_b

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
            self.ctx.db.add_count_event(event)

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
        det_array = np.array([[d.x1, d.y1, d.x2, d.y2] for d in detections], dtype=float) if detections else np.array([])

        # Run counting (this also updates the tracker)
        events = self.counting_service.process(det_array, frame, self.frame_idx, counting_config_fallback=self.counting_config_fallback)

        # Draw overlays on a copy for the web UI
        annotated_frame = self._draw_overlays(frame.copy())

        # Update UI frame + stats
        fps = self.ctx.camera.get_fps() if hasattr(self.ctx.camera, 'get_fps') else self.ctx.config['camera']['fps']
        self.ctx.update_frame(annotated_frame, fps=fps)

        # Recording (use annotated frame so recordings include overlays)
        if self.ctx.video_writer is not None:
            self.ctx.video_writer.write(annotated_frame)

        return events

    def _draw_overlays(self, frame: np.ndarray) -> np.ndarray:
        """Draw gate lines and tracked vehicle bounding boxes on the frame."""
        
        # Colors (BGR)
        COLOR_GATE_A = (255, 201, 0)      # Cyan
        COLOR_GATE_B = (71, 99, 255)       # Coral/Orange-red
        COLOR_ACTIVE = (0, 255, 0)         # Green - active tracks
        COLOR_COUNTED = (255, 0, 0)        # Blue - counted tracks
        COLOR_TEXT_BG = (0, 0, 0)          # Black background for text
        
        # Draw gate lines
        line_a, line_b = self.counting_service.get_gate_lines()
        
        if line_a and len(line_a) == 2:
            pt1, pt2 = line_a
            cv2.line(frame, pt1, pt2, COLOR_GATE_A, 3)
            cv2.putText(frame, "A", (pt1[0] + 5, pt1[1] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_GATE_A, 2)
        
        if line_b and len(line_b) == 2:
            pt1, pt2 = line_b
            cv2.line(frame, pt1, pt2, COLOR_GATE_B, 3)
            cv2.putText(frame, "B", (pt1[0] + 5, pt1[1] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_GATE_B, 2)
        
        # Draw tracked vehicles
        all_tracks = self.ctx.tracker.get_all_tracks()
        
        for track in all_tracks:
            x1, y1, x2, y2 = map(int, track.bbox)
            
            # Choose color based on whether counted
            if track.has_been_counted:
                color = COLOR_COUNTED
                label = f"#{track.vehicle_id}"
                if track.direction:
                    label += f" {track.direction[:1].upper()}"  # First letter of direction
            else:
                color = COLOR_ACTIVE
                label = f"#{track.vehicle_id}"
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label with background
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            
            # Label background
            cv2.rectangle(frame, (x1, y1 - text_h - 6), (x1 + text_w + 4, y1), color, -1)
            
            # Label text
            cv2.putText(frame, label, (x1 + 2, y1 - 4), font, font_scale, (255, 255, 255), thickness)
            
            # Draw trajectory trail (last few points)
            if len(track.trajectory) > 1:
                points = list(track.trajectory)[-10:]  # Last 10 points
                for i in range(1, len(points)):
                    pt1 = (int(points[i-1][0]), int(points[i-1][1]))
                    pt2 = (int(points[i][0]), int(points[i][1]))
                    # Fade color based on age
                    alpha = i / len(points)
                    trail_color = tuple(int(c * alpha) for c in color)
                    cv2.line(frame, pt1, pt2, trail_color, 1)
        
        return frame
