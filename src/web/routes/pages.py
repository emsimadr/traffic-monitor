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


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    if dist_index.exists():
        return FileResponse(dist_index)
    cfg = ConfigService.load_effective_config()
    db_path = cfg["storage"]["local_database_path"]
    direction_labels = (cfg.get("counting", {}) or {}).get("direction_labels")
    stats = StatsService(db_path=db_path, direction_labels=direction_labels).get_summary()
    health = HealthService(cfg=cfg).get_health_summary()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats, "health": health, "cfg": cfg},
    )


@router.get("/config", response_class=HTMLResponse)
def config_page(request: Request):
    if dist_index.exists():
        return FileResponse(dist_index)
    cfg = ConfigService.load_effective_config()
    overrides = ConfigService.load_overrides()
    return templates.TemplateResponse(
        "config.html",
        {"request": request, "cfg": cfg, "overrides": overrides},
    )


@router.get("/calibration", response_class=HTMLResponse)
def calibration_page(request: Request):
    if dist_index.exists():
        return FileResponse(dist_index)
    cfg = ConfigService.load_effective_config()
    return templates.TemplateResponse(
        "calibration.html",
        {"request": request, "cfg": cfg},
    )


@router.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request):
    if dist_index.exists():
        return FileResponse(dist_index)
    cfg = ConfigService.load_effective_config()
    return templates.TemplateResponse("logs.html", {"request": request, "cfg": cfg})


