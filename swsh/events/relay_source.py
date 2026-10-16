"""RELAY WebSocket source.

RELAY is the lowest-latency channel and the only one carrying control-plane
detail: DTMF collection, play and record state, detection results, transcription
progress. Polling can never see any of that.

Its limitation is coverage. RELAY only delivers events for calls routed to a
topic this client subscribes to, so it complements rather than replaces the
poller. The status bar says which channels are live precisely so this is never
mistaken for a complete view.

**Implementation note.** ``RelayClient`` dispatches each ``signalwire.event`` to
a matching ``Call`` object and exposes no global hook for raw events. Subscribing
via ``on_call`` would only ever see inbound calls this client is handling. To get
a full tap, ``_TappedRelayClient`` overrides the private ``_handle_event`` to
publish every payload before delegating upward. That reaches into a private
method, so the override is guarded: if a future SDK version removes it, swsh
falls back to the public ``on_call`` path and reports reduced coverage rather
than failing to start.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from ..client import event_from_relay
from ..config import Profile
from ..models import MessageEvent, Source
from .bus import EventBus


class RelaySource:
    """Streams RELAY events onto the bus, reconnecting as needed."""

    def __init__(self, profile: Profile, bus: EventBus, topics: list[str],
                 *, max_active_calls: int = 1000):
        self.profile = profile
        self.bus = bus
        self.topics = topics
        self.max_active_calls = max_active_calls

        self.connected = False
        self.degraded = False  # true when running without the raw-event tap
        self.last_error: str | None = None
        self.events_seen = 0

        self._client: Any = None
        self._task: asyncio.Task[None] | None = None

    @property
    def status(self) -> str:
        if self.last_error:
            return f"relay: error ({self.last_error})"
        if not self.connected:
            return "relay: connecting"
        suffix = " (degraded)" if self.degraded else ""
        return f"relay: {','.join(self.topics)}{suffix} ({self.events_seen})"

    def start(self) -> asyncio.Task[None]:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run(), name="swsh-relay")
        return self._task

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._client is not None:
            with contextlib.suppress(Exception):
                await self._client.disconnect()
            self._client = None
        self.connected = False

    async def run(self) -> None:
        """Connect and stay connected. The SDK backs off internally; this loop
        handles the case where it gives up entirely."""
        delay = 1.0
        while True:
            try:
                await self._connect_once()
                delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                self.last_error = str(exc)[:120]
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)

    async def _connect_once(self) -> None:
        client = self._build_client()
        self._client = client

        await client.connect()
        self.connected = True
        self.last_error = None

        if self.topics:
            await client.receive(self.topics)

        # Hold the connection open until it drops or the task is cancelled.
        while self.connected:
            await asyncio.sleep(1.0)
            if getattr(client, "_ws", None) is None and not getattr(client, "_connected", True):
                break

    def _build_client(self) -> Any:
        from signalwire.relay import RelayClient

        publish = self._publish
        has_tap = hasattr(RelayClient, "_handle_event")

        if has_tap:
            class _TappedRelayClient(RelayClient):  # type: ignore[misc,valid-type]
                async def _handle_event(self, payload: dict[str, Any]) -> None:
                    try:
                        publish(payload)
                    except Exception:
                        pass  # never let the tap break dispatch
                    await super()._handle_event(payload)

            factory = _TappedRelayClient
            self.degraded = False
        else:
            factory = RelayClient
            self.degraded = True

        client = factory(
            project=self.profile.project,
            token=self.profile.token,
            # RELAY connects to relay.<domain>, not the space host.
            host=self.profile.relay_host,
            contexts=self.topics or None,
            max_active_calls=self.max_active_calls,
        )

        if self.degraded:
            # Public fallback: only inbound calls on our topics are visible.
            @client.on_call
            async def _watch(call: Any) -> None:
                for event_type in (
                    "calling.call.state", "calling.call.play", "calling.call.record",
                    "calling.call.collect", "calling.call.connect", "calling.call.detect",
                ):
                    call.on(event_type, lambda e, t=event_type: publish(
                        {"event_type": t, "params": getattr(e, "params", {})}
                    ))

        return client

    def _publish(self, payload: dict[str, Any]) -> None:
        self.events_seen += 1
        event_type = str(payload.get("event_type", ""))

        if event_type.startswith("messaging."):
            params = payload.get("params", {})
            self.bus.publish(
                MessageEvent(
                    sid=str(params.get("message_id") or ""),
                    state=str(params.get("message_state") or "unknown"),
                    source=Source.RELAY,
                    direction=params.get("direction"),
                    from_number=params.get("from_number"),
                    to_number=params.get("to_number"),
                    body=params.get("body"),
                    media=list(params.get("media") or []),
                    segments=params.get("segments"),
                    raw=dict(params),
                )
            )
            return

        if event_type.startswith("calling."):
            self.bus.publish(event_from_relay(payload))
