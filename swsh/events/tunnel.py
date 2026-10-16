"""Public URL management for the callback sink.

SignalWire has to be able to reach swsh over the public internet to deliver
status callbacks, which is the single most tedious part of local development.
This module drives the ngrok binary, found on ``PATH``, and reads the public URL
back out of ngrok's local API rather than scraping stdout, which is fragile.

Bring-your-own is supported too: pass ``--public-url`` and no tunnel is started.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
from dataclasses import dataclass

import httpx

NGROK_API = "http://127.0.0.1:4040/api/tunnels"


class TunnelError(RuntimeError):
    pass


@dataclass(slots=True)
class Tunnel:
    """A reachable public base URL, and whatever process is backing it."""

    public_url: str
    managed: bool = False
    _process: asyncio.subprocess.Process | None = None

    async def close(self) -> None:
        if self._process is None:
            return
        with contextlib.suppress(ProcessLookupError):
            self._process.terminate()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._process.wait(), timeout=5)
        if self._process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                self._process.kill()
        self._process = None


async def open_tunnel(port: int, *, public_url: str | None = None,
                      timeout: float = 20.0) -> Tunnel:
    """Return a tunnel for ``port``, starting ngrok unless a URL was supplied."""
    if public_url:
        return Tunnel(public_url=public_url.rstrip("/"), managed=False)

    existing = await _find_existing(port)
    if existing:
        # Someone already has ngrok pointed here; reuse rather than fight it.
        return Tunnel(public_url=existing, managed=False)

    binary = shutil.which("ngrok")
    if not binary:
        raise TunnelError(
            "ngrok not found. Install it, or pass --public-url with your own "
            "publicly reachable HTTPS endpoint."
        )

    process = await asyncio.create_subprocess_exec(
        binary, "http", str(port), "--log", "stdout",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if process.returncode is not None:
            raise TunnelError(
                f"ngrok exited immediately with code {process.returncode}. "
                "Is your authtoken configured? Try `ngrok config add-authtoken ...`."
            )
        url = await _find_existing(port)
        if url:
            return Tunnel(public_url=url, managed=True, _process=process)
        await asyncio.sleep(0.4)

    with contextlib.suppress(ProcessLookupError):
        process.terminate()
    raise TunnelError(f"ngrok did not report a public URL within {timeout:.0f}s")


async def _find_existing(port: int) -> str | None:
    """Ask ngrok's local API for an HTTPS tunnel pointing at our port."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as http:
            resp = await http.get(NGROK_API)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        return None

    candidates = []
    for tunnel in payload.get("tunnels", []):
        addr = str(tunnel.get("config", {}).get("addr", ""))
        if not addr.endswith(f":{port}"):
            continue
        url = tunnel.get("public_url", "")
        if url.startswith("https://"):
            return url.rstrip("/")
        candidates.append(url)
    return candidates[0].rstrip("/") if candidates else None
