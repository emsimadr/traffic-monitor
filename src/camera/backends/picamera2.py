"""
Picamera2 camera backend (Raspberry Pi CSI camera via libcamera).

Only works on Raspberry Pi OS with Picamera2 installed:
  sudo apt install -y python3-picamera2
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class Picamera2Config:
    resolution: Tuple[int, int] = (1280, 720)
    fps: int = 30


class Picamera2Camera:
    def __init__(self, cfg: Picamera2Config):
        self.cfg = cfg

        try:
            from picamera2 import Picamera2  # type: ignore
        except Exception as e:  # pragma: no cover
            raise ImportError(
                "Picamera2 is not available. This backend only works on Raspberry Pi OS. "
                "Install with `sudo apt install -y python3-picamera2` or use backend 'opencv'."
            ) from e

        self._picam2 = Picamera2()
        config = self._picam2.create_video_configuration(
            main={"size": self.cfg.resolution, "format": "RGB888"},
            controls={"FrameRate": self.cfg.fps},
        )
        self._picam2.configure(config)
        self._picam2.start()

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        try:
            frame_rgb = self._picam2.capture_array("main")
            # main.py and OpenCV drawing code expect BGR
            frame_bgr = frame_rgb[..., ::-1].copy()
            return True, frame_bgr
        except Exception:  # pragma: no cover
            return False, None

    def release(self) -> None:
        try:
            self._picam2.stop()
        finally:
            try:
                self._picam2.close()
            except Exception:
                pass


