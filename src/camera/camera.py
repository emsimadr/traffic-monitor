"""
Camera factory + credential helpers.

This is the single entrypoint the rest of the project should use to create a camera.
"""

from __future__ import annotations

from typing import Any, Dict

import os
import yaml

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

    if backend == "picamera2":
        return Picamera2Camera(Picamera2Config(resolution=resolution, fps=fps))

    # Default: OpenCV (USB/RTSP)
    return OpenCVCamera(
        device_id=camera_cfg.get("device_id", 0),
        resolution=resolution,
        fps=fps,
        rtsp_transport=camera_cfg.get("rtsp_transport", "tcp"),
    )


