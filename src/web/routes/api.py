from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import cv2
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..services.config_service import ConfigService
from ..services.stats_service import StatsService
from ..services.logs_service import LogsService
from ..services.health_service import HealthService
from ..services.camera_service import CameraService
from ..state import state

router = APIRouter()


@router.get("/health")
def health():
    cfg = ConfigService.load_effective_config()
    return HealthService(cfg=cfg).get_health_summary()


@router.get("/stats/summary")
def stats_summary():
    cfg = ConfigService.load_effective_config()
    db_path = cfg["storage"]["local_database_path"]
    return StatsService(db_path=db_path).get_summary()


class SaveConfigRequest(BaseModel):
    overrides: dict


@router.post("/config")
def save_config(req: SaveConfigRequest):
    try:
        ConfigService.save_overrides(req.overrides)
        # Keep the live pipeline in sync with newly saved config
        state.update_config(ConfigService.load_effective_config())
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/logs/tail")
def logs_tail(lines: int = 200):
    cfg = ConfigService.load_effective_config()
    log_path = cfg.get("log_path")
    return {"path": log_path, "lines": LogsService.tail(log_path, lines=lines)}


@router.get("/camera/snapshot.jpg")
def camera_snapshot():
    cfg = ConfigService.load_effective_config()
    cam_cfg = cfg["camera"]
    try:
        jpeg_bytes = CameraService.snapshot_jpeg(cam_cfg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        iter([jpeg_bytes]),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/camera/stream.mjpg")
def camera_stream(fps: int = 5):
    cfg = ConfigService.load_effective_config()
    cam_cfg = cfg["camera"]

    def gen():
        for chunk in CameraService.mjpeg_stream(cam_cfg=cam_cfg, fps=fps):
            yield chunk

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


class CalibrationCamera(BaseModel):
    swap_rb: Optional[bool] = None
    rotate: Optional[int] = None
    flip_horizontal: Optional[bool] = None
    flip_vertical: Optional[bool] = None


class CalibrationDetection(BaseModel):
    counting_line: Optional[List[List[float]]] = None


class CalibrationTracking(BaseModel):
    max_frames_since_seen: Optional[int] = None
    min_trajectory_length: Optional[int] = None
    iou_threshold: Optional[float] = None


class CalibrationRequest(BaseModel):
    camera: Optional[CalibrationCamera] = None
    detection: Optional[CalibrationDetection] = None
    tracking: Optional[CalibrationTracking] = None


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


@router.get("/calibration")
def get_calibration():
    cfg = ConfigService.load_effective_config()
    cam = cfg.get("camera", {}) or {}
    det = cfg.get("detection", {}) or {}
    track = cfg.get("tracking", {}) or {}
    return {
        "camera": {
            "swap_rb": bool(cam.get("swap_rb", False)),
            "rotate": int(cam.get("rotate", 0) or 0),
            "flip_horizontal": bool(cam.get("flip_horizontal", False)),
            "flip_vertical": bool(cam.get("flip_vertical", False)),
        },
        "detection": {"counting_line": det.get("counting_line")},
        "tracking": {
            "max_frames_since_seen": int(track.get("max_frames_since_seen", 10) or 10),
            "min_trajectory_length": int(track.get("min_trajectory_length", 3) or 3),
            "iou_threshold": float(track.get("iou_threshold", 0.3) or 0.3),
        },
    }


@router.post("/calibration")
def set_calibration(req: CalibrationRequest):
    updates: Dict[str, Any] = {"camera": {}, "detection": {}, "tracking": {}}

    # Camera transforms
    cam = req.camera or CalibrationCamera()
    if cam.swap_rb is not None:
        updates["camera"]["swap_rb"] = bool(cam.swap_rb)
    if cam.rotate is not None:
        r = int(cam.rotate or 0)
        if r not in (0, 90, 180, 270):
            raise HTTPException(status_code=400, detail="camera.rotate must be one of 0,90,180,270")
        updates["camera"]["rotate"] = r
    if cam.flip_horizontal is not None:
        updates["camera"]["flip_horizontal"] = bool(cam.flip_horizontal)
    if cam.flip_vertical is not None:
        updates["camera"]["flip_vertical"] = bool(cam.flip_vertical)

    # Counting line
    det = req.detection or CalibrationDetection()
    if det.counting_line is None and req.detection is not None:
        # Explicitly clear the line
        updates["detection"]["counting_line"] = None
    elif det.counting_line is not None:
        cl = det.counting_line
        if not (isinstance(cl, list) and len(cl) == 2):
            raise HTTPException(status_code=400, detail="detection.counting_line must be [[x1,y1],[x2,y2]]")
        for p in cl:
            if not (isinstance(p, list) and len(p) == 2):
                raise HTTPException(status_code=400, detail="counting_line points must be [x,y]")
            x, y = float(p[0]), float(p[1])
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise HTTPException(status_code=400, detail="counting_line ratios must be between 0 and 1")
        updates["detection"]["counting_line"] = cl

    # Tracking parameters
    trk = req.tracking or CalibrationTracking()
    if trk.max_frames_since_seen is not None:
        mfs = int(trk.max_frames_since_seen)
        if mfs <= 0:
            raise HTTPException(status_code=400, detail="tracking.max_frames_since_seen must be > 0")
        updates["tracking"]["max_frames_since_seen"] = mfs
    if trk.min_trajectory_length is not None:
        mtl = int(trk.min_trajectory_length)
        if mtl <= 0:
            raise HTTPException(status_code=400, detail="tracking.min_trajectory_length must be > 0")
        updates["tracking"]["min_trajectory_length"] = mtl
    if trk.iou_threshold is not None:
        iou = float(trk.iou_threshold)
        if not (0 < iou <= 1):
            raise HTTPException(status_code=400, detail="tracking.iou_threshold must be between 0 and 1")
        updates["tracking"]["iou_threshold"] = iou

    # Remove empty sections to avoid noisy overrides
    if not updates["camera"]:
        updates.pop("camera")
    if not updates.get("detection"):
        updates.pop("detection", None)
    if not updates.get("tracking"):
        updates.pop("tracking", None)

    try:
        overrides = ConfigService.load_overrides()
        merged = _deep_merge(overrides, updates)
        ConfigService.save_overrides(merged)
        state.update_config(ConfigService.load_effective_config())
        return {"ok": True}
    except Exception as e:
        logging.exception("Failed to save calibration")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/camera/live.mjpg")
def camera_live_stream(fps: int = 5):
    """
    Stream MJPEG frames from the shared state (populated by the detector loop).
    Applies calibration transforms so the preview matches runtime processing.
    """
    fps = max(1, min(30, int(fps)))
    delay = 1.0 / fps

    def gen():
        while True:
            frame = state.get_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            cfg = state.get_config_copy() or {}
            cam_cfg = (cfg.get("camera", {}) or {})
            rotate = int(cam_cfg.get("rotate", 0) or 0)
            flip_h = bool(cam_cfg.get("flip_horizontal", False))
            flip_v = bool(cam_cfg.get("flip_vertical", False))
            swap_rb = bool(cam_cfg.get("swap_rb", False))

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

            ok, buf = cv2.imencode(".jpg", frame)
            if not ok:
                time.sleep(delay)
                continue
            jpg = buf.tobytes()
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            time.sleep(delay)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/stats/live")
def live_stats():
    if state.database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        total = state.database.get_vehicle_count()
        last_hour = state.database.get_vehicle_count(start_time=time.time() - 3600)
        by_direction_24h = state.database.get_direction_counts(start_time=time.time() - 86400)
        by_direction_1h = state.database.get_direction_counts(start_time=time.time() - 3600)
        uptime = time.time() - state.system_stats.get("start_time", time.time())
        fps = state.system_stats.get("fps", 0)
        cloud_enabled = getattr(state.database, "cloud_enabled", False)
        return {
            "total_vehicles": total,
            "last_hour": last_hour,
            "fps": fps,
            "uptime_seconds": int(uptime),
            "cloud_enabled": cloud_enabled,
            "last_24h_by_direction": by_direction_24h,
            "last_hour_by_direction": by_direction_1h,
        }
    except Exception as e:
        logging.exception("Error computing live stats")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/range")
def stats_range(start_ts: Optional[float] = None, end_ts: Optional[float] = None, days: int = 30):
    """
    Return totals and direction counts for an arbitrary time range.
    Defaults to the last 30 days if no params are provided.
    """
    if state.database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    now = time.time()
    end_ts = end_ts or now
    if start_ts is None:
        start_ts = end_ts - max(1, days) * 86400

    if start_ts >= end_ts:
        raise HTTPException(status_code=400, detail="start_ts must be before end_ts")

    try:
        total = state.database.get_vehicle_count(start_time=start_ts, end_time=end_ts)
        by_direction = state.database.get_direction_counts(start_time=start_ts, end_time=end_ts)
        return {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "total": total,
            "by_direction": by_direction,
        }
    except Exception as e:
        logging.exception("Error computing range stats")
        raise HTTPException(status_code=500, detail=str(e))


