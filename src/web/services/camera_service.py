from __future__ import annotations

import time
from typing import Any, Dict, Iterable

import cv2

# Use absolute import so running `python src/main.py` or uvicorn both work.
from camera.camera import create_camera, inject_rtsp_credentials


class CameraService:
    @staticmethod
    def snapshot_jpeg(cam_cfg: Dict[str, Any]) -> bytes:
        # Ensure RTSP credentials are injected when needed
        cam_cfg = dict(cam_cfg)
        inject_rtsp_credentials(cam_cfg)

        camera = create_camera(cam_cfg)
        try:
            ok, frame = camera.read()
            if not ok or frame is None:
                raise RuntimeError("Failed to read frame from camera")

            ok2, buf = cv2.imencode(".jpg", frame)
            if not ok2:
                raise RuntimeError("Failed to encode JPEG")
            return buf.tobytes()
        finally:
            camera.release()

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
        camera = create_camera(cam_cfg)
        try:
            while True:
                ok, frame = camera.read()
                if not ok or frame is None:
                    time.sleep(delay)
                    continue
                ok2, buf = cv2.imencode(".jpg", frame)
                if not ok2:
                    time.sleep(delay)
                    continue
                jpg = buf.tobytes()
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                time.sleep(delay)
        finally:
            camera.release()


