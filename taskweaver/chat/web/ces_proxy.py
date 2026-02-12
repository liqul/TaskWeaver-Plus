"""Reverse proxy for CES (Code Execution Service) API routes.

The chat/web server proxies requests under /api/v1/sessions and /api/v1/health
to the CES server. This allows the frontend to talk to a single server while
keeping the CES server as a separate process.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Will be set during app startup
_ces_url: Optional[str] = None


def set_ces_url(url: str) -> None:
    global _ces_url
    _ces_url = url


def _get_ces_url() -> str:
    if not _ces_url:
        raise RuntimeError("CES server URL not configured")
    return _ces_url.rstrip("/")


@router.api_route(
    "/api/v1/{rest_of_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    include_in_schema=False,
)
async def proxy_ces(request: Request, rest_of_path: str) -> Response:
    """Proxy any /api/v1/* request to the CES server.

    The chat router (/api/v1/chat/...) is registered first, so those
    routes are handled directly.  Everything else falls through here.
    """
    return await _proxy_request(request, f"/api/v1/{rest_of_path}")


async def _proxy_request(request: Request, path: str) -> Response:
    """Forward a request to the CES server and return its response."""
    ces_base = _get_ces_url()
    url = f"{ces_base}{path}"

    # Preserve query string
    if request.url.query:
        url = f"{url}?{request.url.query}"

    body = await request.body()
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body if body else None,
                timeout=300.0,
            )
    except httpx.ConnectError:
        return Response(
            content=f'{{"detail":"CES server not reachable at {ces_base}"}}',
            status_code=502,
            media_type="application/json",
        )

    # For SSE streams, return as streaming response
    content_type = resp.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        async def stream_sse():
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    method=request.method,
                    url=url,
                    headers=headers,
                    content=body if body else None,
                    timeout=300.0,
                ) as stream:
                    async for chunk in stream.aiter_bytes():
                        yield chunk

        return StreamingResponse(
            stream_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Copy response headers (skip hop-by-hop)
    resp_headers = {
        k: v
        for k, v in resp.headers.items()
        if k.lower() not in ("content-length", "transfer-encoding", "content-encoding")
    }

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
        media_type=resp.headers.get("content-type"),
    )
