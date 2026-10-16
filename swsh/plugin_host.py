"""Finding and loading plugins: commands that live in other packages.

A plugin is any installed distribution that declares an entry point in the
``swsh.plugins`` group, pointing at a ``swsh.plugin.Plugin``::

    [project.entry-points."swsh.plugins"]
    deploy = "swsh_deploy:plugin"

The entry point's name is the command: that one becomes ``sw deploy``. Plugin
authors import from ``swsh.plugin``; this module is the machinery behind it and
is not part of that contract.

Three rules:

- **Built-ins win.** A plugin can add a command, never replace one. A name that
  collides with a built-in, or with a plugin found earlier, is reported as
  shadowed and not loaded.
- **Nothing is imported until it is asked for.** Listing what is installed reads
  package metadata only; a plugin's module is imported the first time its
  command is resolved, and once per process after that.
- **A broken plugin breaks only itself.** One that fails to import, exports the
  wrong thing or targets another API version still shows up, marked as broken,
  and running it prints one line saying why and exits 1. The rest of ``sw`` keeps
  working.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points

import click
import typer

# Bumped only when a change to ``swsh.plugin`` would break plugins built
# against the previous one. A plugin declares the version it was written for and
# is refused, with a message naming both, when they differ.
API_VERSION = 1

GROUP = "swsh.plugins"

# The `sw --help` panel plugin commands are listed under, apart from the
# built-ins so nobody mistakes one for the other.
HELP_PANEL = "Plugins"


@dataclass(frozen=True)
class Plugin:
    """What a plugin's entry point resolves to."""

    # The Typer app behind the command. Its commands become `sw <name> …`; an
    # app with exactly one command and no callback becomes `sw <name>` itself,
    # the same way Typer always collapses one.
    app: typer.Typer
    # Short help shown next to the command in `sw --help`, when the app's own
    # `help=` is not set.
    help: str = ""
    api_version: int = API_VERSION


@dataclass
class Found:
    """One installed plugin, as `sw plugins list` and `sw doctor` report it."""

    name: str
    entry_point: EntryPoint
    status: str = "available"  # available | loaded | broken | shadowed
    detail: str = ""
    command: click.Command | None = None

    @property
    def package(self) -> str:
        dist = self.entry_point.dist
        return dist.name if dist is not None else "?"

    @property
    def version(self) -> str:
        dist = self.entry_point.dist
        return dist.version if dist is not None else "?"

    def as_json(self) -> dict[str, str]:
        return {"name": self.name, "package": self.package, "version": self.version,
                "target": self.entry_point.value, "status": self.status,
                "detail": self.detail}


# name -> Found, filled by `discover` once per process. Tests reset it.
_cache: dict[str, Found] | None = None
_shadowed: list[Found] = []


def reset() -> None:
    """Forget everything discovered. For tests, which install fake plugins."""
    global _cache
    _cache = None
    _shadowed.clear()


def _entry_points() -> list[EntryPoint]:
    """The raw entry points, in a stable order. Patched by the tests."""
    return sorted(entry_points(group=GROUP), key=lambda ep: (ep.name, ep.value))


def discover(builtins: Collection[str]) -> dict[str, Found]:
    """Every usable plugin by command name. Reads metadata; imports nothing."""
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    for ep in _entry_points():
        found = Found(ep.name, ep)
        if ep.name in builtins:
            found.status = "shadowed"
            found.detail = f"`sw {ep.name}` is a built-in command"
            _shadowed.append(found)
        elif ep.name in _cache:
            found.status = "shadowed"
            found.detail = f"`sw {ep.name}` already comes from {_cache[ep.name].package}"
            _shadowed.append(found)
        else:
            _cache[ep.name] = found
    return _cache


def everything(builtins: Collection[str]) -> list[Found]:
    """Usable and shadowed plugins alike, each loaded so its status is real."""
    usable = discover(builtins)
    for name in list(usable):
        command(name, builtins)
    return sorted([*usable.values(), *_shadowed], key=lambda f: (f.name, f.package))


def command(name: str, builtins: Collection[str]) -> click.Command | None:
    """The click command for plugin ``name``, importing it on first use.

    None when no plugin has that name. A plugin that cannot be loaded still
    yields a command, one that explains the failure, so `sw <name>` says what
    is wrong instead of "No such command".
    """
    found = discover(builtins).get(name)
    if found is None:
        return None
    if found.command is None:
        found.command = _load(found)
    return found.command


def _load(found: Found) -> click.Command:
    try:
        obj = found.entry_point.load()
    except Exception as exc:  # anything a third-party import can raise
        return _broken(found, f"import failed: {type(exc).__name__}: {exc}")
    if not isinstance(obj, Plugin):
        return _broken(found, f"{found.entry_point.value} is a {type(obj).__name__}, "
                              "not a swsh.plugin.Plugin")
    if obj.api_version != API_VERSION:
        return _broken(found, f"written for plugin API v{obj.api_version}; "
                              f"this sw speaks v{API_VERSION}")
    try:
        cmd = typer.main.get_command(obj.app)
    except Exception as exc:
        return _broken(found, f"could not build its commands: {type(exc).__name__}: {exc}")
    cmd.name = found.name
    if obj.help and not cmd.help:
        cmd.help = obj.help
    # Typer's rich help reads the panel off the command object.
    cmd.rich_help_panel = HELP_PANEL  # type: ignore[attr-defined]
    found.status = "loaded"
    return cmd


def _broken(found: Found, why: str) -> click.Command:
    found.status = "broken"
    found.detail = why
    message = f"plugin `{found.name}` from {found.package} {found.version} is broken: {why}"

    stub = typer.Typer()

    # Swallow whatever arguments were meant for the real command, so the
    # failure is this message rather than "no such option".
    @stub.command(name=found.name, help=f"[broken] {why}",
                  context_settings={"ignore_unknown_options": True,
                                    "allow_extra_args": True})
    def run(args: list[str] | None = typer.Argument(None, hidden=True)) -> None:
        from . import ui

        ui.fail(message)
        ui.hint("`sw plugins list` shows every installed plugin and its state.")
        raise typer.Exit(1)

    cmd = typer.main.get_command(stub)
    cmd.rich_help_panel = HELP_PANEL  # type: ignore[attr-defined]
    return cmd
