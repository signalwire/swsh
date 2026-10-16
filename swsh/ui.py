"""Shared rendering: the palette, tables, and output shaping.

Every command supports ``--json``, so rendering is deliberately kept out of the
command bodies. They produce data; this module decides how it looks.

Colours are the locked SignalWire brand set, applied 60-30-10: mostly neutral,
secondary surfaces next, accent used sparingly so it still means something.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable, Sequence
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from rich import box
from rich.console import Console, Group, RenderableType
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from . import resources as res

# Locked brand colours.
BLUE = "#044EF4"
FUCHSIA = "#F72A72"
PURPLE = "#601BE6"
TURQUOISE = "#40E0D0"
GOLD = "#FFD700"

SWSH_THEME = Theme(
    {
        "brand": BLUE,
        "accent": FUCHSIA,
        "alt": PURPLE,
        "cool": TURQUOISE,
        "warn": GOLD,
        "muted": "grey58",
        "heading": f"bold {TURQUOISE}",
        "ok": "green",
        "bad": "red",
        # Call states carry consistent colour everywhere they appear.
        "state.created": "grey58",
        "state.ringing": GOLD,
        "state.answered": TURQUOISE,
        "state.ending": "grey62",
        "state.ended": "grey42",
        "state.unknown": "grey35",
        "src.relay": TURQUOISE,
        "src.callback": FUCHSIA,
        "src.poll": "grey58",
        "src.local": PURPLE,
    }
)

console = Console(theme=SWSH_THEME)
err_console = Console(theme=SWSH_THEME, stderr=True)

STATE_GLYPH = {
    "created": "◌",
    "ringing": "◍",
    "answered": "●",
    "ending": "◐",
    "ended": "○",
    "unknown": "·",
}

SOURCE_GLYPH = {"relay": "R", "callback": "C", "poll": "P", "local": "L"}

# Literal colours, not theme names.
#
# The theme above is registered on this module's Console, but Textual renders
# Rich renderables through its own Console, which has never seen it. Any Text
# built here can end up in either place, so styles have to be self-contained.
STATE_STYLE = {
    "created": "grey58",
    "ringing": GOLD,
    "answered": TURQUOISE,
    "ending": "grey62",
    "ended": "grey42",
    "unknown": "grey35",
}

SOURCE_STYLE = {
    "relay": TURQUOISE,
    "callback": FUCHSIA,
    "poll": "grey58",
    "local": PURPLE,
}


def emit(data: Any, *, as_json: bool, renderer=None) -> None:
    """Print either machine-readable JSON or a rendered view.

    The JSON half goes to stdout unstyled rather than through the themed
    console. ``--json`` exists to be piped, and Rich takes the colour decision
    from the environment as well as from the destination: ``FORCE_COLOR`` or
    ``CLICOLOR_FORCE`` — set by plenty of CI images and terminal profiles —
    makes it write escape sequences into a pipe, which `jq` then rejects with
    ``Invalid numeric literal``. Machine-readable output is not the place to
    let the environment have that say, so it never colours.

    ``console.quiet`` is still honoured, because that is how ``--raw`` silences
    a command's own rendering.
    """
    if as_json:
        if not console.quiet:
            print(json.dumps(data, indent=2, default=str))
        return
    if renderer is not None:
        console.print(renderer(data))
    else:
        console.print(data)


def emit_csv(rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    """Rows as CSV on stdout, for a spreadsheet or `cut`.

    Written with `csv.writer` rather than by joining on commas, because a
    display name containing a comma or a quote is ordinary and hand-rolled CSV
    gets it wrong in a way nothing downstream can detect. Cells go through the
    same `_cell` the table uses, so a timestamp reads the same in both.
    """
    import csv
    import sys

    if console.quiet:
        return
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(res.cell(row, column)) for column in columns])


def json_view(data: Any) -> RenderableType:
    """A payload as JSON, highlighted, wrapped and never truncated.

    The renderer behind the detail pane's json and raw modes, and the reason
    they are worth having on screen: a field sw does not model is still a field
    someone came to read. Highlighting is best-effort, like `_document_panel`.
    """
    from rich.syntax import Syntax

    text = json.dumps(data, indent=2, default=str, sort_keys=False)
    try:
        return Syntax(text, "json", theme="ansi_dark", background_color="default",
                      word_wrap=True)
    except Exception:
        return Text(text)


def state_text(state: str) -> Text:
    glyph = STATE_GLYPH.get(state, "·")
    return Text(f"{glyph} {state}", style=STATE_STYLE.get(state, "grey35"))


def sources_text(sources: Iterable[Any]) -> Text:
    """Render which channels have confirmed a call, so coverage is visible."""
    text = Text()
    seen = {getattr(s, "value", str(s)) for s in sources}
    for name in ("relay", "callback", "poll"):
        if name in seen:
            text.append(SOURCE_GLYPH[name], style=SOURCE_STYLE[name])
        else:
            text.append("·", style="grey30")
    return text


def duration_text(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def short_id(value: str | None, width: int = 12) -> str:
    if not value:
        return "-"
    return value if len(value) <= width else f"{value[:width - 1]}…"


CALL_COLUMNS = ("id", "dir", "to", "from", "started", "ended", "dur", "state")

# Showing the id in full costs 36 columns before anything else is on screen, so
# the layout is chosen from the console width rather than fixed. The content
# budget is
#
#   id 36 · dir 8 · to 13 · from 13 · started 8|14 · ended 8|14 · dur 6 · state 11
#
# and a timestamp is 8 wide for a call from today, 14 for one from last week, so
# the same table needs a different budget depending on what is in it. Hence every
# layout is measured against the rows actually being printed.
#
# Rich's own overhead is 2 columns of padding per column, plus — when the table
# has a box — one per vertical rule, whether or not that box draws them. That is
# measured, not assumed: `SIMPLE_HEAD` reserves the separator cells exactly like
# `HEAVY_HEAD` and renders them blank, so dropping to it saves nothing. Only
# `box=None` gets those 9 columns back.
_NUMBER_MIN_WIDTH = 13  # +15551234567 on one line, and a floor SIP cannot squeeze
_CALL_COL_FIXED = {"dir": 8, "dur": 6, "state": 11}  # 11 = glyph, space, "answered"
_CALL_COL_FLOOR = {"id": 36, "to": _NUMBER_MIN_WIDTH, "from": _NUMBER_MIN_WIDTH}


def call_type_text(call_type: str | None) -> str:
    """The engine behind a leg, shortened: laml, relay, sip, video."""
    return _CALL_TYPE_LABEL.get(call_type or "", call_type or "-")


_CALL_TYPE_LABEL = {
    "laml_call": "laml",
    "relay_pstn_call": "relay",
    "relay_sip_call": "sip",
    "video_room_pstn_leg": "video",
}


def when_text(timestamp: float | None, *, compact: bool = False) -> str:
    """A timestamp in local time, dropping the year: this is a live view.

    ``compact`` drops the date as well *for today's calls only*, which is nearly
    all of them in a newest-first list. An older row keeps its ``mm-dd`` in the
    same column, so a date is never silently implied.
    """
    if not timestamp:
        return "-"
    local = time.localtime(timestamp)
    if compact and local[:3] == time.localtime()[:3]:
        return time.strftime("%H:%M:%S", local)
    return time.strftime("%m-%d %H:%M:%S", local)


def call_row(call: Any, *, compact: bool = True, with_ended: bool = True) -> list[Any]:
    """One call as table cells, shared by the CLI table and the TUI.

    Order is id-first because the id is what gets pasted into `sw calls show` or
    a control command. Which channels saw the call is not here: it is a property
    of the watcher, not the call, and lives in the detail pane's "seen by".
    """
    cells: list[Any] = [
        str(call.ref),  # the full id: a truncated one cannot be pasted anywhere
        (call.direction or "-").replace("outbound-api", "out-api"),
        call.to_number or "-",
        call.from_number or "-",
        when_text(call.started_at, compact=compact),
    ]
    if with_ended:
        cells.append(when_text(call.ended_at, compact=compact))
    cells += [duration_text(call.duration), state_text(call.state.value)]
    return cells


def _call_layout_width(rows: Sequence[Sequence[Any]], headers: Sequence[str],
                       *, boxed: bool) -> int:
    """What this layout needs before Rich starts taking columns away.

    ``to`` and ``from`` are costed at their floor, not their content: a long SIP
    URI is happy to fold over two lines, so it should not price the table out of
    a layout that everything else fits in.
    """
    total = 0
    for index, header in enumerate(headers):
        if header in _CALL_COL_FIXED:
            total += _CALL_COL_FIXED[header]
        elif header in ("to", "from"):
            total += _NUMBER_MIN_WIDTH
        else:
            content = max([len(header)]
                          + [Text(str(row[index])).cell_len for row in rows])
            total += max(content, _CALL_COL_FLOOR.get(header, 0))
    total += 2 * len(headers)  # padding=(0, 1)
    if boxed:
        total += len(headers) + 1  # a separator cell per column, drawn or not
    return total


def _calls_stacked(calls: Sequence[Any], *, title: str | None) -> Group:
    """Two lines per call, for a terminal too narrow to hold the columns.

    The id alone is 36 columns, so below roughly 110 a table can only fit by
    dropping a column or shaving the numbers down to a vertical stack of single
    characters. Neither is worth doing to someone, and both lose more than this
    does: every field in `CALL_COLUMNS` is still here, just wrapped.
    """
    lines: list[Text] = []
    if title:
        lines.append(Text(title, style="heading"))
    if not calls:
        lines.append(Text("no calls", style="muted"))
        return Group(*lines)

    for call in calls:
        head = Text("  ")
        head.append(str(call.ref), style="muted")
        head.append("  ")
        head.append((call.direction or "-").replace("outbound-api", "out-api"))
        head.append("  ")
        head.append(state_text(call.state.value))
        lines.append(head)

        body = Text("    ")
        body.append(call.from_number or "-")
        body.append(" → ", style="grey42")
        body.append(call.to_number or "-")
        body.append("   ")
        body.append(when_text(call.started_at, compact=True))
        body.append(" → ", style="grey42")
        body.append(when_text(call.ended_at, compact=True))
        body.append(f"   {duration_text(call.duration)}", style="muted")
        lines.append(body)
    return Group(*lines)


def calls_table(calls: Sequence[Any], *, title: str | None = None,
                width: int | None = None) -> RenderableType:
    """The calls list, laid out to fit the terminal it is being printed into.

    Wide enough, and every timestamp carries its date inside the usual box. As
    the window narrows the table sheds decoration before it sheds facts: the box
    goes first, then today's dates, and only then the ``ended`` column, which is
    the one thing here that `sw calls show` repeats. Narrower than the columns
    can survive, it stops being a table at all rather than let Rich buy space by
    deleting columns — a silently missing `to` is a trap.
    """
    if width is None:
        width = console.width

    # (boxed with dated timestamps, `ended` column), widest first: the first
    # that fits wins, and if none does the stacked form takes over.
    for full, with_ended in ((True, True), (False, True), (False, False)):
        rows = [call_row(c, compact=not full, with_ended=with_ended) for c in calls]
        headers = [h for h in CALL_COLUMNS if with_ended or h != "ended"]
        if _call_layout_width(rows, headers, boxed=full) <= width:
            break
    else:
        return _calls_stacked(calls, title=title)

    table = Table(
        title=title,
        title_style="heading",
        header_style="bold",
        border_style="grey30",
        box=box.HEAVY_HEAD if full else None,
        expand=False,
        padding=(0, 1),
    )
    table.add_column("id", style="muted", no_wrap=True, min_width=_CALL_COL_FLOOR["id"])
    table.add_column("dir", width=_CALL_COL_FIXED["dir"], no_wrap=True)
    # SIP URIs are long; fold rather than truncate so the address stays legible.
    # The floor matters: without it Rich buys space for the fixed columns by
    # shaving these two down to a few characters, and then by dropping them.
    table.add_column("to", overflow="fold", min_width=_NUMBER_MIN_WIDTH)
    table.add_column("from", overflow="fold", min_width=_NUMBER_MIN_WIDTH)
    table.add_column("started", no_wrap=True)
    if with_ended:
        table.add_column("ended", no_wrap=True)
    table.add_column("dur", justify="right", width=_CALL_COL_FIXED["dur"], no_wrap=True)
    table.add_column("state", width=_CALL_COL_FIXED["state"], no_wrap=True)

    if not calls:
        table.add_row(Text("no calls", style="muted"), *([""] * (len(headers) - 1)))
        return table

    for row in rows:
        table.add_row(*row)
    return table


def messages_table(messages: Sequence[Any], *, title: str | None = None) -> Table:
    table = Table(
        title=title, title_style="heading", header_style="bold",
        border_style="grey30", expand=True, padding=(0, 1),
    )
    table.add_column("state", width=12, no_wrap=True)
    table.add_column("sid", style="muted", no_wrap=True)
    table.add_column("dir", width=9, no_wrap=True)
    table.add_column("from", no_wrap=True)
    table.add_column("to", no_wrap=True)
    table.add_column("body", overflow="ellipsis")

    if not messages:
        table.add_row(Text("no messages", style="muted"), "", "", "", "", "")
        return table

    for msg in messages:
        style = "ok" if msg.state in ("delivered", "received") else (
            "bad" if msg.state in ("failed", "undelivered") else "muted"
        )
        table.add_row(
            Text(msg.state, style=style),
            # In full: a SID with an ellipsis in it cannot be pasted into
            # `sw messages get`, which is the only reason it is in the table.
            msg.sid or "-",
            (msg.direction or "-").replace("outbound-api", "out-api"),
            msg.from_number or "-",
            msg.to_number or "-",
            (msg.body or "").replace("\n", " "),
        )
    return table


def _is_id_column(column: str) -> bool:
    """Columns whose whole value is an identifier someone will paste onwards."""
    tail = column.rsplit(".", 1)[-1]
    return tail == "id" or tail.endswith("_id") or tail == "sid"


# What `local_time` renders: `2026-09-09 16:40:56 EDT`.
_LOCAL_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?: \S+)?$")


def _is_atomic(column: str, cells: Sequence[str]) -> bool:
    """Whether a column holds values that must not be cut or folded.

    An id and a timestamp are both all-or-nothing: half a uuid cannot be pasted
    into the next command, and a timestamp folded across two lines costs a row
    per record to say what fits in one. Everything else — a name, a URL, a
    handler — still reads when it is elided, so it is what gives up the width.
    """
    if _is_id_column(column):
        return True
    filled = [c for c in cells if c and c != "-"]
    return bool(filled) and all(_LOCAL_STAMP_RE.match(c) for c in filled)


def rows_table(rows: Sequence[dict[str, Any]], columns: Sequence[str],
               *, title: str | None = None, overflow: str = "ellipsis") -> Table:
    """Generic table for the many REST resources that need no special shaping.

    ``overflow`` defaults to eliding a long cell, which keeps a wide resource
    listing readable. Pass ``"fold"`` when the long column *is* the information,
    as it is for the endpoint paths in `sw api --list`.

    **Ids and timestamps are pinned to the width of what is in them.**
    ``expand=True`` spreads the console's spare width evenly, which on a wide
    listing spent it on short columns and left the uuid elided — and a uuid
    ending in ``…`` is the one value in the row that cannot be pasted into the
    next command, so eliding it is the same as not printing it. The width comes
    from the rows rather than a constant, so a listing of short ids does not
    reserve 36 columns it has no use for.
    """
    table = Table(
        title=title, title_style="heading", header_style="bold",
        border_style="grey30", expand=True, padding=(0, 1),
    )
    rendered = [[_cell(res.cell(row, column)) for column in columns] for row in rows]
    for index, column in enumerate(columns):
        cells = [row[index] for row in rendered]
        if _is_atomic(column, cells):
            table.add_column(column, no_wrap=True,
                             width=max([len(column), *(len(c) for c in cells)]))
        else:
            table.add_column(column, overflow=overflow)
    if not rows:
        # Not a row of dashes: that is indistinguishable from one real record
        # whose every field happens to be null, and a dozen of a fresh
        # project's collections are empty.
        table.add_row(Text("no rows", style="muted"), *[""] * (len(columns) - 1))
        return table
    for row in rendered:
        table.add_row(*row)
    return table


def detail_table(row: dict[str, Any], *, title: str | None = None) -> Table:
    """One record as field/value rows: the transpose of a list table.

    ``get`` returns a single object, and a one-row table of its declared columns
    would hide the forty fields that are the reason for asking. So every key the
    API sent is a row here, in the order it sent them, nulls included — that a
    fallback URL is unset is a fact worth seeing, and it is the field someone
    came to check.
    """
    table = Table(
        title=title, title_style="heading", header_style="bold",
        border_style="grey30", expand=True, padding=(0, 1),
    )
    table.add_column("field", style="muted", no_wrap=True)
    # Fold, never elide: a webhook URL that ends in "…" cannot be pasted
    # anywhere, and the whole point of this view is the long values.
    table.add_column("value", overflow="fold")
    for key, value in row.items():
        table.add_row(key, _detail_cell(value))
    return table


# The APIs hand back UTC as ISO-8601 with a Z. Read out loud that is a
# timezone conversion someone has to do in their head every time, so the detail
# view does it and names the zone it converted to. `--json` keeps the wire form.
_ISO_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.\d+)?"
                     r"(Z|[+-]\d{2}:?\d{2})$")


# Not every API answers in ISO-8601. The compatibility surface — recordings
# among them — sends RFC 2822, `Wed, 13 Aug 2025 15:50:16 +0000`, which is the
# same instant in a shape that sorts alphabetically by weekday.
_RFC2822_RE = re.compile(r"^[A-Z][a-z]{2}, \d{1,2} [A-Z][a-z]{2} \d{4} "
                         r"\d{2}:\d{2}:\d{2} [+-]\d{4}$")


def local_time(value: str) -> str | None:
    """A timestamp as local time, or None if the string is not one."""
    if _ISO_RE.match(value):
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
        except ValueError:
            return None
    elif _RFC2822_RE.match(value):
        try:
            stamp = parsedate_to_datetime(value).astimezone()
        except (TypeError, ValueError):
            return None
    else:
        return None
    return stamp.strftime("%Y-%m-%d %H:%M:%S %Z")


def _detail_cell(value: Any) -> Text:
    """A value at full length, distinguishing "unset" from "set to empty"."""
    if value is None:
        return Text("-", style="grey42")
    if value == "":
        return Text('""', style="grey42")
    if isinstance(value, bool):
        return Text("yes" if value else "no")
    if isinstance(value, str) and (when := local_time(value)) is not None:
        return Text(when)
    if isinstance(value, list) and all(
            isinstance(v, (str, int, float, bool)) for v in value):
        return Text(", ".join(str(v) for v in value))
    if isinstance(value, (dict, list)):
        return Text(json.dumps(value, default=str, indent=2))
    return Text(str(value))


def detail_title(row: dict[str, Any], id_field: str = "id") -> str:
    """Name the record being shown: its human handle, then its id in full.

    The id is never shortened here. It is what gets pasted into the next
    command, and a truncated one is worse than none.
    """
    ident = str(res.cell(row, id_field) or "")
    label = next((str(row[k]) for k in ("name", "display_name", "number", "friendly_name")
                  if row.get(k)), "")
    if label and label != ident:
        return f"{label}  ·  {ident}" if ident else label
    return ident


def routing_tree(routing: Any) -> Group:
    """A row's routing as one indented tree per channel.

    Reads top to bottom the way a call arrives: the channel, the handler that
    claims it, the resource it hands off to, and that resource's document in
    full. The fields no live handler reads are last, under a heading that says
    so — they are set, they look like configuration, and they do nothing.
    """
    lines: list[RenderableType] = []
    for channel in routing.channels:
        head = Text()
        head.append(channel.name.upper(), style="heading")
        head.append("  ")
        head.append(channel.handler, style=PURPLE)
        lines.append(head)
        for key, value in channel.live.items():
            lines.append(_kv(key, value, indent=3))
        if channel.note:
            lines.append(Text("   " + channel.note, style="muted"))
        if channel.target is not None:
            lines.extend(_node_lines(channel.target, depth=0))
        lines.append(Text(""))

    if routing.unused:
        lines.append(Text("NOT IN USE", style="heading")
                     + Text("  set, but no live handler reads them", style="muted"))
        for key, value in routing.unused.items():
            lines.append(_kv(key, value, indent=3))
    return Group(*lines)


def _kv(key: str, value: Any, *, indent: int) -> Text:
    text = Text(" " * indent)
    text.append(f"{key}  ", style="grey58")
    text.append_text(_detail_cell(value))
    return text


def _node_lines(node: Any, *, depth: int) -> list[RenderableType]:
    """One hop and everything under it."""
    pad = " " * (3 + depth * 3)
    head = Text(pad)
    head.append("└─ ", style="grey42")
    head.append(node.kind, style=TURQUOISE)
    if node.id:
        head.append(f"  {node.id}", style="muted")
    if node.name and node.name != node.id:
        # A webhook's display name is its whole URL, which wraps the header onto
        # a second line and buries the type. The full value is a field below.
        head.append(f'  "{short_id(node.name, 46)}"')
    lines: list[RenderableType] = [head]

    inner = 3 + (depth + 1) * 3
    for key, value in node.fields.items():
        lines.append(_kv(key, value, indent=inner))
    if node.note:
        lines.append(Text(" " * inner + node.note, style="warn"))
    for document in node.documents:
        lines.append(Text(" " * inner + document.label, style="grey58"))
        lines.append(_document_panel(document, indent=inner))
    if node.child is not None:
        lines.extend(_node_lines(node.child, depth=depth + 1))
    return lines


def _document_panel(document: Any, *, indent: int) -> RenderableType:
    """A document at full length, syntax-highlighted, never truncated.

    The whole point of `--full` is the document, so it is not elided, not
    scrolled and not summarised. Highlighting is best-effort: a body that turns
    out not to be the markup it claimed still has to print.
    """
    from rich.padding import Padding
    from rich.syntax import Syntax

    if document.language in ("xml", "json"):
        try:
            body: RenderableType = Syntax(document.text, document.language,
                                          theme="ansi_dark", background_color="default",
                                          word_wrap=True)
        except Exception:  # a body that is not the markup it claimed still prints
            body = Text(document.text)
    else:
        body = Text(document.text)
    return Padding(body, (0, 0, 0, indent))


def _cell(value: Any) -> str:
    """One list-table cell.

    Timestamps are converted the same way ``detail_table`` converts them. They
    used to arrive in whatever shape the API chose — ISO-8601 with a ``Z`` from
    Fabric, the same with milliseconds from the voice log, RFC 2822 from
    recordings — so three listings side by side showed three spellings of the
    same instant, none of them in the reader's own timezone.
    """
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)[:60]
    text = str(value)
    return local_time(text) or text


def event_line(event: Any) -> Text:
    """One line in the live event feed."""
    stamp = time.strftime("%H:%M:%S", time.localtime(getattr(event, "at", time.time())))
    source = getattr(getattr(event, "source", None), "value", "?")
    text = Text()
    text.append(f"{stamp} ", style="grey42")
    text.append(f"{SOURCE_GLYPH.get(source, '?')} ", style=SOURCE_STYLE.get(source, "grey58"))

    if hasattr(event, "ref"):
        state = getattr(event.state, "value", "unknown")
        text.append(f"{short_id(str(event.ref), 14):<15}", style="grey58")
        text.append(f"{event.kind:<10}", style=PURPLE)
        text.append(state, style=STATE_STYLE.get(state, "grey35"))
        if event.end_reason:
            text.append(f" {event.end_reason}", style=GOLD)
        if event.from_number or event.to_number:
            text.append(f"  {event.from_number or '?'} → {event.to_number or '?'}",
                        style="grey50")
    else:
        text.append(f"{short_id(getattr(event, 'sid', ''), 14):<15}", style="grey58")
        text.append(f"{'message':<10}", style=PURPLE)
        text.append(str(getattr(event, "state", "")), style=TURQUOISE)
        body = getattr(event, "body", None)
        if body:
            text.append(f"  {body[:48]}", style="grey50")
    return text


def fail(message: str) -> None:
    err_console.print(Text("error: ", style="bad") + Text(message))


def hint(message: str) -> None:
    """A follow-up line telling someone what to do about the error above."""
    err_console.print(Text("  " + message, style="muted"))
