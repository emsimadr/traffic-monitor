"""
Pipeline engine for the traffic monitoring system.

This module provides a clean abstraction over the main processing loop,
using the observation layer for frame input while keeping detection,
tracking, storage, and web state updates unchanged.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np

from models.frame import FrameData
from observation.base import ObservationSource
from observation.opencv_source import OpenCVSource, OpenCVSourceConfig
from runtime.context import RuntimeContext
from runtime.services import CountingService, FrameIngestService


@dataclass
class PipelineConfig:
    """
    Configuration for the pipeline engine.
    
    Attributes:
        max_consecutive_failures: Max frame read failures before stopping.
        stats_log_interval: Seconds between status log messages.
        cleanup_interval: Seconds between database cleanup runs.
        retention_days: Days of data to retain in database.
        display: Enable cv2 display window.
        record: Enable video recording.
        output_dir: Directory for recorded videos.
    """
    max_consecutive_failures: int = 10
    stats_log_interval: float = 60.0
    cleanup_interval: float = 86400.0  # 24 hours
    retention_days: int = 30
    display: bool = False
    record: bool = False
    output_dir: str = "output/video"


@dataclass
class PipelineStats:
    """Runtime statistics for the pipeline."""
    frame_count: int = 0
    vehicle_count: int = 0
    count_by_direction: Dict[str, int] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    last_stats_log_time: float = field(default_factory=time.time)
    last_cleanup_time: float = field(default_factory=time.time)
    consecutive_failures: int = 0


class PipelineEngine:
    """
    Main processing engine using ObservationSource for frame input.
    
    This engine:
    - Reads frames from any ObservationSource
    - Runs detection, tracking, and counting (unchanged)
    - Updates storage (unchanged)
    - Updates web state (unchanged)
    
    Example:
        source = OpenCVSource(OpenCVSourceConfig(device_id=0))
        engine = PipelineEngine(source, ctx, counting_service, config)
        engine.run()
    """

    def __init__(
        self,
        source: ObservationSource,
        ctx: RuntimeContext,
        counting_service: CountingService,
        config: PipelineConfig,
    ):
        self.source = source
        self.ctx = ctx
        self.counting_service = counting_service
        self.config = config
        self.stats = PipelineStats()
        self._running = False
        self._video_writer: Optional[cv2.VideoWriter] = None
        self._output_path: Optional[str] = None
        self._callbacks: List[Callable[[FrameData, List], None]] = []

    def add_callback(self, callback: Callable[[FrameData, List], None]) -> None:
        """
        Add a callback to be called after each frame is processed.
        
        Args:
            callback: Function taking (frame_data, events) as arguments.
        """
        self._callbacks.append(callback)

    def run(self) -> None:
        """
        Run the main processing loop.
        
        Opens the observation source, processes frames until stopped or
        exhausted, then closes resources.
        """
        self._running = True
        self.stats = PipelineStats()
        
        # Setup video recording if enabled
        if self.config.record:
            self._setup_recording()

        try:
            self.source.open()
            logging.info(f"Pipeline started: source={self.source.source_id}")
            
            while self._running:
                frame_data = self.source.read()
                
                if frame_data is None:
                    self.stats.consecutive_failures += 1
                    if self.stats.consecutive_failures >= self.config.max_consecutive_failures:
                        logging.error(
                            f"Too many consecutive failures ({self.stats.consecutive_failures}), stopping"
                        )
                        break
                    logging.warning(
                        f"Frame read failed ({self.stats.consecutive_failures}/"
                        f"{self.config.max_consecutive_failures})"
                    )
                    time.sleep(0.5)
                    continue
                
                self.stats.consecutive_failures = 0
                events = self._process_frame(frame_data)
                
                # Call registered callbacks
                for callback in self._callbacks:
                    try:
                        callback(frame_data, events)
                    except Exception as e:
                        logging.warning(f"Callback error: {e}")
                
                # Handle display
                if self.config.display:
                    if not self._handle_display(frame_data):
                        break  # User pressed 'q'
                
                # Periodic tasks
                self._handle_periodic_tasks()
                
        except KeyboardInterrupt:
            logging.info("Pipeline interrupted by user")
        except Exception as e:
            logging.error(f"Pipeline error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._cleanup()

    def stop(self) -> None:
        """Signal the pipeline to stop after the current frame."""
        self._running = False

    def _process_frame(self, frame_data: FrameData) -> List:
        """
        Process a single frame through detection, tracking, and counting.
        
        Returns list of count events from this frame.
        """
        frame = frame_data.frame
        self.stats.frame_count += 1
        
        # Detect objects
        detections = self.ctx.detector.detect(frame)
        det_array = (
            np.array([[d.x1, d.y1, d.x2, d.y2] for d in detections], dtype=float)
            if detections
            else np.array([])
        )
        
        # Track and count
        events = self.counting_service.process(
            det_array, frame, self.stats.frame_count, counting_config_fallback=None
        )
        
        # Accumulate statistics
        for event in events:
            self.stats.vehicle_count += 1
            direction = event.direction
            self.stats.count_by_direction[direction] = (
                self.stats.count_by_direction.get(direction, 0) + 1
            )
            logging.info(
                f"Vehicle {event.track_id} counted: direction={direction}, "
                f"total={self.stats.vehicle_count}"
            )
        
        # Draw overlays
        annotated_frame = self._draw_overlays(frame.copy())
        
        # Update web state
        fps = self.ctx.config["camera"].get("fps", 30)
        self.ctx.update_frame(annotated_frame, fps=fps)
        
        # Write to video if recording
        if self._video_writer is not None:
            self._video_writer.write(annotated_frame)
        
        return events

    def _draw_overlays(self, frame: np.ndarray) -> np.ndarray:
        """Draw gate lines and tracked vehicles on the frame."""
        # Colors (BGR)
        COLOR_GATE_A = (255, 201, 0)  # Cyan
        COLOR_GATE_B = (71, 99, 255)  # Coral
        COLOR_ACTIVE = (0, 255, 0)  # Green
        COLOR_COUNTED = (255, 0, 0)  # Blue
        
        # Draw gate lines
        line_a, line_b = self.counting_service.get_gate_lines()
        
        if line_a and len(line_a) == 2:
            cv2.line(frame, line_a[0], line_a[1], COLOR_GATE_A, 3)
            cv2.putText(frame, "A", (line_a[0][0] + 5, line_a[0][1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_GATE_A, 2)
        
        if line_b and len(line_b) == 2:
            cv2.line(frame, line_b[0], line_b[1], COLOR_GATE_B, 3)
            cv2.putText(frame, "B", (line_b[0][0] + 5, line_b[0][1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_GATE_B, 2)
        
        # Draw tracked vehicles
        for track in self.ctx.tracker.get_all_tracks():
            x1, y1, x2, y2 = map(int, track.bbox)
            color = COLOR_COUNTED if track.has_been_counted else COLOR_ACTIVE
            label = f"#{track.vehicle_id}"
            if track.has_been_counted and track.direction:
                label += f" {track.direction[:1].upper()}"
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Label with background
            font = cv2.FONT_HERSHEY_SIMPLEX
            (tw, th), _ = cv2.getTextSize(label, font, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
            cv2.putText(frame, label, (x1 + 2, y1 - 4), font, 0.5, (255, 255, 255), 1)
            
            # Trajectory trail
            if len(track.trajectory) > 1:
                points = list(track.trajectory)[-10:]
                for i in range(1, len(points)):
                    pt1 = (int(points[i-1][0]), int(points[i-1][1]))
                    pt2 = (int(points[i][0]), int(points[i][1]))
                    alpha = i / len(points)
                    trail_color = tuple(int(c * alpha) for c in color)
                    cv2.line(frame, pt1, pt2, trail_color, 1)
        
        return frame

    def _handle_display(self, frame_data: FrameData) -> bool:
        """
        Handle cv2 display window.
        
        Returns False if user pressed 'q' to quit.
        """
        cv2.imshow("Traffic Monitor", frame_data.frame)
        key = cv2.waitKey(1) & 0xFF
        return key != ord('q')

    def _handle_periodic_tasks(self) -> None:
        """Run periodic tasks (logging, cleanup)."""
        now = time.time()
        
        # Log statistics periodically
        if now - self.stats.last_stats_log_time >= self.config.stats_log_interval:
            logging.info(
                f"Pipeline stats: frames={self.stats.frame_count}, "
                f"vehicles={self.stats.vehicle_count}, "
                f"by_direction={self.stats.count_by_direction}"
            )
            self.stats.last_stats_log_time = now
            
            # Update database aggregates
            if hasattr(self.ctx.db, "update_hourly_counts"):
                self.ctx.db.update_hourly_counts()
            if hasattr(self.ctx.db, "update_daily_counts"):
                self.ctx.db.update_daily_counts()
        
        # Database cleanup periodically
        if now - self.stats.last_cleanup_time >= self.config.cleanup_interval:
            if hasattr(self.ctx.db, "cleanup_old_data"):
                self.ctx.db.cleanup_old_data(retention_days=self.config.retention_days)
            self.stats.last_cleanup_time = now
            logging.info(f"Database cleanup completed (retention: {self.config.retention_days} days)")
            
            # Rotate video file if recording
            if self.config.record and self._video_writer is not None:
                self._rotate_video()

    def _setup_recording(self) -> None:
        """Initialize video recording."""
        import os
        if not os.path.exists(self.config.output_dir):
            os.makedirs(self.config.output_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._output_path = f"{self.config.output_dir}/traffic_{timestamp}.avi"
        
        resolution = self.ctx.config["camera"].get("resolution", [1280, 720])
        fps = self.ctx.config["camera"].get("fps", 30)
        
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self._video_writer = cv2.VideoWriter(
            self._output_path, fourcc, fps, tuple(resolution), True
        )
        logging.info(f"Video recording started: {self._output_path}")

    def _rotate_video(self) -> None:
        """Close current video and start a new one."""
        if self._video_writer is not None:
            self._video_writer.release()
            logging.info(f"Video saved: {self._output_path}")
            
            # Upload to cloud if available
            if self.ctx.cloud_sync and hasattr(self.ctx.cloud_sync, "upload_video_sample"):
                try:
                    metadata = {
                        "timestamp": str(datetime.now()),
                        "vehicle_count": str(self.stats.vehicle_count),
                    }
                    self.ctx.cloud_sync.upload_video_sample(self._output_path, metadata)
                except Exception as e:
                    logging.warning(f"Cloud upload failed: {e}")
            
            # Start new recording
            self._setup_recording()

    def _cleanup(self) -> None:
        """Clean up resources."""
        self._running = False
        
        # Close observation source
        try:
            self.source.close()
        except Exception as e:
            logging.warning(f"Error closing source: {e}")
        
        # Close video writer
        if self._video_writer is not None:
            self._video_writer.release()
            logging.info(f"Video saved: {self._output_path}")
        
        # Close display window
        if self.config.display:
            cv2.destroyAllWindows()
        
        logging.info("Pipeline stopped")


def create_engine_from_config(
    config: Dict[str, Any],
    ctx: RuntimeContext,
    counting_service: CountingService,
    display: bool = False,
    record: bool = False,
) -> PipelineEngine:
    """
    Factory function to create a PipelineEngine from existing config dict.
    
    This adapts the existing config structure to the new engine.
    
    Args:
        config: Full application config dict.
        ctx: RuntimeContext with db, detector, tracker, etc.
        counting_service: CountingService instance.
        display: Enable display window.
        record: Enable video recording.
    """
    # Create observation source from camera config
    camera_cfg = config.get("camera", {})
    source_config = OpenCVSourceConfig.from_camera_config(camera_cfg, source_id="main-camera")
    source = OpenCVSource(source_config)
    
    # Create pipeline config
    storage_cfg = config.get("storage", {})
    pipeline_config = PipelineConfig(
        retention_days=storage_cfg.get("retention_days", 30),
        display=display,
        record=record,
    )
    
    return PipelineEngine(source, ctx, counting_service, pipeline_config)

