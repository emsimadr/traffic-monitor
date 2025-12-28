"""
Camera factory + credential helpers.

This is the single entrypoint the rest of the project should use to create a camera.
"""

from __future__ import annotations

from typing import Any, Dict

import os
import yaml

import cv2

from .base import Camera
from .backends.opencv import OpenCVCamera
from .backends.picamera2 import Picamera2Camera, Picamera2Config


def inject_rtsp_credentials(camera_cfg: Dict[str, Any]) -> None:
    """
    If the camera device_id is RTSP and a secrets file is provided, inject
    username/password into the RTSP URL in-place.
    """

    device_id = camera_cfg.get("device_id")
    secrets_file = camera_cfg.get("secrets_file")
    if not (isinstance(device_id, str) and device_id.startswith("rtsp://") and secrets_file):
        return

    if not os.path.exists(secrets_file):
        return

    with open(secrets_file, "r") as f:
        secrets = yaml.safe_load(f) or {}

    username = secrets.get("username")
    password = secrets.get("password")
    if not (username and password):
        return

    protocol, rest = device_id.split("://", 1)
    camera_cfg["device_id"] = f"{protocol}://{username}:{password}@{rest}"


def create_camera(camera_cfg: Dict[str, Any]) -> Camera:
    backend = camera_cfg.get("backend", "opencv")
    resolution = tuple(camera_cfg.get("resolution", [1280, 720]))
    fps = int(camera_cfg.get("fps", 30))
    swap_rb = bool(camera_cfg.get("swap_rb", False))
    rotate = int(camera_cfg.get("rotate", 0) or 0)
    flip_h = bool(camera_cfg.get("flip_horizontal", False))
    flip_v = bool(camera_cfg.get("flip_vertical", False))

    if backend == "picamera2":
        base_cam: Camera = Picamera2Camera(Picamera2Config(resolution=resolution, fps=fps))
    else:
        # Default: OpenCV (USB/RTSP)
        base_cam = OpenCVCamera(
            device_id=camera_cfg.get("device_id", 0),
            resolution=resolution,
            fps=fps,
            rtsp_transport=camera_cfg.get("rtsp_transport", "tcp"),
            swap_rb=False,  # apply swap in wrapper for all backends consistently
        )

    needs_post = swap_rb or rotate in (90, 180, 270) or flip_h or flip_v
    if not needs_post:
        return base_cam

    class _PostProcessCamera(Camera):
        def __init__(self, inner: Camera):
            self._inner = inner

        def read(self):
            ok, frame = self._inner.read()
            if ok and frame is not None:
                if rotate in (90, 180, 270):
                    if rotate == 90:
                        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                    elif rotate == 180:
                        frame = cv2.rotate(frame, cv2.ROTATE_180)
                    elif rotate == 270:
                        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

                if flip_h or flip_v:
                    flip_code = -1 if (flip_h and flip_v) else (1 if flip_h else 0)
                    frame = cv2.flip(frame, flip_code)

                if swap_rb:
                    frame = frame[..., ::-1].copy()
            return ok, frame

        def release(self) -> None:
            return self._inner.release()

    return _PostProcessCamera(base_cam)


