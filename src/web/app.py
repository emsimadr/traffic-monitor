"""
FastAPI application factory for Traffic Monitor.

Routes:
- / , /config, /health, /logs, /calibration -> React SPA
- /legacy/* -> Jinja2 templates (backward compat)
- /api/* -> REST API
- /static/* -> Static assets (CSS, images)
- /assets/* -> Vite-built assets (JS, CSS bundles)
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .routes import pages, api


def create_app() -> FastAPI:
    """Create the FastAPI app and wire routes/static assets."""
    app = FastAPI(
        title="Traffic Monitor",
        version="0.2.0",
        description="Edge-deployed traffic monitoring system",
    )

    # CORS for development (Vite dev server)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes (highest priority)
    app.include_router(api.router, prefix="/api")
    app.include_router(api.router_v1)

    # Page routes (/, /config, /health, /logs, /legacy/*)
    app.include_router(pages.router)

    # Static files for Jinja templates (CSS, images, etc.)
    static_path = Path("src/web/static")
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # Vite-built assets (frontend/dist/assets)
    dist_path = Path("frontend/dist")
    assets_path = dist_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

    # SPA catch-all for client-side routing
    # This handles routes like /config, /health that the React router manages
    @app.get("/{full_path:path}")
    async def spa_catch_all(request: Request, full_path: str):
        """
        Catch-all route for SPA client-side routing.
        
        Serves index.html for any route not matched by API or static files.
        This allows React Router to handle navigation.
        """
        # Skip if path starts with api, static, assets, or legacy
        skip_prefixes = ("api/", "static/", "assets/", "legacy/")
        if any(full_path.startswith(p) for p in skip_prefixes):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        
        # Serve React SPA
        index_file = dist_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        
        return JSONResponse(
            {"detail": "Frontend not built. Run 'npm run build' in frontend/"},
            status_code=503,
        )

    return app


# Exported application instance for uvicorn
app = create_app()
