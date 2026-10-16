#!/usr/bin/env python3
"""Dump the cockpit as painted text, so a layout bug is visible without eyes.

Textual's test harness answers questions about widgets, not about pixels. A
widget can exist, hold the value you set, pass `query_one`, report a sensible
`region` — and be laid out past the bottom of the screen, where nothing paints
it. That is exactly how the phone panel shipped invisible the first time: the
`ContentSwitcher` above it had no `height: 1fr`, took the whole left column,
and pushed the panel and the action bar off the screen. Every assertion about
them passed.

There is no text export in Textual, so this goes via `export_screenshot()` and
reassembles the SVG's text runs back into rows by their y and x. The result is
approximate — proportional glyph advances mean columns drift a cell or two —
so read it for structure, not for alignment. For alignment, assert on
`region` and `content_size`, the way
`test_lab.py::TestThePanelFitsTheColumnItSharesWithTheTable` does.

    python scripts/paint_cockpit.py                  # calls view, 170 cols
    python scripts/paint_cockpit.py --width 110      # narrow, to find clipping
    python scripts/paint_cockpit.py --busy           # on a call, agent up
    python scripts/paint_cockpit.py --view home

No credentials and no network: the profile is fake and every fetch fails,
which is fine — this is about where things land, not what they say.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swsh import agentlab, softphone
from swsh.config import Profile
from swsh.tui.app import SwshApp

# Wide enough that the banner does not wrap and the left column holds three
# phone columns; see LOGO_WIDTH in tui/home.py.
DEFAULT_WIDTH = 170
DEFAULT_HEIGHT = 38
# The SVG's font advance. Only used to turn an x offset back into a column.
CELL = 8.0

FAKE = Profile(name="paint", project="proj-1", token="tok",
               space="example.signalwire.com")
DOMAIN = "example-0123456789ab.sip.signalwire.com"

_TEXT = re.compile(
    r'<text[^>]*\sx="([\d.]+)"[^>]*\sy="([\d.]+)"[^>]*>(.*?)</text>', re.S)


def svg_to_text(svg: str) -> str:
    """Reassemble the SVG's text runs into rows. Structure, not alignment."""
    rows: dict[int, list[tuple[float, str]]] = {}
    for match in _TEXT.finditer(svg):
        x, y = float(match.group(1)), float(match.group(2))
        body = html.unescape(re.sub(r"<[^>]+>", "", match.group(3)))
        rows.setdefault(round(y), []).append((x, body))
    out: list[str] = []
    for y in sorted(rows):
        line = ""
        for x, text in sorted(rows[y]):
            col = round(x / CELL)
            if col > len(line):
                line += " " * (col - len(line))
            line += text
        out.append(line.rstrip())
    return "\n".join(out)


async def paint(args: argparse.Namespace) -> str:
    app = SwshApp(profile=FAKE)
    async with app.run_test(size=(args.width, args.height)) as pilot:
        await pilot.pause()
        if args.view == "calls":
            app.action_go_calls()
        elif args.view == "home":
            app.action_go_home()
        app.phone.device = softphone.Device("alice", "pw", DOMAIN)
        app.phone.state = softphone.REGISTERED
        if args.busy:
            # `on_call` is what the hook reads, and it reads `_call`.
            app.phone._call = object()
            app.phone.line = softphone.Line(
                state="up", peer=f"sip:+14405550166@{DOMAIN}", direction="out")
            app.lab.state = agentlab.RUNNING
            app.lab.live = agentlab.Live(
                spec=agentlab.AgentSpec(name="front desk"),
                public_url="https://example.ngrok.app", resource_id="wh-1",
                dial=f"sip:front-desk@{DOMAIN}")
        else:
            app.query_one("#phone-target").value = "+14405550166"
        app._render_phone()
        await pilot.pause()
        screen = svg_to_text(app.export_screenshot())
        if args.geometry:
            screen += "\n\n" + geometry(app, args.height)
        return screen


def geometry(app: SwshApp, height: int) -> str:
    """The numbers the picture cannot be trusted for."""
    out = ["geometry (region / content; OFF means never painted)"]
    for sel in ("#left", "#main", "#calls", "#phone", "#phone-top",
                "#phone-dial", "#phone-target", "#phone-hook", "#phone-keypad",
                "#phone-state", "#phone-buttons", "#actionbar"):
        found = app.query(sel)
        if not found:
            out.append(f"  --  {sel:15} absent")
            continue
        node = found.first()
        region, content = node.region, node.content_size
        painted = "ok " if (region.y + region.height) <= height else "OFF"
        out.append(f"  {painted} {sel:15} "
                   f"{region.width}x{region.height} @({region.x},{region.y})"
                   f"  content={content.width}x{content.height}")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--view", choices=("calls", "home"), default="calls")
    parser.add_argument("--busy", action="store_true",
                        help="a call in progress and the agent standing")
    parser.add_argument("--geometry", action="store_true", default=True)
    parser.add_argument("--no-geometry", dest="geometry", action="store_false")
    args = parser.parse_args()
    print(asyncio.run(paint(args)))


if __name__ == "__main__":
    main()
