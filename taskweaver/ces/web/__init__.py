"""Static file serving for the CES (Code Execution Service) web interface."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def get_static_dir() -> Optional[Path]:
    """Locate the built CES frontend static files directory."""
    current_dir = Path(__file__).parent

    static_dir = current_dir / "static"
    if static_dir.exists() and (static_dir / "index.html").exists():
        return static_dir

    frontend_dist = current_dir / "frontend" / "dist"
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        return frontend_dist

    return None


def mount_frontend(app: FastAPI, static_dir: Optional[Path] = None) -> bool:
    """Mount the CES frontend static files to the FastAPI app.

    Returns True if mounted successfully, False if no static files found.
    """
    if static_dir is None:
        static_dir = get_static_dir()

    if static_dir is None:
        logger.warning(
            "CES frontend static files not found. "
            "Run 'npm run build' in taskweaver/ces/web/frontend to build the frontend.",
        )
        return False

    index_html = static_dir / "index.html"

    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    async def serve_index(request: Request):
        return FileResponse(str(index_html))

    logger.info(f"Mounted CES frontend static files from {static_dir}")
    return True
