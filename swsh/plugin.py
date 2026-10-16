"""The API a plugin is written against. Import from here and nowhere else.

A plugin is a separate package that adds a command to ``sw``. It declares an
entry point in the ``swsh.plugins`` group naming a ``Plugin``; the entry point's
name is the command::

    # pyproject.toml of the plugin
    [project.entry-points."swsh.plugins"]
    deploy = "swsh_deploy:plugin"

    # swsh_deploy/__init__.py
    import typer
    from swsh.plugin import Plugin, SwshClient, coro, emit

    app = typer.Typer(help="Deploy agents to SignalWire.")

    @app.command()
    @coro
    async def push(client: SwshClient, name: str) -> None:
        emit(await client.whoami())

    plugin = Plugin(app=app)

That gives ``sw deploy push NAME``, with the same ``--json``, ``--raw``,
``--profile`` and ``--timeout`` as every built-in command, the same credential
resolution and the same error reporting. Install it into the environment sw
runs from: ``uv tool install swsh --with swsh-deploy``, or ``pip install`` into
the same venv.

Everything named in ``__all__`` is the contract, versioned by ``API_VERSION``.
The rest of ``swsh`` is not: reach past this module and the plugin can break on
any release.
"""

from __future__ import annotations

from typing import Any

from . import ui
from .cli import Ctx, _emit_raw, _profile, coro, raw_capable, with_global_flags
from .client import SwshClient, SwshError
from .config import Profile
from .plugin_host import API_VERSION, Plugin

__all__ = [
    "API_VERSION",
    "Plugin",
    "Profile",
    "SwshClient",
    "SwshError",
    "coro",
    "emit",
    "emit_raw",
    "json_output",
    "profile",
    "raw_capable",
    "ui",
    "with_global_flags",
]


def json_output() -> bool:
    """True when the command was run with ``--json`` (or ``--raw``)."""
    return Ctx.as_json


def emit(data: Any, renderer=None) -> None:
    """Print a result: JSON under ``--json``, otherwise ``renderer(data)``.

    ``renderer`` returns anything Rich can print; ``ui.rows_table`` is the one
    the built-in listings use. Without one the data is printed as is.
    """
    ui.emit(data, as_json=Ctx.as_json, renderer=renderer)


def emit_raw(payload: Any) -> bool:
    """Hand ``--raw`` the API response a command exists to fetch.

    Returns True when ``--raw`` took the output, in which case the command
    should print nothing else. Only a command marked ``@raw_capable`` may call
    it; every other command refuses ``--raw`` before its body runs.
    """
    return _emit_raw(payload)


def profile() -> Profile:
    """The credentials this run resolved to, honouring ``--profile``.

    For a command that needs them without making a request through
    ``SwshClient``, such as one that hands them to a subprocess. Exits with a
    usage error, as built-in commands do, when none are configured.
    """
    return _profile()
