from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable

import cv2

from observation import create_source_from_config
from observation.rtsp_utils import inject_rtsp_credentials


class CameraService:
    @staticmethod
    def snapshot_jpeg(cam_cfg: Dict[str, Any]) -> bytes:
        # Ensure RTSP credentials are injected when needed
        cam_cfg = dict(cam_cfg)
        inject_rtsp_credentials(cam_cfg)

        source = create_source_from_config(cam_cfg)
        try:
            source.open()
            frame_data = source.read()
            if frame_data is None:
                raise RuntimeError("Failed to read frame from camera")

            ok, buf = cv2.imencode(".jpg", frame_data.frame)
            if not ok:
                raise RuntimeError("Failed to encode JPEG")
            return buf.tobytes()
        finally:
            source.close()

    @staticmethod
    def mjpeg_stream(cam_cfg: Dict[str, Any], fps: int = 5) -> Iterable[bytes]:
        """
        Yield MJPEG multipart chunks.

        Note: This opens the camera for the duration of the stream. In a future
        version we should coordinate access with the detection pipeline.
        """

        fps = max(1, min(30, int(fps)))
        delay = 1.0 / fps

        cam_cfg = dict(cam_cfg)
        inject_rtsp_credentials(cam_cfg)
        source = create_source_from_config(cam_cfg)
        try:
            source.open()
            while True:
                frame_data = source.read()
                if frame_data is None:
                    time.sleep(delay)
                    continue
                ok, buf = cv2.imencode(".jpg", frame_data.frame)
                if not ok:
                    time.sleep(delay)
                    continue
                jpg = buf.tobytes()
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                time.sleep(delay)
        finally:
            source.close()


