from __future__ import annotations

import logging
import os
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
from ..api_models import StatsSummary, LiveStatsResponse, RangeStatsResponse, StatusResponse, CompactStatusResponse

router = APIRouter()
router_v1 = APIRouter(prefix="/api/v1")


def _derive_status(last_frame_age: Optional[float], disk_pct_free: Optional[float], temp_c: Optional[float]):
    """
    Lightweight status classifier used by /api/status.
    Thresholds: >10s last frame => offline; >2s => degraded; disk free <10% warn; temp >80C warn.
    """
    level = "running"
    alerts: List[str] = []
    if last_frame_age is None or last_frame_age > 10:
        level = "offline"
        alerts.append("camera_offline")
    elif last_frame_age > 2:
        level = "degraded"
        alerts.append("camera_stale")

    if disk_pct_free is not None and disk_pct_free < 10:
        alerts.append("disk_low")
        if level == "running":
            level = "degraded"

    if temp_c is not None and temp_c > 80:
        alerts.append("temp_high")
        if level == "running":
            level = "degraded"

    return level, alerts


@router.get("/health")
@router_v1.get("/healthz", response_model=dict)
def health():
    cfg = ConfigService.load_effective_config()
    return HealthService(cfg=cfg).get_health_summary()


@router.get("/stats/summary")
@router_v1.get("/stats/summary", response_model=StatsSummary)
def stats_summary():
    cfg = ConfigService.load_effective_config()
    db_path = cfg["storage"]["local_database_path"]
    direction_labels = (cfg.get("counting", {}) or {}).get("direction_labels")
    return StatsService(db_path=db_path, direction_labels=direction_labels).get_summary()


@router.get("/status")
@router_v1.get("/ready", response_model=StatusResponse)
def status():
    """
    Aggregate system status for the UI: combines health, stats, and camera freshness.
    Fields:
    - status: running|degraded|offline
    - alerts: list of strings (camera_offline, camera_stale, disk_low, temp_high)
    - last_frame_age: seconds since last frame was seen (None if never)
    - fps: recent fps from system stats
    - uptime_seconds: uptime derived from web_state.start_time
    - disk: {total_bytes, used_bytes, free_bytes, pct_free}
    - temp_c: best-effort CPU temperature (None if unavailable)
    - NOTE: If Hailo-8 inference is enabled in the future, extend this with inference latency and accelerator health stats.
    - stats: StatsService summary (totals, last_hour, last_24h, by_direction)
    - health: base HealthService summary (platform, python, paths, etc.)
    """
    now = time.time()
    cfg = ConfigService.load_effective_config()
    db_path = cfg["storage"]["local_database_path"]

    stats = StatsService(db_path=db_path).get_summary()
    health = HealthService(cfg=cfg).get_health_summary()

    sys_stats = state.get_system_stats_copy() if hasattr(state, "get_system_stats_copy") else getattr(state, "system_stats", {}) or {}
    start_time = sys_stats.get("start_time") or None
    uptime = now - start_time if start_time else None
    last_frame_ts = sys_stats.get("last_frame_ts")
    last_frame_age = now - last_frame_ts if last_frame_ts else None
    fps = sys_stats.get("fps", 0)

    disk = HealthService.disk_usage(os.path.dirname(db_path) or ".")
    temp_c = HealthService.read_cpu_temp_c()

    level, alerts = _derive_status(last_frame_age, disk.get("pct_free"), temp_c)

    return {
        "status": level,
        "alerts": alerts,
        "last_frame_age": last_frame_age,
        "fps": fps,
        "uptime_seconds": int(uptime) if uptime is not None else None,
        "disk": disk,
        "temp_c": temp_c,
        "stats": stats,
        "health": health,
        "timestamp": now,
    }


def _compute_warnings(
    last_frame_age_s: Optional[float],
    disk_free_pct: Optional[float],
    cpu_temp_c: Optional[float],
) -> list[str]:
    """
    Compute warning flags for compact status endpoint.
    
    Thresholds:
    - camera_stale: last_frame_age_s > 2
    - camera_offline: last_frame_age_s > 10
    - disk_low: disk_free_pct < 10
    - temp_high: cpu_temp_c > 80
    """
    warnings = []
    
    if last_frame_age_s is not None:
        if last_frame_age_s > 10:
            warnings.append("camera_offline")
        elif last_frame_age_s > 2:
            warnings.append("camera_stale")
    else:
        # No frame timestamp means camera never started
        warnings.append("camera_offline")
    
    if disk_free_pct is not None and disk_free_pct < 10:
        warnings.append("disk_low")
    
    if cpu_temp_c is not None and cpu_temp_c > 80:
        warnings.append("temp_high")
    
    return warnings


def _get_today_start_timestamp() -> float:
    """Get Unix timestamp for start of today (local time)."""
    from datetime import datetime
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start.timestamp()


@router.get("/api/status", response_model=CompactStatusResponse)
@router_v1.get("/status", response_model=CompactStatusResponse)
def compact_status():
    """
    Compact status endpoint optimized for frontend polling (every 2s).
    
    Returns only essential fields needed for dashboard display:
    - running: system operational status
    - last_frame_age_s: seconds since last frame
    - fps_capture: camera capture rate
    - counts_today_total: total counts since midnight
    - counts_by_direction_code: breakdown by A_TO_B/B_TO_A
    - direction_labels: mapping from config
    - cpu_temp_c: CPU temperature
    - disk_free_pct: free disk percentage
    - warnings: list of active warning codes
    """
    now = time.time()
    
    # Get system stats
    sys_stats = state.get_system_stats_copy() if hasattr(state, "get_system_stats_copy") else getattr(state, "system_stats", {}) or {}
    last_frame_ts = sys_stats.get("last_frame_ts")
    last_frame_age_s = (now - last_frame_ts) if last_frame_ts else None
    fps_capture = sys_stats.get("fps")
    
    # Get counts from database (new count_events table)
    counts_today_total = 0
    counts_by_direction_code: Dict[str, int] = {}
    
    if state.database is not None:
        today_start = _get_today_start_timestamp()
        try:
            counts_today_total = state.database.get_count_total(start_time=today_start)
            counts_by_direction_code = state.database.get_counts_by_direction_code(start_time=today_start)
        except Exception as e:
            logging.warning(f"Error getting counts: {e}")
    
    # Get direction labels from config
    cfg = state.get_config_copy() or {}
    counting_cfg = cfg.get("counting", {}) or {}
    direction_labels_cfg = counting_cfg.get("direction_labels", {}) or {}
    
    # Build direction_labels mapping (A_TO_B -> label, B_TO_A -> label)
    direction_labels = {
        "A_TO_B": direction_labels_cfg.get("a_to_b", "northbound"),
        "B_TO_A": direction_labels_cfg.get("b_to_a", "southbound"),
    }
    
    # Get health metrics
    disk = HealthService.disk_usage(".")
    disk_free_pct = disk.get("pct_free")
    cpu_temp_c = HealthService.read_cpu_temp_c()
    
    # Compute warnings
    warnings = _compute_warnings(last_frame_age_s, disk_free_pct, cpu_temp_c)
    
    # Determine running status (no camera_offline warning = running)
    running = "camera_offline" not in warnings
    
    # Inference metrics (placeholder for future Hailo/YOLO integration)
    fps_infer = None
    infer_latency_ms_p50 = None
    infer_latency_ms_p95 = None
    
    return CompactStatusResponse(
        running=running,
        last_frame_age_s=last_frame_age_s,
        fps_capture=fps_capture,
        fps_infer=fps_infer,
        infer_latency_ms_p50=infer_latency_ms_p50,
        infer_latency_ms_p95=infer_latency_ms_p95,
        counts_today_total=counts_today_total,
        counts_by_direction_code=counts_by_direction_code,
        direction_labels=direction_labels,
        cpu_temp_c=cpu_temp_c,
        disk_free_pct=disk_free_pct,
        warnings=warnings,
    )


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


class CalibrationTracking(BaseModel):
    max_frames_since_seen: Optional[int] = None
    min_trajectory_length: Optional[int] = None
    iou_threshold: Optional[float] = None


class CalibrationGateParams(BaseModel):
    max_gap_frames: Optional[int] = None
    min_age_frames: Optional[int] = None
    min_displacement_px: Optional[float] = None


class CalibrationCounting(BaseModel):
    line_a: Optional[List[List[float]]] = None
    line_b: Optional[List[List[float]]] = None
    direction_labels: Optional[Dict[str, str]] = None
    gate: Optional[CalibrationGateParams] = None


class CalibrationRequest(BaseModel):
    camera: Optional[CalibrationCamera] = None
    tracking: Optional[CalibrationTracking] = None
    counting: Optional[CalibrationCounting] = None


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
    counting = cfg.get("counting", {}) or {}
    return {
        "camera": {
            "swap_rb": bool(cam.get("swap_rb", False)),
            "rotate": int(cam.get("rotate", 0) or 0),
            "flip_horizontal": bool(cam.get("flip_horizontal", False)),
            "flip_vertical": bool(cam.get("flip_vertical", False)),
        },
        "detection": {},
        "counting": {
            "line_a": counting.get("line_a"),
            "line_b": counting.get("line_b"),
            "direction_labels": counting.get("direction_labels", {}),
            "gate": counting.get("gate", {}),
        },
        "tracking": {
            "max_frames_since_seen": int(track.get("max_frames_since_seen", 10) or 10),
            "min_trajectory_length": int(track.get("min_trajectory_length", 3) or 3),
            "iou_threshold": float(track.get("iou_threshold", 0.3) or 0.3),
        },
    }


@router.post("/calibration")
def set_calibration(req: CalibrationRequest):
    updates: Dict[str, Any] = {"camera": {}, "tracking": {}, "counting": {}}

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

    # Counting / Gate parameters
    cnt = req.counting or CalibrationCounting()
    if cnt.line_a is not None:
        updates["counting"]["line_a"] = cnt.line_a
    if cnt.line_b is not None:
        updates["counting"]["line_b"] = cnt.line_b
    if cnt.direction_labels is not None:
        updates["counting"]["direction_labels"] = cnt.direction_labels
    if cnt.gate is not None:
        gate_updates = {}
        if cnt.gate.max_gap_frames is not None:
            gate_updates["max_gap_frames"] = int(cnt.gate.max_gap_frames)
        if cnt.gate.min_age_frames is not None:
            gate_updates["min_age_frames"] = int(cnt.gate.min_age_frames)
        if cnt.gate.min_displacement_px is not None:
            gate_updates["min_displacement_px"] = float(cnt.gate.min_displacement_px)
        if gate_updates:
            updates["counting"]["gate"] = gate_updates

    # Remove empty sections to avoid noisy overrides
    if not updates["camera"]:
        updates.pop("camera")
    if not updates.get("tracking"):
        updates.pop("tracking", None)
    if not updates.get("counting"):
        updates.pop("counting", None)

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
@router_v1.get("/stats/live", response_model=LiveStatsResponse)
def live_stats():
    if state.database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        cfg = state.get_config_copy() or {}
        direction_labels = (cfg.get("counting", {}) or {}).get("direction_labels", {})

        def map_dirs(counts: dict) -> dict:
            mapped = {}
            for code, cnt in counts.items():
                if code == "A_TO_B":
                    label = direction_labels.get("a_to_b", code)
                elif code == "B_TO_A":
                    label = direction_labels.get("b_to_a", code)
                else:
                    label = code
                mapped[label] = mapped.get(label, 0) + cnt
            return mapped

        total = state.database.get_count_total()
        last_hour = state.database.get_count_total(start_time=time.time() - 3600)
        by_direction_24h = map_dirs(state.database.get_counts_by_direction_code(start_time=time.time() - 86400))
        by_direction_1h = map_dirs(state.database.get_counts_by_direction_code(start_time=time.time() - 3600))
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
@router_v1.get("/stats/range", response_model=RangeStatsResponse)
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
        cfg = state.get_config_copy() or {}
        direction_labels = (cfg.get("counting", {}) or {}).get("direction_labels", {})

        def map_dirs(counts: dict) -> dict:
            mapped = {}
            for code, cnt in counts.items():
                if code == "A_TO_B":
                    label = direction_labels.get("a_to_b", code)
                elif code == "B_TO_A":
                    label = direction_labels.get("b_to_a", code)
                else:
                    label = code
                mapped[label] = mapped.get(label, 0) + cnt
            return mapped

        total = state.database.get_count_total(start_time=start_ts, end_time=end_ts)
        by_direction = map_dirs(state.database.get_counts_by_direction_code(start_time=start_ts, end_time=end_ts))
        return {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "total": total,
            "by_direction": by_direction,
        }
    except Exception as e:
        logging.exception("Error computing range stats")
        raise HTTPException(status_code=500, detail=str(e))


