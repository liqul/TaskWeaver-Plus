import click

from .chat import chat
from .init import init
from .server import server
from .util import CliContext, get_ascii_banner

_tw_version: str = __import__("taskweaver").__version__


@click.group(
    name="taskweaver",
    help=f"\b\n{get_ascii_banner(center=False)}\nTaskWeaver",
    invoke_without_command=True,
    commands=[init, chat, server],
)
@click.pass_context
@click.version_option(version=_tw_version, prog_name="taskweaver")
@click.option(
    "--project",
    "-p",
    help="Path to the project directory",
    type=click.Path(
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    required=False,
    default=None,
)
@click.option(
    "--server-url",
    help="URL of the Code Execution Server (e.g., http://localhost:8081).",
    type=str,
    required=False,
    default=None,
)
def taskweaver(ctx: click.Context, project: str, server_url: str):
    from taskweaver.utils.app_utils import discover_app_dir

    workspace_base, is_valid, is_empty = discover_app_dir(project)

    ctx.obj = CliContext(
        workspace=workspace_base,
        workspace_param=project,
        is_workspace_valid=is_valid,
        is_workspace_empty=is_empty,
        server_url=server_url,
    )
    if not ctx.invoked_subcommand:
        ctx.invoke(chat)
        return
