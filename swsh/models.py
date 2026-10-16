"""Normalised domain model.

swsh watches calls through three channels that disagree about names, states and
identifiers. Everything is funnelled through the types here so the TUI and the
CLI only ever see one vocabulary.

The identity problem is real and worth stating plainly: the Twilio-compatible
API keys calls by ``CA...`` SIDs, while the native calling API and RELAY key the
same call by a UUID. ``CallRef`` carries both and merges as it learns.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CallState(str, Enum):
    """One vocabulary for call lifecycle, whichever channel reported it."""

    CREATED = "created"
    RINGING = "ringing"
    ANSWERED = "answered"
    ENDING = "ending"
    ENDED = "ended"
    UNKNOWN = "unknown"

    @property
    def is_live(self) -> bool:
        return self in (CallState.CREATED, CallState.RINGING, CallState.ANSWERED, CallState.ENDING)

    @property
    def rank(self) -> int:
        """Lifecycle ordering, so a late-arriving stale event cannot regress state."""
        return _STATE_RANK[self]


_STATE_RANK: dict[CallState, int] = {
    CallState.UNKNOWN: -1,
    CallState.CREATED: 0,
    CallState.RINGING: 1,
    CallState.ANSWERED: 2,
    CallState.ENDING: 3,
    CallState.ENDED: 4,
}

# RELAY reports these directly.
_RELAY_STATES = {
    "created": CallState.CREATED,
    "ringing": CallState.RINGING,
    "answered": CallState.ANSWERED,
    "ending": CallState.ENDING,
    "ended": CallState.ENDED,
}

# The compat/LaML API uses Twilio's vocabulary, which folds the end reason into
# the status itself. Splitting that back apart is the whole job of this table.
_COMPAT_STATES: dict[str, tuple[CallState, str | None]] = {
    "queued": (CallState.CREATED, None),
    "initiated": (CallState.CREATED, None),
    "ringing": (CallState.RINGING, None),
    "in-progress": (CallState.ANSWERED, None),
    "completed": (CallState.ENDED, "hangup"),
    "busy": (CallState.ENDED, "busy"),
    "no-answer": (CallState.ENDED, "noAnswer"),
    "failed": (CallState.ENDED, "error"),
    "canceled": (CallState.ENDED, "cancel"),
    "cancelled": (CallState.ENDED, "cancel"),
}

# Status-callback payloads use yet another spelling for the same events.
_CALLBACK_EVENTS = {
    "initiated": CallState.CREATED,
    "ringing": CallState.RINGING,
    "answered": CallState.ANSWERED,
    "in-progress": CallState.ANSWERED,
    "completed": CallState.ENDED,
}

# The voice logs API (``/api/voice/logs``) is the one surface that lists every
# call leg the project carries, whichever engine ran it, and it does so while
# the leg is still up. Each engine writes its own vocabulary into ``status``:
# LaML legs say ``initiated`` / ``in-progress`` / ``completed``, RELAY legs say
# ``created`` / ``answered`` / ``ended``, and a PSTN leg parked in a video room
# says ``joined``. Verified live on 2026-09-09; ``joined`` is the only spelling
# neither of the other two dialects has.
_VOICE_LOG_EXTRA: dict[str, tuple[CallState, str | None]] = {
    "joined": (CallState.ANSWERED, None),
}


def parse_state(value: str | None, *, dialect: str = "auto") -> tuple[CallState, str | None]:
    """Map any channel's status string to (CallState, end_reason)."""
    if not value:
        return CallState.UNKNOWN, None
    key = str(value).strip().lower()

    if dialect in ("relay", "voicelog", "auto") and key in _RELAY_STATES:
        return _RELAY_STATES[key], None
    if dialect in ("compat", "voicelog", "auto") and key in _COMPAT_STATES:
        return _COMPAT_STATES[key]
    if dialect in ("callback", "auto") and key in _CALLBACK_EVENTS:
        return _CALLBACK_EVENTS[key], None
    if dialect in ("voicelog", "auto") and key in _VOICE_LOG_EXTRA:
        return _VOICE_LOG_EXTRA[key]
    return CallState.UNKNOWN, None


class Source(str, Enum):
    """Which channel produced a given fact. Shown in the UI so coverage is honest."""

    RELAY = "relay"
    CALLBACK = "callback"
    POLL = "poll"
    LOCAL = "local"


@dataclass(slots=True)
class CallRef:
    """A call's identity across both key spaces.

    Either identifier may be absent depending on which channel saw the call
    first. ``key`` is what the event bus deduplicates on.
    """

    sid: str | None = None  # compat/LaML, "CA..."
    call_id: str | None = None  # native calling API and RELAY, a UUID
    node_id: str | None = None  # RELAY node, required by some control commands

    @property
    def key(self) -> str:
        """Stable dedupe key. Prefers the UUID because RELAY and calling share it."""
        return self.call_id or self.sid or ""

    def matches(self, other: CallRef) -> bool:
        if self.call_id and other.call_id:
            return self.call_id == other.call_id
        if self.sid and other.sid:
            return self.sid == other.sid
        return False

    def merge(self, other: CallRef) -> None:
        """Fold in whatever the other reference knows that we do not."""
        self.sid = self.sid or other.sid
        self.call_id = self.call_id or other.call_id
        self.node_id = self.node_id or other.node_id

    def __str__(self) -> str:
        return self.call_id or self.sid or "<unidentified>"


@dataclass(slots=True)
class Call:
    """Current best-known state of one call, merged across all channels."""

    ref: CallRef
    state: CallState = CallState.UNKNOWN
    direction: str | None = None
    from_number: str | None = None
    to_number: str | None = None
    end_reason: str | None = None
    # Which engine carries the leg, as the voice logs API names it:
    # ``laml_call``, ``relay_pstn_call``, ``relay_sip_call``,
    # ``video_room_pstn_leg``. It decides which control surface works, so it
    # is shown rather than buried in ``raw``.
    call_type: str | None = None
    started_at: float | None = None
    answered_at: float | None = None
    ended_at: float | None = None
    duration_reported: int | None = None
    sources: set[Source] = field(default_factory=set)
    raw: dict[str, Any] = field(default_factory=dict)
    first_seen: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)

    @property
    def duration(self) -> float:
        """Live duration in seconds, counting from answer where known."""
        if self.duration_reported is not None:
            return float(self.duration_reported)
        start = self.answered_at or self.started_at or self.first_seen
        end = self.ended_at or time.time()
        return max(0.0, end - start)

    @property
    def is_live(self) -> bool:
        return self.state.is_live

    def as_json(self) -> dict[str, Any]:
        """sw's shape of the call: the merged view, not any one source's row.

        `raw` is what a source sent; this is what sw made of every source. Both
        the CLI (`sw calls show --json`) and the cockpit's detail pane render
        it, so the two cannot drift.
        """
        return {
            "id": str(self.ref),
            "sid": self.ref.sid,
            "call_id": self.ref.call_id,
            "state": self.state.value,
            "status": self.raw.get("status"),
            "type": self.call_type,
            "direction": self.direction,
            "from": self.from_number,
            "to": self.to_number,
            "started_at": _iso_utc_or_none(self.started_at),
            "ended_at": _iso_utc_or_none(self.ended_at),
            "duration": self.duration,
            "end_reason": self.end_reason,
            "sources": sorted(s.value for s in self.sources),
        }

    def apply(self, event: CallEvent) -> bool:
        """Merge an event in. Returns True when something actually changed.

        State only ever moves forward: a poll result that arrives after a RELAY
        ``ended`` event must not resurrect the call.
        """
        changed = False
        self.ref.merge(event.ref)

        if event.state is not CallState.UNKNOWN and event.state.rank > self.state.rank:
            self.state = event.state
            changed = True
            now = event.at
            # A push channel reports the answer as it happens, so its arrival
            # time is the answer time. A poll only learns the call is up some
            # time later; taking that as the answer would restart the clock,
            # so a polled call keeps counting from ``started_at``.
            if (event.state is CallState.ANSWERED and self.answered_at is None
                    and event.source is not Source.POLL):
                self.answered_at = now
            elif event.state is CallState.ENDED and self.ended_at is None:
                self.ended_at = event.ended_at or now

        for attr in ("direction", "from_number", "to_number", "end_reason", "call_type"):
            incoming = getattr(event, attr, None)
            if incoming and getattr(self, attr) != incoming:
                setattr(self, attr, incoming)
                changed = True

        if event.started_at and self.started_at is None:
            self.started_at = event.started_at
            changed = True
        reported = event.duration_reported
        if reported is not None and self.duration_reported != reported:
            self.duration_reported = reported
            changed = True

        if event.source not in self.sources:
            self.sources.add(event.source)
            changed = True

        if event.raw:
            self.raw.update(event.raw)
        self.last_update = event.at
        return changed


@dataclass(slots=True)
class CallEvent:
    """A single observation about a call, from one channel."""

    ref: CallRef
    kind: str  # "state", "play", "record", "collect", "dtmf", ...
    source: Source
    state: CallState = CallState.UNKNOWN
    at: float = field(default_factory=time.time)
    direction: str | None = None
    from_number: str | None = None
    to_number: str | None = None
    end_reason: str | None = None
    call_type: str | None = None
    started_at: float | None = None
    ended_at: float | None = None
    duration_reported: int | None = None
    detail: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return self.ref.key


@dataclass(slots=True)
class MessageEvent:
    """A single observation about an SMS/MMS."""

    sid: str
    state: str
    source: Source
    direction: str | None = None
    from_number: str | None = None
    to_number: str | None = None
    body: str | None = None
    media: list[str] = field(default_factory=list)
    segments: int | None = None
    error: str | None = None
    at: float = field(default_factory=time.time)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return self.sid


def _iso_utc_or_none(timestamp: float | None) -> str | None:
    """A wall-clock instant as UTC ISO-8601, or None when there is not one."""
    if not timestamp:
        return None
    from datetime import UTC, datetime

    return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
