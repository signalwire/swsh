"""An example sw plugin. Install it and `sw hello` exists.

Two commands, one per shape a plugin command usually takes:

- ``sw hello world``: no API, plain options, still answers ``--json``;
- ``sw hello project``: talks to the platform through the same client, profile
  resolution and error handling as the built-ins, and supports ``--raw``.
"""

from __future__ import annotations

import typer
from rich.text import Text

from swsh.plugin import Plugin, SwshClient, coro, emit, emit_raw, raw_capable, with_global_flags

app = typer.Typer(help="Say hello: an example of an sw plugin.", no_args_is_help=True)


@app.command()
@with_global_flags
def world(name: str = typer.Option("world", "--name", "-n", help="Who to greet.")) -> None:
    """Greet someone, without touching the API."""
    emit({"greeting": f"hello, {name}"},
         renderer=lambda d: Text(d["greeting"], style="bold"))


@app.command()
@coro
@raw_capable
async def project(client: SwshClient) -> None:
    """Greet the project the current profile points at."""
    account = await client.whoami()
    if emit_raw(account):
        return
    name = account.get("friendly_name") or "unnamed project"
    emit({"project": client.profile.project, "space": client.profile.host, "name": name},
         renderer=lambda d: Text(f"hello, {d['name']} on {d['space']}", style="bold"))


plugin = Plugin(app=app)
