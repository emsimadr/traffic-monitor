"""
Camera interfaces.

We support multiple capture backends:
- OpenCV VideoCapture (USB cameras, RTSP streams) [current]
- Picamera2/libcamera (CSI camera on Raspberry Pi) [planned]
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np


class Camera:
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        raise NotImplementedError

    def release(self) -> None:
        raise NotImplementedError


