"""The phone: a SIP device and a local AI agent, rendered for the calls view.

This was a screen of its own called the lab, and being its own screen was the
problem. A softphone exists to make a call happen; the thing you want to watch
while it does is the event feed, and that is on the calls view. Two tabs meant
dialling on one and watching on the other, which is the one thing a phone on a
screen is supposed to make possible. So the phone is a panel under the live
calls table now, and `sw sh` has one fewer view.

Nothing in this module talks to anything. It renders `softphone.Softphone` and
`agentlab.AgentLab` state, the way `home.py` renders counts the app fetched, so
the panel cannot be the reason a call is slow.
"""

from __future__ import annotations

import time
from typing import Any

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from .. import softphone as sp
from .. import ui
from ..softphone import FAILED, OFFLINE, REGISTERED, REGISTERING

# One colour per state, shared by both panels so "green means working" holds
# across the screen.
_STATE_STYLE = {
    OFFLINE: "grey42",
    REGISTERING: ui.GOLD,
    REGISTERED: "green",
    FAILED: "red",
    "stopped": "grey42",
    "starting": ui.GOLD,
    "running": "green",
    "failed": "red",
    # call states
    "idle": "grey42",
    "calling": ui.GOLD,
    "ringing": ui.GOLD,
    "up": ui.TURQUOISE,
    "ended": "grey50",
}


def _kv(table: Table, key: str, value: Any, style: str = "") -> None:
    table.add_row(Text(key, style="grey50"), Text(str(value), style=style))


def _grid() -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", no_wrap=True)
    table.add_column(overflow="fold")
    return table


def _feed(entries: list[tuple[float, str]], lines: int = 8) -> Text:
    """The last few things that happened, oldest first.

    Short on purpose: this is a panel, not a log viewer, and the whole point is
    that the state above it is already the answer. The feed is for when it is
    not — a registration that failed, a call the far end declined.
    """
    text = Text()
    for stamp, line in entries[-lines:]:
        text.append(time.strftime("%H:%M:%S ", time.localtime(stamp)), style="grey35")
        text.append(line + "\n", style="grey62")
    return text



def diagnostics(phone: Any, profile: Any = None, agent: Any = None) -> str:
    """Everything a failing call needs, as plain text somebody can paste.

    The cockpit is a full-screen app, so what is on it cannot be selected with
    a mouse and cannot be quoted in a ticket. That made the one thing worth
    quoting — the shape of the account and the dial target — the hardest thing
    to get out, and a call was debugged for days across screenshots instead.

    The account line is the reason this exists. It shows whether a transport
    parameter is on the URI, and the request line and `To` of every INVITE are
    built from it, so it answers "what am I actually sending" without a packet
    capture. The password is redacted; nothing here is a credential.
    """
    out: list[str] = ["sw phone diagnostics"]

    def row(label: str, value: Any) -> None:
        out.append(f"  {label:<14}{value}")

    if profile is not None:
        row("profile", f"{profile.name}  ({profile.space})")
    row("sip stack", "installed" if sp.available() else sp.unavailable_reason())

    device = getattr(phone, "device", None)
    out.append("")
    if device is None:
        out.append("  no device configured")
    else:
        row("identity", device.aor)
        row("transport", device.transport_label)
        row("audio", device.audio)
        if device.registrar:
            row("registrar", device.registrar)
        if device.auth_user:
            row("auth user", device.auth_user)
        if device.codecs:
            row("codecs", ", ".join(device.codecs))
        row("dtmf", device.dtmf_mode)
        # The line that matters. Whether ";transport=" appears inside the
        # angle brackets is the whole question.
        row("account", sp.redacted_aor(device))

    out.append("")
    row("state", getattr(phone, "state", "?"))
    if getattr(phone, "error", ""):
        row("error", phone.error)
    if getattr(phone, "last_dial", ""):
        row("last dial", phone.last_dial)
    line = getattr(phone, "line", None)
    if line is not None and getattr(line, "state", "idle") != "idle":
        row("call", f"{line.state} {line.direction} {line.peer}".strip())

    traced = bool(device is not None and device.sip_trace)
    row("sip trace", str(sp.trace_path()) if traced
        else "off - tick 'log SIP signalling' on the device form")

    if agent is not None and getattr(agent, "state", "stopped") != "stopped":
        out.append("")
        row("agent", getattr(agent, "state", "?"))
        for name in ("route", "address", "public_url"):
            value = getattr(agent, name, "")
            if value:
                row(name, value)

    log = list(getattr(phone, "log", []))[-40:]
    if log:
        out.append("")
        out.append("  feed (newest last)")
        for when, text in log:
            out.append(f"    {time.strftime('%H:%M:%S', time.localtime(when))}  {text}")

    return "\n".join(out) + "\n"


def _peer(peer: str, device: Any) -> str:
    """The other end, short enough to fit on one line.

    A dialled URI is `sip:+14405550166@` plus a domain carrying the space's own
    SIP identifier — fifty-odd characters for eleven digits of information. The
    domain is dropped when it is the device's own, because then it is already
    in the border title and folding it across two rows pushed the agent's line
    off the bottom of a four-row column. A peer somewhere else keeps its
    domain, which is the case where the domain is the point.
    """
    if not peer:
        return "-"
    user = sp.user_part(peer)
    if not user:
        return peer
    domain = peer.rsplit("@", 1)[-1] if "@" in peer else ""
    own = getattr(device, "domain", "") or ""
    if domain and own and domain.split(";")[0].lower() == own.lower():
        return user
    return f"{user}@{domain}" if domain else user


def title(phone: Any, *, available: bool) -> str:
    """The panel's border title: who this phone is and whether it is up.

    These live in the border rather than in a column because they are the
    longest strings on the panel and the least likely to change. A space's SIP
    domain carries a per-space identifier, which makes an AOR about fifty
    characters — wider than a third of the left pane, so in a column it folded
    across three lines and shoved the call state around every time it did. The
    border is the one place on the panel that is always the full width.
    """
    if not available:
        return "phone - no SIP stack"
    parts = ["phone", phone.state]
    device = phone.device
    if device is not None:
        parts.append(device.aor)
        parts.append(device.transport_label)
    else:
        parts.append("no device")
    return "  ".join(parts)


def state(phone: Any, lab: Any, *, available: bool) -> RenderableType:
    """What the phone is *doing*, for the narrow column beside the keypad.

    Only the moving parts. Who the phone is and whether it registered are in
    the border title, which has room for them; this column is four rows and
    about a third of the panel, and it is where you look while a call is
    connecting.

    Labels are left off on purpose. Every value here says what it is: a state
    is a word, a peer is a number or a URI, and an arrow is a direction.
    """
    if not available:
        return Text(f"{sp.unavailable_hint()}\n\noptional; the rest of sw works "
                    f"without it", style="grey50")

    out = Text()
    if phone.error:
        out.append(phone.error + "\n", style="red")
    if phone.device is None:
        out.append("no identity yet\n", style="grey62")
        out.append("press Device… to set\n", style="grey42")
        out.append("one, then Register", style="grey42")
        return out
    if phone.state != REGISTERED and not phone.error:
        out.append(phone.state + "\n", style=_STATE_STYLE.get(phone.state, "grey50"))
        if phone.state in (OFFLINE, FAILED):
            out.append("press Register\n", style="grey42")
        return out

    line = phone.line
    if line.state != "idle":
        out.append(line.state, style=_STATE_STYLE.get(line.state, "grey50"))
        if line.state == "up":
            out.append("  " + ui.duration_text(line.seconds), style="grey62")
        out.append("\n")
        arrow = "<-" if line.direction == "in" else "->"
        out.append(f"{arrow} {_peer(line.peer, phone.device)}\n", style="grey62")
        if line.reason:
            out.append(line.reason + "\n", style="grey50")
    elif not phone.error:
        # Idle is where somebody sits wondering what the pad is for, so this
        # is the one place the panel says. It is two short lines and it goes
        # away the moment there is a call to report instead.
        out.append("ready\n", style="green")
        out.append("type or tap a number,\n", style="grey42")
        out.append("then Dial. On a call the\n", style="grey42")
        out.append("keypad sends DTMF.", style="grey42")

    if lab is not None and getattr(lab, "state", "stopped") != "stopped":
        out.append("agent " + lab.state,
                   style=_STATE_STYLE.get(lab.state, "grey50"))
        out.append("\n")
        live = getattr(lab, "live", None)
        if live is not None and live.dial:
            # Same reason as the peer: the agent's SIP address is on the
            # device's own domain, so the domain is noise here.
            out.append(_peer(live.dial, phone.device) + "\n",
                       style=f"bold {ui.TURQUOISE}")
        if getattr(lab, "error", ""):
            out.append(lab.error + "\n", style="red")

    return out


def feed_lines(phone: Any, lab: Any, lines: int = 3) -> RenderableType:
    """The last few things either half said, newest last.

    Three lines, not eight. The panel sits under the calls table and above the
    action bar, and the event feed on the right is the log; this is only here
    so a failed registration says so where the button that caused it is.
    """
    entries = list(getattr(phone, "log", []))
    if lab is not None:
        entries += list(getattr(lab, "log", []))
    entries.sort(key=lambda row: row[0])
    return _feed(entries, lines=lines)
