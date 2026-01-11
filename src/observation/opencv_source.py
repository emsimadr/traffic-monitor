"""
OpenCV-based observation source.

Supports:
- USB webcams (device_id as int, e.g., 0)
- RTSP/IP cameras (device_id as str URL)
- Video files (device_id as file path)

This wraps the existing OpenCV capture functionality without modifying
the src/camera modules.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union

import cv2
import numpy as np

from models.frame import FrameData
from .base import ObservationSource, ObservationConfig
from .rtsp_utils import sanitize_url


@dataclass
class OpenCVSourceConfig(ObservationConfig):
    """
    Configuration for OpenCV-based observation sources.
    
    Attributes:
        device_id: Camera index (int), RTSP URL (str), or file path (str).
        rtsp_transport: Transport protocol for RTSP ("tcp" or "udp").
        buffer_size: OpenCV capture buffer size (reduces latency for live feeds).
        max_retries: Maximum retries for camera initialization.
        swap_rb: Swap R/B channels (fixes RGB vs BGR issues).
        rotate: Rotation in degrees (0, 90, 180, 270).
        flip_horizontal: Flip frame horizontally.
        flip_vertical: Flip frame vertically.
    """
    device_id: Union[int, str] = 0
    rtsp_transport: str = "tcp"
    buffer_size: int = 1
    max_retries: int = 3
    swap_rb: bool = False
    rotate: int = 0
    flip_horizontal: bool = False
    flip_vertical: bool = False

    @classmethod
    def from_camera_config(cls, camera_cfg: Dict[str, Any], source_id: str = "camera") -> "OpenCVSourceConfig":
        """
        Adapter: Create OpenCVSourceConfig from existing camera config dict.
        
        Args:
            camera_cfg: Camera configuration dict (from config.yaml).
            source_id: Identifier for this source.
        """
        resolution = camera_cfg.get("resolution")
        if resolution:
            resolution = tuple(resolution)
        
        return cls(
            source_id=source_id,
            resolution=resolution,
            fps=camera_cfg.get("fps"),
            device_id=camera_cfg.get("device_id", 0),
            rtsp_transport=camera_cfg.get("rtsp_transport", "tcp"),
            buffer_size=camera_cfg.get("buffer_size", 1),
            max_retries=camera_cfg.get("max_retries", 3),
            swap_rb=camera_cfg.get("swap_rb", False),
            rotate=camera_cfg.get("rotate", 0) or 0,
            flip_horizontal=camera_cfg.get("flip_horizontal", False),
            flip_vertical=camera_cfg.get("flip_vertical", False),
        )


class OpenCVSource(ObservationSource):
    """
    OpenCV-based observation source for cameras and video files.
    
    Wraps cv2.VideoCapture to provide frames as FrameData objects.
    Handles automatic reconnection for camera streams.
    
    Example:
        config = OpenCVSourceConfig(device_id=0, resolution=(1280, 720))
        with OpenCVSource(config) as source:
            for frame_data in source:
                process(frame_data.frame)
    """

    def __init__(self, config: OpenCVSourceConfig):
        super().__init__(config)
        self._opencv_config = config
        self._cap: Optional[cv2.VideoCapture] = None
        self._consecutive_failures = 0
        self._start_time: Optional[float] = None

    @property
    def device_id(self) -> Union[int, str]:
        return self._opencv_config.device_id

    @property
    def is_rtsp(self) -> bool:
        """Check if this is an RTSP stream."""
        return isinstance(self.device_id, str) and (
            self.device_id.startswith("rtsp://") or 
            self.device_id.startswith("rtsps://")
        )

    @property
    def is_file(self) -> bool:
        """Check if this is a video file."""
        return (
            isinstance(self.device_id, str) and 
            not self.is_rtsp and 
            os.path.exists(self.device_id)
        )

    def open(self) -> None:
        """Open the video source."""
        if self._is_open:
            return
        
        self._initialize(retry_count=0)
        self._is_open = True
        self._frame_index = 0
        self._start_time = time.time()
        
        logging.info(
            f"OpenCVSource opened: source_id={self.source_id}, "
            f"device={sanitize_url(self.device_id)}, resolution={self._opencv_config.resolution}"
        )

    def _initialize(self, retry_count: int = 0) -> None:
        """Initialize or reinitialize the capture device."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

        if retry_count > 0:
            wait_time = min(2 ** retry_count, 10)
            logging.info(
                f"Retrying initialization (attempt {retry_count + 1}/"
                f"{self._opencv_config.max_retries}) after {wait_time}s"
            )
            time.sleep(wait_time)

        # Set RTSP transport for FFmpeg
        if self.is_rtsp:
            logging.info(f"Setting RTSP transport to: {self._opencv_config.rtsp_transport}")
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                f"rtsp_transport;{self._opencv_config.rtsp_transport}"
            )

        self._cap = cv2.VideoCapture(self.device_id)

        if not self._cap.isOpened():
            if retry_count < self._opencv_config.max_retries - 1:
                logging.warning(f"Failed to open device {sanitize_url(self.device_id)}, retrying...")
                return self._initialize(retry_count + 1)
            raise RuntimeError(
                f"Failed to open device {sanitize_url(self.device_id)} after "
                f"{self._opencv_config.max_retries} attempts"
            )

        # Set properties for USB cameras (not streams/files)
        if isinstance(self.device_id, int) and self._opencv_config.resolution:
            w, h = self._opencv_config.resolution
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            if self._opencv_config.fps:
                self._cap.set(cv2.CAP_PROP_FPS, self._opencv_config.fps)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, self._opencv_config.buffer_size)

            actual_w = self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_h = self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
            logging.info(
                f"Camera actual settings - Resolution: ({actual_w}x{actual_h}), FPS: {actual_fps}"
            )
        
        # Brief warmup for cameras
        if not self.is_file:
            time.sleep(0.5)
        
        self._consecutive_failures = 0

    def read(self) -> Optional[FrameData]:
        """Read the next frame from the source."""
        if not self._is_open or self._cap is None:
            return None

        if not self._cap.isOpened():
            logging.warning("Capture not opened, attempting to reinitialize")
            try:
                self._initialize()
            except RuntimeError:
                return None

        ret, frame = self._cap.read()

        if not ret or frame is None:
            self._consecutive_failures += 1
            
            # For files, end of video is expected
            if self.is_file:
                logging.info("End of video file reached")
                return None
            
            # For cameras, try to reconnect
            if self._consecutive_failures <= 3:
                logging.warning(
                    f"Failed to read frame (failures: {self._consecutive_failures}), reinitializing..."
                )
                try:
                    self._initialize()
                    ret, frame = self._cap.read()
                    if not ret or frame is None:
                        return None
                    self._consecutive_failures = 0
                except RuntimeError:
                    logging.error("Reinitialization failed")
                    return None
            else:
                logging.error("Too many consecutive read failures")
                return None

        # Apply post-processing transforms
        frame = self._apply_transforms(frame)

        # Create FrameData
        timestamp = time.time()
        self._frame_index += 1

        return FrameData(
            frame=frame,
            width=frame.shape[1],
            height=frame.shape[0],
            timestamp=timestamp,
            frame_index=self._frame_index,
            source=self.source_id,
        )

    def _apply_transforms(self, frame: np.ndarray) -> np.ndarray:
        """Apply configured image transforms (rotate, flip, swap_rb)."""
        cfg = self._opencv_config

        # Rotation
        if cfg.rotate == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif cfg.rotate == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif cfg.rotate == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Flip
        if cfg.flip_horizontal or cfg.flip_vertical:
            if cfg.flip_horizontal and cfg.flip_vertical:
                flip_code = -1
            elif cfg.flip_horizontal:
                flip_code = 1
            else:
                flip_code = 0
            frame = cv2.flip(frame, flip_code)

        # Color channel swap (RGB <-> BGR)
        if cfg.swap_rb:
            frame = frame[..., ::-1].copy()

        return frame

    def close(self) -> None:
        """Close the video source and release resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._is_open = False
        logging.info(f"OpenCVSource closed: source_id={self.source_id}")

    def get_video_info(self) -> Dict[str, Any]:
        """Get information about the video source (for files)."""
        if self._cap is None or not self._cap.isOpened():
            return {}
        
        return {
            "width": int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": self._cap.get(cv2.CAP_PROP_FPS),
            "frame_count": int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT)) if self.is_file else None,
            "fourcc": int(self._cap.get(cv2.CAP_PROP_FOURCC)),
        }

