"""
Legacy camera package.

Canonical imports:
- `from camera.camera import create_camera, inject_rtsp_credentials`
- `from camera.backends.opencv import OpenCVCamera` (USB + RTSP)
- `from camera.backends.picamera2 import Picamera2Camera` (CSI)

`src/capture/` remains only as a temporary compatibility shim.
"""


