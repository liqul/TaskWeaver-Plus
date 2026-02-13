import click

from taskweaver.cli.util import CliContext, get_ascii_banner, require_workspace


@click.command()
@require_workspace()
@click.pass_context
@click.option(
    "--server-url",
    help="URL of the CES (Code Execution Service) server",
    type=str,
    required=False,
    default=None,
)
def chat(ctx: click.Context, server_url: str):
    """Chat with TaskWeaver in command line.

    Requires a CES server to be running. Start one first with:
        python -m taskweaver.ces.server --port 8081

    \b
    Example:
        taskweaver -p ./project/ chat --server-url http://localhost:8081
    """
    ctx_obj: CliContext = ctx.obj

    effective_server_url = server_url or ctx_obj.server_url
    if not effective_server_url:
        click.secho(
            "Error: --server-url is required. Start a CES server first:\n"
            "  python -m taskweaver.ces.server --port 8081\n"
            "Then run:\n"
            f"  taskweaver -p {ctx_obj.workspace} chat --server-url http://localhost:8081",
            fg="red",
        )
        raise SystemExit(1)

    from taskweaver.chat.console import chat_taskweaver

    click.echo(get_ascii_banner())
    chat_taskweaver(ctx_obj.workspace, server_url=effective_server_url)
