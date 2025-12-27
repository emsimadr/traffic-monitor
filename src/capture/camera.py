"""
Compatibility shim.

New code should import from `camera.camera`:
  from camera.camera import create_camera, inject_rtsp_credentials
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import os
import yaml

from camera.camera import create_camera, inject_rtsp_credentials


__all__ = ["create_camera", "inject_rtsp_credentials"]


