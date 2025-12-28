from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import pages, api


def create_app() -> FastAPI:
    """Create the FastAPI app and wire routes/static assets."""
    app = FastAPI(title="Traffic Monitor", version="0.1.0")

    app.include_router(pages.router)
    app.include_router(api.router, prefix="/api")

    app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
    return app


# Exported application instance for uvicorn
app = create_app()

