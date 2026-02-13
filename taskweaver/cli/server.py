"""Server subcommand for starting the TaskWeaver Chat/Web server.

This starts the chat/web server that serves the frontend UI and handles
WebSocket chat connections. It uses a separate CES (Code Execution Service)
server for code execution.

Usage:
    1. Start the CES server first:
       python -m taskweaver.ces.server --port 8081

    2. Start the chat/web server:
       taskweaver -p ./project/ server --port 8082 --ces-url http://localhost:8081
"""

import os

import click

from taskweaver.cli.util import CliContext, require_workspace


def _check_ces_health(ces_url: str) -> bool:
    """Check if the CES server is reachable and healthy."""
    import urllib.request
    import urllib.error

    health_url = f"{ces_url.rstrip('/')}/api/v1/health"
    try:
        req = urllib.request.Request(health_url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


@click.command()
@require_workspace()
@click.pass_context
@click.option(
    "--host",
    type=str,
    default=None,
    help="Host to bind to (default: localhost)",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help="Port to bind to (default: 8082)",
)
@click.option(
    "--ces-url",
    type=str,
    default=None,
    help="URL of the CES server (default: http://localhost:8081)",
)
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error", "critical"]),
    default="info",
    help="Log level (default: info)",
)
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    help="Enable auto-reload for development",
)
def server(
    ctx: click.Context,
    host: str,
    port: int,
    ces_url: str,
    log_level: str,
    reload: bool,
):
    """Start the TaskWeaver Chat/Web server.

    This server serves the web UI and handles chat sessions. It requires
    a CES (Code Execution Service) server to be running for code execution.

    \b
    Example:
        # Start CES server first
        python -m taskweaver.ces.server --port 8081

        # Then start the chat/web server
        taskweaver -p ./project/ server --port 8082 --ces-url http://localhost:8081
    """
    ctx_obj: CliContext = ctx.obj
    workspace = ctx_obj.workspace
    assert workspace is not None

    from taskweaver.config.config_mgt import AppConfigSource

    app_config_file = os.path.join(workspace, "taskweaver_config.json")
    config_src = AppConfigSource(
        config_file_path=app_config_file if os.path.exists(app_config_file) else None,
        config={},
        app_base_path=workspace,
    )

    def get_config(key: str, default):
        return config_src.json_file_store.get(key, default)

    effective_host = host or get_config("chat.server.host", "localhost")
    effective_port = port or get_config("chat.server.port", 8082)
    effective_ces_url = ces_url or get_config(
        "execution_service.server.url",
        "http://localhost:8081",
    )

    os.environ["TASKWEAVER_APP_DIR"] = workspace
    os.environ["TASKWEAVER_CES_URL"] = effective_ces_url

    # Check CES server connectivity before starting
    click.echo()
    click.echo(f"Checking CES server at {effective_ces_url} ...")
    ces_healthy = _check_ces_health(effective_ces_url)
    if not ces_healthy:
        click.secho(
            f"Error: Cannot connect to CES server at {effective_ces_url}",
            fg="red",
        )
        click.echo()
        click.echo("Please start the CES server first:")
        click.echo(f"  python -m taskweaver.ces.server --port {effective_ces_url.rsplit(':', 1)[-1]}")
        raise SystemExit(1)
    click.secho("CES server is healthy.", fg="green")

    click.echo()
    click.echo("=" * 60)
    click.echo("  TaskWeaver Chat/Web Server")
    click.echo("=" * 60)
    click.echo(f"  Project:      {ctx_obj.workspace}")
    click.echo(f"  Host:         {effective_host}")
    click.echo(f"  Port:         {effective_port}")
    click.echo(f"  Chat UI:      http://{effective_host}:{effective_port}/chat")
    click.echo(f"  Sessions UI:  Served by CES at {effective_ces_url}/")
    click.echo(f"  CES Server:   {effective_ces_url}")
    click.echo("=" * 60)
    click.echo()

    try:
        import uvicorn
    except ImportError:
        click.secho(
            "Error: uvicorn is required to run the server. " "Please install it with: pip install uvicorn",
            fg="red",
        )
        raise SystemExit(1)

    try:
        import fastapi  # noqa: F401
    except ImportError:
        click.secho(
            "Error: fastapi is required to run the server. " "Please install it with: pip install fastapi",
            fg="red",
        )
        raise SystemExit(1)

    try:
        import websockets  # noqa: F401

        ws_impl = "websockets"
    except ImportError:
        try:
            import wsproto  # noqa: F401

            ws_impl = "wsproto"
        except ImportError:
            click.secho(
                "Error: a WebSocket library is required. "
                "Please install one with: pip install websockets",
                fg="red",
            )
            raise SystemExit(1)

    uvicorn.run(
        "taskweaver.chat.web.app:app",
        host=effective_host,
        port=effective_port,
        reload=reload,
        log_level=log_level,
        ws=ws_impl,
    )
