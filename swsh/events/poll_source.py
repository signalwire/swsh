"""REST polling source.

This is the channel that always works. It needs no public URL, no topic on a
number, and no configuration beyond credentials, so swsh shows a correct call
table the moment a token is pasted in. RELAY and status callbacks are layered on
top for latency; this one is the floor and the reconciler.

It reads the voice logs API, which lists every leg on the project while it is
up and keeps the row when it ends. That shape drives the delta logic: a leg is
published while live and once more when its row turns terminal, carrying the
real end reason and duration. Rows that were already over when the poller first
saw them are history, not events, and are left alone.

The interval adapts: fast while calls are up, slow when the project is quiet, and
backing off on errors so a rate limit or an outage does not turn into a hot loop.
"""

from __future__ import annotations

import asyncio
import random
import time

from ..client import SwshClient, event_from_call
from ..models import CallEvent, CallRef, CallState, Source
from .bus import EventBus


class PollSource:
    """Polls live calls on an adaptive interval and publishes deltas."""

    def __init__(
        self,
        client: SwshClient,
        bus: EventBus,
        *,
        active_interval: float = 2.0,
        # Idle is how long a brand-new call can go unnoticed when no push
        # channel is on, which is the default. The voice log read is cheap.
        idle_interval: float = 5.0,
        max_interval: float = 120.0,
        limit: int = 100,
    ):
        self.client = client
        self.bus = bus
        self.active_interval = active_interval
        self.idle_interval = idle_interval
        self.max_interval = max_interval
        self.limit = limit

        self.connected = False
        self.last_poll: float | None = None
        self.last_error: str | None = None
        self.polls = 0

        # Live calls from the last poll: key -> (state, ref). Only live ones,
        # so a terminal row is recognised as "this call just ended" exactly once.
        self._seen: dict[str, tuple[CallState, CallRef]] = {}
        self._failures = 0
        self._task: asyncio.Task[None] | None = None

    @property
    def status(self) -> str:
        if self.last_error:
            return f"poll: error ({self.last_error})"
        if not self.connected:
            return "poll: starting"
        return f"poll: ok ({self.polls})"

    def start(self) -> asyncio.Task[None]:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run(), name="swsh-poll")
        return self._task

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def run(self) -> None:
        while True:
            interval = await self._tick()
            # Jitter keeps several swsh instances on one project from
            # synchronising their polls into a thundering herd.
            await asyncio.sleep(interval * random.uniform(0.85, 1.15))

    async def _tick(self) -> float:
        try:
            calls = await self.client.recent_calls(
                limit=self.limit, lookback=self.client.LIVE_LOOKBACK_SECONDS
            )
        except Exception as exc:
            self._failures += 1
            self.connected = False
            self.last_error = str(exc)[:120]
            # Exponential backoff, capped.
            return min(self.idle_interval * (2 ** min(self._failures, 5)), self.max_interval)

        self._failures = 0
        self.connected = True
        self.last_error = None
        self.last_poll = time.time()
        self.polls += 1

        current: dict[str, tuple[CallState, CallRef]] = {}
        for call in calls:
            key = call.ref.key
            if not key:
                continue
            previous = self._seen.get(key)
            if call.is_live:
                current[key] = (call.state, call.ref)
                # Only publish when this poll actually learned something.
                # Without this the bus would emit every live call every two
                # seconds.
                if previous is None or previous[0] != call.state:
                    self.bus.publish(event_from_call(call))
            elif previous is not None:
                # Was live last poll, over now: the row carries the reason and
                # the final duration, so this is the authoritative "ended".
                self.bus.publish(event_from_call(call))

        # A call that was live last time and has left the window entirely has
        # ended between polls. The row is gone, so the reason is unknown; a
        # push channel or a later log lookup can fill it in.
        for key, (_, ref) in self._seen.items():
            if key in current:
                continue
            if any(c.ref.key == key for c in calls):
                continue  # handled above as a terminal row
            self.bus.publish(
                CallEvent(
                    ref=ref,
                    kind="state",
                    source=Source.POLL,
                    state=CallState.ENDED,
                    detail="disappeared between polls",
                )
            )

        self._seen = current
        return self.active_interval if current else self.idle_interval
