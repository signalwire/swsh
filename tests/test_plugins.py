"""Plugins: commands other packages add to `sw` through an entry point.

Real installs are not involved. Each test registers fake entry points through
the same hook discovery reads, pointing at modules placed in ``sys.modules``,
so what is exercised is everything from metadata onwards.
"""

from __future__ import annotations

import json
import sys
import types
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from swsh import cli, plugin_host
from swsh.plugin import Plugin, emit, with_global_flags

runner = CliRunner()

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "swsh-hello"


@pytest.fixture(autouse=True)
def never_touch_the_real_config(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.config, "config_path", lambda: tmp_path / "config.toml")
    for var in ("SIGNALWIRE_PROJECT_ID", "SIGNALWIRE_API_TOKEN", "SIGNALWIRE_SPACE"):
        monkeypatch.delenv(var, raising=False)


def _greeter() -> Plugin:
    app = typer.Typer(no_args_is_help=True)

    @app.command()
    @with_global_flags
    def wave(name: str = "you") -> None:
        """Wave at someone."""
        emit({"waved_at": name}, renderer=lambda d: f"*waves at {d['waved_at']}*")

    @app.command()
    def nod() -> None:
        """Nod."""

    return Plugin(app=app, help="Gestures, from a plugin.")


def _install(monkeypatch, **targets: object) -> None:
    """Register `name=object` as plugins, as if installed packages declared them.

    A string target is used as the entry point value as is, which is how a test
    points one at a module that does not exist.
    """
    eps = []
    for name, target in targets.items():
        if isinstance(target, str):
            value = target
        else:
            module = types.ModuleType(f"fake_plugin_{name}")
            module.plugin = target
            monkeypatch.setitem(sys.modules, module.__name__, module)
            value = f"{module.__name__}:plugin"
        eps.append(EntryPoint(name=name, value=value, group=plugin_host.GROUP))
    plugin_host.reset()
    monkeypatch.setattr(plugin_host, "_entry_points", lambda: eps)


def test_a_plugin_command_runs_with_the_global_flags(monkeypatch):
    _install(monkeypatch, gesture=_greeter())
    result = runner.invoke(cli.app, ["gesture", "wave", "--name", "Ada"])
    assert result.exit_code == 0, result.output
    assert "*waves at Ada*" in result.output

    result = runner.invoke(cli.app, ["gesture", "wave", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"waved_at": "you"}


def test_a_plugin_resolves_by_prefix_like_any_command(monkeypatch):
    _install(monkeypatch, gesture=_greeter())
    result = runner.invoke(cli.app, ["gest", "wa", "--name", "Ada"])
    assert result.exit_code == 0, result.output
    assert "*waves at Ada*" in result.output


def test_sw_help_lists_plugins_in_their_own_panel(monkeypatch):
    _install(monkeypatch, gesture=_greeter())
    out = runner.invoke(cli.app, ["--help"]).output
    assert "Plugins" in out
    assert "Gestures, from a plugin." in out


def test_nothing_is_imported_until_the_plugin_is_used(monkeypatch):
    _install(monkeypatch, gesture=_greeter())
    assert runner.invoke(cli.app, ["profile", "path"]).exit_code == 0
    found = plugin_host.discover(set())
    assert found["gesture"].status == "available"


def test_a_builtin_wins_a_name_and_the_plugin_is_reported_shadowed(monkeypatch):
    _install(monkeypatch, docs=_greeter())
    result = runner.invoke(cli.app, ["docs", "--list"])
    assert result.exit_code == 0
    assert "resources" in result.output  # the built-in ran, not the plugin

    rows = json.loads(runner.invoke(cli.app, ["plugins", "list", "--json"]).stdout)
    assert [(r["name"], r["status"]) for r in rows] == [("docs", "shadowed")]
    assert "built-in" in rows[0]["detail"]


@pytest.mark.parametrize(("target", "why"), [
    ("no_such_module_anywhere:plugin", "import failed"),
    (object(), "not a swsh.plugin.Plugin"),
    (Plugin(app=typer.Typer(), api_version=99), "API v99"),
])
def test_a_broken_plugin_explains_itself_and_breaks_nothing_else(monkeypatch, target, why):
    _install(monkeypatch, broken=target, gesture=_greeter())

    result = runner.invoke(cli.app, ["broken", "anything", "--whatever"])
    assert result.exit_code == 1
    assert why in result.output

    # The neighbours, and sw itself, are unaffected.
    assert runner.invoke(cli.app, ["gesture", "wave"]).exit_code == 0
    assert runner.invoke(cli.app, ["--help"]).exit_code == 0

    rows = json.loads(runner.invoke(cli.app, ["plugins", "list", "--json"]).stdout)
    status = {r["name"]: r["status"] for r in rows}
    assert status == {"broken": "broken", "gesture": "loaded"}


def test_plugins_list_with_nothing_installed():
    result = runner.invoke(cli.app, ["plugins", "list"])
    assert result.exit_code == 0
    assert "no plugins installed" in result.output
    assert json.loads(runner.invoke(cli.app, ["plugins", "list", "--json"]).stdout) == []


def test_the_example_plugin_works(monkeypatch):
    """`examples/swsh-hello` is documentation; this keeps it true."""
    monkeypatch.syspath_prepend(str(EXAMPLE))
    _install(monkeypatch, hello="swsh_hello:plugin")
    result = runner.invoke(cli.app, ["hello", "world", "--name", "Ada", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"greeting": "hello, Ada"}
    # Needs credentials, and says so the way a built-in does.
    result = runner.invoke(cli.app, ["hello", "project"])
    assert result.exit_code != 0


def test_doctor_reports_a_plugin_that_cannot_run(monkeypatch):
    _install(monkeypatch, broken="no_such_module_anywhere:plugin", gesture=_greeter())
    monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "p")
    monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "t")
    monkeypatch.setenv("SIGNALWIRE_SPACE", "example")

    async def whoami(self):
        return {"friendly_name": "test"}

    async def nothing(self, *a, **kw):
        return []

    monkeypatch.setattr(cli.SwshClient, "whoami", whoami)
    monkeypatch.setattr(cli.SwshClient, "verify_compat", nothing)
    monkeypatch.setattr(cli.SwshClient, "list_calls", nothing)

    result = runner.invoke(cli.app, ["doctor", "--json"])
    checks = {c["check"]: c for c in json.loads(result.stdout)}
    assert checks["plugin broken"]["ok"] is False
    assert "import failed" in checks["plugin broken"]["detail"]
    assert "plugin gesture" not in checks  # a healthy plugin is not news
    assert result.exit_code == 1
