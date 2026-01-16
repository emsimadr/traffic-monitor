"""
Picamera2-based observation source.

Supports Raspberry Pi CSI cameras via libcamera/Picamera2.

Requirements:
  - Raspberry Pi with camera module
  - Picamera2 installed: sudo apt install -y python3-picamera2
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from models.frame import FrameData
from .base import ObservationSource, ObservationConfig


@dataclass
class Picamera2SourceConfig(ObservationConfig):
    """
    Configuration for Picamera2-based observation sources.
    
    Attributes:
        swap_rb: Swap R/B channels (default False - Picamera2 outputs RGB, we convert to BGR).
        rotate: Rotation in degrees (0, 90, 180, 270).
        flip_horizontal: Flip frame horizontally.
        flip_vertical: Flip frame vertically.
    """
    swap_rb: bool = False
    rotate: int = 0
    flip_horizontal: bool = False
    flip_vertical: bool = False

    @classmethod
    def from_camera_config(cls, camera_cfg: Dict[str, Any], source_id: str = "picamera2") -> "Picamera2SourceConfig":
        """
        Adapter: Create Picamera2SourceConfig from existing camera config dict.
        
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
            swap_rb=camera_cfg.get("swap_rb", False),
            rotate=camera_cfg.get("rotate", 0) or 0,
            flip_horizontal=camera_cfg.get("flip_horizontal", False),
            flip_vertical=camera_cfg.get("flip_vertical", False),
        )


class Picamera2Source(ObservationSource):
    """
    Picamera2-based observation source for Raspberry Pi CSI cameras.
    
    Uses libcamera backend for modern Raspberry Pi camera support.
    
    Example:
        config = Picamera2SourceConfig(resolution=(1280, 720), fps=30)
        with Picamera2Source(config) as source:
            for frame_data in source:
                process(frame_data.frame)
    """

    def __init__(self, config: Picamera2SourceConfig):
        super().__init__(config)
        self._picam_config = config
        self._picam2: Any = None
        self._start_time: Optional[float] = None

    def open(self) -> None:
        """Open the Picamera2 source."""
        if self._is_open:
            return
        
        try:
            from picamera2 import Picamera2  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Picamera2 is not available. This backend only works on Raspberry Pi OS. "
                "Install with `sudo apt install -y python3-picamera2` or use backend 'opencv'."
            ) from e

        self._picam2 = Picamera2()
        
        # Configure the camera
        resolution = self._picam_config.resolution or (1280, 720)
        fps = self._picam_config.fps or 30
        
        video_config = self._picam2.create_video_configuration(
            main={"size": resolution, "format": "RGB888"},
            controls={"FrameRate": fps},
        )
        self._picam2.configure(video_config)
        self._picam2.start()
        
        self._is_open = True
        self._frame_index = 0
        self._start_time = time.time()
        
        logging.info(
            f"Picamera2Source opened: source_id={self.source_id}, "
            f"resolution={resolution}, fps={fps}"
        )

    def read(self) -> Optional[FrameData]:
        """Read the next frame from Picamera2."""
        if not self._is_open or self._picam2 is None:
            return None

        try:
            # Capture frame (RGB888 format)
            frame_rgb = self._picam2.capture_array("main")
            
            # Convert RGB to BGR (for OpenCV compatibility)
            frame_bgr = frame_rgb[..., ::-1].copy()
            
            # Apply post-processing transforms
            frame = self._apply_transforms(frame_bgr)
            
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
        except Exception as e:
            logging.error(f"Error capturing frame from Picamera2: {e}")
            return None

    def _apply_transforms(self, frame: np.ndarray) -> np.ndarray:
        """Apply configured image transforms (rotate, flip, swap_rb)."""
        try:
            import cv2
        except ImportError:
            logging.warning("cv2 not available for transforms")
            return frame
            
        cfg = self._picam_config

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

        # Color channel swap (swap back to RGB if needed)
        if cfg.swap_rb:
            frame = frame[..., ::-1].copy()

        return frame

    def close(self) -> None:
        """Close Picamera2 and release resources."""
        if self._picam2 is not None:
            try:
                self._picam2.stop()
            except Exception:
                pass
            try:
                self._picam2.close()
            except Exception:
                pass
            self._picam2 = None
        self._is_open = False
        logging.info(f"Picamera2Source closed: source_id={self.source_id}")

    def get_video_info(self) -> Dict[str, Any]:
        """Get information about the camera."""
        if self._picam2 is None:
            return {}
        
        resolution = self._picam_config.resolution or (1280, 720)
        fps = self._picam_config.fps or 30
        
        return {
            "width": resolution[0],
            "height": resolution[1],
            "fps": fps,
            "backend": "picamera2",
        }

