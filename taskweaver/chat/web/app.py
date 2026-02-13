"""FastAPI application for the TaskWeaver Web/Chat server.

This is a separate server from the CES (Code Execution Service) server.
It serves the web UI, handles chat WebSocket connections, and uses the
CES client internally to communicate with a running CES server.

Usage:
    1. Start the CES server first:
       python -m taskweaver.ces.server --port 8081

    2. Start the chat/web server:
       taskweaver -p ./project/ server --port 8082 --ces-url http://localhost:8081
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from taskweaver.chat.web import chat_router
from taskweaver.chat.web.routes import chat_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle."""
    logger.info("Starting TaskWeaver Chat Server")

    app_dir = getattr(app.state, "app_dir", None)
    ces_url = getattr(app.state, "ces_url", None)

    if app_dir:
        chat_manager.set_app_dir(app_dir)
    if ces_url:
        chat_manager.set_server_url(ces_url)

    logger.info(f"Chat server initialized with app_dir={app_dir}, ces_url={ces_url}")

    yield

    logger.info("Shutting down TaskWeaver Chat Server")
    chat_manager.cleanup_all()


def create_app(
    app_dir: Optional[str] = None,
    ces_url: Optional[str] = None,
    cors_origins: Optional[list[str]] = None,
    serve_frontend: bool = True,
) -> FastAPI:
    """Create and configure the chat/web FastAPI application.

    Args:
        app_dir: TaskWeaver project directory (contains taskweaver_config.json).
        ces_url: URL of the CES (Code Execution Service) server.
        cors_origins: List of allowed CORS origins. Defaults to allowing all.
        serve_frontend: Whether to serve the frontend static files.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="TaskWeaver Chat Server",
        description="Web UI and chat interface for TaskWeaver",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.app_dir = app_dir or os.getenv("TASKWEAVER_APP_DIR")
    app.state.ces_url = ces_url or os.getenv("TASKWEAVER_CES_URL")

    if cors_origins is None:
        cors_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router)

    if serve_frontend:
        try:
            from taskweaver.web import mount_frontend

            mount_frontend(app)
        except ImportError:
            logger.debug("Frontend static files not available")

    return app


# Default app instance for uvicorn
app = create_app()
