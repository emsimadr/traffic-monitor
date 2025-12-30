"""
Page routes for the Traffic Monitor web interface.

- Main routes (/, /config, /health, /logs) serve the React SPA
- Legacy routes (/legacy/*) serve Jinja2 templates
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from ..services.config_service import ConfigService
from ..services.stats_service import StatsService
from ..services.health_service import HealthService

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")
dist_index = Path("frontend/dist/index.html")


# -----------------------------------------------------------------------------
# React SPA Routes (served from frontend/dist/index.html)
# -----------------------------------------------------------------------------

def _serve_spa():
    """Serve the React SPA index.html."""
    if dist_index.exists():
        return FileResponse(dist_index)
    return HTMLResponse(
        content="<h1>Frontend not built</h1><p>Run <code>npm run build</code> in frontend/</p>",
        status_code=503,
    )


@router.get("/", response_class=HTMLResponse)
def spa_dashboard():
    """Dashboard page (React SPA)."""
    return _serve_spa()


@router.get("/config", response_class=HTMLResponse)
def spa_config():
    """Configuration page (React SPA)."""
    return _serve_spa()


@router.get("/health", response_class=HTMLResponse)
def spa_health():
    """Health page (React SPA)."""
    return _serve_spa()


@router.get("/logs", response_class=HTMLResponse)
def spa_logs():
    """Logs page (React SPA)."""
    return _serve_spa()


@router.get("/calibration", response_class=HTMLResponse)
def spa_calibration():
    """Calibration page (React SPA)."""
    return _serve_spa()


# -----------------------------------------------------------------------------
# Legacy Jinja2 Template Routes (preserved for backward compatibility)
# -----------------------------------------------------------------------------

@router.get("/legacy", response_class=HTMLResponse)
@router.get("/legacy/", response_class=HTMLResponse)
def legacy_dashboard(request: Request):
    """Legacy dashboard (Jinja2 template)."""
    cfg = ConfigService.load_effective_config()
    db_path = cfg["storage"]["local_database_path"]
    direction_labels = (cfg.get("counting", {}) or {}).get("direction_labels")
    stats = StatsService(db_path=db_path, direction_labels=direction_labels).get_summary()
    health = HealthService(cfg=cfg).get_health_summary()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats, "health": health, "cfg": cfg},
    )


@router.get("/legacy/config", response_class=HTMLResponse)
def legacy_config_page(request: Request):
    """Legacy config page (Jinja2 template)."""
    cfg = ConfigService.load_effective_config()
    overrides = ConfigService.load_overrides()
    return templates.TemplateResponse(
        "config.html",
        {"request": request, "cfg": cfg, "overrides": overrides},
    )


@router.get("/legacy/calibration", response_class=HTMLResponse)
def legacy_calibration_page(request: Request):
    """Legacy calibration page (Jinja2 template)."""
    cfg = ConfigService.load_effective_config()
    return templates.TemplateResponse(
        "calibration.html",
        {"request": request, "cfg": cfg},
    )


@router.get("/legacy/logs", response_class=HTMLResponse)
def legacy_logs_page(request: Request):
    """Legacy logs page (Jinja2 template)."""
    cfg = ConfigService.load_effective_config()
    return templates.TemplateResponse("logs.html", {"request": request, "cfg": cfg})
