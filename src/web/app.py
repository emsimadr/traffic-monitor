from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routes import pages, api


def create_app() -> FastAPI:
    """Create the FastAPI app and wire routes/static assets."""
    app = FastAPI(title="Traffic Monitor", version="0.1.0")

    app.include_router(pages.router)
    app.include_router(api.router, prefix="/api")
    app.include_router(api.router_v1)

    app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

    # Serve built React frontend if present (frontend/dist). This is optional; falls back gracefully if missing.
    dist_path = Path("frontend") / "dist"
    assets_dir = dist_path / "assets"
    if dist_path.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}")
        def spa_catch_all(full_path: str):
            # Only serve index.html for non-API paths; API routes are already mounted under /api.
            index_file = dist_path / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return {"detail": "frontend not built"}

    return app


# Exported application instance for uvicorn
app = create_app()

