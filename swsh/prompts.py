"""Interactive prompting for the CLI.

The rule: a missing detail is asked for, not errored on — and any
value swsh can enumerate is offered as a list, never a blank prompt. Running a
mutating command without a required value drops into a prompt here; an
enumerable field (a *from* number, an e911 address) becomes a numbered picker
backed by the shared selector service.

Non-interactive runs (``--json``/``--yes``, or no TTY) turn a missing required
value back into a hard error, so scripts stay strict.
"""

from __future__ import annotations

import sys

import typer

from . import resources as res
from .selectors import Option


def interactive() -> bool:
    """True when we may prompt: attached to a real terminal."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def pick(title: str, options: list[Option], *, allow_other: bool = False) -> str | None:
    """Show a numbered picker and return the chosen value.

    Kept dependency-free (a numbered list, not a fullscreen selector) so it works
    in any terminal and in a pipe-free interactive shell.
    """
    if not options:
        if allow_other:
            return typer.prompt(title)
        return None
    typer.echo(f"\n{title}")
    for i, opt in enumerate(options, 1):
        typer.echo(f"  {i}) {opt.display}")
    if allow_other:
        typer.echo("  0) enter another value")
    while True:
        raw = typer.prompt("choose", default="1")
        if raw.strip() == "0" and allow_other:
            return typer.prompt("value")
        try:
            idx = int(raw)
        except ValueError:
            # Allow typing the value directly too.
            match = [o for o in options if o.value == raw.strip()]
            if match:
                return match[0].value
            typer.echo("  not a number; try again")
            continue
        if 1 <= idx <= len(options):
            return options[idx - 1].value
        typer.echo(f"  out of range 1-{len(options)}")


def _flag(name: str) -> str:
    """The option spelling of a field name: `from_` is `--from`."""
    return "--" + name.rstrip("_").replace("_", "-")


async def fill_missing(
    resource: res.Resource, mode: str, body: dict, client, *,
    allow_prompt: bool, channel: str | None = None, hint: str = "--set {name}=…",
) -> dict:
    """Prompt for required fields absent from ``body``.

    Enumerable fields become pickers (capability-filtered when a channel is
    given); free-text fields become plain prompts. With ``allow_prompt`` false,
    a missing required field raises, keeping non-interactive use strict.
    """
    filled = dict(body)
    for field_def in resource.form_fields(mode):
        if not field_def.required or field_def.name in filled:
            continue
        if not allow_prompt:
            raise typer.BadParameter(
                f"missing required '{field_def.name}' "
                f"(run interactively, or pass "
                f"{hint.format(name=field_def.name, flag=_flag(field_def.name))})"
            )
        if field_def.options_from:
            opts = await client.selector.options(field_def.options_from)
            if channel:
                from .selectors import Selector
                opts = Selector.capable(opts, channel)
            chosen = pick(f"? {field_def.title}", opts,
                          allow_other=not field_def.options_from[0].startswith("numbers"))
            if chosen is None:
                raise typer.BadParameter(f"no {field_def.title} available to choose")
            filled[field_def.name] = chosen
        else:
            filled[field_def.name] = typer.prompt(f"? {field_def.title}")
    return filled


async def choose_number(client, *, channel: str, prompt: str = "From which number?") -> str:
    """The from-number rule: pick a sending number capable of ``channel``."""
    from .selectors import Selector

    opts = Selector.capable(await client.selector.options(
        ("numbers.list", "number", "name")), channel)
    if not opts:
        raise typer.BadParameter(f"no {channel}-capable numbers on this project")
    value = pick(prompt, opts)
    if value is None:
        raise typer.BadParameter("no number chosen")
    return value
