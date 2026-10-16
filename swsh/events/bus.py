"""The unified event bus and the call store that sits on it.

Three channels feed this bus: RELAY over WebSocket, status callbacks over HTTP,
and REST polling. They overlap heavily by design, so the store's job is to merge
them into one truth without double counting and without letting a slow channel
overwrite a fast one with stale data.

Ordering is the subtle part. A poll issued before a call ended can land after
the RELAY ``ended`` event. ``Call.apply`` refuses to move state backwards, which
makes the merge order-independent.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections import deque
from collections.abc import AsyncIterator, Callable, Iterable
from pathlib import Path
from typing import Any

from ..models import Call, CallEvent, CallRef, MessageEvent, Source


class Subscription:
    """One consumer's view of the bus.

    Bounded so a stalled consumer cannot grow memory without limit; when it
    overflows the oldest events are dropped and counted rather than blocking
    the producers.
    """

    def __init__(self, maxsize: int = 2048, kinds: Iterable[str] | None = None):
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=maxsize)
        self.kinds = set(kinds) if kinds else None
        self.dropped = 0

    def wants(self, event: Any) -> bool:
        if self.kinds is None:
            return True
        return getattr(event, "kind", None) in self.kinds

    def offer(self, event: Any) -> None:
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
                self.dropped += 1
            with contextlib.suppress(asyncio.QueueFull):
                self._queue.put_nowait(event)

    async def get(self) -> Any:
        return await self._queue.get()

    async def __aiter__(self) -> AsyncIterator[Any]:
        while True:
            yield await self._queue.get()


class EventBus:
    """Fan-out for call and message events, with a replay buffer."""

    def __init__(self, replay: int = 500, record_to: Path | None = None):
        self._subs: list[Subscription] = []
        self._replay: deque[Any] = deque(maxlen=replay)
        self._record_path = record_to
        self._record_handle = None
        self.published = 0

    def subscribe(self, kinds: Iterable[str] | None = None, maxsize: int = 2048) -> Subscription:
        sub = Subscription(maxsize=maxsize, kinds=kinds)
        self._subs.append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        if sub in self._subs:
            self._subs.remove(sub)

    def history(self) -> list[Any]:
        return list(self._replay)

    def publish(self, event: Any) -> None:
        self.published += 1
        self._replay.append(event)
        self._record(event)
        for sub in self._subs:
            if sub.wants(event):
                sub.offer(event)

    def _record(self, event: Any) -> None:
        """Append to a JSONL trace when recording is on. Never fatal."""
        if self._record_path is None:
            return
        if self._record_handle is None:
            self._record_path.parent.mkdir(parents=True, exist_ok=True)
            self._record_handle = self._record_path.open("a", encoding="utf-8")
        try:
            self._record_handle.write(json.dumps(_jsonable(event), default=str) + "\n")
            self._record_handle.flush()
        except Exception:
            pass

    def close(self) -> None:
        if self._record_handle is not None:
            with contextlib.suppress(Exception):
                self._record_handle.close()
            self._record_handle = None


class CallStore:
    """Merged, deduplicated view of every call swsh knows about.

    Deduplication is the reason this class exists. The same call routinely
    arrives three times: once from RELAY with a UUID, once from a status
    callback with a ``CA`` SID, and once from a poll with both. ``_alias`` maps
    every identifier seen onto a single canonical entry.
    """

    def __init__(self, bus: EventBus, *, retain_ended: int = 200):
        self.bus = bus
        self._calls: dict[str, Call] = {}
        self._alias: dict[str, str] = {}
        self._ended_order: deque[str] = deque()
        self._retain_ended = retain_ended
        self._listeners: list[Callable[[Call, CallEvent], None]] = []
        self.messages: dict[str, MessageEvent] = {}

    def on_change(self, callback: Callable[[Call, CallEvent], None]) -> None:
        self._listeners.append(callback)

    # ------------------------------------------------------------------ querying

    def get(self, key: str) -> Call | None:
        return self._calls.get(self._alias.get(key, key))

    def all(self) -> list[Call]:
        return list(self._calls.values())

    def live(self) -> list[Call]:
        calls = [c for c in self._calls.values() if c.is_live]
        return sorted(calls, key=lambda c: c.started_at or c.first_seen, reverse=True)

    def recent(self, limit: int = 100) -> list[Call]:
        calls = sorted(self._calls.values(), key=lambda c: c.last_update, reverse=True)
        return calls[:limit]

    def resolve(self, fragment: str) -> Call | None:
        """Find a call by full or partial identifier, the way k9s does it."""
        exact = self.get(fragment)
        if exact is not None:
            return exact
        hits = [
            call
            for key, call in self._calls.items()
            if key.startswith(fragment)
            or (call.ref.sid or "").startswith(fragment)
            or (call.ref.call_id or "").startswith(fragment)
        ]
        return hits[0] if len(hits) == 1 else None

    # ------------------------------------------------------------------ ingesting

    def apply(self, event: CallEvent) -> Call | None:
        """Merge one event. Returns the affected call, or None if unidentifiable."""
        if not event.ref.sid and not event.ref.call_id:
            return None

        call = self._canonical(event.ref)
        if call is None:
            call = Call(ref=CallRef(sid=event.ref.sid, call_id=event.ref.call_id,
                                    node_id=event.ref.node_id))
            self._calls[call.ref.key] = call

        was_live = call.is_live
        changed = call.apply(event)
        self._reindex(call)

        if was_live and not call.is_live:
            self._retire(call)

        if changed:
            for listener in self._listeners:
                try:
                    listener(call, event)
                except Exception:
                    pass
        return call

    def apply_message(self, event: MessageEvent) -> MessageEvent:
        existing = self.messages.get(event.sid)
        if existing is None or event.at >= existing.at:
            self.messages[event.sid] = event
        return self.messages[event.sid]

    def _canonical(self, ref: CallRef) -> Call | None:
        """Find the existing entry for a reference, merging two entries if this
        event is the first to prove they are the same call."""
        by_id = self._calls.get(self._alias.get(ref.call_id or "", ref.call_id or ""))
        by_sid = self._calls.get(self._alias.get(ref.sid or "", ref.sid or ""))

        if by_id is not None and by_sid is not None and by_id is not by_sid:
            return self._fuse(by_id, by_sid)
        return by_id or by_sid

    def _fuse(self, keep: Call, drop: Call) -> Call:
        """Collapse two entries that turned out to be one call."""
        keep.ref.merge(drop.ref)
        keep.sources |= drop.sources
        keep.raw = {**drop.raw, **keep.raw}
        for attr in ("direction", "from_number", "to_number", "end_reason", "call_type",
                     "started_at", "answered_at", "ended_at", "duration_reported"):
            if getattr(keep, attr) is None:
                setattr(keep, attr, getattr(drop, attr))
        keep.first_seen = min(keep.first_seen, drop.first_seen)
        self._calls.pop(drop.ref.key, None)
        for identifier in (drop.ref.sid, drop.ref.call_id):
            if identifier:
                self._alias[identifier] = keep.ref.key
        return keep

    def _reindex(self, call: Call) -> None:
        canonical = call.ref.key
        if canonical not in self._calls:
            self._calls[canonical] = call
        for identifier in (call.ref.sid, call.ref.call_id):
            if identifier and identifier != canonical:
                self._alias[identifier] = canonical

    def _retire(self, call: Call) -> None:
        """Bound memory by forgetting the oldest ended calls."""
        self._ended_order.append(call.ref.key)
        while len(self._ended_order) > self._retain_ended:
            stale = self._ended_order.popleft()
            dropped = self._calls.pop(stale, None)
            if dropped is not None:
                for identifier in (dropped.ref.sid, dropped.ref.call_id):
                    self._alias.pop(identifier or "", None)

    # -------------------------------------------------------------------- running

    async def run(self) -> None:
        """Consume the bus forever, folding events into state."""
        sub = self.bus.subscribe()
        try:
            while True:
                event = await sub.get()
                if isinstance(event, CallEvent):
                    self.apply(event)
                elif isinstance(event, MessageEvent):
                    self.apply_message(event)
        finally:
            self.bus.unsubscribe(sub)


def _jsonable(event: Any) -> dict[str, Any]:
    """Best-effort dict for the JSONL recorder."""
    if hasattr(event, "__slots__"):
        data = {slot: getattr(event, slot, None) for slot in event.__slots__}
    else:
        data = dict(getattr(event, "__dict__", {"value": repr(event)}))
    data["_type"] = type(event).__name__
    data["_recorded_at"] = time.time()
    ref = data.get("ref")
    if isinstance(ref, CallRef):
        data["ref"] = {"sid": ref.sid, "call_id": ref.call_id, "node_id": ref.node_id}
    if isinstance(data.get("source"), Source):
        data["source"] = data["source"].value
    return data
