#!/usr/bin/env python3
"""Read the INVITE this stack actually emits, byte for byte. No network.

`probe_dial_uri.py` answers which targets are *dialable*. This answers what
goes on the wire once one is — the request line, `To` and `Contact` — because
that is what the far end routes on, and it is not the string that was dialled.

    .venv/bin/python scripts/probe_invite_uri.py

A raw socket on 127.0.0.1 is the far end, so nothing leaves the machine and no
account, space or credential is involved. Each case runs in its own process:
the stack allows exactly one runtime per process.

The case that matters is whether a `;transport=` parameter can be kept *out*
of the request URI and `To`. `Account.aor()` renders
`<sip:user@domain;transport=X>` unconditionally and the stack copies that
parameter onto the target it completes, so an INVITE out of `Account` always
carries one. A FreeSWITCH INVITE that routes to the PSTN carries none — it
names its transport in `Contact` only, which is where RFC 3261 puts it.

`UserAgent.create` also accepts a **raw AOR string**, which is the lever: an
AOR with no transport parameter is the only way to ask this stack for the
clean request URI, and this probe is how that claim gets checked rather than
assumed.

What it found, and what `swsh.softphone.aor_of` is built on:

    Account(transport="udp")        INVITE sip:+1...@host;transport=udp
    Account(transport="tcp")        INVITE sip:+1...@host;transport=tcp
    raw AOR, no transport           INVITE sip:+1...@host
    raw AOR + ";transport=udp"      INVITE sip:+1...@host;transport=udp

The `To` header always matches the request line, and `Contact` names the
transport only when it is not the default UDP socket — which is the shape the
working FreeSWITCH trunk sends. So:

  * there is no way through `Account` to omit the parameter;
  * a `;transport=` on the *dial* URI is copied through, so it cannot be used
    to clean up an account that names one;
  * a `To` passed in `dial(headers=...)` is **ignored** — the stack renders
    `To` from the target URI either way;
  * the raw AOR is the only clean request URI on offer, and asking for `tcp`
    or `tls` necessarily puts the parameter back, because the URI is the only
    place baresip takes the transport from.

**`To` always mirrors the request line here, and that cannot be separated.**
That matters because a softphone whose calls *do* reach the PSTN sends the
parameter in the request URI and **not** in `To`:

    INVITE sip:+1440...@space;transport=UDP SIP/2.0     <- parameter
    To: <sip:+1440...@space>                            <- none

So the request-URI parameter is demonstrably harmless, and only `To` is
suspect. Since this stack cannot produce that combination, a named transport
cannot be had with a clean `To` — which leaves an unnamed transport (UDP, no
parameter anywhere) as the only shape here that matches a call known to route.
"""

from __future__ import annotations

import selectors
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swsh.softphone import available

LISTEN_PORT = 15098   # the far end: a raw socket, not a stack
FIRST_DIAL_PORT = 15060  # each case binds its own stack, on its own port
TARGET_USER = "+15551234567"

# Every case dials the same complete URI at the same host. The only thing that
# changes is how the account is described to the stack.
CASES: dict[str, str] = {
    "account-udp": """
account = baresip.Account(user="probe", domain=DOMAIN, password="", reg_interval=0)
target = f"sip:{USER}@{HOST}"
""",
    "account-tcp": """
account = baresip.Account(user="probe", domain=DOMAIN, password="", reg_interval=0,
                          transport="tcp")
target = f"sip:{USER}@{HOST}"
""",
    "aor-no-transport": """
account = f"<sip:probe@{DOMAIN}>;regint=0;answermode=manual;dtmfmode=rtpevent"
target = f"sip:{USER}@{HOST}"
""",
    "aor-no-transport-uri-udp": """
account = f"<sip:probe@{DOMAIN}>;regint=0;answermode=manual;dtmfmode=rtpevent"
target = f"sip:{USER}@{HOST};transport=udp"
""",
    # The two that matter: the real code path, through the real Device.
    "swsh-device-default": """
from swsh import softphone
account = softphone.aor_of(softphone.Device(
    username="probe", password="", domain=DOMAIN, register=False))
target = f"sip:{USER}@{HOST}"
""",
    "swsh-device-tcp": """
from swsh import softphone
account = softphone.aor_of(softphone.Device(
    username="probe", password="", domain=DOMAIN, register=False,
    transport="tcp"))
target = f"sip:{USER}@{HOST}"
""",
    # A working softphone sends the parameter in the request URI but NOT in
    # `To`. These two ask whether this stack can be made to do the same --
    # i.e. whether TCP is reachable without a parameter in `To`.
    "aor-tcp-clean-dial-uri": """
account = f"<sip:probe@{DOMAIN};transport=tcp>;regint=0;answermode=manual"
target = f"sip:{USER}@{HOST}"
""",
    "aor-tcp-to-header-override": """
account = f"<sip:probe@{DOMAIN};transport=tcp>;regint=0;answermode=manual"
target = f"sip:{USER}@{HOST}"
headers = {"To": f"<sip:{USER}@{HOST}>"}
""",
}

CHILD = """
import asyncio, sys, baresip
sys.path.insert(0, {repo!r})

DOMAIN = "127.0.0.1:{dial_port}"
HOST = "127.0.0.1:{listen_port}"
USER = "{user}"

async def main():
    runtime = baresip.Runtime()
    await runtime.start(baresip.Config(
        audio_driver="aumem", native_log_level="error",
        net_interface="127.0.0.1",
        extra_config_text="sip_listen 127.0.0.1:{dial_port}\\n"))
{case}
    agent = await baresip.UserAgent.create(runtime, account)
    try:
        call = await agent.dial(target, headers=locals().get('headers'))
        # The INVITE is already on its way; the far end is a dumb socket and
        # will never answer, so there is nothing to wait for.
        await asyncio.sleep(1.5)
        await call.hangup()
    except Exception as exc:
        print(f"dial failed: {{type(exc).__name__}}: {{exc}}", flush=True)
    await runtime.close()

asyncio.run(main())
"""


def listen() -> tuple[socket.socket, socket.socket]:
    """The far end: one UDP socket and one TCP listener on the same port."""
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind(("127.0.0.1", LISTEN_PORT))
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp.bind(("127.0.0.1", LISTEN_PORT))
    tcp.listen(1)
    return udp, tcp


def first_invite(udp: socket.socket, tcp: socket.socket, timeout: float) -> str:
    """The first INVITE to arrive over either transport, as text."""
    sel = selectors.DefaultSelector()
    sel.register(udp, selectors.EVENT_READ, "udp")
    sel.register(tcp, selectors.EVENT_READ, "tcp")
    for key, _ in sel.select(timeout) or ():
        if key.data == "udp":
            return udp.recvfrom(65535)[0].decode("utf8", "replace")
        conn, _ = tcp.accept()
        with conn:
            conn.settimeout(timeout)
            return conn.recv(65535).decode("utf8", "replace")
    return ""


def report(name: str, message: str) -> None:
    if not message:
        print(f"{name:26} no INVITE arrived")
        return
    lines = message.splitlines()
    request = lines[0] if lines else ""
    print(f"{name:26} {request}")
    for header in ("To:", "From:", "Contact:", "Via:"):
        for line in lines[1:]:
            if line.startswith(header):
                print(f"{'':26}   {line}")
                break


def main() -> int:
    if not available():
        print("the SIP stack did not load; nothing to probe")
        return 0
    print(f"far end: 127.0.0.1:{LISTEN_PORT} (a raw socket, never answers)\n")
    for offset, (name, case) in enumerate(CASES.items()):
        udp, tcp = listen()
        # A terminated child can hold its port into the next case, and the
        # stack answers that with "Address already in use" and never dials.
        dial_port = FIRST_DIAL_PORT + offset
        script = CHILD.format(repo=str(Path(__file__).resolve().parents[1]),
                              dial_port=dial_port, listen_port=LISTEN_PORT,
                              user=TARGET_USER,
                              case="\n".join("    " + line for line
                                             in case.strip().splitlines()))
        child = subprocess.Popen([sys.executable, "-c", script],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True)
        try:
            message = first_invite(udp, tcp, timeout=10.0)
        finally:
            child.terminate()
            try:
                output, _ = child.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                output = ""
            udp.close()
            tcp.close()
        report(name, message)
        if not message:
            # A silent "no INVITE" is useless: the reason is in the child, and
            # the common one is a port the previous case has not released yet.
            for line in (output or "").strip().splitlines()[-3:]:
                print(f"{'':26}   {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
