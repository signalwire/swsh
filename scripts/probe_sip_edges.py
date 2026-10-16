#!/usr/bin/env python3
"""Ask a space's SIP edges whether they answer this machine, over UDP and TCP.

A registration that stops working where it used to looks exactly like "the
stack cannot register" if the only thing you can see is the error your own
client printed. This separates the network path from the client: UDP timing
out while TCP returns `200 Keepalive`, or an edge that accepts the connection
and returns nothing, is the path, not sw.

One OPTIONS per edge per transport, and no retries. Nothing here
authenticates: an OPTIONS needs no credentials, so no project token is read and
no account is created.

    python scripts/probe_sip_edges.py example-0123456789ab.sip.signalwire.com

The domain is the one on the project's SIP profile - `sw sipprofile get`, or
the `identity` line that `y` copies out of the cockpit. It is never derived
from the space host: it carries a per-space identifier only the profile knows.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swsh.softphone import edge_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("domain", help="the project's SIP domain")
    parser.add_argument("--timeout", type=float, default=4.0,
                        help="seconds to wait per probe (default: 4)")
    args = parser.parse_args()
    for line in asyncio.run(edge_report(args.domain, timeout=args.timeout)):
        print(line)


if __name__ == "__main__":
    main()
