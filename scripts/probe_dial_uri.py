#!/usr/bin/env python3
"""Ask the SIP stack which dial targets it will accept. No network, no account.

The shape of a dial target has been got wrong twice, both times by reasoning
about the string instead of asking the stack. This settles it: it brings a
runtime up on loopback with no registrar and calls `UserAgent.dial` with every
shape a person might type, printing what came back.

    .venv/bin/python scripts/probe_dial_uri.py

Nothing leaves the machine — `ua_connect` validates and builds the request
before any packet is sent, so the refusals here happen locally and the
successes are hung up immediately. It is the companion to
`verify_softphone.py`: that one proves a call completes, this one proves which
strings are even dialable.

What it found, and what `swsh.softphone.dial_uri` is built on:

    sip:user@host              OK
    sip:user@host;user=phone   OK
    user@host                  refused
    user                       refused
    tel:+1...                  refused
    sips:user@host             refused

The errno on a refusal is not stable — ENOENT ("No such file or directory")
and ENOSYS ("Function not implemented") both come back depending on the host —
so do not match on the message. The refusal is the constant.

`ua_connect` does **not** complete the scheme. That is the whole finding: the
scheme is mandatory, so it cannot carry a routing decision. What decides
whether a call reaches the PSTN is the user part being E.164.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swsh.softphone import INSTALL_HINT, available

PORT = 15099
DOMAIN = "example-0123456789ab.sip.signalwire.com"

TARGETS = (
    f"sip:+15551234567@{DOMAIN}",
    f"+15551234567@{DOMAIN}",
    "+15551234567",
    f"sip:1001@{DOMAIN}",
    f"1001@{DOMAIN}",
    "1001",
    "tel:+15551234567",
    f"sips:bob@{DOMAIN}",
    f"sip:+15551234567@{DOMAIN};user=phone",
    "sip:x@127.0.0.1:5060",
)


async def main() -> int:
    if not available():
        print(f"the SIP stack did not load: {INSTALL_HINT}")
        return 2
    import baresip

    runtime = baresip.Runtime()
    await runtime.start(baresip.Config(
        audio_driver="aumem", native_log_level="error", max_concurrent_calls=1,
        net_interface="127.0.0.1",
        extra_config_text=f"sip_listen 127.0.0.1:{PORT}\n"))
    agent = await baresip.UserAgent.create(runtime, baresip.Account(
        user="probe", domain="127.0.0.1", password="", reg_interval=0))

    width = max(len(t) for t in TARGETS) + 2
    for target in TARGETS:
        try:
            call = await agent.dial(target)
            print(f"  OK     {target:<{width}} accepted")
            try:
                await call.hangup()
            except Exception:
                pass
        except Exception as exc:
            print(f"  FAIL   {target:<{width}} {type(exc).__name__}: {exc}")
        await asyncio.sleep(0.15)

    await runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
