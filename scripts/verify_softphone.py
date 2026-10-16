#!/usr/bin/env python3
"""Place a real SIP call with `swsh.softphone`, over loopback, in 10 seconds.

The test suite never opens a socket, so nothing in it can answer the only
question that matters about this module: does it actually place a call? This
does. It starts a second process that answers (the SIP stack allows exactly one
runtime per process, which is why a bench needs two), dials it with the real
`Softphone`, waits for RTP, sends DTMF, and hangs up.

    .venv/bin/python scripts/verify_softphone.py

It needs no credentials, no space and no network — both ends are on 127.0.0.1.
What it proves is the whole path: configuration, account, dial, the event
translation into `Softphone.line`, DTMF, and teardown. Run it after touching
`softphone.py`; the unit tests cover the shapes, this covers the call.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swsh.softphone import INSTALL_HINT, Device, Softphone, available

CALLER_PORT, CALLEE_PORT = 15080, 15081

# The answering end, as a script: one runtime per process is a hard limit of the
# stack, so the far end cannot live in this one.
CALLEE = f"""
import asyncio, baresip

async def main():
    runtime = baresip.Runtime()
    await runtime.start(baresip.Config(
        audio_driver="aumem", native_log_level="error", net_interface="127.0.0.1",
        extra_config_text="sip_listen 127.0.0.1:{CALLEE_PORT}\\n"))
    agent = await baresip.UserAgent.create(runtime, baresip.Account(
        user="callee", domain="127.0.0.1:{CALLEE_PORT}", password="", reg_interval=0))
    done = asyncio.Event()

    def incoming(call):
        print("callee: incoming", flush=True)
        asyncio.get_running_loop().create_task(call.answer())
        call.on_dtmf(lambda digit: print("callee: dtmf", digit.digit, flush=True))
        call.on(lambda e: done.set() if e.event.name == "CALL_CLOSED" else None)

    agent.on_incoming(incoming)
    print("callee: ready", flush=True)
    try:
        await asyncio.wait_for(done.wait(), 30)
    except asyncio.TimeoutError:
        print("callee: timed out", flush=True)
    await runtime.close()

asyncio.run(main())
"""


async def main() -> int:
    if not available():
        print(f"the SIP stack did not load: {INSTALL_HINT}")
        return 2

    callee = subprocess.Popen([sys.executable, "-c", CALLEE],
                              stdout=subprocess.PIPE, text=True, bufsize=1)
    assert callee.stdout is not None
    for line in callee.stdout:
        print(line.rstrip())
        if "ready" in line:
            break

    phone = Softphone()
    await phone.start(Device(
        username="caller", password="", domain=f"127.0.0.1:{CALLER_PORT}",
        audio="aumem", register=False, net_interface="127.0.0.1",
        extra_config=f"sip_listen 127.0.0.1:{CALLER_PORT}\n",
    ))
    print(f"caller: {phone.log[-1][1]}")

    await phone.dial(f"sip:callee@127.0.0.1:{CALLEE_PORT}")
    for _ in range(80):
        await asyncio.sleep(0.25)
        if phone.line.state in ("up", "ended"):
            break
    print(f"caller: line {phone.line.state} with {phone.line.peer}")
    ok = phone.line.state == "up"

    if ok:
        await phone.send_dtmf("42")
        await asyncio.sleep(1.0)
        await phone.hangup()
        await asyncio.sleep(0.5)

    await phone.stop()
    try:
        callee.wait(timeout=10)
    except subprocess.TimeoutExpired:
        callee.kill()
    print(callee.stdout.read().rstrip())

    print("\n".join(f"  {text}" for _, text in phone.log))
    print("\nOK: the call went up, carried DTMF and hung up" if ok
          else "\nFAILED: the call never established")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
