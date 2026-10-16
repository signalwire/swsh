"""`sw listen`: tunnel, sink, rewrite, stream, restore.

The flow, in order, because the ordering matters for safety:

1. open a tunnel (or accept a supplied public URL)
2. start the local sink and wait for it to actually bind
3. journal the current routing of every number about to be touched
4. rewrite their status callback URLs
5. stream callbacks until interrupted
6. restore, always, including on an unhandled exception

Step 3 before step 4 is what makes an unclean exit recoverable.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from typing import Any

from rich.panel import Panel
from rich.text import Text

from . import ui
from .client import SwshClient
from .config import Profile
from .events.bus import EventBus
from .events.rewrite import CallbackRewriter, RewriteError
from .events.tunnel import TunnelError, open_tunnel
from .events.webhook_source import WebhookSink, serve_sink


async def run_listen(
    *,
    profile: Profile,
    port: int,
    public_url: str | None,
    numbers: list[str],
    rewrite: bool,
    forward: str | None,
    restore_only: bool,
    verify_signatures: bool,
    as_json: bool,
) -> None:
    async with SwshClient(profile) as client:
        if restore_only:
            await _restore_only(client)
            return

        bus = EventBus()
        sink = WebhookSink(
            bus,
            auth_token=profile.token,
            verify_signatures=verify_signatures,
            forward_to=forward,
            on_request=None,
        )

        tunnel = None
        rewriter: CallbackRewriter | None = None
        server_task: asyncio.Task[None] | None = None

        try:
            server_task = await serve_sink(sink, port)

            try:
                tunnel = await open_tunnel(port, public_url=public_url)
            except TunnelError as exc:
                ui.fail(str(exc))
                return
            sink.public_url = tunnel.public_url
            callback_url = sink.url_for("cb/voice")

            selected: list[dict[str, Any]] = []
            if rewrite:
                selected = await _select_numbers(client, numbers)
                if not selected:
                    ui.fail(
                        "no matching numbers; "
                        "use --no-rewrite to watch without changing config"
                    )
                    return
                rewriter = CallbackRewriter(client=client)
                await rewriter.apply(selected, callback_url)

            _print_header(tunnel.public_url, callback_url, rewriter, port)
            await _stream(bus, sink, as_json=as_json)

        finally:
            # Restore first: it is the part the user cannot do themselves.
            if rewriter is not None and rewriter.snapshots:
                ui.console.print("\n[muted]restoring callback URLs...[/muted]")
                for number, error in await rewriter.restore():
                    if error:
                        ui.fail(f"{number}: {error}  (retry with `sw listen --restore`)")
                    else:
                        ui.console.print(f"  [ok]restored[/ok] {number}")
            if tunnel is not None:
                await tunnel.close()
            if server_task is not None:
                server_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await server_task
            bus.close()


async def _restore_only(client: SwshClient) -> None:
    try:
        rewriter = CallbackRewriter.load_journal(client)
    except RewriteError as exc:
        ui.fail(str(exc))
        return
    if rewriter is None:
        ui.console.print("[muted]nothing to restore[/muted]")
        return
    for number, error in await rewriter.restore():
        if error:
            ui.fail(f"{number}: {error}")
        else:
            ui.console.print(f"[ok]restored[/ok] {number}")


async def _select_numbers(client: SwshClient, wanted: list[str]) -> list[dict[str, Any]]:
    """Resolve the numbers to rewrite, matching on E.164 or resource id."""
    payload = await client.call_sdk("phone_numbers.list")
    rows = payload.get("data", []) if isinstance(payload, dict) else list(payload or [])
    if not wanted:
        return rows

    targets = {w.strip() for w in wanted}
    return [
        row
        for row in rows
        if str(row.get("number", "")) in targets or str(row.get("id", "")) in targets
    ]


def _print_header(public_url: str, callback_url: str, rewriter: CallbackRewriter | None,
                  port: int) -> None:
    body = Text()
    body.append("tunnel    ", style="muted")
    body.append(f"{public_url}\n", style="cool")
    body.append("callback  ", style="muted")
    body.append(f"{callback_url}\n", style="accent")
    body.append("local     ", style="muted")
    body.append(f"http://127.0.0.1:{port}\n", style="grey58")

    if rewriter is not None:
        body.append("\nrewritten\n", style="bold")
        for snapshot in rewriter.snapshots:
            body.append(f"  {snapshot.number}", style="brand")
            body.append(f"  ({snapshot.applied_field})\n", style="grey50")
        for number, reason in rewriter.skipped:
            body.append(f"  {number}", style="grey50")
            body.append(f"  skipped: {reason}\n", style="warn")
    else:
        body.append("\nno numbers changed (--no-rewrite)\n", style="muted")

    body.append("\nCtrl-C to stop and restore.", style="muted")
    ui.console.print(Panel(body, title="sw listen", border_style="brand", expand=False))


async def _stream(bus: EventBus, sink: WebhookSink, *, as_json: bool) -> None:
    """Print callbacks as they land, until interrupted."""
    sub = bus.subscribe()
    stop = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    async def pump() -> None:
        while True:
            event = await sub.get()
            if as_json:
                import json

                from .events.bus import _jsonable

                print(json.dumps(_jsonable(event), default=str), flush=True)
            else:
                ui.console.print(ui.event_line(event))

    pump_task = asyncio.create_task(pump())
    try:
        await stop.wait()
    finally:
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump_task
        bus.unsubscribe(sub)
        ui.console.print(
            f"\n[muted]{sink.received} callbacks received, {sink.rejected} rejected[/muted]"
        )
