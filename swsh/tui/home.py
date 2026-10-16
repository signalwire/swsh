"""The cockpit's landing view: a banner and the project at a glance.

The app used to open on the live calls table, which is the one screen that is
blank on a quiet project — a new arrival saw an empty table and no indication
of what else was there. This is what `sw sh` opens on instead: the wordmark,
which profile and space are in play, and a handful of counts that say what the
project actually holds, in the spirit of the dashboard on the portal.

Nothing here talks to the API. ``METRICS`` says what to count and the app's
worker fills the values in, so a slow or unreachable space costs a dash in a
tile rather than a frozen interface.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .. import ui

# The wordmark, five rows of block glyphs. Hand-set rather than generated: no
# figlet dependency, and it has to survive terminals whose font renders the
# half-block characters at odd widths, so only full blocks are used.
_GLYPHS = {
    "S": ("█████", "█    ", "█████", "    █", "█████"),
    "I": ("█████", "  █  ", "  █  ", "  █  ", "█████"),
    "G": ("█████", "█    ", "█  ██", "█   █", "█████"),
    "N": ("█   █", "██  █", "█ █ █", "█  ██", "█   █"),
    "A": ("█████", "█   █", "█████", "█   █", "█   █"),
    "L": ("█    ", "█    ", "█    ", "█    ", "█████"),
    "W": ("█   █", "█   █", "█ █ █", "█████", "██ ██"),
    "R": ("████ ", "█   █", "████ ", "█  █ ", "█   █"),
    "E": ("█████", "█    ", "█████", "█    ", "█████"),
}
_WORD = "SIGNALWIRE"
# 10 glyphs, 5 columns each, one column of air between: the banner needs this
# much room or it wraps into noise, and `banner` drops to one line instead.
LOGO_WIDTH = len(_WORD) * 6 - 1


def _logo_rows() -> list[str]:
    return [" ".join(_GLYPHS[letter][row] for letter in _WORD) for row in range(5)]


def banner(*, version: str, profile, width: int) -> RenderableType:
    """The wordmark over one line saying which project this is.

    Below ``LOGO_WIDTH`` the block letters wrap and read as noise, so a narrow
    terminal gets the same information on a single line instead.
    """
    where = Text(no_wrap=True)
    where.append("sw ", style=f"bold {ui.TURQUOISE}")
    where.append(version, style="grey50")
    where.append("  ·  ", style="grey30")
    where.append(profile.host, style=ui.TURQUOISE)
    where.append("  ·  ", style="grey30")
    where.append(profile.project[:8], style=ui.BLUE)
    if profile.name:
        where.append("  ·  ", style="grey30")
        where.append(profile.name, style=f"bold {ui.BLUE}")

    if width < LOGO_WIDTH + 4:
        compact = Text("SignalWire", style=f"bold {ui.TURQUOISE}")
        return Group(Text(""), Align.center(compact), Align.center(where), Text(""))

    logo = Text("\n".join(_logo_rows()), style=ui.TURQUOISE, no_wrap=True)
    wave = Text("~" * LOGO_WIDTH, style=ui.BLUE)
    return Group(Text(""), Align.center(logo), Align.center(wave),
                 Text(""), Align.center(where), Text(""))


@dataclass(frozen=True)
class Metric:
    """One tile. ``source`` says where the number comes from.

    ``store`` is counted from the merged call view already in memory and costs
    nothing. ``calls`` is the voice log over a window, the one count the API
    gives exactly. Anything else names a registry resource and is a `list`,
    which answers a page at a time — hence ``more`` on the value.
    """

    label: str
    source: str
    window: int = 0  # seconds, for the voice-log count


METRICS: tuple[Metric, ...] = (
    Metric("live calls", "store"),
    Metric("calls · 24h", "calls", window=24 * 3600),
    Metric("phone numbers", "numbers"),
    Metric("SIP endpoints", "sip"),
    Metric("AI agents", "agents"),
    Metric("SWML scripts", "swml"),
    Metric("subscribers", "subscribers"),
    Metric("video rooms", "videorooms"),
)


@dataclass(frozen=True)
class Count:
    """A tile's answer: a number, whether more pages follow, or why not."""

    value: int | None = None
    more: bool = False
    error: str = ""

    def render(self) -> Text:
        if self.error:
            return Text("—", style="grey35")
        if self.value is None:
            return Text("·", style="grey35")
        style = ui.TURQUOISE if self.value else "grey50"
        return Text(f"{self.value}{'+' if self.more else ''}", style=f"bold {style}")


def tiles(counts: dict[str, Count], *, width: int) -> RenderableType:
    """The metric tiles, wrapped to the terminal rather than fixed at four."""
    per_row = max(1, min(4, (width - 2) // 20))
    grid = Table.grid(padding=(0, 1))
    for _ in range(per_row):
        grid.add_column(justify="center")

    cells: list[RenderableType] = []
    for metric in METRICS:
        count = counts.get(metric.label, Count())
        cells.append(Panel(Align.center(count.render()), title=metric.label,
                           title_align="left", border_style="#1c2130",
                           height=3, width=18))
    for start in range(0, len(cells), per_row):
        row = cells[start:start + per_row]
        grid.add_row(*row, *[""] * (per_row - len(row)))
    return Align.center(grid)


def hints() -> RenderableType:
    """The four keys worth knowing on arrival, wrapping centred when narrow."""
    text = Text(justify="center")
    for key, what in ((":", "open a resource"), ("?", "every key"),
                      ("r", "refresh"), ("q", "quit")):
        text.append(f" {key} ", style=f"bold {ui.GOLD}")
        text.append(f"{what}   ", style="grey50")
    return text


def screen(*, version: str, profile, counts: dict[str, Count], width: int,
           note: str = "") -> RenderableType:
    parts: list[RenderableType] = [
        banner(version=version, profile=profile, width=width),
        tiles(counts, width=width),
        Text(""),
        hints(),
    ]
    if note:
        parts += [Text(""), Align.center(Text(note, style="grey35"))]
    return Group(*parts)
