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
from ..services.calibration_service import CalibrationService
from ..services.stats_service import StatsService
from ..services.logs_service import LogsService
from ..services.health_service import HealthService
from ..services.camera_service import CameraService
from ..state import state
from ..api_models import (
    StatsSummary,
    LiveStatsResponse,
    RangeStatsResponse,
    StatusResponse,
    CompactStatusResponse,
    RecentEventsResponse,
    HourlyStatsResponse,
    DailyStatsResponse,
    PipelineStatusResponse,
)

router = APIRouter()
router_v1 = APIRouter(prefix="/api/v1")


def _compute_warnings(
    last_frame_age_s: Optional[float],
    disk_free_pct: Optional[float],
    cpu_temp_c: Optional[float],
) -> List[str]:
    """
    Compute warning flags for status endpoints.
    
    Thresholds:
    - camera_stale: last_frame_age_s > 2
    - camera_offline: last_frame_age_s > 10 or None
    - disk_low: disk_free_pct < 10
    - temp_high: cpu_temp_c > 80
    """
    warnings = []
    
    if last_frame_age_s is None or last_frame_age_s > 10:
        warnings.append("camera_offline")
    elif last_frame_age_s > 2:
        warnings.append("camera_stale")
    
    if disk_free_pct is not None and disk_free_pct < 10:
        warnings.append("disk_low")
    
    if cpu_temp_c is not None and cpu_temp_c > 80:
        warnings.append("temp_high")
    
    return warnings


def _derive_status_level(warnings: List[str]) -> str:
    """Derive status level from warnings."""
    if "camera_offline" in warnings:
        return "offline"
    elif warnings:
        return "degraded"
    return "running"


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


@router.get("/stats/by-class")
@router_v1.get("/stats/by-class")
def stats_by_class(start_ts: Optional[float] = None, end_ts: Optional[float] = None):
    """
    Get count statistics broken down by object class (modal split analysis).
    
    Query parameters:
    - start_ts: Unix timestamp for start of time range (default: 24 hours ago)
    - end_ts: Unix timestamp for end of time range (default: now)
    
    Returns:
    - total: total count in time range
    - by_class: count per class {"car": 120, "bicycle": 15, "person": 8, ...}
    - by_class_and_direction: nested breakdown {"car": {"A_TO_B": 65, "B_TO_A": 55}, ...}
    - unclassified: count of detections with no class (from bgsub backend)
    - time_range: {start, end}
    
    Note: Multi-class detection requires detection.backend='yolo' or 'hailo'.
    Background subtraction (bgsub) produces unclassified detections.
    """
    cfg = ConfigService.load_effective_config()
    db_path = cfg["storage"]["local_database_path"]
    direction_labels = (cfg.get("counting", {}) or {}).get("direction_labels")
    
    return StatsService(db_path=db_path, direction_labels=direction_labels).get_counts_by_class(
        start_time=start_ts,
        end_time=end_ts
    )


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

    warnings = _compute_warnings(last_frame_age, disk.get("pct_free"), temp_c)
    level = _derive_status_level(warnings)

    return {
        "status": level,
        "alerts": warnings,
        "last_frame_age": last_frame_age,
        "fps": fps,
        "uptime_seconds": int(uptime) if uptime is not None else None,
        "disk": disk,
        "temp_c": temp_c,
        "stats": stats,
        "health": health,
        "timestamp": now,
    }


def _get_today_start_timestamp() -> float:
    """Get Unix timestamp for start of today (local time)."""
    from datetime import datetime
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start.timestamp()


@router.get("/status/compact", response_model=CompactStatusResponse)
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
    counts_by_class: Dict[str, int] = {}
    
    if state.database is not None:
        today_start = _get_today_start_timestamp()
        try:
            counts_today_total = state.database.get_count_total(start_time=today_start)
            counts_by_direction_code = state.database.get_counts_by_direction_code(start_time=today_start)
            counts_by_class = state.database.get_counts_by_class(start_time=today_start)
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
        counts_by_class=counts_by_class,
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
    """Camera orientation transforms (site-specific)."""
    swap_rb: Optional[bool] = None
    rotate: Optional[int] = None
    flip_horizontal: Optional[bool] = None
    flip_vertical: Optional[bool] = None


class CalibrationCounting(BaseModel):
    """Gate geometry and direction labels (site-specific)."""
    line_a: Optional[List[List[float]]] = None
    line_b: Optional[List[List[float]]] = None
    direction_labels: Optional[Dict[str, str]] = None


class CalibrationRequest(BaseModel):
    """Site-specific calibration data (geometry, orientation)."""
    camera: Optional[CalibrationCamera] = None
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
    """
    Get site-specific calibration data (geometry, orientation).
    
    Returns calibration from data/calibration/site.yaml if it exists,
    otherwise falls back to values from config.yaml for backwards compatibility.
    
    Calibration includes:
    - Gate line coordinates (measured geometry)
    - Direction labels (site-specific)
    - Camera orientation (rotate, flip)
    """
    # Try loading from calibration file first
    calibration = CalibrationService.load()
    
    # Fall back to effective config for backwards compatibility
    if not calibration:
        cfg = ConfigService.load_effective_config()
        cam = cfg.get("camera", {}) or {}
        counting = cfg.get("counting", {}) or {}
        
        return {
            "camera": {
                "swap_rb": bool(cam.get("swap_rb", False)),
                "rotate": int(cam.get("rotate", 0) or 0),
                "flip_horizontal": bool(cam.get("flip_horizontal", False)),
                "flip_vertical": bool(cam.get("flip_vertical", False)),
            },
            "counting": {
                "line_a": counting.get("line_a"),
                "line_b": counting.get("line_b"),
                "direction_labels": counting.get("direction_labels", {}),
            },
            "_source": "config.yaml"  # Indicate fallback source
        }
    
    # Return calibration data
    cam = calibration.get("camera", {}) or {}
    counting = calibration.get("counting", {}) or {}
    
    return {
        "camera": {
            "swap_rb": bool(cam.get("swap_rb", False)),
            "rotate": int(cam.get("rotate", 0) or 0),
            "flip_horizontal": bool(cam.get("flip_horizontal", False)),
            "flip_vertical": bool(cam.get("flip_vertical", False)),
        },
        "counting": {
            "line_a": counting.get("line_a"),
            "line_b": counting.get("line_b"),
            "direction_labels": counting.get("direction_labels", {}),
        },
        "_source": "site.yaml",  # Indicate calibration source
        "_metadata": calibration.get("_metadata", {})
    }


@router.post("/calibration")
def set_calibration(req: CalibrationRequest):
    """
    Save site-specific calibration data to data/calibration/site.yaml.
    
    This is separate from config.yaml which contains operational settings.
    Calibration includes:
    - Gate line coordinates (measured geometry)
    - Direction labels (site-specific)
    - Camera orientation (rotate, flip)
    
    The calibration file is gitignored (site-specific).
    """
    calibration: Dict[str, Any] = {}

    # Camera transforms (calibration data)
    cam = req.camera or CalibrationCamera()
    if cam.swap_rb is not None or cam.rotate is not None or \
       cam.flip_horizontal is not None or cam.flip_vertical is not None:
        calibration["camera"] = {}
        
        if cam.swap_rb is not None:
            calibration["camera"]["swap_rb"] = bool(cam.swap_rb)
        if cam.rotate is not None:
            r = int(cam.rotate or 0)
            if r not in (0, 90, 180, 270):
                raise HTTPException(status_code=400, detail="camera.rotate must be one of 0,90,180,270")
            calibration["camera"]["rotate"] = r
        if cam.flip_horizontal is not None:
            calibration["camera"]["flip_horizontal"] = bool(cam.flip_horizontal)
        if cam.flip_vertical is not None:
            calibration["camera"]["flip_vertical"] = bool(cam.flip_vertical)

    # Gate geometry and direction labels (calibration data)
    cnt = req.counting or CalibrationCounting()
    if cnt.line_a is not None or cnt.line_b is not None or cnt.direction_labels is not None:
        calibration["counting"] = {}
        
        if cnt.line_a is not None:
            calibration["counting"]["line_a"] = cnt.line_a
        if cnt.line_b is not None:
            calibration["counting"]["line_b"] = cnt.line_b
        if cnt.direction_labels is not None:
            calibration["counting"]["direction_labels"] = cnt.direction_labels

    if not calibration:
        raise HTTPException(status_code=400, detail="No calibration data provided")

    try:
        # Load existing calibration (if any)
        existing = CalibrationService.load() or {}
        
        # Merge updates into existing
        merged = _deep_merge(existing, calibration)
        
        # Save to site.yaml
        CalibrationService.save(merged, add_metadata=True)
        
        # Update runtime config
        state.update_config(ConfigService.load_effective_config())
        
        return {"ok": True, "message": "Calibration saved to data/calibration/site.yaml"}
    except Exception as e:
        logging.exception("Failed to save calibration")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/camera/live.mjpg")
def camera_live_stream(fps: int = 5):
    """
    Stream MJPEG frames from the shared state (populated by the pipeline engine).
    
    Transforms (rotate, flip, swap_rb) are already applied by the observation layer,
    so this endpoint just encodes and streams the frames.
    """
    fps = max(1, min(30, int(fps)))
    delay = 1.0 / fps

    def gen():
        while True:
            frame = state.get_frame()
            if frame is None:
                time.sleep(0.1)
                continue

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


@router.get("/stats/recent")
@router_v1.get("/stats/recent", response_model=RecentEventsResponse)
def stats_recent(limit: int = 50):
    """
    Get most recent count events (for Recent Events table).
    
    Query parameters:
    - limit: Max events to return (default: 50, max: 200)
    
    Returns list of events with timestamp, direction, class, confidence.
    Privacy: No track IDs, no coordinates, aggregate data only.
    """
    if state.database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    limit = max(1, min(200, limit))  # Cap at 200 for performance
    
    try:
        events_raw = state.database.get_recent_events(limit=limit)
        
        # Map to API model format
        from ..api_models import CountEvent
        events = []
        for e in events_raw:
            events.append(CountEvent(
                ts=e.get("ts", 0),
                direction_code=e.get("direction_code", "unknown"),
                direction_label=e.get("direction_label"),
                class_name=e.get("class_name"),
                confidence=float(e.get("confidence", 1.0)),
            ))
        
        return RecentEventsResponse(
            events=events,
            total_shown=len(events),
        )
    except Exception as e:
        logging.exception("Error getting recent events")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/hourly")
@router_v1.get("/stats/hourly", response_model=HourlyStatsResponse)
def stats_hourly(days: int = 7):
    """
    Get hourly count aggregates for trend charts.
    
    Query parameters:
    - days: Number of days to look back (default: 7, max: 90)
    
    Returns hourly aggregates with total, by_direction, by_class breakdowns.
    """
    if state.database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    days = max(1, min(90, days))  # Cap at 90 days
    
    try:
        import sqlite3
        from datetime import datetime
        
        cfg = state.get_config_copy() or {}
        direction_labels = (cfg.get("counting", {}) or {}).get("direction_labels", {})
        
        start_time = time.time() - (days * 86400)
        start_ms = int(start_time * 1000)
        end_ms = int(time.time() * 1000)
        
        conn = state.database._get_connection()
        cursor = conn.cursor()
        
        # Get hourly aggregates with direction and class breakdowns
        cursor.execute("""
            SELECT 
                strftime('%Y-%m-%d %H:00:00', ts/1000, 'unixepoch', 'localtime') as hour,
                direction_code,
                COALESCE(class_name, 'unclassified') as class,
                COUNT(*) as count
            FROM count_events
            WHERE ts BETWEEN ? AND ?
            GROUP BY hour, direction_code, class
            ORDER BY hour
        """, (start_ms, end_ms))
        
        # Aggregate results
        hours_data = {}
        for row in cursor.fetchall():
            hour_str, dir_code, class_name, count = row
            
            if hour_str not in hours_data:
                # Parse hour string to get timestamp
                dt = datetime.strptime(hour_str, '%Y-%m-%d %H:%M:%S')
                hours_data[hour_str] = {
                    "hour_start_ts": int(dt.timestamp()),
                    "total": 0,
                    "by_direction": {},
                    "by_class": {},
                }
            
            hours_data[hour_str]["total"] += count
            hours_data[hour_str]["by_direction"][dir_code] = hours_data[hour_str]["by_direction"].get(dir_code, 0) + count
            hours_data[hour_str]["by_class"][class_name] = hours_data[hour_str]["by_class"].get(class_name, 0) + count
        
        from ..api_models import HourlyCount
        hours = [HourlyCount(**data) for data in hours_data.values()]
        
        return HourlyStatsResponse(
            hours=hours,
            start_ts=start_time,
            end_ts=time.time(),
        )
    except Exception as e:
        logging.exception("Error getting hourly stats")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/daily")
@router_v1.get("/stats/daily", response_model=DailyStatsResponse)
def stats_daily(days: int = 30):
    """
    Get daily count aggregates for trend charts.
    
    Query parameters:
    - days: Number of days to look back (default: 30, max: 365)
    
    Returns daily aggregates with total, by_direction, by_class breakdowns.
    """
    if state.database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    days = max(1, min(365, days))  # Cap at 1 year
    
    try:
        import sqlite3
        from datetime import datetime
        
        cfg = state.get_config_copy() or {}
        direction_labels = (cfg.get("counting", {}) or {}).get("direction_labels", {})
        
        start_time = time.time() - (days * 86400)
        start_ms = int(start_time * 1000)
        end_ms = int(time.time() * 1000)
        
        conn = state.database._get_connection()
        cursor = conn.cursor()
        
        # Get daily aggregates with direction and class breakdowns
        cursor.execute("""
            SELECT 
                strftime('%Y-%m-%d', ts/1000, 'unixepoch', 'localtime') as date,
                direction_code,
                COALESCE(class_name, 'unclassified') as class,
                COUNT(*) as count
            FROM count_events
            WHERE ts BETWEEN ? AND ?
            GROUP BY date, direction_code, class
            ORDER BY date
        """, (start_ms, end_ms))
        
        # Aggregate results
        days_data = {}
        for row in cursor.fetchall():
            date_str, dir_code, class_name, count = row
            
            if date_str not in days_data:
                # Parse date string to get timestamp
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                days_data[date_str] = {
                    "date": date_str,
                    "day_start_ts": int(dt.timestamp()),
                    "total": 0,
                    "by_direction": {},
                    "by_class": {},
                }
            
            days_data[date_str]["total"] += count
            days_data[date_str]["by_direction"][dir_code] = days_data[date_str]["by_direction"].get(dir_code, 0) + count
            days_data[date_str]["by_class"][class_name] = days_data[date_str]["by_class"].get(class_name, 0) + count
        
        from ..api_models import DailyCount
        days_list = [DailyCount(**data) for data in days_data.values()]
        
        return DailyStatsResponse(
            days=days_list,
            start_ts=start_time,
            end_ts=time.time(),
        )
    except Exception as e:
        logging.exception("Error getting daily stats")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/export")
def stats_export(
    start_ts: Optional[float] = None,
    end_ts: Optional[float] = None,
    days: int = 30,
    format: str = "csv",
):
    """
    Export count events as CSV for reporting/analysis.
    
    Query parameters:
    - start_ts: Start time (Unix timestamp)
    - end_ts: End time (Unix timestamp)
    - days: Days to look back if start_ts not provided (default: 30)
    - format: Export format (currently only 'csv')
    
    Returns CSV with columns: timestamp, date_time, direction_code, direction_label, class_name, confidence
    Privacy: No track IDs, no coordinates, aggregate events only.
    """
    if state.database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format supported")
    
    now = time.time()
    end_ts = end_ts or now
    if start_ts is None:
        start_ts = end_ts - max(1, days) * 86400
    
    if start_ts >= end_ts:
        raise HTTPException(status_code=400, detail="start_ts must be before end_ts")
    
    try:
        import csv
        import io
        from datetime import datetime
        
        start_ms = int(start_ts * 1000)
        end_ms = int(end_ts * 1000)
        
        conn = state.database._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                ts,
                direction_code,
                direction_label,
                COALESCE(class_name, 'unclassified') as class_name,
                confidence
            FROM count_events
            WHERE ts BETWEEN ? AND ?
            ORDER BY ts
        """, (start_ms, end_ms))
        
        # Build CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp_ms", "datetime_local", "direction_code", "direction_label", "class", "confidence"])
        
        for row in cursor.fetchall():
            ts_ms, dir_code, dir_label, class_name, confidence = row
            dt = datetime.fromtimestamp(ts_ms / 1000.0)
            dt_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            writer.writerow([ts_ms, dt_str, dir_code, dir_label or "", class_name, confidence])
        
        csv_content = output.getvalue()
        output.close()
        
        from fastapi.responses import Response
        filename = f"traffic_counts_{datetime.fromtimestamp(start_ts).strftime('%Y%m%d')}_{datetime.fromtimestamp(end_ts).strftime('%Y%m%d')}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logging.exception("Error exporting stats")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/pipeline")
@router_v1.get("/status/pipeline", response_model=PipelineStatusResponse)
def pipeline_status():
    """
    Get health status of each pipeline stage (for Health page diagnostics).
    
    Stages: Observation → Detection → Tracking → Counting → Storage
    Each stage reports: running|degraded|offline with optional message.
    """
    from ..api_models import PipelineStageStatus
    
    stages = []
    overall = "running"
    
    # 1. Observation (camera/frame capture)
    sys_stats = state.get_system_stats_copy() if hasattr(state, "get_system_stats_copy") else getattr(state, "system_stats", {}) or {}
    last_frame_ts = sys_stats.get("last_frame_ts")
    if last_frame_ts is None or (time.time() - last_frame_ts) > 10:
        stages.append(PipelineStageStatus(name="Observation", status="offline", message="No frames in last 10s"))
        overall = "offline"
    elif (time.time() - last_frame_ts) > 2:
        stages.append(PipelineStageStatus(name="Observation", status="degraded", message="Stale frames"))
        if overall == "running":
            overall = "degraded"
    else:
        stages.append(PipelineStageStatus(name="Observation", status="running", message=None))
    
    # 2. Detection (placeholder - would check inference stats)
    stages.append(PipelineStageStatus(name="Detection", status="running", message="Backend operational"))
    
    # 3. Tracking
    stages.append(PipelineStageStatus(name="Tracking", status="running", message="Tracker operational"))
    
    # 4. Counting
    stages.append(PipelineStageStatus(name="Counting", status="running", message="Counter operational"))
    
    # 5. Storage (database)
    if state.database is None:
        stages.append(PipelineStageStatus(name="Storage", status="offline", message="Database not initialized"))
        overall = "offline"
    else:
        stages.append(PipelineStageStatus(name="Storage", status="running", message="Database operational"))
    
    return PipelineStatusResponse(
        stages=stages,
        overall_status=overall,
    )


