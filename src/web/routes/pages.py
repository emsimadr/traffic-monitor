from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..services.config_service import ConfigService
from ..services.stats_service import StatsService
from ..services.health_service import HealthService

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    cfg = ConfigService.load_effective_config()
    db_path = cfg["storage"]["local_database_path"]
    stats = StatsService(db_path=db_path).get_summary()
    health = HealthService(cfg=cfg).get_health_summary()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats, "health": health, "cfg": cfg},
    )


@router.get("/config", response_class=HTMLResponse)
def config_page(request: Request):
    cfg = ConfigService.load_effective_config()
    overrides = ConfigService.load_overrides()
    return templates.TemplateResponse(
        "config.html",
        {"request": request, "cfg": cfg, "overrides": overrides},
    )


@router.get("/calibration", response_class=HTMLResponse)
def calibration_page(request: Request):
    cfg = ConfigService.load_effective_config()
    return templates.TemplateResponse(
        "calibration.html",
        {"request": request, "cfg": cfg},
    )


@router.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request):
    cfg = ConfigService.load_effective_config()
    return templates.TemplateResponse("logs.html", {"request": request, "cfg": cfg})


