"""The sw command line.

Every command that produces data accepts ``--json`` so sw composes with jq and
scripts, and ``--raw`` for the API response under it, unshaped. Human rendering
lives in ``swsh.ui``; nothing here formats a table inline.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import inspect
import json
import os
import re
import signal
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import click
import httpx
import typer
from rich.panel import Panel
from rich.text import Text
from typer._completion_classes import completion_init as _completion_init

from . import __version__, config, plugin_host, prompts, resources, routing, spec, ui
from .client import SwshClient, SwshError, _describe, error_doc_urls
from .client import next_page as client_next_page
from .config import (
    ConfigError,
    Profile,
    delete_profile,
    list_profiles,
    resolve,
    save_profile,
    set_default,
)


class _PrefixGroup(typer.core.TyperGroup):
    """Resolve a unique prefix of a command at any level: ``sw num li``.

    Nouns are long (``fabricaddresses``, ``subscribers``) and completion is not
    always installed. Every group, the root and each noun, uses this class. An
    exact name always wins; a prefix that matches several commands is an error
    that names them rather than a guess.
    """

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        exact = super().get_command(ctx, cmd_name)
        if exact is not None:
            return exact
        matches = sorted(n for n in self.list_commands(ctx) if n.startswith(cmd_name))
        if len(matches) == 1:
            # Through `self`, not `super()`: at the root the match may be a
            # plugin, which only `_RootGroup.get_command` knows how to load.
            return self.get_command(ctx, matches[0])
        if len(matches) > 1:
            ctx.fail(f"'{cmd_name}' is ambiguous: {', '.join(matches)}")
        return None

    def resolve_command(self, ctx: click.Context, args: list[str]):
        # Report the full name, so `sw num --help` reads "sw numbers".
        name, cmd, rest = super().resolve_command(ctx, args)
        return (cmd.name if cmd is not None else name), cmd, rest


class _RootGroup(_PrefixGroup):
    """The `sw` group itself: the built-ins, then any installed plugins.

    Plugins are listed from package metadata and imported only when one is
    resolved, by name or by prefix. A built-in always wins a name; see
    ``swsh.plugin_host`` for the rules.
    """

    def list_commands(self, ctx: click.Context) -> list[str]:
        names = super().list_commands(ctx)
        return names + sorted(plugin_host.discover(self.commands))

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        if cmd_name not in self.commands:
            plugin = plugin_host.command(cmd_name, self.commands)
            if plugin is not None:
                return _with_prefixes(plugin)
        return super().get_command(ctx, cmd_name)


def _with_prefixes(cmd: Any) -> Any:
    """Give a plugin's groups the prefix matching every built-in group has.

    A plugin builds a plain Typer app, so without this `sw num li` works and
    `sw deploy li` does not. `_PrefixGroup` adds behaviour and no state, so
    swapping the class of an already-built group is safe, and idempotent.
    """
    if type(cmd) is typer.core.TyperGroup:
        cmd.__class__ = _PrefixGroup
    for sub in getattr(cmd, "commands", {}).values():
        _with_prefixes(sub)
    return cmd


def _builtin_names() -> set[str]:
    """Every built-in top-level command, which is what a plugin may not take."""
    # Not `isinstance(root, click.Group)`: Typer builds its groups on its own
    # vendored click, so that check is always false.
    return set(getattr(typer.main.get_command(app), "commands", {}))


app = typer.Typer(
    name="sw",
    cls=_RootGroup,
    help="The SignalWire CLI: scriptable commands, a live cockpit (sw sh), "
         "and a callback sink.",
    # Typer's `--install-completion` / `--show-completion` are off: `sw
    # completion install|show|status|uninstall` covers them and adds the undo
    # Typer never had. Two ways to do the same thing, one of them irreversible,
    # is worse than one.
    #
    # This also silently breaks *runtime* completion, which is not obvious:
    # typer only calls `completion_init()` — the function that registers the
    # per-shell completion classes — while building those two options. Without
    # it, an installed completion script gets "Shell zsh not supported". So we
    # call it ourselves below.
    add_completion=False,
    rich_markup_mode="rich",
    # The last line of `sw` and `sw --help`. Someone who types `sw` blind gets a
    # 60-command listing and no hint that an interactive view exists; `sh` is
    # one row in it. Bare `sw` deliberately does *not* launch the cockpit — it
    # would break in a pipe or a CI job, and the listing is the only place the
    # command tree advertises itself — so the signpost does that job instead.
    epilog="New here? [bold]sw sh[/bold] opens the interactive cockpit.",
)

# Register the per-shell completion classes that `add_completion=False` skips.
# Without this an installed completion script fails with "Shell zsh not
# supported"; `tests/test_completion.py` pins that it stays registered.
_completion_init()

# The command tree is noun-first: `sw numbers list`, `sw swml delete <id>`,
# `sw numbers assign-e911-address <id> --e911-address-id …`. Every registry
# resource is a command group named by its key, and its verbs and extras are
# generated from the registry at import time (see `_install_resource_groups`
# at the bottom of this module). There are no verb-first aliases: one path to
# each operation.
#
# A handful of groups are hand-written because they need shaping the registry
# cannot express (call control, the number search flags, a message send with a
# picker). They register onto the *same* group the registry would generate, so
# `sw numbers` is one command with `list`, `buy`, `search` and the E911 actions
# side by side. A hand-written command wins over a generated one of the same
# name.
_resource_apps: dict[str, typer.Typer] = {}


def resource_app(key: str) -> typer.Typer:
    """The command group for a registry resource, created on first use."""
    if key in _resource_apps:
        return _resource_apps[key]
    resource = resources.get(key)
    if resource is None:
        raise KeyError(key)
    sub = typer.Typer(cls=_PrefixGroup, name=key, no_args_is_help=True,
                      help=_group_help(resource))
    app.add_typer(sub, name=key, rich_help_panel=resources.group_title(resource.group))
    _resource_apps[key] = sub
    return sub


def _group_help(resource: resources.Resource) -> str:
    title = resource.title[:1].upper() + resource.title[1:]
    return f"{title}." + (f" {resource.help}" if resource.help else "")


calls_app = typer.Typer(cls=_PrefixGroup, name="calls", no_args_is_help=True,
                        help="Place, watch and control calls.")
app.add_typer(calls_app, rich_help_panel=resources.group_title("voice"))
numbers_app = resource_app("numbers")
messages_app = resource_app("messages")
logs_app = resource_app("logs")

profile_app = typer.Typer(cls=_PrefixGroup, name="profile", no_args_is_help=True,
                          help="Manage credential profiles.")
app.add_typer(profile_app)
plugins_app = typer.Typer(cls=_PrefixGroup, name="plugins", no_args_is_help=True,
                          help="See the commands installed packages add to sw.")
app.add_typer(plugins_app)


class Ctx:
    """Global options, resolved once and shared by every command."""

    profile_name: str | None = None
    as_json: bool = False
    raw: bool = False
    raw_emitted: bool = False
    timeout: float | None = None
    csv: bool = False


def _profile() -> Profile:
    try:
        return resolve(Ctx.profile_name)
    except ConfigError as exc:
        ui.fail(str(exc))
        raise typer.Exit(2) from exc


# `--json`, `--raw` and `--profile` describe how a *command* behaves, so they
# belong to every command and to nothing else. All of these work, in any order:
#
#     sw whoami --json
#     sw numbers list --json --profile scratch
#     sw numbers list --profile scratch --json
#
# And this is a usage error, on purpose:
#
#     sw --json numbers list
#
# They used to be on the root callback too. That made `sw --help` list them
# among `sw`'s own options, which reads as though `sw --json` were a command in
# its own right. It is not.
#
# They are appended as real Typer parameters rather than plucked out of argv, so
# `sw whoami --help` actually lists them. Munging argv would make the flags work
# while leaving --help silently lying about them.
_JSON_PARAM = "_json_out"
_PROFILE_PARAM = "_profile_name"
_RAW_PARAM = "_raw_out"
_TIMEOUT_PARAM = "_timeout"


def _global_params() -> list[inspect.Parameter]:
    return [
        inspect.Parameter(
            _JSON_PARAM, inspect.Parameter.KEYWORD_ONLY, annotation=bool,
            default=typer.Option(False, "--json", help="Machine-readable output."),
        ),
        inspect.Parameter(
            _RAW_PARAM, inspect.Parameter.KEYWORD_ONLY, annotation=bool,
            default=typer.Option(False, "--raw",
                                 help="Print the API response exactly as it arrived, "
                                      "envelope included. Implies --json."),
        ),
        inspect.Parameter(
            # A real type object, not the string "str | None": the module's
            # `from __future__ import annotations` makes its own hints lazy, but
            # Typer resolves these at parser-build time and cannot evaluate a
            # string, which fails as "Type not yet supported".
            _PROFILE_PARAM, inspect.Parameter.KEYWORD_ONLY, annotation=str | None,
            default=typer.Option(None, "--profile", "-P", help="Credential profile."),
        ),
        inspect.Parameter(
            _TIMEOUT_PARAM, inspect.Parameter.KEYWORD_ONLY, annotation=float | None,
            default=typer.Option(None, "--timeout",
                                 help="Seconds to wait on the platform. "
                                      "Also SWSH_TIMEOUT. Default 30."),
        ),
    ]


def _absorb_global_flags(kwargs: dict[str, Any]) -> None:
    """Fold a command's own flags into Ctx, then remove them.

    Must run before anything reads Ctx — in particular before ``_profile()``,
    which is what ``--profile`` has to influence.
    """
    if kwargs.pop(_JSON_PARAM, False):
        Ctx.as_json = True
    if kwargs.pop(_RAW_PARAM, False):
        # Raw output is machine output, so it inherits everything `--json`
        # already settled: no pickers, no prompts for a missing field, strict
        # failure instead. Nothing else needs to learn about `--raw`.
        Ctx.raw = True
        Ctx.as_json = True
    profile = kwargs.pop(_PROFILE_PARAM, None)
    if profile:
        Ctx.profile_name = profile
    Ctx.timeout = kwargs.pop(_TIMEOUT_PARAM, None)


# `--raw`: the response, not a view of it.
#
# `--json` is sw's own shape — the rows lifted out of a list envelope, a call
# flattened to the fields the tool models, `--limit` already applied. `--raw` is
# what the platform sent for the one call the command is about: the envelope and
# its paging links, every field of every row, nothing added and nothing taken
# off. It is what to reach for when sw's shape is missing the field you came for
# and you do not want to rebuild the request by hand with `sw api`.
#
# Three rules keep it honest:
#
# - **Rendering is suppressed for the whole command**, not skipped print by
#   print. A resolved handle, a "deleted <id>" line or a progress note landing in
#   the middle of the document would make it unparseable, and every command
#   prints something.
# - **The command names the response.** `_emit_raw` is called with the payload
#   of the operation the command exists to perform, so `get` shows the read and
#   not the list its handle lookup happened to need first.
# - **A command with no single response says so, first.** `raw_capable` marks
#   the ones that have one; every other command refuses `--raw` before its body
#   runs, because `sw listen --raw` must not open a tunnel and rewrite every
#   number's status callback before admitting it cannot answer.


def raw_capable(fn):
    """Mark a command as having one API response that ``--raw`` can show.

    Innermost of the decorators, so ``coro`` and ``with_global_flags`` see it.
    """
    fn.raw_capable = True
    return fn


def _raw_guard(fn) -> None:
    """Refuse ``--raw`` on a command with no single response, before it runs."""
    if Ctx.raw and not getattr(fn, "raw_capable", False):
        ui.fail("--raw shows one API response, and this command has none to show.")
        ui.hint("Use --json for sw's own shape, or `sw api` for any endpoint raw.")
        raise typer.Exit(2)


def _emit_raw(payload: Any) -> bool:
    """Print one API response untouched. True when ``--raw`` took the output."""
    if not Ctx.raw:
        return False
    Ctx.raw_emitted = True
    quiet, ui.console.quiet = ui.console.quiet, False
    try:
        ui.emit(payload, as_json=True)
    finally:
        ui.console.quiet = quiet
    return True


def _raw_already() -> None:
    """For a command whose normal output *is* the response, byte for byte.

    ``sw api`` echoes what the platform said and nothing else, so `--raw` has
    nothing to add: it must not silence that output, and must not then report
    that no response was shown.
    """
    if Ctx.raw:
        Ctx.raw_emitted = True
        ui.console.quiet = False


def _raw_refuse(why: str) -> None:
    """Refuse a flag combination that ``--raw`` cannot represent."""
    if Ctx.raw:
        ui.fail(why)
        raise typer.Exit(2)


@contextlib.contextmanager
def _raw_output():
    """Silence rendered output for the duration of a ``--raw`` command."""
    if not Ctx.raw:
        yield
        return
    ui.console.quiet = True
    try:
        yield
    finally:
        ui.console.quiet = False


def _raw_check() -> None:
    """The net under a ``raw_capable`` command that returned without emitting."""
    if Ctx.raw and not Ctx.raw_emitted:
        ui.fail("--raw found no response to show for this command.")
        raise typer.Exit(2)


class _LazyProfile:
    """Credentials resolved on first use, not when the command starts.

    ``coro`` used to call ``_profile()`` to build the client, so a command that
    never makes a request still demanded credentials: ``sw api --list`` reads
    only the checked-in catalog and failed with "not logged in".

    ``SwshClient`` only touches its profile when it builds the HTTP or SDK
    client, so deferring costs nothing and the failure still surfaces — at the
    moment a request is actually attempted, with the same exit code.
    """

    __slots__ = ("_resolved",)

    def __init__(self) -> None:
        self._resolved: Profile | None = None

    def __getattr__(self, name: str) -> Any:
        if self._resolved is None:
            self._resolved = _profile()
        return getattr(self._resolved, name)


def with_global_flags(fn):
    """Give a non-async command the same `--json` / `--profile` that ``coro``
    provides. For the handful of commands that need no client."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        _absorb_global_flags(kwargs)
        _raw_guard(fn)
        with _raw_output():
            result = fn(*args, **kwargs)
        _raw_check()
        return result

    signature = inspect.signature(fn)
    wrapper.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=[*signature.parameters.values(), *_global_params()]
    )
    return wrapper


# Typer vendors its own copy of click (`typer._click`), so a `typer.BadParameter`
# raised by a command body is *not* a `click.ClickException`. Catching only the
# latter sent every "missing required field" through the catch-all below as
# exit 1 with a traceback hint, instead of the usage error (exit 2) it is.
_CLICK_EXCEPTIONS: tuple[type[BaseException], ...] = tuple({
    click.ClickException,
    next(c for c in typer.BadParameter.__mro__ if c.__name__ == "ClickException"),
})


def coro(fn):
    """Let command bodies be async and receive a ready client as their first
    argument, without each one repeating the asyncio and error boilerplate.

    Typer builds its parser by inspecting the signature, so the injected
    ``client`` parameter has to be stripped from the wrapper's advertised
    signature or Typer tries to turn it into a CLI option.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        _absorb_global_flags(kwargs)
        _raw_guard(fn)

        async def runner():
            async with SwshClient(_LazyProfile(),  # type: ignore[arg-type]
                                  timeout=Ctx.timeout) as client:
                return await fn(client, *args, **kwargs)

        try:
            with _raw_output():
                result = asyncio.run(runner())
            _raw_check()
            return result
        except (typer.Exit, typer.Abort, *_CLICK_EXCEPTIONS):
            # Control flow, not failure. A command body that has already
            # reported a usage problem and chosen its exit code must keep it —
            # the catch-all below would otherwise rewrite every `Exit(2)` to 1.
            raise
        except SwshError as exc:
            ui.fail(str(exc))
            # The platform attaches a doc link per offending field. It goes
            # under the message, not inside it: a 200-character URL in the
            # middle of a sentence is half of why these were unreadable.
            for url in error_doc_urls(exc.body)[:3]:
                ui.hint(url)
            raise typer.Exit(1) from exc
        except KeyboardInterrupt:
            raise typer.Exit(130) from None
        except httpx.HTTPError as exc:
            ui.fail(_describe_network_error(exc))
            raise typer.Exit(1) from exc
        except OSError as exc:
            ui.fail(f"{type(exc).__name__}: {exc}")
            raise typer.Exit(1) from exc
        except Exception as exc:  # the last line of defence before a traceback
            # A CLI must not answer a mistyped space or a flaky network with a
            # 200-line Rich traceback. Anything unhandled gets one line and a
            # documented way to see the whole thing.
            if os.environ.get("SW_TRACEBACK"):
                raise
            ui.fail(f"{type(exc).__name__}: {exc}")
            ui.hint("Re-run with SW_TRACEBACK=1 to see the full traceback.")
            raise typer.Exit(1) from exc

    signature = inspect.signature(fn)
    wrapper.__signature__ = signature.replace(  # type: ignore[attr-defined]
        # [1:] strips the injected client; the globals are appended so every
        # command accepts them in either position.
        parameters=[*list(signature.parameters.values())[1:], *_global_params()]
    )
    return wrapper


def _describe_network_error(exc: Exception) -> str:
    """Turn a transport failure into a line that names the likely cause.

    A DNS failure here almost always means the space is wrong, and the raw
    "nodename nor servname provided" says nothing about that. The space is
    included in the message because that is the value to go and check.
    """
    space = "the configured space"
    try:
        space = _profile().host
    except Exception:  # reporting an error must never raise one
        pass

    if isinstance(exc, httpx.ConnectTimeout | httpx.ReadTimeout | httpx.WriteTimeout):
        return f"timed out talking to {space}"
    if isinstance(exc, httpx.ConnectError):
        return (
            f"cannot reach {space}: {exc}. "
            "Check SIGNALWIRE_SPACE, or `sw whoami` to see what is set."
        )
    return f"{type(exc).__name__} talking to {space}: {exc}"


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    # `--json` and `--profile` deliberately do NOT live here. They describe what
    # a command does, not what `sw` is, and listing them in the root options
    # block reads as though `sw --json` were a command in its own right. They are
    # declared on every command instead, so `sw numbers list --json` works and
    # `sw --json numbers list` is a usage error.
    if version:
        ui.console.print(f"sw {__version__}")
        raise typer.Exit()
    # Reset per invocation: the commands set these, and the module-level state
    # would otherwise leak from one run to the next in a single process.
    Ctx.profile_name = None
    Ctx.as_json = False
    Ctx.raw = False
    Ctx.raw_emitted = False
    Ctx.timeout = None
    Ctx.csv = False
    # `--version` is an option, not a command, so the callback must run without a
    # subcommand; when there is genuinely nothing to do, fall back to help.
    if ctx.invoked_subcommand is None:
        ui.console.print(ctx.get_help())
        raise typer.Exit()
    # Not in front of `sw completion ...` itself: installing completion one line
    # above the uninstall someone just asked for is its own kind of rude.
    if ctx.invoked_subcommand != "completion":
        _autoinstall_completion()


# -------------------------------------------------------------------------- sh
#
# `sw sh` is the cockpit. The name is the old one, split: `swsh` was the
# interactive shell through 2.0, and `sw` + `sh` still spells it while putting
# the shell where every other capability already is — a subcommand, not a second
# binary. There is no `sw tui` and no `swsh` script; one spelling, no aliases.
#
# Defined first on purpose. Typer lists commands in registration order and
# always prints the default "Commands" panel before every named one, so the
# first `@app.command()` in this module is the first row a person reads. The
# cockpit is the front door for anyone who does not already know what to type;
# it was the ninth row of that panel, between `listen` and `profile`.


@app.command("sh")
def shell(
    topics: list[str] = typer.Option([], "--topic", "-t",
                                     help="RELAY topic to subscribe to. Repeatable."),
    poll_interval: float = typer.Option(2.0, "--poll", help="Active poll interval, seconds."),
    record: str | None = typer.Option(None, "--record", help="Write a JSONL event trace here."),
) -> None:
    """Launch the live cockpit: browse, edit and watch every resource."""
    from .tui.app import SwshApp

    # With no credentials this used to fail here, two lines before the cockpit
    # was built — and the cockpit contains a perfectly good profile form, which
    # `ctrl+p` reaches, but only once you already have working credentials. So
    # the one screen able to fix the problem was behind the problem. It opens on
    # that form instead; `_profile()` is still what fails for every other
    # command, where there is nowhere better to go.
    try:
        profile = _profile()
        onboarding = False
    except typer.Exit:
        profile = Profile(name="", project="", token="", space="")
        onboarding = True

    SwshApp(profile=profile, topics=list(topics), poll_interval=poll_interval,
            record_path=record, onboarding=onboarding).run()


# ------------------------------------------------------------------ completion
#
# Typer ships `--install-completion` but no way to undo it, and it never says
# what it wrote. These commands make it inspectable and reversible.

completion_app = typer.Typer(cls=_PrefixGroup, name="completion", no_args_is_help=True,
                             help="Install, inspect or remove shell tab completion.")
app.add_typer(completion_app)

# Where each shell's completion script lands, and the line the installer appends
# to the shell's startup file. Read from typer._completion_shared, which is where
# `--install-completion` writes; if that ever moves, `status` reports absent
# rather than lying, and `tests/test_completion.py` compares against typer.
_COMPLETION_LAYOUT: dict[str, dict[str, Any]] = {
    "zsh": {
        "script": lambda prog: Path.home() / ".zfunc" / f"_{prog}",
        "rc": Path.home() / ".zshrc",
        # Shared infrastructure: other tools put completions in ~/.zfunc too, so
        # this line is only removed when nothing else is left there.
        "rc_line": "fpath+=~/.zfunc; autoload -Uz compinit; compinit",
        "rc_line_shared": True,
    },
    "bash": {
        "script": lambda prog: Path.home() / ".bash_completions" / f"{prog}.sh",
        "rc": Path.home() / ".bashrc",
        "rc_line": None,  # computed per prog: source '<script>'
        "rc_line_shared": False,
    },
    "fish": {
        "script": lambda prog: Path.home() / ".config/fish/completions" / f"{prog}.fish",
        "rc": None,
        "rc_line": None,
        "rc_line_shared": False,
    },
}

# `sw` is the only console script now. `swsh` is still listed because people
# who installed completion for it before the rename have those files on disk,
# and `completion status` should say so and `uninstall --all` should remove
# them. Nothing installs it any more.
_PROG_NAMES = ("sw", "swsh")


def _current_shell() -> str | None:
    """The running shell, by inspecting the parent process then falling back.

    shellingham reads the process tree, which fails under a pipe or an odd
    parent. $SHELL is the login shell rather than the running one, so it is the
    fallback, not the first choice.
    """
    try:
        import shellingham

        return str(shellingham.detect_shell()[0])
    except Exception:
        shell = os.environ.get("SHELL", "")
        return Path(shell).name or None


def _rc_line_for(shell: str, prog: str) -> str | None:
    layout = _COMPLETION_LAYOUT[shell]
    if layout["rc_line"] is not None:
        return str(layout["rc_line"])
    if shell == "bash":
        return f"source '{layout['script'](prog)}'"
    return None


def _completion_state(shell: str) -> list[dict[str, Any]]:
    """What is installed for this shell, per program name."""
    layout = _COMPLETION_LAYOUT[shell]
    rows = []
    for prog in _PROG_NAMES:
        script = layout["script"](prog)
        rc = layout["rc"]
        line = _rc_line_for(shell, prog)
        rc_present = False
        if rc is not None and line is not None and rc.is_file():
            rc_present = line in rc.read_text()
        rows.append({"program": prog, "shell": shell, "script": script,
                     "installed": script.is_file(), "rc": rc,
                     "rc_line": line, "rc_line_present": rc_present})
    return rows


# Completion is set up on first use rather than asked for. Typing `sw numb<TAB>`
# and getting nothing is how most people conclude a CLI has no completion, and
# `--install-completion` is a thing you have to already know exists. pip cannot
# do it: installing a wheel runs no code, so the first interactive run is the
# earliest honest moment.
#
# Three rules keep that from being presumptuous:
#
# - **Only in a real terminal**, read off the streams themselves rather than
#   through `prompts.interactive()`. Whether to *prompt* and whether to *edit
#   someone's shell configuration* are different questions, and tests patch the
#   first one to True all the time to exercise a confirmation. One that did
#   exactly that appended to the developer's real `~/.zshrc`, which is the
#   thing this whole module is supposed not to do.
# - **Once, ever.** The marker is written whatever the outcome — installed,
#   unsupported shell, or failed — so `sw completion uninstall` is final and a
#   shell we cannot detect is not re-probed on every command.
# - **It says what it did.** One line naming the file, and the command that
#   undoes it. A tool that edits your shell configuration in silence is worse
#   than one that does not offer completion at all.
AUTO_COMPLETION_ENV = "SWSH_NO_COMPLETION_INSTALL"


def _on_a_terminal() -> bool:
    """Both streams are a real terminal.

    Deliberately not `prompts.interactive()`, which is the same test but is a
    *policy* about prompting that tests patch to True to exercise a
    confirmation. One of them did, and appended to the developer's own
    `~/.zshrc`. This is its own function so a test can say "not a terminal"
    without reaching into whatever object pytest's capture has put in
    `sys.stdout`.
    """
    return sys.stdin.isatty() and sys.stdout.isatty()


def _completion_marker() -> Path:
    """Records that first-run setup has happened, next to the config file."""
    return config.config_path().parent / "completion-attempted"


def _mark_completion_attempted() -> None:
    marker = _completion_marker()
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        pass  # a read-only home is not a reason to fail the command


def _autoinstall_completion() -> None:
    """Install completion the first time `sw` runs in a terminal."""
    if os.environ.get(AUTO_COMPLETION_ENV):
        return
    if not _on_a_terminal():
        return
    if _completion_marker().exists():
        return

    shell = _current_shell()
    if shell not in _COMPLETION_LAYOUT:
        _mark_completion_attempted()
        return
    if any(row["installed"] for row in _completion_state(shell)):
        _mark_completion_attempted()
        return

    from typer._completion_shared import install as typer_install

    try:
        _, path = typer_install(shell=shell, prog_name="sw")
    except Exception:
        # Silent: this is running in front of the command someone actually
        # typed, and a completion script is not what they came for.
        _mark_completion_attempted()
        return

    _mark_completion_attempted()
    # `soft_wrap` so the path and the undo command are never broken across a
    # line: a wrapped `sw completion uninstall` is not one you can copy.
    ui.console.print(
        f"[muted]tab completion installed for {shell}:[/muted] [brand]{path}[/brand]",
        soft_wrap=True)
    ui.console.print(
        "[muted]active in a new shell; undo with[/muted] "
        "[brand]sw completion uninstall[/brand]", soft_wrap=True)


@completion_app.command("status")
@with_global_flags
def completion_status(
    shell: str | None = typer.Option(None, "--shell", help="Which shell to check."),
) -> None:
    """Show whether tab completion is installed, and exactly which files hold it."""
    shells = [shell] if shell else sorted(_COMPLETION_LAYOUT)
    unknown = [s for s in shells if s not in _COMPLETION_LAYOUT]
    if unknown:
        ui.fail(f"unknown shell: {', '.join(unknown)}")
        ui.hint(f"known: {', '.join(sorted(_COMPLETION_LAYOUT))}")
        raise typer.Exit(2)

    rows = [row for s in shells for row in _completion_state(s)]
    running = _current_shell()

    if Ctx.as_json:
        ui.emit({"running_shell": running,
                 "entries": [{**r, "script": str(r["script"]),
                              "rc": str(r["rc"]) if r["rc"] else None} for r in rows]},
                as_json=True)
        return

    body = Text()
    body.append("  running shell  ", style="muted")
    body.append(f"{running or 'unknown'}\n\n")
    # Only a present script counts as installed. The zsh startup line is shared
    # across every tool using ~/.zfunc, so treating it as evidence reported
    # `swsh` as installed whenever `sw` was.
    installed_rows = [r for r in rows if r["installed"]]
    any_installed = bool(installed_rows)
    for row in installed_rows:
        body.append("  installed  ", style="ok")
        body.append(f"{row['program']}", style="brand")
        body.append(f" for {row['shell']}\n", style="muted")
        body.append(f"      {row['script']}\n", style="muted")
        if row["rc_line_present"]:
            body.append(f"      {row['rc']} carries the startup line\n", style="muted")
    if not any_installed:
        body.append("  not installed for any known shell\n", style="muted")
        body.append("  install with ", style="muted")
        body.append("sw completion install", style="brand")
        body.append("\n", style="muted")
    ui.console.print(Panel(body, title="completion", border_style="brand", expand=False))


@completion_app.command("install")
def completion_install(
    shell: str | None = typer.Option(None, "--shell", help="Override shell detection."),
) -> None:
    """Install tab completion.

    Writes a completion script and, for bash and zsh, a line in your shell's
    startup file. It does **not** affect the shell you are in: completion works
    in new shells, or after re-sourcing your startup file.
    """
    from typer._completion_shared import install as typer_install

    try:
        installed_shell, path = typer_install(shell=shell, prog_name="sw")
    except Exception as exc:
        ui.fail(f"could not install completion: {exc}")
        ui.hint("Pass --shell zsh (or bash, fish) to skip detection.")
        raise typer.Exit(1) from exc

    ui.console.print(f"[ok]installed[/ok] {installed_shell} completion for [brand]sw[/brand]")
    ui.console.print(f"[muted]{path}[/muted]")
    ui.console.print("[muted]Takes effect in a new shell, or after[/muted] "
                     "[brand]exec $SHELL[/brand]")
    _warn_if_not_on_path()
    ui.console.print("[muted]Remove it later with[/muted] "
                     "[brand]sw completion uninstall[/brand]")


def _warn_if_not_on_path() -> None:
    """Completion invokes `sw` by name, so it needs `sw` on PATH.

    Installed with `pip install -e .` inside a virtualenv, `sw` lives at
    `.venv/bin/sw` and exists only while that environment is active. A new
    terminal has no venv, cannot find `sw`, and the completion script then does
    nothing at all — silently, with no error to follow.
    """
    import shutil
    import sysconfig

    found = shutil.which("sw")
    venv_bin = sysconfig.get_path("scripts")
    inside_venv = bool(found) and str(Path(found).parent) == str(Path(venv_bin))
    if found and not inside_venv:
        return  # reachable independently of any environment

    ui.console.print()
    ui.console.print("[warn]note[/warn] completion runs [brand]sw[/brand] by name, and "
                     "[brand]sw[/brand] is only on PATH inside this virtualenv.")
    ui.console.print("[muted]A new terminal will not find it, so completion will "
                     "silently do nothing.[/muted]")
    ui.console.print("[muted]For an install that works everywhere:[/muted]")
    ui.console.print("  [brand]uv tool install .[/brand]   [muted]or[/muted]   "
                     "[brand]pipx install -e .[/brand]")


@completion_app.command("uninstall")
def completion_uninstall(
    shell: str | None = typer.Option(None, "--shell", help="Which shell to clean up."),
    all_progs: bool = typer.Option(False, "--all",
                                   help="Also remove completion left behind by "
                                        "the old `swsh` command."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation."),
) -> None:
    """Remove tab completion. Typer provides no way to undo its installer.

    Deletes the completion script and, for bash, the `source` line it added to
    your startup file. The zsh startup line is left alone unless nothing else
    uses `~/.zfunc`, because other tools put their completions there too.
    """
    target = shell or _current_shell()
    if target not in _COMPLETION_LAYOUT:
        ui.fail(f"cannot clean up completion for shell: {target or 'unknown'}")
        ui.hint(f"Pass --shell with one of: {', '.join(sorted(_COMPLETION_LAYOUT))}")
        raise typer.Exit(2)

    # Whatever this call finds, first-run setup must not put it back on the next
    # command. That holds for `no completion installed` too: someone uninstalling
    # pre-emptively has said what they want.
    _mark_completion_attempted()

    progs = _PROG_NAMES if all_progs else ("sw",)
    rows = [r for r in _completion_state(target) if r["program"] in progs]
    # A present script, or a startup line that names *our* script (bash). The
    # shared zsh line is handled after the loop, not per program.
    present = [r for r in rows if r["installed"] or (
        r["rc_line_present"] and not _COMPLETION_LAYOUT[target]["rc_line_shared"])]
    if not present:
        ui.console.print(f"[muted]no {target} completion installed for "
                         f"{', '.join(progs)}[/muted]")
        return

    if not yes:
        if not prompts.interactive() or Ctx.as_json:
            ui.fail("removing completion needs --yes when not running interactively")
            raise typer.Exit(2)
        for row in present:
            if row["installed"]:
                ui.console.print(f"[warn]remove[/warn] {row['script']}")
        if not typer.confirm(f"Remove {target} completion?"):
            ui.console.print("[dim]cancelled[/dim]")
            return

    for row in present:
        if row["installed"]:
            row["script"].unlink()
            ui.console.print(f"[ok]removed[/ok] {row['script']}")
        # The bash line names our script, so it is ours to remove.
        if row["rc_line_present"] and not _COMPLETION_LAYOUT[target]["rc_line_shared"]:
            _strip_rc_line(row["rc"], row["rc_line"])
            ui.console.print(f"[ok]cleaned[/ok] {row['rc']}")

    layout = _COMPLETION_LAYOUT[target]
    if layout["rc_line_shared"]:
        script_dir = layout["script"]("x").parent
        leftovers = list(script_dir.glob("_*")) if script_dir.is_dir() else []
        if leftovers:
            ui.console.print(
                f"[muted]left {layout['rc']} alone: {len(leftovers)} other "
                f"completion(s) still use {script_dir}[/muted]")
        elif layout["rc"].is_file() and layout["rc_line"] in layout["rc"].read_text():
            _strip_rc_line(layout["rc"], layout["rc_line"])
            ui.console.print(f"[ok]cleaned[/ok] {layout['rc']}")

    ui.console.print("[muted]Takes effect in a new shell.[/muted]")


def _strip_rc_line(rc: Path, line: str) -> None:
    """Drop one exact line from a startup file, leaving everything else."""
    kept = [ln for ln in rc.read_text().splitlines() if ln.strip() != line.strip()]
    rc.write_text("\n".join(kept).rstrip() + "\n")


@completion_app.command("show")
def completion_show(
    shell: str | None = typer.Option(None, "--shell", help="Override shell detection."),
) -> None:
    """Print the completion script without installing it.

    Useful when you would rather manage shell config yourself than have an
    installer edit it.
    """
    from typer._completion_shared import get_completion_script

    target = shell or _current_shell()
    try:
        typer.echo(get_completion_script(
            prog_name="sw", complete_var="_SW_COMPLETE", shell=str(target)))
    except Exception as exc:
        ui.fail(f"no completion script for shell: {target or 'unknown'} ({exc})")
        raise typer.Exit(2) from exc


# ------------------------------------------------------------------------ auth


async def _check_credentials(project: str, token: str, space: str) -> str | None:
    """None when the three values work, else one line saying what went wrong."""
    profile = Profile(name="probe", project=project, token=token, space=space)
    try:
        async with SwshClient(profile) as client:
            await client.whoami()
    except SwshError as exc:
        return str(exc)
    except httpx.HTTPError as exc:
        return _describe_network_error(exc)
    except Exception as exc:  # a mistyped space can fail in many shapes
        return f"{type(exc).__name__}: {exc}"
    return None


@app.command()
def login(
    name: str = typer.Option("default", "--name", "-n", help="Profile name."),
    project: str | None = typer.Option(None, help="Project ID."),
    token: str | None = typer.Option(None, help="API token."),
    space: str | None = typer.Option(None, help="Space, e.g. example.signalwire.com."),
) -> None:
    """Store credentials durably in ~/ (0600 config file), so a profile survives
    reboots and new terminals. Set SWSH_USE_KEYRING=1 to also mirror the token
    into the OS keyring."""
    if not (project and token and space):
        # Where the three values come from. The tool never said, and a token is
        # not something anyone has lying around.
        ui.console.print("[muted]API credentials live at[/muted] "
                         "[brand]https://<your-space>.signalwire.com/credentials[/brand]")
    project = project or typer.prompt("Project ID")
    token = token or typer.prompt("API token", hide_input=True)
    space = space or typer.prompt("Space (e.g. example.signalwire.com)")

    # Check before storing. `save_profile` wrote whatever it was given and the
    # first sign of a typo was whatever command someone ran next failing in a
    # way that looked like the tool's fault.
    checked = asyncio.run(_check_credentials(project, token, space))
    if checked is not None:
        ui.fail(checked)
        ui.hint("Nothing was saved. Check the three values and try again.")
        raise typer.Exit(1)

    saved = save_profile(name, project, token, space)
    ui.console.print(f"[ok]saved[/ok] profile [brand]{name}[/brand] for {saved.host}")
    ui.console.print(f"[muted]{config.config_path()}[/muted]")

    # Say so now rather than letting `whoami` be the first hint. Saving a profile
    # that an ambient variable immediately overrides is the single most
    # confusing thing this tool does, and the moment to mention it is here.
    summary = config.active_source_summary()
    shadow = {k: v for k, v in summary.items() if v in config.shadowing_sources(summary)}
    if shadow:
        ui.console.print(
            f"[warn]note[/warn] {', '.join(sorted(shadow))} will still come from "
            f"{', '.join(sorted(set(shadow.values())))}, which outranks the default profile."
        )
        ui.console.print(f"[muted]Unset it, or pass --profile {name} to use this "
                         "profile regardless.[/muted]")
    ui.console.print("Verify it with [brand]sw whoami[/brand].")


@app.command()
@coro
@raw_capable
async def whoami(client: SwshClient) -> None:
    """Verify credentials and show the active project — and where they came from."""
    account = await client.whoami()
    if _emit_raw(account):  # the account record, not sw's summary of the profile
        return
    # The same resolution the client used, so `whoami -P x` describes profile x.
    sources = config.active_source_summary(Ctx.profile_name)
    data = {**client.profile.redacted(), "account_status": account.get("status"),
            "friendly_name": account.get("friendly_name"),
            "credentials_from": ", ".join(sorted(set(sources.values()))) or "profile"}
    if Ctx.as_json:
        ui.emit({**data, "sources": sources}, as_json=True)
        return
    body = Text()
    for key, value in data.items():
        body.append(f"{key:>16}  ", style="muted")
        body.append(f"{value}\n", style="cool" if key == "space" else "")
    # Warn when the environment is overriding, since that is what makes
    # profile switching look broken. Say where it really comes from: exported
    # variables, or a .env file in the working directory or ~/.swsh.
    shadowing = config.shadowing_sources(sources)
    if shadowing:
        origin = ("a .env file" if all(s.startswith(".env") for s in shadowing)
                  else "environment variables")
        body.append("\nnote: ", style="warn")
        body.append(f"credentials come from {origin} ({', '.join(sorted(shadowing))}), "
                    "which outrank the default profile.\n"
                    "Pass --profile NAME to use a stored profile regardless.\n",
                    style="muted")
    ui.console.print(Panel(body, title="sw", border_style="brand", expand=False))


@app.command()
def logout(
    name: str | None = typer.Option(None, "--name", "-n", hidden=True),
) -> None:
    """Log out: deselect the active profile, keeping every profile stored.

    Logging out is not deleting. Nothing is removed, so logging back in is
    `sw profile use NAME` with nothing to re-enter. To remove a profile and its
    token, use `sw profile delete NAME`.

    Warns if an environment variable or a ``.env`` file will keep providing
    credentials afterwards — the usual reason logging out seems to do nothing.
    """
    from .config import logout as do_logout

    if name is not None:
        # This used to delete the named profile. Silently doing something
        # different now would be worse than saying so.
        ui.fail("logout takes no --name: it deselects the active profile and "
                "keeps them all.")
        ui.hint(f"To remove one: sw profile delete {name}")
        ui.hint("To switch instead: sw profile use " + name)
        raise typer.Exit(2)

    report = do_logout()
    was, kept = report["profile"], report["kept"]
    if not was:
        # Nothing changed, so there is nothing to explain. Repeating what was
        # kept and how to get back in is noise on a no-op.
        ui.console.print("[muted]already logged out[/muted]")
    else:
        ui.console.print(f"[ok]logged out[/ok] of [brand]{was}[/brand]")
        if kept:
            ui.console.print(
                f"[muted]{len(kept)} profile{'s' if len(kept) != 1 else ''} kept:[/muted] "
                f"{', '.join(kept)}"
            )
            ui.console.print(
                "[muted]log back in with[/muted] [brand]sw profile use NAME[/brand]")

    shadow = report["still_provided_by"]
    if shadow:
        srcs = ", ".join(sorted(set(shadow.values())))
        ui.fail(f"still logged in: credentials are also set via {srcs}.")
        if ".env" in shadow.values():
            ui.console.print("  remove or rename the [brand].env[/brand] in this "
                             "directory to fully log out.")
        if "env" in shadow.values():
            ui.console.print("  unset [brand]SIGNALWIRE_PROJECT_ID / _API_TOKEN / "
                             "_SPACE[/brand] to fully log out.")


@profile_app.command("list")
@with_global_flags
def profile_list() -> None:
    """List stored profiles, and say which one is actually in effect."""
    names = list_profiles()
    if Ctx.as_json:
        ui.emit({"profiles": names, "default": config.default_profile_name(),
                 "config_path": str(config.config_path()),
                 "sources": config.active_source_summary()}, as_json=True)
        return

    active = config.default_profile_name()
    shadowed = config.shadowing_sources(config.active_source_summary())

    body = Text()
    if not names:
        body.append("  no stored profiles\n", style="muted")
        body.append("  run ", style="muted")
        body.append("sw login", style="brand")
        body.append(" to create one\n", style="muted")
    for name in names:
        body.append("  ")
        body.append("* " if name == active else "  ", style="ok")
        body.append(name, style="brand" if name == active else "")
        body.append("  (active)\n" if name == active else "\n", style="muted")

    if names and config.is_logged_out():
        # Profiles kept, none selected. Without saying so, the absence of a `*`
        # looks like a rendering glitch rather than a state.
        body.append("\n  logged out", style="warn")
        body.append(" — none selected. ", style="muted")
        body.append("sw profile use NAME", style="brand")
        body.append("\n", style="muted")

    body.append(f"\n  {config.config_path()}\n", style="muted")
    if shadowed:
        # A starred profile that is not the one being used is the single most
        # confusing state this tool has, so name it here rather than leaving it
        # for `whoami` to reveal later.
        body.append("\n  note: ", style="warn")
        body.append(
            f"credentials currently come from {', '.join(sorted(shadowed))}, "
            "which outranks the default profile above.\n"
            "  Pass --profile NAME on a command to use a profile regardless.\n",
            style="muted")
    ui.console.print(Panel(body, title="profiles", border_style="brand", expand=False))


@profile_app.command("path")
def profile_path() -> None:
    """Print the config file path, for scripting or opening by hand.

    The location follows each OS's convention, so it is somewhere different on
    macOS, Linux and Windows and not worth memorising:

        $EDITOR "$(sw profile path)"
    """
    typer.echo(str(config.config_path()))


@profile_app.command("edit")
def profile_edit() -> None:
    """Open the config file in $EDITOR."""
    path = config.config_path()
    if not path.exists():
        ui.fail(f"no config file yet at {path}")
        ui.hint("Run `sw login` to create one.")
        raise typer.Exit(2)
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    try:
        raise typer.Exit(subprocess.call([editor, str(path)]))
    except FileNotFoundError as exc:
        ui.fail(f"cannot run editor {editor!r}: {exc}")
        ui.hint("Set $EDITOR, or edit `sw profile path` directly.")
        raise typer.Exit(2) from exc


@profile_app.command("use")
def profile_use(name: str) -> None:
    """Make a profile the default."""
    try:
        set_default(name)
    except ConfigError as exc:
        ui.fail(str(exc))
        raise typer.Exit(2) from exc
    ui.console.print(f"[ok]active[/ok] profile is now [brand]{name}[/brand]")

    shadowed = config.shadowing_sources(config.active_source_summary())
    if shadowed:
        # Switching the default is a no-op while something outranks it. Saying
        # nothing here is what makes profile switching look broken.
        ui.console.print(
            f"[warn]note[/warn] the default has no effect right now: credentials come "
            f"from {', '.join(sorted(shadowed))}. Unset them, or pass "
            f"--profile {name} on a command to use it regardless."
        )


def _complete_profile(incomplete: str) -> list[str]:
    """Completion over stored profile names. Local file, so no network."""
    try:
        return [n for n in list_profiles() if n.startswith(incomplete)]
    except Exception:  # completion must never be the thing that breaks
        return []


@profile_app.command("delete")
def profile_delete(
    names: list[str] = typer.Argument(..., help="Profile name(s) to remove.",
                                      autocompletion=_complete_profile),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation."),
) -> None:
    """Remove one or more profiles and their stored tokens.

    Irreversible: the API token is gone from this machine, and from the OS
    keyring if it was mirrored there. Asks first unless --yes. Takes several
    names at once. To stop using a profile without deleting it, `sw logout`.
    """
    known = list_profiles()
    missing = [n for n in names if n not in known]
    if missing:
        ui.fail(f"no such profile: {', '.join(missing)}")
        if known:
            ui.hint(f"stored profiles: {', '.join(known)}")
        else:
            ui.hint("there are no stored profiles; `sw login` creates one.")
        raise typer.Exit(2)

    active = config.default_profile_name()
    if not yes:
        if not prompts.interactive() or Ctx.as_json:
            ui.fail("deleting a profile needs --yes when not running interactively")
            raise typer.Exit(2)
        plural = "these profiles" if len(names) > 1 else "this profile"
        possessive = "their" if len(names) > 1 else "its"
        ui.console.print(
            f"[warn]This removes {plural} and {possessive} API token from this "
            f"machine.[/warn]"
        )
        if not typer.confirm(f"Delete {', '.join(names)}?"):
            ui.console.print("[dim]cancelled[/dim]")
            return

    for name in names:
        delete_profile(name)
        ui.console.print(f"[ok]deleted[/ok] {name}")

    # Deleting the active profile silently repoints the default. Saying so is the
    # difference between a tool that did something surprising and one that did
    # something explicable.
    if active in names:
        if list_profiles():
            ui.console.print(f"[muted]active profile is now[/muted] "
                             f"[brand]{config.default_profile_name()}[/brand]")
        else:
            ui.console.print("[muted]no profiles left; run[/muted] [brand]sw login[/brand]")

    shadow = config.shadowing_sources(config.active_source_summary())
    if shadow:
        ui.console.print(
            f"[warn]note[/warn] credentials still come from "
            f"{', '.join(sorted(shadow))}, so sw is not logged out."
        )


@app.command()
@coro
async def doctor(client: SwshClient) -> None:
    """Check credentials, the LaML surface, the tunnel and installed plugins.

    Runs the checks that the rest of sw depends on: whether credentials work,
    whether the LaML surface is reachable, which identifiers recent calls carry,
    whether a tunnel binary is available, whether any plugin is broken, and
    whether a previous `sw listen` left numbers to restore.
    """
    checks: list[tuple[str, bool, str]] = []

    try:
        account = await client.whoami()
        checks.append(("credentials", True,
                       f"{client.profile.project} on {client.profile.host} "
                       f"({account.get('friendly_name', 'unnamed')})"))
    except SwshError as exc:
        checks.append(("credentials", False, str(exc)))
        _report(checks)
        raise typer.Exit(1) from exc

    try:
        await client.verify_compat()
        checks.append((
            "laml surface", True,
            f"reachable; sending {client.compat_encoding}-encoded bodies",
        ))
    except SwshError as exc:
        checks.append(("laml surface", False, str(exc)))

    try:
        recent = await client.list_calls(limit=20)
        if recent:
            native = sum(1 for c in recent if c.ref.call_id)
            laml = len(recent) - native
            detail = (f"{len(recent)} recent legs from the voice log; {native} native "
                      f"(transfer/play/dtmf work), {laml} LaML (compat control only)")
            checks.append(("call identifiers", True, detail))
        else:
            checks.append(("call identifiers", True, "no recent calls to sample"))
    except SwshError as exc:
        checks.append(("call identifiers", False, str(exc)))

    import shutil

    ngrok = shutil.which("ngrok")
    checks.append(("tunnel", bool(ngrok), ngrok or "ngrok not found; use --public-url"))

    from .events.rewrite import has_pending_restore

    for found in plugin_host.everything(_builtin_names()):
        if found.status in ("broken", "shadowed"):
            checks.append((f"plugin {found.name}", False,
                           f"{found.package} {found.version}: {found.detail}"))

    if has_pending_restore():
        checks.append(("pending restore", False,
                       "a previous `sw listen` left rewritten numbers; "
                       "run `sw listen --restore`"))

    _report(checks)
    if any(not ok for _, ok, _ in checks):
        raise typer.Exit(1)


def _report(checks: list[tuple[str, bool, str]]) -> None:
    if Ctx.as_json:
        ui.emit([{"check": n, "ok": ok, "detail": d} for n, ok, d in checks], as_json=True)
        return
    for name, ok, detail in checks:
        mark = Text("  ok  ", style="ok") if ok else Text(" fail ", style="bad")
        ui.console.print(mark + Text(f"{name:<18}", style="bold") + Text(detail, style="muted"))


@app.command()
@with_global_flags
def docs(
    output: str | None = typer.Option(None, "--output", "-o",
                                      help="Write to this file instead of stdout."),
    table: bool = typer.Option(False, "--list", "-l",
                               help="One line per resource: key, operations, API."),
) -> None:
    """Generate the resource reference straight from the registry.

    The docs are rendered from the same registry that drives the CLI and TUI, so
    they cannot drift from what sw actually does: every resource, its command
    group, operations, backing API and editable fields, in Markdown. `--list`
    prints the summary table instead.
    """
    if table:
        _resources_table()
        return
    text = _render_docs()
    if output:
        from pathlib import Path

        Path(output).write_text(text, encoding="utf-8")
        ui.console.print(f"[ok]wrote[/ok] {output}  ({len(resources.RESOURCES)} resources)")
    else:
        ui.console.print(text)


def _resources_table() -> None:
    """Every resource as one row: what `sw --help` shows, with the ops and API."""
    rows = [
        {
            "command": f"sw {r.key}",
            "resource": r.title,
            "group": resources.group_title(r.group),
            "ops": "".join(c for c in "LCRUD" if r.can(c)) or "live",
            "api": r.api or r.namespace or "-",
        }
        for r in resources.RESOURCES
    ]
    ui.emit(rows, as_json=Ctx.as_json, renderer=lambda r: ui.rows_table(
        r, ["command", "resource", "group", "ops", "api"],
        title="resources  (L=list C=create R=read U=update D=delete)",
    ))


def _commands_for(r: resources.Resource) -> list[str]:
    """The `sw <key> …` commands a resource offers, verbs first, then extras."""
    verbs = [f"sw {r.key} {r.verb(op)}" for op in _cli_ops(r)]
    extras = [f"sw {r.key} {e.command}" for e in r.extras]
    return verbs + extras


def _render_docs() -> str:
    """Markdown for every registered resource, grouped as the menus are."""
    from collections import defaultdict

    by_group: dict[str, list[Any]] = defaultdict(list)
    for r in resources.RESOURCES:
        by_group[r.group].append(r)

    lines: list[str] = [
        f"# sw resource reference  (v{__version__})",
        "",
        "Generated from the registry — the single source of truth behind both "
        "the CLI and the TUI. Do not edit by hand; run `sw docs`.",
        "",
        f"{len(resources.RESOURCES)} resources across {len(by_group)} groups, "
        f"out of {spec.total()} operations the platform exposes.",
        "",
        "Anything not listed here is still reachable with `sw api`, which "
        "resolves any operation id from the same catalog: `sw api --list` "
        "enumerates all of them. That is how the compatibility API is used, "
        "since it is deliberately not modelled as resources.",
        "",
    ]
    ordered = [g for g in resources.GROUPS if g in by_group]
    ordered += sorted(g for g in by_group if g not in resources.GROUPS)
    for group in ordered:
        lines.append(f"## {resources.group_title(group)}")
        lines.append("")
        for r in sorted(by_group[group], key=lambda x: x.key):
            ops = "".join(c for c in "LCRUD" if r.can(c)) or "live"
            api = r.api or r.namespace or "-"
            lines.append(f"### `{r.key}` — {r.title}")
            lines.append("")
            lines.append(f"- operations: `{ops}`  (L=list C=create R=read U=update D=delete)")
            commands = _commands_for(r)
            if commands:
                lines.append("- commands: " + ", ".join(f"`{c}`" for c in commands))
            lines.append(f"- backend: {r.transport} · {api}")
            if r.help:
                lines.append(f"- {r.help}")
            editable = [f for f in r.fields if f.on_create or f.on_update]
            if editable:
                lines.append("- fields:")
                for f in editable:
                    req = " *(required)*" if f.required else ""
                    kind = f.kind + (f"={list(f.choices)}" if f.choices else "")
                    lines.append(f"  - `{f.name}` ({kind}){req}"
                                 + (f" — {f.help}" if f.help else ""))
            lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------- plugins


@plugins_app.command("list")
@with_global_flags
def plugins_list() -> None:
    """Every installed plugin: its command, package, version and state.

    A plugin is a package declaring a `swsh.plugins` entry point. Loaded ones
    run as `sw <name>`; a broken one says why, and a shadowed one lost its name
    to a built-in or to another plugin and is not run at all.
    """
    rows = [f.as_json() for f in plugin_host.everything(_builtin_names())]
    if not rows and not Ctx.as_json:
        ui.console.print("[muted]no plugins installed[/muted]")
        ui.hint('A plugin is a package with a "swsh.plugins" entry point; '
                "install it into the environment sw runs from.")
        return
    ui.emit(rows, as_json=Ctx.as_json, renderer=lambda r: ui.rows_table(
        r, ["name", "package", "version", "status", "detail"], title="plugins",
        overflow="fold"))


# ----------------------------------------------------------------------- calls


@calls_app.command("list")
@coro
async def calls_list(
    client: SwshClient,
    live: bool = typer.Option(False, "--live", help="Only calls that are up right now."),
    status: str | None = typer.Option(
        None, "--status",
        help="Filter by status: an engine's word (in-progress, ended) or a state (answered)."),
    limit: int = typer.Option(25, "--limit", "-n"),
) -> None:
    """List calls, newest first, whichever engine carried them.

    This is the voice log seen as calls: LaML, RELAY, SIP and video legs all
    appear, with the full id so it can be pasted into `sw calls show` or a
    control command. `--live` keeps only legs that are up right now.
    """
    calls = await (
        client.live_calls(limit) if live else client.list_calls(status=status, limit=limit)
    )
    if Ctx.as_json:
        ui.emit([_call_json(c) for c in calls], as_json=True)
        return
    ui.console.print(ui.calls_table(calls, title="live calls" if live else "calls"))


@calls_app.command("show")
@coro
@raw_capable
async def calls_show(client: SwshClient, sid: str) -> None:
    """Show one call in full."""
    call = await client.get_call(sid)
    if _emit_raw(call.raw):
        return
    ui.emit(_call_json(call) if Ctx.as_json else call.raw, as_json=Ctx.as_json)
    if not Ctx.as_json:
        ui.console.print(ui.calls_table([call]))


@calls_app.command("dial")
@coro
async def calls_dial(
    client: SwshClient,
    to: str = typer.Argument(..., help="Destination in E.164."),
    from_: str | None = typer.Option(None, "--from", "-f",
                                     help="Caller ID you own. Prompted if omitted."),
    url: str | None = typer.Option(None, "--url", help="cXML URL driving the call."),
    tts: str | None = typer.Option(None, "--tts", help="Speak this, then hang up."),
    callback: str | None = typer.Option(None, "--status-callback"),
) -> None:
    """Place an outbound call.

    ``--tts`` inlines a cXML document, so a one-off test call needs no hosted
    URL. Omit ``--from`` and sw offers your voice-capable numbers to pick from.
    """
    if not url and not tts:
        ui.fail("give either --url or --tts")
        raise typer.Exit(2)
    if not from_:
        if not prompts.interactive() or Ctx.as_json:
            ui.fail("--from is required (non-interactive)")
            raise typer.Exit(2)
        from_ = await prompts.choose_number(client, channel="voice",
                                            prompt="Call from which number?")
    call = await client.dial(to=to, from_=from_, url=url, say=tts, status_callback=callback)
    ui.emit(_call_json(call), as_json=Ctx.as_json,
            renderer=lambda d: f"[ok]dialing[/ok] {d['sid'] or d['call_id']}")


@calls_app.command("hangup")
@coro
async def calls_hangup(client: SwshClient, ids: list[str]) -> None:
    """End one or more calls."""
    for identifier in ids:
        try:
            await client.hangup(identifier)
            ui.console.print(f"[ok]ended[/ok] {identifier}")
        except SwshError as exc:
            ui.fail(f"{identifier}: {exc}")


@calls_app.command("transfer")
@coro
async def calls_transfer(client: SwshClient, call_id: str, dest: str) -> None:
    """Transfer a call. Needs the native call id, not a CA SID."""
    await client.transfer(call_id, dest)
    ui.console.print(f"[ok]transferred[/ok] {call_id} → {dest}")


@calls_app.command("play")
@coro
async def calls_play(client: SwshClient, call_id: str,
                     tts: str = typer.Option(..., "--tts")) -> None:
    """Speak into a live call."""
    await client.play_tts(call_id, tts)
    ui.console.print(f"[ok]playing[/ok] on {call_id}")


@calls_app.command("digits")
@coro
async def calls_digits(client: SwshClient, call_id: str, digits: str) -> None:
    """Send DTMF into a live call."""
    await client.send_digits(call_id, digits)
    ui.console.print(f"[ok]sent[/ok] {digits} to {call_id}")


@calls_app.command("record")
@coro
async def calls_record(client: SwshClient, identifier: str) -> None:
    """Start recording a live call."""
    result = await client.start_recording(identifier)
    ui.emit(result, as_json=Ctx.as_json,
            renderer=lambda d: f"[ok]recording[/ok] {d.get('sid', identifier)}")


@calls_app.command("stream")
@coro
async def calls_stream(client: SwshClient, call_id: str,
                       url: str = typer.Option(..., "--to", help="wss:// audio sink.")) -> None:
    """Fork call audio to a WebSocket."""
    await client.call_command(call_id, "stream", url=url)
    ui.console.print(f"[ok]streaming[/ok] {call_id} → {url}")


@calls_app.command("tap")
@coro
async def calls_tap(client: SwshClient, call_id: str,
                    url: str = typer.Option(..., "--to", help="wss:// tap sink.")) -> None:
    """Tap (media mirror) a live call to a WebSocket."""
    await client.call_command(call_id, "tap", device={"type": "ws", "uri": url})
    ui.console.print(f"[ok]tapping[/ok] {call_id} → {url}")


@calls_app.command("detect")
@coro
async def calls_detect(client: SwshClient, call_id: str,
                       kind: str = typer.Option("machine", "--type",
                                                help="machine, fax, or digit.")) -> None:
    """Run detection (answering machine / fax / DTMF) on a live call."""
    await client.call_command(call_id, "detect", detect={"type": kind})
    ui.console.print(f"[ok]detecting[/ok] {kind} on {call_id}")


@calls_app.command("ai-message")
@coro
async def calls_ai_message(client: SwshClient, call_id: str, message: str,
                           role: str = typer.Option("user", "--role")) -> None:
    """Inject a message into an AI agent on a live call."""
    await client.call_command(call_id, "ai_message", message_text=message, role=role)
    ui.console.print(f"[ok]sent to AI[/ok] on {call_id}")


# -------------------------------------------------------------------- messages


@messages_app.command("send")
@coro
@raw_capable
async def msg_send(
    client: SwshClient,
    to: str = typer.Argument(...),
    from_: str = typer.Option(..., "--from", "-f"),
    body: str | None = typer.Option(None, "--body", "-b"),
    media: list[str] = typer.Option([], "--media", "-m", help="Media URL, repeatable."),
    callback: str | None = typer.Option(None, "--status-callback"),
) -> None:
    """Send an SMS or MMS."""
    if not body and not media:
        ui.fail("give --body, --media, or both")
        raise typer.Exit(2)
    message = await client.send_message(to=to, from_=from_, body=body, media=media,
                                        status_callback=callback)
    if _emit_raw(message.raw):
        return
    ui.emit({"sid": message.sid, "state": message.state}, as_json=Ctx.as_json,
            renderer=lambda d: f"[ok]sent[/ok] {d['sid']} ({d['state']})")


# --------------------------------------------------------------------- numbers


# `list`, `get`, `buy`, `update`, `release` and the E911 actions are generated
# from the registry; only the search needs hand-written flags.


@numbers_app.command("search")
@coro
@raw_capable
async def numbers_search(
    client: SwshClient,
    area_code: str | None = typer.Option(None, "--area-code", "-a"),
    contains: str | None = typer.Option(None, "--contains", help="3-7 digits anywhere."),
    starts_with: str | None = typer.Option(None, "--starts-with", help="3-7 leading digits."),
    ends_with: str | None = typer.Option(None, "--ends-with", help="3-7 trailing digits."),
    region: str | None = typer.Option(None, "--region", help="State or province, e.g. AL."),
    city: str | None = typer.Option(None, "--city", help="Requires --region."),
    number_type: str = typer.Option("local", "--type", help="local or toll-free."),
    limit: int = typer.Option(25, "--limit", "-n"),
) -> None:
    """Search numbers available to buy.

    The digit filters (--contains / --starts-with / --ends-with) each take 3-7
    digits, no wildcards. Toll-free numbers have no geography, so --area-code /
    --region / --city are ignored for `--type toll-free`. Pass the E.164 from the
    results to `sw numbers buy`.
    """
    if city and not region:
        ui.fail("--city only works together with --region")
        raise typer.Exit(2)
    for label, value in (("--contains", contains), ("--starts-with", starts_with),
                         ("--ends-with", ends_with)):
        if value and (not value.isdigit() or not 3 <= len(value) <= 7):
            ui.fail(f"{label} must be 3-7 digits, no letters or wildcards")
            raise typer.Exit(2)

    tollfree = number_type == "toll-free"
    params = {
        "areacode": None if tollfree else area_code,
        "region": None if tollfree else region,
        "city": None if tollfree else city,
        "contains": contains, "starts_with": starts_with, "ends_with": ends_with,
        "number_type": number_type, "max_results": limit,
    }
    payload = await client.call_sdk(
        "phone_numbers.search", **{k: v for k, v in params.items() if v is not None}
    )
    if _emit_raw(payload):
        return
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    ui.emit(rows, as_json=Ctx.as_json, renderer=lambda r: ui.rows_table(
        r,
        ["e164", "national_number_formatted", "region", "rate_center", "capabilities"],
        title="available numbers"))


# ------------------------------------------------------------------------ logs


# What a voice-log event row actually carries (verified live 2026-09-09). The
# previous guess (type/created_at/description) matched nothing and drew dashes.
LOG_EVENT_COLUMNS = ["event_at", "name", "level", "details"]


# `sw logs list` and `sw logs get` are generated from the registry; the event
# timeline is hand-written for its column shaping.
@logs_app.command("events")
@coro
@raw_capable
async def logs_events(client: SwshClient, log_id: str) -> None:
    """The full event timeline for one call."""
    payload = await client.voice_log_events(log_id)
    if _emit_raw(payload):
        return
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    # The event rows are {event_at, name, level, details}; `details` is a dict
    # that is empty for state changes and carries the engine payload otherwise.
    ui.emit(rows, as_json=Ctx.as_json, renderer=lambda r: ui.rows_table(
        r, LOG_EVENT_COLUMNS, title=f"events for {log_id}"))


# ------------------------------------------------------------------------- api
#
# The escape hatch. Every operation the platform has, whether or not the registry
# models it, reachable by path or by catalog operation id. This is what keeps a
# missing resource from being a dead end, and it is how the compatibility API
# (excluded from the registry) stays usable.


# The compat surface wants urlencoded bodies; everything else wants JSON. Getting
# this wrong produces a confusing 4xx rather than an obvious error, so it is
# inferred from the path and only overridden on request. See
# SwshClient.verify_compat for why form is the right default there.
_FORM_PREFIX = "/api/laml/"

# Placeholders filled from the profile rather than asked for. {AccountSid} alone
# appears in 52 of the 79 compat operations.
_PROFILE_PLACEHOLDERS = ("AccountSid", "project", "project_id", "ProjectId")

def _complete_operation(incomplete: str) -> list[tuple[str, str]]:
    """Completion over every catalog operation. Pure, so <TAB> hits no network."""
    out: list[tuple[str, str]] = []
    for op in spec.operations():
        if op.operation_id.startswith(incomplete):
            out.append((op.operation_id, f"{op.method} {op.path}"))
    return out[:200]


def _parse_kv(pairs: list[str], *, sep: str = "=",
              what: str = "key=value") -> list[tuple[str, str]]:
    """Split repeated ``key=value`` flags, keeping order and duplicates.

    Duplicates matter: repeating a key is how a caller sends a list to the LaML
    surface (``-f StatusCallbackEvent=initiated -f StatusCallbackEvent=answered``),
    so this cannot collapse into a dict.
    """
    out: list[tuple[str, str]] = []
    for pair in pairs:
        if sep not in pair:
            ui.fail(f"expected {what}, got '{pair}'")
            raise typer.Exit(2)
        key, _, value = pair.partition(sep)
        out.append((key.strip(), value.strip() if sep == ":" else value))
    return out


def _typed(value: str) -> Any:
    """`-F` semantics: JSON-ish scalars become real types, @file reads a file."""
    if value.startswith("@"):
        path = Path(value[1:])
        try:
            return path.read_text()
        except OSError as exc:
            ui.fail(f"cannot read {path}: {exc}")
            raise typer.Exit(2) from exc
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in ("null", "~"):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _collect_body(fields: list[str], raw_fields: list[str]) -> dict[str, Any]:
    """Merge -F and -f into one body, repeating keys into lists."""
    body: dict[str, Any] = {}

    def add(key: str, value: Any) -> None:
        if key in body:
            existing = body[key]
            body[key] = [*existing, value] if isinstance(existing, list) else [existing, value]
        else:
            body[key] = value

    for key, value in _parse_kv(raw_fields):
        add(key, value)
    for key, value in _parse_kv(fields):
        add(key, _typed(value))
    return body


def _resolve_endpoint(endpoint: str) -> tuple[str, str | None]:
    """Turn what was typed into (path, default_method).

    A path is used as given. An operation id is resolved through the catalog, so
    the method and the full route come for free. An id that collides across APIs
    is reported with its options rather than guessed at, which is why
    ``spec.candidates`` exists.
    """
    if "/" in endpoint:
        path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        return path, None

    if ":" in endpoint:
        api, _, operation_id = endpoint.partition(":")
        operation = spec.get(operation_id, api=api)
        if operation is None:
            ui.fail(f"no operation '{operation_id}' in {api}. Try `sw api --list {api}`.")
            raise typer.Exit(2)
        return operation.path, operation.method

    matches = spec.candidates(endpoint)
    if not matches:
        ui.fail(f"unknown endpoint '{endpoint}'. Pass a path, or see `sw api --list`.")
        raise typer.Exit(2)
    if len(matches) > 1:
        ui.fail(
            f"'{endpoint}' exists in {len(matches)} APIs. Qualify it:\n  "
            + "\n  ".join(f"{m.key}   ({m.method} {m.path})" for m in matches)
        )
        raise typer.Exit(2)
    return matches[0].path, matches[0].method


def _fill_placeholders(path: str, params: list[tuple[str, str]],
                       positional: str | None, project: str) -> str:
    """Substitute {Name} segments from the profile, -p values, then a bare id."""
    supplied = dict(params)
    for name in _PROFILE_PLACEHOLDERS:
        supplied.setdefault(name, project)

    for name, value in supplied.items():
        path = path.replace("{" + name + "}", str(value))

    remaining = re.findall(r"\{([^}]+)\}", path)
    if remaining and positional is not None and len(remaining) == 1:
        # One placeholder left and one bare argument: the same convenience
        # client._invoke_rest offers, so `sw api retrieve_fax FX123` works.
        path = path.replace("{" + remaining[0] + "}", positional)
        remaining = []
    if remaining:
        ui.fail(
            f"unfilled path parameter(s): {', '.join(remaining)}. "
            f"Pass -p {remaining[0]}=…"
        )
        raise typer.Exit(2)
    return path


def _render_api_list(api: str | None) -> list[dict[str, str]]:
    ops = spec.by_api(api) if api else list(spec.operations())
    if api and not ops:
        ui.fail(f"unknown API '{api}'. Known: {', '.join(sorted(spec.apis()))}")
        raise typer.Exit(2)
    return [
        {"operation": op.operation_id, "api": op.api, "method": op.method, "path": op.path}
        for op in sorted(ops, key=lambda o: (o.api, o.operation_id))
    ]


@app.command("api")
@coro
@raw_capable
async def api_command(
    client: SwshClient,
    endpoint: str = typer.Argument(
        None, help="A path (/api/relay/rest/phone_numbers) or a catalog "
                   "operation id (send_fax, or compatibility-api:create_queue).",
        autocompletion=_complete_operation),
    resource_id: str = typer.Argument(None, help="Fills a single remaining path parameter."),
    method: str = typer.Option(None, "--method", "-X",
                               help="HTTP method. Defaults to the catalog's, else GET."),
    fields: list[str] = typer.Option([], "--field", "-F",
                                     help="key=value, typed. @file reads a file. Repeatable."),
    raw_fields: list[str] = typer.Option([], "--raw-field", "-f",
                                         help="key=value, always a string. Repeatable."),
    params: list[str] = typer.Option([], "--param", "-p",
                                     help="key=value to fill a {placeholder}. Repeatable."),
    query: list[str] = typer.Option([], "--query", "-q",
                                    help="key=value query-string parameter. Repeatable."),
    headers: list[str] = typer.Option([], "--header", "-H",
                                      help="key:value request header. Repeatable."),
    input_file: str = typer.Option(None, "--input",
                                   help="Body from a file, or - for stdin. Beats -F/-f."),
    form: bool = typer.Option(False, "--form", help="Force urlencoded body."),
    json_body_flag: bool = typer.Option(False, "--json-body", help="Force a JSON body."),
    include: bool = typer.Option(False, "--include", "-i",
                                 help="Print the status line and response headers first."),
    paginate: bool = typer.Option(False, "--paginate", help="Follow next links and merge pages."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the request. Send nothing."),
    force: bool = typer.Option(False, "--force", "-y", help="Skip the confirmation on a write."),
    silent: bool = typer.Option(False, "--silent", help="Suppress the response body."),
    list_ops: bool = typer.Option(False, "--list",
                                  help="Enumerate catalog operations instead of calling one. "
                                       "Pass an API name as the argument to scope it."),
) -> None:
    """Call any SignalWire endpoint directly.

    The escape hatch: anything the registry does not model is still one command
    away, including the whole compatibility API. An operation id resolves its own
    method and path from the catalog, and {AccountSid} fills from your profile.

    \b
    sw api --list compatibility-api
    sw api /api/relay/rest/phone_numbers | jq '.data | length'
    sw api list_subscribers
    sw api send_fax -f To=+15551234567 -f From=+15559876543 -f MediaUrl=https://x/f.pdf
    sw api delete_fax FX123 -X DELETE --force

    Output is the response body verbatim, so it pipes into jq. A write prompts
    for confirmation unless --force; without a terminal it errors instead.
    """
    # This command is `--raw` by construction: everything below echoes the
    # response as it came. So the flag neither silences it nor goes unanswered.
    _raw_already()

    if list_ops:
        # `--list` takes its optional API filter from the endpoint argument,
        # because Click has no optional-valued option.
        rows = _render_api_list(endpoint)
        ui.emit(rows, as_json=Ctx.as_json, renderer=lambda r: ui.rows_table(
            r, ["operation", "api", "method", "path"],
            title=f"{len(r)} operations" + (f" in {endpoint}" if endpoint else ""),
            # The path is the whole point of this listing, so it must not be
            # truncated to fit; fold it instead.
            overflow="fold",
        ))
        return

    if not endpoint:
        ui.fail("give an endpoint, or use --list to see what exists")
        raise typer.Exit(2)

    path, catalog_method = _resolve_endpoint(endpoint)
    path = _fill_placeholders(path, _parse_kv(params), resource_id, client.profile.project)
    verb = (method or catalog_method or "GET").upper()

    # Body: --input wins, then the -F/-f fields.
    body: Any = None
    if input_file:
        text = sys.stdin.read() if input_file == "-" else Path(input_file).read_text()
        try:
            body = json.loads(text)
        except json.JSONDecodeError as exc:
            ui.fail(f"--input is not valid JSON: {exc}")
            raise typer.Exit(2) from exc
    elif fields or raw_fields:
        body = _collect_body(fields, raw_fields)

    if form and json_body_flag:
        ui.fail("pass either --form or --json-body, not both")
        raise typer.Exit(2)
    use_form = form or (path.startswith(_FORM_PREFIX) and not json_body_flag)

    query_params = dict(_parse_kv(query))
    header_map = dict(_parse_kv(headers, sep=":", what="key:value"))

    if dry_run:
        # soft_wrap so a long URL is not hard-wrapped mid-path, which makes it
        # unreadable and uncopyable — the one thing a dry run is for.
        ui.console.print(f"[brand]{verb}[/brand] {client.profile.base_url}{path}",
                         soft_wrap=True)
        if query_params:
            ui.console.print(f"  query    {query_params}", soft_wrap=True)
        if header_map:
            ui.console.print(f"  headers  {header_map}", soft_wrap=True)
        if body is not None:
            ui.console.print(f"  encoding {'form' if use_form else 'json'}")
            ui.console.print(f"  body     {json.dumps(body, default=str)}", soft_wrap=True)
        ui.console.print("[dim]dry run: nothing was sent[/dim]")
        return

    if verb != "GET" and not force:
        # A write through the escape hatch skips every other guard in the tool,
        # so it asks first. With no terminal to ask, it refuses rather than
        # proceeding silently, matching how prompts.py treats missing values.
        if not prompts.interactive() or Ctx.as_json:
            ui.fail(f"{verb} {path} needs --force when not running interactively")
            raise typer.Exit(2)
        if not typer.confirm(f"{verb} {path} — send it?"):
            ui.console.print("[dim]cancelled[/dim]")
            return

    pages: list[Any] = []
    seen: set[str] = set()
    next_path: str | None = path
    response = None

    while next_path is not None:
        if next_path in seen:
            break  # a malformed next link must not loop forever
        seen.add(next_path)
        response = await client.raw_request(
            verb, next_path,
            params=query_params or None,
            json_body=None if use_form else body,
            form_body=body if use_form and isinstance(body, dict) else None,
            headers=header_map or None,
        )
        if include:
            ui.console.print(f"HTTP {response.status_code}")
            for key, value in response.headers.items():
                ui.console.print(f"{key}: {value}")
            ui.console.print("")
        if response.status_code >= 400:
            if response.text and not silent:
                typer.echo(response.text)
            ui.fail(_describe(response.status_code, _safe_json(response)))
            raise typer.Exit(1)
        if not paginate:
            break
        payload = _safe_json(response)
        pages.append(payload)
        next_path = client_next_page(payload)
        # Only the first request carries a body; page links are plain GETs.
        body, use_form, query_params, verb = None, False, {}, "GET"

    if silent or response is None:
        return

    if paginate:
        typer.echo(json.dumps(_merge_pages(pages), default=str))
    else:
        # Verbatim, so `| jq` sees exactly what the platform returned.
        if response.text:
            typer.echo(response.text)


def _safe_json(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


def _merge_pages(pages: list[Any]) -> Any:
    """One object whose `data` is every page's rows concatenated.

    `gh --paginate` emits one JSON document per page, which is awkward to pipe.
    A single merged object keeps `sw api --paginate | jq '.data'` working. The
    paging links are dropped because they describe pages already followed.
    """
    if not pages:
        return {}
    if not isinstance(pages[0], dict):
        return pages
    merged = {k: v for k, v in pages[0].items() if k not in ("links", "next_page_uri")}
    rows: list[Any] = []
    for page in pages:
        if isinstance(page, dict):
            found = page.get("data")
            if isinstance(found, list):
                rows.extend(found)
    if rows or "data" in merged:
        merged["data"] = rows
    return merged


# ------------------------------------------------------------------- resources


# ------------------------------------------------------- resource command groups
#
# One command group per registry resource, named by its key, holding its CRUD
# verbs and every Extra. Generated here, from the same registry the TUI and
# `sw docs` read, so the three cannot describe different operations. A resource
# may rename a verb (`numbers`: buy / release) and an Extra may name its command
# (`logs events`); nothing is aliased.


def _parse_pairs(pairs: list[str], target: Any) -> dict[str, Any]:
    """Turn repeated ``key=value`` flags into a typed request body.

    Values are coerced using the field's declared type where the registry knows
    it. Unknown keys pass through as strings, so fields sw has not catalogued
    are still settable.
    """
    known = {f.name: f for f in target.fields}
    body: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            ui.fail(f"expected key=value, got '{pair}'")
            raise typer.Exit(2)
        key, _, value = pair.partition("=")
        key = key.strip()
        field_def = known.get(key)
        if field_def is None:
            body[key] = value
            continue
        try:
            coerced = resources.coerce(field_def, value)
        except ValueError as exc:
            ui.fail(str(exc))
            raise typer.Exit(2) from exc
        if coerced is not None:
            body[key] = coerced
    return body


# `read`, `update` and `delete` take an id as their argument, so a placeholder
# in their route is the thing the user typed. `list` and `create` take no id,
# so a placeholder in *their* route is one the command has nowhere to accept.
_ID_TAKING = ("read", "update", "delete")


def _cli_ops(resource: resources.Resource) -> list[str]:
    """The CRUD ops the CLI offers.

    The declared caps plus any CRUD route in ``rest_ops`` — which is what the
    coverage gate counts as reachable — **less the ones whose route needs a
    parent id the command cannot take**. `sw orders list` and `sw campaigns
    list` were generated from `rest_ops` and answered `needs a resource id`
    every single time, for every user, on every project. A command that cannot
    succeed is worse than a missing one: it reads as a broken tool rather than
    as a thing reached another way. Both listings are reached through their
    parent (`sw brands campaigns <id>`, `sw brands orders <campaign-id>`).
    """
    ops = [op for letter, op in (("L", "list"), ("C", "create"), ("R", "read"),
                                 ("U", "update"), ("D", "delete"))
           if resource.can(letter) or op in resource.rest_ops]
    return [op for op in ops
            if op in _ID_TAKING
            or not resources.route_placeholders(resource.rest_ops.get(op, ""),
                                                resource.api)]


def _registered(sub: typer.Typer) -> set[str]:
    return {c.name for c in sub.registered_commands if c.name}


def _param(name: str, annotation: Any, default: Any) -> inspect.Parameter:
    return inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY,
                             annotation=annotation, default=default)


_CLIENT_PARAM = inspect.Parameter("client", inspect.Parameter.POSITIONAL_OR_KEYWORD)


def _command(sub: typer.Typer, name: str, fn: Any, params: list[inspect.Parameter],
             doc: str) -> None:
    """Register ``fn(client, **kwargs)`` as ``name`` with an explicit signature.

    The body takes ``**kwargs`` so one function serves every resource; the
    signature tells Typer (and ``coro``) which arguments and options it has.
    """
    fn.__signature__ = inspect.Signature([_CLIENT_PARAM, *params])
    fn.__name__ = f"{sub.info.name}_{name}".replace("-", "_")
    fn.__doc__ = doc
    sub.command(name)(coro(fn))


def _discovered_columns(rows: list[dict[str, Any]], limit: int = 7) -> list[str]:
    """Columns for rows the registry has no declaration for (an extra's result)."""
    if not rows:
        return ["id"]
    scalar = [k for k, v in rows[0].items()
              if isinstance(v, (str, int, float, bool, type(None)))]
    return sorted(scalar, key=lambda k: (k not in ("id", "sid", "name"), k))[:limit]


def _show_rows(rows: list[dict[str, Any]], columns: list[str], title: str) -> None:
    if Ctx.as_json:
        ui.emit(rows, as_json=True)
        return
    if Ctx.csv:
        ui.emit_csv(rows, columns)
        return
    ui.console.print(ui.rows_table(rows, columns, title=title))


def _sorted_rows(rows: list[dict[str, Any]], field: str | None,
                 descending: bool) -> list[dict[str, Any]]:
    """Rows in the order someone asked for, nulls last either way.

    A null sorting as "smallest" puts every unnamed row at the top of an
    ascending sort and every named one at the top of a descending one, which
    makes `--desc` look like it did something other than reverse. Missing
    values are simply last.
    """
    if not field:
        return rows

    def key(row: dict[str, Any]) -> str:
        value = resources.cell(row, field)
        # One comparable type: rows mix strings, numbers and nulls in the same
        # column, and sorting them against each other is a TypeError.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f"{float(value):020.4f}"
        return str(value).lower()

    # Partitioned rather than sorted on a (is_null, value) key, because
    # `reverse=True` would flip that flag too and float every unnamed row to
    # the top — which is what `--desc` did on `sw numbers list --sort name`.
    filled = [r for r in rows if resources.cell(r, field) not in (None, "")]
    empty = [r for r in rows if resources.cell(r, field) in (None, "")]
    return sorted(filled, key=key, reverse=descending) + empty


def _chosen_columns(spec_text: str | None, resource: resources.Resource,
                    rows: list[dict[str, Any]]) -> list[str]:
    """``--columns`` if given, else whatever the registry would have shown.

    Unknown names are not silently dropped: asking for a column and getting a
    table without it, with no complaint, is how someone concludes the data is
    missing rather than the name is.
    """
    if not spec_text:
        return resources.columns_for(resource, rows)
    wanted = [c.strip() for c in spec_text.split(",") if c.strip()]
    if rows:
        unknown = [c for c in wanted if not any(resources.has_key(r, c) for r in rows)]
        if unknown:
            ui.fail(f"no such column: {', '.join(unknown)}")
            present = sorted({k for row in rows for k in row})
            ui.hint(f"this row has: {', '.join(present[:18])}")
            raise typer.Exit(2)
    return wanted


# A walk has to stop somewhere. At the platform's 50-row default page this is
# 5,000 rows, which is past any listing a person reads and well past anything
# `--limit` asks for; it exists so a project with a runaway collection cannot
# hang a script rather than to ration ordinary use.
_PAGE_CAP = 100


async def _list_rows(client: SwshClient, resource: resources.Resource, *,
                     limit: int | None = None, **params: Any) -> list[dict[str, Any]]:
    """The list route's rows, following the API's paging until ``limit`` is met.

    This used to be one request, with ``--limit`` applied afterwards as a slice
    of whatever that single page happened to hold. Two things followed, both
    silent: ``sw logs list -n 200`` answered with 50 rows and no sign there were
    more, and ``--match`` — which sifts client-side over these rows — reported
    *no rows* for records that exist further down the collection. A search that
    confidently says "not found" about something present is worse than one that
    is slow.

    ``limit=None`` means every page, which is what a search needs. The walk is
    the one already proven in ``routing._bin_index``: ``next_page`` reads both
    paging styles the platform uses, and a payload that carries neither — an SDK
    response, a bare list — ends the loop on the first pass.
    """
    payload = await client.invoke(resource, "list", **params)
    rows = resources.unwrap(payload, resource.data_key)
    seen: set[str] = set()
    for _ in range(_PAGE_CAP):
        if limit is not None and len(rows) >= limit:
            break
        link = client_next_page(payload)
        # A next link that repeats is a malformed envelope, not a page.
        if not link or link in seen:
            break
        seen.add(link)
        payload = await client.rest_call("GET", link)
        rows.extend(resources.unwrap(payload, resource.data_key))
    return rows[:limit] if limit is not None else rows


async def _search_rows(client: SwshClient, resource: resources.Resource, query: str,
                       fields: Sequence[str]) -> list[dict[str, Any]]:
    """Rows of ``resource`` whose ``fields`` match ``query``.

    Matching happens on the platform wherever the resource declares a
    ``list_filters`` entry for the field, so searching a project with thousands
    of numbers does not mean paging through them. Fields with no declared
    filter — and resources with none at all — are matched here, over **every**
    page the list route offers.

    That "every" is the whole point. Sifting one page made the answer depend on
    where a row happened to sit: `sw resources list -m "Test AI API"` printed
    *no rows* for a resource that was row 80 of 134. A false negative from a
    search is indistinguishable from the record not existing, which is the one
    answer a search must never get wrong.
    """
    terms = [query]
    digits = re.sub(r"\D", "", query)
    # `(209) 555-0183` has to reach `filter_number`, which matches on the
    # stored `+12095550183`, so the punctuation-free form goes too.
    if len(digits) >= 3 and digits != query:
        terms.append(digits)

    filtered = [(resource.list_filters[f], term) for f in fields
                if f in resource.list_filters for term in terms]
    local = [f for f in fields if f not in resource.list_filters]

    calls = [_list_rows(client, resource, **{param: term}) for param, term in filtered]
    if local or not filtered:
        calls.append(_list_rows(client, resource))
    pages = await asyncio.gather(*calls)

    found: dict[str, dict[str, Any]] = {}
    for index, rows in enumerate(pages):
        # The server already applied the filter for its own page; an unfiltered
        # page is ours to sift, and only on the fields no filter covered.
        server_side = index < len(filtered)
        for row in rows:
            if not server_side and not resources.row_matches(row, query, local or fields):
                continue
            found.setdefault(str(resources.cell(row, resource.id_field) or id(row)), row)
    return list(found.values())


async def _resolve_id(client: SwshClient, resource: resources.Resource,
                      identifier: str) -> str:
    """Turn what someone typed into the id the read route needs.

    An id-shaped identifier is passed straight through. Anything else is a
    handle — a phone number, a name — resolved against ``resource.lookup_fields``. An
    exact hit wins outright; several substring hits are reported as the
    ambiguity they are rather than silently resolved to the first row.
    """
    if not resource.lookup_fields or resources.looks_like_id(identifier):
        return identifier

    rows = await _search_rows(client, resource, identifier, resource.lookup_fields)
    exact = [r for r in rows
             if resources.row_matches_exactly(r, identifier, resource.lookup_fields)]
    candidates = exact or rows

    if not candidates:
        # Not a handle we know: it may still be an id whose shape we do not
        # recognise, so let the read route have it and report its own 404.
        return identifier
    if len(candidates) > 1:
        ui.fail(f"{identifier!r} matches {len(candidates)} {resource.title}")
        ui.console.print(ui.rows_table(
            candidates, resources.columns_for(resource, candidates), title="candidates"))
        raise typer.Exit(2)
    return str(resources.cell(candidates[0], resource.id_field))


def _id_metavar(resource: resources.Resource) -> str:
    """What the positional identifier is called in `--help`.

    A resource with handles advertises them, because ``ID`` alone reads as "and
    nothing else" and is the reason someone pastes a uuid they had to go and
    look up.
    """
    if not resource.lookup_fields:
        return "ID"
    return "ID|" + "|".join(f.rsplit(".", 1)[-1].upper() for f in resource.lookup_fields)


def _by_what(resource: resources.Resource) -> str:
    if not resource.lookup_fields:
        return "by id"
    return "by id, " + " or ".join(f.rsplit(".", 1)[-1] for f in resource.lookup_fields)


def _said(typed: str, resource_id: str) -> str:
    """Name a row the way the person named it, and by the id that was acted on.

    ``updated Fax Number (bbbbbbbb-…)`` is the only form that both confirms sw
    resolved the handle they meant and hands them the id for the next command.
    """
    return resource_id if typed == resource_id else f"{typed} ({resource_id})"


def _id_param(resource: resources.Resource, name: str = "identifier") -> inspect.Parameter:
    return _param(name, str, typer.Argument(..., metavar=_id_metavar(resource)))


def _add_list(sub: typer.Typer, resource: resources.Resource) -> None:
    @raw_capable
    async def run(client: SwshClient, **kw: Any) -> None:
        query = kw.get("match")
        if Ctx.raw:
            # `--match` is sw sifting rows it fetched, over as many requests as
            # the lookup fields need; there is no single response that means it.
            # Refusing beats printing an unfiltered page under a flag that says
            # filtered.
            if query:
                _raw_refuse("--match and --raw do not go together: --match sifts "
                            "rows across as many requests as the lookup needs, "
                            "and --raw shows one response.")
            _emit_raw(await client.invoke(resource, "list"))
            return
        Ctx.csv = bool(kw.get("csv"))
        if query:
            # No limit on the walk: a search that stops early is a search that
            # can answer "no rows" about a record on the next page.
            rows = await _search_rows(client, resource, query, resource.search_fields)
        else:
            # Sorting reorders what was fetched, so the page has to be filled
            # before the limit is applied or `--sort` would order an arbitrary
            # slice and call it the top of the list.
            rows = await _list_rows(client, resource,
                                    limit=None if kw.get("sort") else kw["limit"])
        rows = _sorted_rows(rows, kw.get("sort"), bool(kw.get("desc")))
        rows = rows[:kw["limit"]]
        _show_rows(rows, _chosen_columns(kw.get("columns"), resource, rows),
                   resource.title)

    searched = ", ".join(resource.search_fields) or "every column"
    _command(sub, resource.verb("list"), run,
             [_param("limit", int, typer.Option(50, "--limit", "-n", help="Rows to show.")),
              _param("match", str | None,
                     typer.Option(None, "--match", "-m",
                                  help="Show only rows matching this text. "
                                       f"Searches {searched}.")),
              _param("sort", str | None,
                     typer.Option(None, "--sort", help="Order by this field.")),
              _param("desc", bool,
                     typer.Option(False, "--desc", help="Reverse the sort.")),
              _param("columns", str | None,
                     typer.Option(None, "--columns",
                                  help="Comma-separated fields to show instead "
                                       "of the default ones.")),
              _param("csv", bool,
                     typer.Option(False, "--csv", help="Comma-separated output."))],
             f"List {resource.title}.\n\n"
             "--sort orders the whole collection, not the page --limit would "
             "have stopped at. --columns takes any field a row carries, "
             "including the ones the default table leaves out.\n\n"
             "--raw prints the response envelope as it arrived, paging links and "
             "all: --limit does not apply to it, and --match is refused.")


def _add_get(sub: typer.Typer, resource: resources.Resource) -> None:
    @raw_capable
    async def run(client: SwshClient, **kw: Any) -> None:
        if kw.get("full"):
            _raw_refuse("--full and --raw do not go together: --full follows "
                        "the routing across several requests, and --raw shows "
                        "one response.")
        # A singleton's read route carries no `{id}`: the project has exactly
        # one SIP profile and asking for it needs no identifier. `sw sipprofile
        # get` demanded one anyway and there was none to give.
        if resource.is_singleton:
            row = await client.invoke(resource, "read")
        else:
            resource_id = await _resolve_id(client, resource, kw["identifier"])
            row = await client.invoke(resource, "read", resource_id=resource_id)
        # Before the body-fill below and before any shaping: --raw is the record
        # as the platform sent it, not as sw completes it.
        if _emit_raw(row):
            return
        if kw.get("full") and isinstance(row, dict):
            expanded = await routing.expand(client, resource, row)
            if Ctx.as_json:
                ui.emit(expanded.as_dict(), as_json=True)
                return
            ui.console.print(ui.detail_title(row, resource.id_field), style="heading")
            ui.console.print()
            ui.console.print(ui.routing_tree(expanded))
            return
        # The message logs API omits the body; fill it in from the row's LaML
        # url so `messages get <id>` shows the content, like the dashboard does.
        if resource.key == "messages" and isinstance(row, dict) and row.get("url") \
                and not row.get("body"):
            try:
                full = await client.rest_call("GET", row["url"])
                if isinstance(full, dict) and full.get("body"):
                    row["body"] = full["body"]
            except SwshError:
                pass  # leave the metadata as-is if the body cannot be fetched
        if Ctx.as_json or not isinstance(row, dict):
            ui.emit(row, as_json=True)
            return
        ui.console.print(ui.detail_table(
            row, title=ui.detail_title(row, resource.id_field)))

    params = [] if resource.is_singleton else [_id_param(resource)]
    doc = (f"Show the {resource.title}." if resource.is_singleton
           else f"Fetch one of the {resource.title} {_by_what(resource)}.")
    if resource.routing:
        channels = " and ".join(r.channel for r in resource.routing)
        params.append(_param("full", bool, typer.Option(
            False, "--full", "-f",
            help="Follow the routing to what it points at, documents included.")))
        doc += ("\n\n--full resolves the " + channels + " routing: the handler in "
                "effect, the resource it hands off to, and that resource's SWML, "
                "cXML or flow in full. Fields no live handler reads are listed "
                "separately.")
    _command(sub, resource.verb("read"), run, params, doc)


def _BODY_PARAMS() -> list[inspect.Parameter]:
    """`--set key=value …` and `--body '{…}'`: how create and update take input."""
    return [
        _param("values", list[str],
               typer.Option([], "--set", "-s", help="key=value, repeatable.")),
        _param("body", str | None,
               typer.Option(None, "--body", help="Raw JSON body, overrides --set.")),
    ]


def _add_create(sub: typer.Typer, resource: resources.Resource) -> None:
    verb = resource.verb("create")

    @raw_capable
    async def run(client: SwshClient, **kw: Any) -> None:
        payload = _body_from(kw["body"], kw["values"], resource, allow_empty=True)
        payload = await prompts.fill_missing(
            resource, "create", payload, client,
            allow_prompt=prompts.interactive() and not Ctx.as_json,
        )
        if not payload:
            ui.fail("nothing to send; pass --set key=value or --body '{...}'")
            raise typer.Exit(2)
        result = await client.invoke(resource, "create", body=payload)
        if _emit_raw(result):
            return
        ui.emit(result, as_json=Ctx.as_json,
                renderer=lambda d: f"[ok]{_past(verb)}[/ok] {d.get(resource.id_field, '')}"
                if isinstance(d, dict) else f"[ok]{_past(verb)}[/ok]")

    _command(sub, verb, run, _BODY_PARAMS(),
             f"{verb.capitalize()} one of the {resource.title}. Omit a required field and, "
             "in a terminal, sw prompts for it; enumerable fields are offered as a picker. "
             "With --json it errors instead.")


def _add_update(sub: typer.Typer, resource: resources.Resource) -> None:
    @raw_capable
    async def run(client: SwshClient, **kw: Any) -> None:
        payload = _body_from(kw["body"], kw["values"], resource)
        resource_id = await _resolve_id(client, resource, kw["identifier"])
        result = await client.invoke(resource, "update", resource_id=resource_id,
                                     body=payload)
        if _emit_raw(result):
            return
        ui.emit(result, as_json=Ctx.as_json,
                renderer=lambda d: f"[ok]updated[/ok] {_said(kw['identifier'], resource_id)}")

    _command(sub, resource.verb("update"), run,
             [_id_param(resource), *_BODY_PARAMS()],
             f"Update one of the {resource.title} in place, {_by_what(resource)}.")


def _add_delete(sub: typer.Typer, resource: resources.Resource) -> None:
    verb = resource.verb("delete")

    @raw_capable
    async def run(client: SwshClient, **kw: Any) -> None:
        # Resolve every handle *before* asking, and before touching anything:
        # an ambiguous one has to stop the whole command, not release two of
        # three numbers and then find out. The confirmation then names the rows
        # that will actually go, which is the point of asking at all.
        ids = [await _resolve_id(client, resource, typed) for typed in kw["ids"]]
        if not kw["yes"]:
            noun = resource.title if len(ids) > 1 else resource.title.rstrip("s")
            for typed, resource_id in zip(kw["ids"], ids, strict=True):
                if typed != resource_id:
                    ui.console.print(f"  {typed}  →  {resource_id}")
            typer.confirm(f"{verb} {len(ids)} {noun}?", abort=True)
        done: list[str] = []
        failed: dict[str, str] = {}
        bodies: list[Any] = []
        for resource_id in ids:
            try:
                bodies.append(await client.invoke(resource, "delete",
                                                  resource_id=resource_id))
                done.append(resource_id)
                if not Ctx.as_json:
                    ui.console.print(f"[ok]{_past(verb)}[/ok] {resource_id}")
            except SwshError as exc:
                failed[resource_id] = str(exc)
                # Under --raw the failure has no field to live in, so it is said
                # on stderr, where it does not touch the document on stdout.
                if Ctx.raw or not Ctx.as_json:
                    ui.fail(f"{resource_id}: {exc}")
        if Ctx.raw:
            # One id, one response. Several, one per id in the order given —
            # a Fabric delete answers 204 with no body, so most of these are {}.
            _emit_raw(bodies[0] if len(ids) == 1 and bodies else bodies)
        elif Ctx.as_json:
            ui.emit({_past(verb): done, "failed": failed}, as_json=True)
        if failed:  # one bad id fails the command, even after the others went through
            raise typer.Exit(1)

    _command(sub, verb, run, [
        _param("ids", list[str], typer.Argument(..., metavar=f"{_id_metavar(resource)}...")),
        _param("yes", bool, typer.Option(False, "--yes", "-y", help="Skip the confirmation.")),
    ], f"{verb.capitalize()} one or more of the {resource.title}, {_by_what(resource)}. "
       "Asks first unless --yes.")


_IRREGULAR_PAST = {"buy": "bought"}


def _past(verb: str) -> str:
    return _IRREGULAR_PAST.get(verb) or verb + ("d" if verb.endswith("e") else "ed")


def _flag(field_def: resources.Field) -> str:
    # `from_` is spelled that way because `from` is a keyword; the flag is --from.
    return "--" + field_def.name.rstrip("_").replace("_", "-")


def _add_extra(sub: typer.Typer, resource: resources.Resource, extra: resources.Extra) -> None:
    """A subcommand for one Extra: a drill lists, an action acts.

    Positional ID when the extra works on a row (or on a drill's row), one
    option per declared field, ``--yes`` when it asks first. The body is built
    the way the TUI form builds it, so the two send the same request.
    """
    # An extra bound to a drill acts on that drill's rows — a membership, a
    # stream — so the parent's handles mean nothing to it and resolving against
    # them would send the wrong id. Only an extra on the resource's own rows
    # takes a handle.
    on_own_rows = extra.needs_id and not extra.on_drill

    @raw_capable
    async def run(client: SwshClient, **kw: Any) -> None:
        typed = kw.pop("identifier", None)
        identifier = typed
        yes = kw.pop("yes", False)
        if on_own_rows and typed is not None:
            identifier = await _resolve_id(client, resource, typed)
        values = {f.name: kw[f.name] for f in extra.fields if kw.get(f.name) is not None}
        if extra.fields:
            values = await prompts.fill_missing(
                extra, "create", values, client,
                allow_prompt=prompts.interactive() and not Ctx.as_json,
                hint="{flag} …",
            )
            try:
                body = resources.build_body(extra, "create", values)
            except ValueError as exc:
                ui.fail(str(exc))
                raise typer.Exit(2) from exc
        else:
            body = {}
        if extra.confirm and not yes:
            target = _said(typed, identifier) if typed is not None else ""
            typer.confirm(f"{extra.label} {target}".rstrip() + "?", abort=True)
        payload = await client.invoke(
            resource, extra.method,
            resource_id=identifier if extra.needs_id else None,
            body=body or None,
        )
        if _emit_raw(payload):
            return
        rows = resources.unwrap(payload)
        if isinstance(payload, list) or (isinstance(payload, dict) and rows
                                         and not payload.get(resource.id_field)):
            _show_rows(rows, _discovered_columns(rows), f"{resource.title}: {extra.label}")
        elif payload not in (None, {}, ""):
            ui.emit(payload, as_json=True)  # one object: show all of it
        else:
            ui.emit({"ok": True, "action": extra.label, "id": identifier}, as_json=Ctx.as_json,
                    renderer=lambda d: f"[ok]{extra.label}[/ok] "
                                       f"{_said(typed, identifier) if typed else ''}".rstrip())

    params: list[inspect.Parameter] = []
    if extra.needs_id:
        params.append(_id_param(resource) if on_own_rows
                      else _param("identifier", str, typer.Argument(..., metavar="ID")))
    for field_def in extra.fields:
        help_text = field_def.help or field_def.title
        if field_def.choices:
            help_text += f" One of: {', '.join(field_def.choices)}."
        if field_def.required:
            help_text += " Required."
        flag = _flag(field_def)
        if field_def.kind == "bool":
            params.append(_param(field_def.name, bool | None,
                                 typer.Option(None, f"{flag}/--no-{flag[2:]}", help=help_text)))
        elif field_def.kind == "int":
            params.append(_param(field_def.name, int | None,
                                 typer.Option(None, flag, help=help_text)))
        else:
            params.append(_param(field_def.name, str | None,
                                 typer.Option(None, flag, help=help_text)))
    if extra.confirm:
        params.append(_param("yes", bool,
                             typer.Option(False, "--yes", "-y", help="Skip the confirmation.")))
    doc = extra.label[:1].upper() + extra.label[1:] + "."
    if extra.on_drill:
        doc += f" ID is a row from `{extra.on_drill}`."
    _command(sub, extra.command, run, params, doc)


def _install_resource_groups() -> None:
    """Give every registry resource its command group, verbs and extras.

    Runs once at import, after the hand-written commands, so a hand-written
    `numbers search` or `logs events` is kept and the generated one skipped.
    A resource with nothing reachable (the live calls view, which has its own
    hand-written group) gets no group at all.
    """
    adders = {"list": _add_list, "read": _add_get, "create": _add_create,
              "update": _add_update, "delete": _add_delete}
    for resource in resources.RESOURCES:
        if resource.key == "calls":
            continue
        ops = _cli_ops(resource)
        if not ops and not resource.extras:
            continue
        sub = resource_app(resource.key)
        taken = _registered(sub)
        for op in ops:
            if resource.verb(op) not in taken:
                adders[op](sub, resource)
        taken = _registered(sub)
        # The TUI's detail drills ("log detail") open the same operation `get`
        # already reaches; a second command for it would be an alias.
        crud_ops = {resource.rest_ops.get(op) for op in ops}
        for extra in resource.extras:
            if extra.command in taken or (extra.spec_op and extra.spec_op in crud_ops):
                continue
            _add_extra(sub, resource, extra)


def _body_from(raw: str | None, values: list[str], target: Any,
               allow_empty: bool = False) -> dict[str, Any]:
    if raw:
        import json as _json

        try:
            parsed = _json.loads(raw)
        except ValueError as exc:
            ui.fail(f"--body is not valid JSON: {exc}")
            raise typer.Exit(2) from exc
        if not isinstance(parsed, dict):
            ui.fail("--body must be a JSON object")
            raise typer.Exit(2)
        return parsed
    payload = _parse_pairs(list(values), target)
    if not payload and not allow_empty:
        ui.fail("nothing to send; pass --set key=value or --body '{...}'")
        raise typer.Exit(2)
    return payload


# ---------------------------------------------------------------------- listen


@app.command()
@with_global_flags
def listen(
    port: int = typer.Option(8787, "--port", help="Local port for the sink."),
    public_url: str | None = typer.Option(None, "--public-url",
                                             help="Skip ngrok and use this base URL."),
    numbers: list[str] = typer.Option([], "--number", "-N",
                                      help="Number or id to rewrite. Repeatable. Default: all."),
    no_rewrite: bool = typer.Option(False, "--no-rewrite",
                                    help="Print the URL but change nothing."),
    forward: str | None = typer.Option(None, "--forward",
                                          help="Also POST every callback here."),
    restore: bool = typer.Option(False, "--restore",
                                 help="Undo a rewrite left by a crashed run, then exit."),
    verify: bool = typer.Option(False, "--verify-signatures",
                                help="Reject callbacks failing HMAC validation (unverified)."),
) -> None:
    """Receive status callbacks locally and stream them to your terminal.

    Opens a tunnel, points your numbers' status callbacks at it, prints every
    callback as it arrives, and restores the original URLs on exit. The original
    values are journalled to disk first, so an unclean exit can still be undone
    with ``--restore``.
    """
    from .listen import run_listen

    try:
        asyncio.run(
            run_listen(
                profile=_profile(),
                port=port,
                public_url=public_url,
                numbers=list(numbers),
                rewrite=not no_rewrite,
                forward=forward,
                restore_only=restore,
                verify_signatures=verify,
                as_json=Ctx.as_json,
            )
        )
    except SwshError as exc:
        ui.fail(str(exc))
        raise typer.Exit(1) from exc
    except KeyboardInterrupt:
        raise typer.Exit(130) from None


def _call_json(call: Any) -> dict[str, Any]:
    """sw's shape of a call. The cockpit's detail pane renders the same dict."""
    return call.as_json()


# Generate the noun groups last, so every hand-written command above is already
# registered and wins over a generated one of the same name.
_install_resource_groups()


def main() -> None:
    # Restore default SIGPIPE so `sw calls list | head` exits quietly.
    with __import__("contextlib").suppress(AttributeError, ValueError):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    app()


# There was a second console script, `swsh`, which forwarded to `sw` and opened
# the cockpit when run bare. It is gone: the shell it was named for is now
# `sw sh`, and two spellings of one tool is the thing that made the name worth
# splitting in the first place.


if __name__ == "__main__":
    main()
