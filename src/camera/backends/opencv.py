"""
OpenCV camera backend.

Supports:
- USB webcams (device_id as int, e.g. 0)
- RTSP/IP cameras (device_id as str URL, e.g. "rtsp://...")
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional, Tuple, Union

import cv2
import numpy as np


class OpenCVCamera:
    """
    OpenCV-based capture for both USB webcams and RTSP IP cameras.

    The rest of the project should treat this as an abstract camera with:
    - read() -> (ok, frame_bgr)
    - release()
    """

    def __init__(
        self,
        device_id: Union[int, str] = 0,
        resolution: Tuple[int, int] = (640, 480),
        fps: int = 30,
        buffer_size: int = 1,
        max_retries: int = 3,
        rtsp_transport: str = "tcp",
    ) -> None:
        self.device_id = device_id
        self.resolution = resolution
        self.fps = fps
        self.buffer_size = buffer_size
        self.max_retries = max_retries
        self.rtsp_transport = rtsp_transport

        self._cap: Optional[cv2.VideoCapture] = None
        self._consecutive_failures = 0

        self._initialize()
        logging.info(f"Camera initialized (backend=opencv, id={device_id}, res={resolution}, fps={fps})")

    def _initialize(self, retry_count: int = 0) -> None:
        if self._cap is not None:
            self.release()

        if retry_count > 0:
            wait_time = min(2 ** retry_count, 10)
            logging.info(
                f"Retrying camera initialization (attempt {retry_count + 1}/{self.max_retries}) after {wait_time}s"
            )
            time.sleep(wait_time)

        # RTSP transport selection (FFmpeg option)
        if isinstance(self.device_id, str) and (
            self.device_id.startswith("rtsp://") or self.device_id.startswith("rtsps://")
        ):
            logging.info(f"Setting RTSP transport to: {self.rtsp_transport}")
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{self.rtsp_transport}"

        self._cap = cv2.VideoCapture(self.device_id)

        if not self._cap.isOpened():
            if retry_count < self.max_retries - 1:
                logging.warning(f"Failed to open camera device {self.device_id}, retrying...")
                return self._initialize(retry_count + 1)
            logging.error(f"Failed to open camera device {self.device_id} after {self.max_retries} attempts")
            raise RuntimeError(f"Failed to open camera device {self.device_id} after {self.max_retries} attempts")

        # Only set properties for USB cameras (integers), not IP streams
        if isinstance(self.device_id, int):
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self._cap.set(cv2.CAP_PROP_FPS, self.fps)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)

            actual_width = self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
            logging.info(f"Camera actual settings - Resolution: ({actual_width}x{actual_height}), FPS: {actual_fps}")
        else:
            logging.info(f"IP Camera initialized: {self.device_id}")

        time.sleep(1.0)
        self._consecutive_failures = 0

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self._cap is None or not self._cap.isOpened():
            logging.warning("Camera not opened, attempting to reinitialize")
            try:
                self._initialize()
            except RuntimeError:
                return False, None

        assert self._cap is not None
        ret, frame = self._cap.read()

        if not ret:
            self._consecutive_failures += 1
            if self._consecutive_failures <= 3:
                logging.warning(
                    f"Failed to read frame (consecutive failures: {self._consecutive_failures}), reinitializing..."
                )
                try:
                    self._initialize()
                    assert self._cap is not None
                    ret, frame = self._cap.read()
                    if ret:
                        self._consecutive_failures = 0
                except RuntimeError:
                    logging.error("Camera reinitialization failed")
                    return False, None
            else:
                logging.error("Too many consecutive camera read failures")
                return False, None

        return ret, frame

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logging.info("Camera released")


