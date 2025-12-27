"""
Capture interfaces (camera sources).

We support multiple camera *types* via different backends:
- OpenCV backend: USB webcams + RTSP IP cameras (anything cv2.VideoCapture can open)
- Picamera2 backend: Raspberry Pi CSI camera (libcamera)
"""

from __future__ import annotations

from typing import Optional, Protocol, Tuple

import numpy as np


class Camera(Protocol):
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        ...

    def release(self) -> None:
        ...


