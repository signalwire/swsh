"""Async facade over the SignalWire SDK.

Two things this layer exists to solve.

**Blocking.** ``signalwire.rest.RestClient`` is synchronous and ``requests``
backed. A TUI that called it directly would stall its paint loop, so every SDK
call is dispatched to a thread here.

**Compat encoding.** The SDK sends ``Content-Type: application/json`` to every
endpoint, including the Twilio-compatible LaML surface at
``/api/laml/2010-04-01``. LaML is historically ``application/x-www-form-urlencoded``.
Rather than guess, swsh owns its own transport for compat writes: form encoding
by default, which is what LaML specifies, with JSON as a switch.
``verify_compat()`` only reads.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from . import __version__
from .config import Profile
from .models import Call, CallEvent, CallRef, MessageEvent, Source, parse_state

CompatEncoding = Literal["form", "json"]


class SwshError(RuntimeError):
    """Anything that went wrong talking to SignalWire, with context attached."""

    def __init__(self, message: str, *, status: int | None = None, body: Any = None,
                 url: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body
        self.url = url

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.status is not None:
            parts.append(f"(HTTP {self.status})")
        if self.url:
            parts.append(f"at {self.url}")
        return " ".join(parts)


class SwshClient:
    """One handle onto a SignalWire project.

    Wraps the SDK's ``RestClient`` for the breadth of its 21 namespaces, and
    keeps a private ``httpx`` client for compat writes and for anything the SDK
    does not model.
    """

    def __init__(self, profile: Profile, *, compat_encoding: CompatEncoding = "form",
                 timeout: float | None = None):
        self.profile = profile
        self.compat_encoding: CompatEncoding = compat_encoding
        self._timeout = default_timeout() if timeout is None else timeout
        self._rest: Any | None = None
        self._http: httpx.AsyncClient | None = None
        self._selector: Any | None = None

    @property
    def selector(self) -> Any:
        """Shared, session-cached provider of enumerable field options."""
        if self._selector is None:
            from .selectors import Selector

            self._selector = Selector(self)
        return self._selector

    # ---------------------------------------------------------------- lifecycle

    @property
    def rest(self) -> Any:
        """The SDK client, built lazily so importing swsh stays cheap."""
        if self._rest is None:
            from signalwire.rest import RestClient

            self._rest = RestClient(
                project=self.profile.project,
                token=self.profile.token,
                host=self.profile.host,
            )
            _give_it_a_timeout(self._rest, self._timeout)
        return self._rest

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.profile.base_url,
                auth=(self.profile.project, self.profile.token),
                timeout=self._timeout,
                headers={"User-Agent": f"sw/{__version__}"},
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def __aenter__(self) -> SwshClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------- plumbing

    async def call_sdk(self, path: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke a dotted SDK path in a thread, e.g. ``"logs.voice.list"``.

        Keeps the TUI responsive and gives one place to translate SDK errors.
        """
        target: Any = self.rest
        for part in path.split("."):
            target = getattr(target, part)

        def run() -> Any:
            return target(*args, **kwargs)

        try:
            return await asyncio.to_thread(run)
        except Exception as exc:  # SignalWireRestError and anything requests raises
            raise _translate(exc, path) from exc

    # Attempts, not retries: 3 means the original plus two more. Past that a
    # command that has already waited seconds is better off telling someone
    # than waiting more.
    ATTEMPTS = 3
    RETRY_ON = frozenset({429, 500, 502, 503, 504})
    # A 5xx may have been processed before it failed, so replaying a create
    # could make two of something. A 429 is different: the platform is saying
    # it did *not* process the request, so any method is safe to send again.
    REPLAYABLE = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """One request, retried when the platform says to try again.

        A 429 used to surface as `request failed` and exit 1 — a rate limit
        reported as a dead end, when the one thing the platform told us was how
        long to wait. `Retry-After` is honoured when it is sent; otherwise the
        wait doubles, which is what keeps a burst of parallel list pages from
        arriving back in step.
        """
        delay = 0.5
        for attempt in range(1, self.ATTEMPTS + 1):
            resp = await self.http.request(method, path, **kwargs)
            if resp.status_code not in self.RETRY_ON or attempt == self.ATTEMPTS:
                return resp
            if resp.status_code != 429 and method not in self.REPLAYABLE:
                return resp
            await asyncio.sleep(_retry_after(resp) or delay)
            delay = min(delay * 2, 8.0)
        return resp

    async def rest_call(self, method: str, path: str, *, params: dict[str, Any] | None = None,
                        body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Issue a raw REST call against the space and normalise the response.

        This is the second registry backend: resources whose surface has no SDK
        method (e911, WhatsApp, …) reach the platform through here instead of
        ``call_sdk``. Everything downstream sees the same dict either way.
        """
        resp = await self._send(
            method.upper(), path, params=_clean(params) if params else None,
            json=_clean(body) if body else None,
        )
        return _unwrap(resp)

    async def raw_request(self, method: str, path: str, *,
                          params: dict[str, Any] | None = None,
                          json_body: Any = None,
                          form_body: dict[str, Any] | None = None,
                          headers: dict[str, str] | None = None) -> httpx.Response:
        """Issue a request and hand back the response untouched.

        This is what `sw api` runs on, and the reason it does not reuse
        ``rest_call``: ``_unwrap`` discards the status code and the headers on
        success, and rewraps a top-level JSON array as ``{"data": [...]}``. An
        escape hatch has to show what the platform actually said, byte for byte,
        so nothing here interprets the response.

        Exactly one of ``json_body`` / ``form_body`` should be given. Form bodies
        go through ``_form_data`` so a list value becomes repeated keys, which is
        what the LaML surface expects.
        """
        request_kwargs: dict[str, Any] = {}
        if form_body is not None:
            request_kwargs["data"] = _form_data(_clean(form_body))
        elif json_body is not None:
            request_kwargs["json"] = (
                _clean(json_body) if isinstance(json_body, dict) else json_body
            )
        return await self._send(
            method.upper(),
            path,
            params=_clean(params) if params else None,
            headers=headers or None,
            **request_kwargs,
        )

    async def invoke(self, resource: Any, op: str, *, resource_id: str | None = None,
                     body: dict[str, Any] | None = None, **params: Any) -> Any:
        """Run one operation on a resource, dispatching by its transport.

        ``sdk`` resources call a dotted SDK method; ``rest`` resources resolve
        the operation's route from the spec catalog and issue it. The registry,
        forms and CLI verbs call this and never care which backend answered.
        """
        # An op named in rest_ops always goes over REST, even on a mostly-SDK
        # resource. This lets a resource whose SDK namespace lacks one method
        # (a relay address's update, a video room's streams) fill just that gap
        # without becoming an all-REST resource.
        if op in getattr(resource, "rest_ops", {}):
            return await self._invoke_rest(resource, op, resource_id, body, params)
        if getattr(resource, "transport", "sdk") == "rest":
            return await self._invoke_rest(resource, op, resource_id, body, params)
        return await self._invoke_sdk(resource, op, resource_id, body, params)

    async def _invoke_sdk(self, resource: Any, op: str, resource_id: str | None,
                          body: dict[str, Any] | None, params: dict[str, Any]) -> Any:
        method_name = resource.sdk_method(op)
        path = f"{resource.namespace}.{method_name}"
        args = [resource_id] if resource_id is not None else []
        kwargs = {**(body or {}), **params}
        return await self.call_sdk(path, *args, **kwargs)

    async def _invoke_rest(self, resource: Any, op: str, resource_id: str | None,
                           body: dict[str, Any] | None, params: dict[str, Any]) -> Any:
        from . import spec

        # An op-name maps to a spec operation id via rest_ops. Failing that, an
        # extra whose `method` matches carries the id in its `spec_op` — that is
        # what the field is for, and it is how a drill like the voice-log event
        # timeline (method "list_events", spec_op "list_voice_log_events")
        # resolves once its resource is rest-backed. Last resort: treat the
        # op-name as the operation id, which is how extras written directly
        # against a spec id resolve.
        op_id = resource.rest_ops.get(op)
        if op_id is None:
            op_id = next(
                (e.spec_op for e in getattr(resource, "extras", ())
                 if e.method == op and e.spec_op),
                op,
            )
        operation = spec.get(op_id, api=resource.api)
        if operation is None:
            raise SwshError(f"{resource.key}: no spec operation for '{op}'")
        path = operation.path
        if "{id}" in path:
            if resource_id is None:
                raise SwshError(f"{resource.key}.{op} needs a resource id")
            path = path.replace("{id}", str(resource_id))
        # Named placeholders are filled from params, so routes like
        # /phone_numbers/{id}/e911_address or /lookup/{e164_number} resolve.
        for key, value in list(params.items()):
            token = "{" + key + "}"
            if token in path:
                path = path.replace(token, str(value))
                params.pop(key)
        # A form hands everything it collected as the body. When one of those
        # values names a route placeholder (`mfa_request_id` on
        # /mfa/{mfa_request_id}/verify, `name` on /rooms/{name}) it *is* the
        # route, so fill it there and do not also send it.
        if body:
            body = dict(body)
            for key in list(body):
                token = "{" + key + "}"
                if token in path:
                    path = path.replace(token, str(body.pop(key)))
        # A single remaining placeholder (a route whose id is not literally
        # "id", e.g. /lookup/{e164_number}) is filled from resource_id, so a
        # caller can always pass the identifier positionally.
        remaining = re.findall(r"\{([^}]+)\}", path)
        if remaining:
            if resource_id is not None and len(remaining) == 1:
                path = path.replace("{" + remaining[0] + "}", str(resource_id))
            else:
                raise SwshError(
                    f"{resource.key}.{op} needs {', '.join(remaining)}"
                )
        return await self.rest_call(operation.method, path, params=params, body=body)

    @property
    def _laml_base(self) -> str:
        return f"/api/laml/2010-04-01/Accounts/{self.profile.project}"

    async def compat_get(self, path: str, **params: Any) -> dict[str, Any]:
        url = f"{self._laml_base}/{path.lstrip('/')}"
        resp = await self.http.get(url, params=_clean(params) or None)
        return _unwrap(resp)

    async def compat_post(self, path: str, **data: Any) -> dict[str, Any]:
        """POST to the LaML surface using the configured encoding.

        Lists are expanded to repeated keys, which is how LaML expects repeated
        parameters such as ``StatusCallbackEvent``.
        """
        url = f"{self._laml_base}/{path.lstrip('/')}"
        payload = _clean(data)
        if self.compat_encoding == "json":
            resp = await self.http.post(url, json=payload)
        else:
            resp = await self.http.post(url, data=_form_data(payload))
        return _unwrap(resp)

    async def compat_delete(self, path: str) -> dict[str, Any]:
        url = f"{self._laml_base}/{path.lstrip('/')}"
        resp = await self.http.delete(url)
        return _unwrap(resp)

    async def verify_compat(self) -> dict[str, Any]:
        """Confirm the LaML surface is reachable. Read-only.

        This used to create a LaML bin and delete it to discover which encoding
        the endpoint wanted. Do not reintroduce that: a check must never create
        or delete anything on the project it is checking.

        The question it was answering is settled anyway: both form and JSON
        bodies are accepted on the LaML surface. swsh sends form because that
        is what LaML specifies, and repeated parameters such as
        ``StatusCallbackEvent`` encode naturally that way.
        """
        return await self.compat_get("")

    # ------------------------------------------------------------------- identity

    async def whoami(self) -> dict[str, Any]:
        """Cheap authenticated round trip that also proves the space is right."""
        return await self.compat_get("")

    # ---------------------------------------------------------------------- calls

    # Every call leg on the project, whichever engine ran it, comes from the
    # voice logs API. The compat ``Calls`` list only knows LaML legs: a SIP
    # endpoint dialling out through SWML, a call flow, an AI agent or a video
    # room never appears there, which is why polling it showed "no calls" while
    # a call was plainly up. Verified live on 2026-09-09: ``/api/voice/logs``
    # lists a leg from the moment it is ``initiated`` and updates its status in
    # place, so it doubles as the live view. It honours ``created_after`` /
    # ``created_before`` and ``page_size`` (max 200), and ignores ``status``,
    # so live filtering happens here.
    LIVE_LOOKBACK_SECONDS = 24 * 3600
    VOICE_LOG_PAGE_MAX = 200

    async def recent_calls(self, *, limit: int = 50, lookback: float | None = None,
                           **filters: Any) -> list[Call]:
        """Voice log rows, newest first, normalised to ``Call``.

        ``lookback`` bounds the window in seconds via ``created_after``; the
        poller uses it so a live call is found without paging through history.
        """
        from . import spec

        operation = spec.get("list_voice_logs", api="voice-api")
        if operation is None:  # pragma: no cover - the catalog is checked in
            raise SwshError("catalog has no list_voice_logs operation")
        params: dict[str, Any] = {"page_size": min(limit, self.VOICE_LOG_PAGE_MAX), **filters}
        if lookback is not None:
            params.setdefault("created_after", _iso_utc(time.time() - lookback))
        payload = await self.rest_call(operation.method, operation.path, params=params)
        rows = payload.get("data") if isinstance(payload, dict) else payload
        return [call_from_voice_log(row) for row in (rows or [])[:limit]]

    async def list_calls(self, *, status: str | None = None, limit: int = 50,
                         **filters: Any) -> list[Call]:
        """List calls of every kind, newest first.

        ``status`` matches either the engine's own word (``in-progress``,
        ``ended``) or the normalised state (``answered``); the API has no such
        filter so it is applied here, over a wider page so the count still
        comes out near ``limit``.
        """
        if not status:
            return await self.recent_calls(limit=limit, **filters)
        wanted = status.strip().lower()
        calls = await self.recent_calls(limit=self.VOICE_LOG_PAGE_MAX, **filters)
        matched = [
            c for c in calls
            if str(c.raw.get("status", "")).lower() == wanted or c.state.value == wanted
        ]
        return matched[:limit]

    async def live_calls(self, limit: int = 50, *, lookback: float | None = None) -> list[Call]:
        """Calls currently up, across every engine.

        A failure is raised rather than swallowed: the caller has to be able to
        tell "no calls are up" from "the API is unreachable", or the poller
        would report itself healthy while seeing nothing.
        """
        lookback = self.LIVE_LOOKBACK_SECONDS if lookback is None else lookback
        calls = await self.recent_calls(limit=self.VOICE_LOG_PAGE_MAX, lookback=lookback)
        live = [c for c in calls if c.is_live]
        return sorted(live, key=lambda c: c.started_at or c.first_seen, reverse=True)[:limit]

    async def get_call(self, identifier: str) -> Call:
        """One call by id. The voice log row covers every engine; a LaML leg
        falls back to the richer compat record when the log has no row yet."""
        from . import spec

        operation = spec.get("get_voice_log", api="voice-api")
        try:
            if operation is None:
                raise SwshError("catalog has no get_voice_log operation")
            path = operation.path.replace("{id}", identifier)
            return call_from_voice_log(await self.rest_call(operation.method, path))
        except SwshError:
            return call_from_compat(await self.compat_get(f"Calls/{identifier}.json"))

    async def dial(self, *, to: str, from_: str, url: str | None = None,
                   say: str | None = None,
                   status_callback: str | None = None,
                   status_callback_events: Iterable[str] | None = None,
                   **extra: Any) -> Call:
        """Place an outbound call.

        The call needs something to run when answered: a ``url`` (SWML or
        cXML), or ``say``, which is inlined as a one-line cXML document so a
        test call needs no hosted script. ``status_callback_events`` is sent as
        repeated ``StatusCallbackEvent`` keys, which is how LaML asks for more
        than the default terminal event.
        """
        if not url and not say and "Twiml" not in extra:
            raise SwshError("a call needs a URL to run, or something to say")
        body: dict[str, Any] = {"To": to, "From": from_, **extra}
        if url:
            body["Url"] = url
        elif say:
            from xml.sax.saxutils import escape

            body["Twiml"] = f"<Response><Say>{escape(say)}</Say></Response>"
        if status_callback:
            body["StatusCallback"] = status_callback
            body["StatusCallbackEvent"] = list(
                status_callback_events or ("initiated", "ringing", "answered", "completed")
            )
        return call_from_compat(await self.compat_post("Calls.json", **body))

    async def resolve_ref(self, ref: CallRef | str) -> CallRef:
        """Turn a bare identifier into a reference that knows its engine.

        Every id on this platform is a UUID, so nothing about the string says
        whether the calling API or the compat surface can drive the call. The
        voice log row does: a LaML leg's id belongs in ``sid``, anything else
        in ``call_id``. One lookup per control command is cheaper than a 422
        ("must not point to a cXML call") and a second guess.
        """
        if isinstance(ref, CallRef):
            return ref
        try:
            return (await self.get_call(str(ref))).ref
        except SwshError:
            return _as_ref(ref)

    async def hangup(self, ref: CallRef | str) -> dict[str, Any]:
        """End a call through whichever surface owns it: compat for a LaML
        leg, ``calling.end`` for a native one."""
        ref = await self.resolve_ref(ref)
        if ref.sid:
            return await self.compat_post(f"Calls/{ref.sid}.json", Status="completed")
        if ref.call_id:
            return await self.call_sdk("calling.end", ref.call_id, reason="hangup")
        raise SwshError("cannot hang up a call with no identifier")

    async def transfer(self, ref: CallRef | str, dest: str) -> dict[str, Any]:
        ref = await self._native_ref(ref, "transfer")
        return await self.call_sdk("calling.transfer", ref.call_id, dest=dest)

    async def play_tts(self, ref: CallRef | str, text: str, **params: Any) -> dict[str, Any]:
        ref = await self._native_ref(ref, "play")
        return await self.call_sdk(
            "calling.play", ref.call_id, play=[{"type": "tts", "text": text}], **params
        )

    async def send_digits(self, ref: CallRef | str, digits: str) -> dict[str, Any]:
        ref = await self._native_ref(ref, "send_digits")
        return await self.call_sdk("calling.send_digits", ref.call_id, digits=digits)

    async def start_recording(self, ref: CallRef | str, **params: Any) -> dict[str, Any]:
        ref = await self.resolve_ref(ref)
        if ref.sid:
            return await self.compat_post(f"Calls/{ref.sid}/Recordings.json", **params)
        if ref.call_id:
            return await self.call_sdk("calling.record", ref.call_id, **params)
        raise SwshError("cannot record a call with no identifier")

    async def call_command(self, ref: CallRef | str, command: str,
                           **params: Any) -> dict[str, Any]:
        """Run any native calling-api command on a live call by its call id.

        Covers the surface beyond the named helpers — tap, stream, detect,
        ai_message, denoise, and the rest of ``client.calling``. Requires a
        native leg; LaML legs cannot be driven this way.
        """
        ref = await self._native_ref(ref, command)
        return await self.call_sdk(f"calling.{command}", ref.call_id, **params)

    async def _native_ref(self, ref: CallRef | str, command: str) -> CallRef:
        """Resolve a reference that must be driveable by the calling API, and
        say plainly why when it is not."""
        ref = await self.resolve_ref(ref)
        if ref.call_id:
            return ref
        if ref.sid:
            raise SwshError(
                f"{command}: {ref.sid} is a LaML (cXML) call, which the calling API "
                "cannot drive; hangup and record still work on it"
            )
        raise SwshError(f"{command} needs a call id")

    # ------------------------------------------------------------------- messages

    async def send_message(self, *, to: str, from_: str, body: str | None = None,
                           media: Iterable[str] | None = None,
                           status_callback: str | None = None,
                           **extra: Any) -> MessageEvent:
        payload: dict[str, Any] = {"To": to, "From": from_, **extra}
        if body is not None:
            payload["Body"] = body
        if media:
            payload["MediaUrl"] = list(media)
        if status_callback:
            payload["StatusCallback"] = status_callback
        return message_from_compat(await self.compat_post("Messages.json", **payload))

    async def list_messages(self, limit: int = 50, **filters: Any) -> list[MessageEvent]:
        payload = await self.compat_get("Messages.json", PageSize=min(limit, 1000), **filters)
        rows = payload.get("messages") or payload.get("Messages") or []
        return [message_from_compat(row) for row in rows[:limit]]

    # ----------------------------------------------------------------------- logs

    async def voice_logs(self, **params: Any) -> Any:
        return await self.call_sdk("logs.voice.list", **params)

    async def voice_log_events(self, log_id: str, **params: Any) -> Any:
        """Per-call event timeline. This is how swsh backfills a call it joined late."""
        return await self.call_sdk("logs.voice.list_events", log_id, **params)


# --------------------------------------------------------------------- normalising


def call_from_compat(row: dict[str, Any]) -> Call:
    """Build a ``Call`` from a LaML call payload.

    LaML has been seen with both ``sid`` and ``Sid`` casing depending on the
    endpoint, so every lookup tries both.
    """
    get = _caseless(row)
    state, reason = parse_state(get("status"), dialect="compat")
    ref = CallRef(sid=get("sid"), call_id=get("call_id") or get("callId"))
    call = Call(
        ref=ref,
        state=state,
        end_reason=reason,
        direction=get("direction"),
        from_number=get("from") or get("from_formatted"),
        to_number=get("to") or get("to_formatted"),
        raw=dict(row),
    )
    call.sources.add(Source.POLL)
    duration = get("duration")
    if duration not in (None, ""):
        try:
            call.duration_reported = int(duration)
        except (TypeError, ValueError):
            pass
    return call


def call_from_voice_log(row: dict[str, Any]) -> Call:
    """Build a ``Call`` from a ``/api/voice/logs`` row.

    The row's ``id`` is the call's identifier in whichever key space its
    engine uses. For a LaML leg (``source == "laml"``) that is the compat SID,
    so it goes in ``ref.sid`` and control runs through the compat surface. For
    everything else it is the native call id that the calling API accepts, so
    it goes in ``ref.call_id``. Putting a LaML id in ``call_id`` would make
    ``transfer`` and ``play`` look possible and then fail with "must not point
    to a cXML call".
    """
    identifier = row.get("id")
    if row.get("source") == "laml":
        ref = CallRef(sid=identifier)
    else:
        ref = CallRef(call_id=identifier)
    state, reason = parse_state(row.get("status"), dialect="voicelog")
    call = Call(
        ref=ref,
        state=state,
        end_reason=reason,
        direction=row.get("direction"),
        from_number=row.get("from"),
        to_number=row.get("to"),
        call_type=row.get("type"),
        started_at=_parse_iso(row.get("created_at")),
        raw=dict(row),
    )
    call.sources.add(Source.POLL)
    duration = row.get("duration")
    # A live leg's reported duration is a snapshot that goes stale between
    # polls; leaving it unset lets ``Call.duration`` tick from ``started_at``.
    if not call.is_live and duration not in (None, ""):
        try:
            call.duration_reported = int(duration)
        except (TypeError, ValueError):
            pass
        if call.started_at is not None and call.duration_reported is not None:
            call.ended_at = call.started_at + call.duration_reported
    return call


def _parse_iso(value: Any) -> float | None:
    """ISO-8601 (``2026-09-09T21:02:49.458Z``) to a UNIX timestamp."""
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def event_from_callback(form: dict[str, Any]) -> CallEvent:
    """Build a ``CallEvent`` from a status-callback POST body.

    Prefers ``CallStatus`` and falls back to ``CallbackSource``/``StatusCallbackEvent``,
    since which field carries the state depends on how the callback was wired.
    """
    get = _caseless(form)
    status = get("callstatus") or get("statuscallbackevent") or get("callbackevent")
    state, reason = parse_state(status, dialect="auto")
    ref = CallRef(sid=get("callsid"), call_id=get("callid"))
    return CallEvent(
        ref=ref,
        kind="state",
        source=Source.CALLBACK,
        state=state,
        direction=get("direction") or get("calldirection"),
        from_number=get("from"),
        to_number=get("to"),
        end_reason=get("endreason") or reason,
        detail=status,
        raw=dict(form),
    )


def event_from_relay(payload: dict[str, Any]) -> CallEvent:
    """Build a ``CallEvent`` from a RELAY ``signalwire.event`` params block."""
    params = payload.get("params", payload)
    event_type = payload.get("event_type") or payload.get("eventType") or "calling.call.state"
    state, _ = parse_state(params.get("call_state"), dialect="relay")
    device = params.get("device") or {}
    device_params = device.get("params", {}) if isinstance(device, dict) else {}
    return CallEvent(
        ref=CallRef(
            call_id=params.get("call_id"),
            sid=params.get("call_sid"),
            node_id=params.get("node_id"),
        ),
        kind=event_type.rsplit(".", 1)[-1],
        source=Source.RELAY,
        state=state,
        direction=params.get("direction"),
        from_number=device_params.get("from_number") or device_params.get("from"),
        to_number=device_params.get("to_number") or device_params.get("to"),
        end_reason=params.get("end_reason"),
        detail=params.get("state") or params.get("call_state"),
        raw=dict(params),
    )


def event_from_call(call: Call) -> CallEvent:
    """Re-emit a polled ``Call`` as an event so the bus has one input type."""
    return CallEvent(
        ref=call.ref,
        kind="state",
        source=Source.POLL,
        state=call.state,
        direction=call.direction,
        from_number=call.from_number,
        to_number=call.to_number,
        end_reason=call.end_reason,
        call_type=call.call_type,
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_reported=call.duration_reported,
        raw=call.raw,
    )


def message_from_compat(row: dict[str, Any]) -> MessageEvent:
    get = _caseless(row)
    segments = get("num_segments") or get("numsegments")
    try:
        segments = int(segments) if segments not in (None, "") else None
    except (TypeError, ValueError):
        segments = None
    return MessageEvent(
        sid=get("sid") or "",
        state=get("status") or "unknown",
        source=Source.POLL,
        direction=get("direction"),
        from_number=get("from"),
        to_number=get("to"),
        body=get("body"),
        segments=segments,
        error=get("error_message") or get("errormessage"),
        raw=dict(row),
    )


# ------------------------------------------------------------------------ helpers


def _caseless(row: dict[str, Any]):
    """Look a key up ignoring case and underscores, because LaML casing varies."""
    index = {str(k).lower().replace("_", ""): v for k, v in row.items()}

    def get(name: str) -> Any:
        return index.get(name.lower().replace("_", ""))

    return get


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


def next_page(payload: Any) -> str | None:
    """The path of the next page, or None when this is the last one.

    The platform paginates two ways and which field carries the link is
    transport knowledge, so it lives here rather than in the CLI:

    * Relay REST and the newer APIs return ``{"links": {"next": "/api/..."}}``
    * the compat/LaML surface follows Twilio's ``next_page_uri``

    An empty or null value counts as absent, which is how both surfaces signal
    the end rather than omitting the key.
    """
    if not isinstance(payload, dict):
        return None
    links = payload.get("links")
    if isinstance(links, dict):
        nxt = links.get("next")
        if nxt:
            return str(nxt)
    nxt = payload.get("next_page_uri")
    if nxt:
        return str(nxt)
    return None


def _form_data(data: dict[str, Any]) -> dict[str, Any]:
    """Shape a body for urlencoded posting.

    Must stay a dict: httpx treats a list of tuples as an iterable request body
    and tries to stream it, which fails on an async client. A dict whose values
    are lists is what httpx expects, and it urlencodes those as repeated keys,
    which is how LaML wants ``StatusCallbackEvent`` and friends.
    """
    shaped: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, (list, tuple, set)):
            shaped[key] = [_stringify(v) for v in value]
        else:
            shaped[key] = _stringify(value)
    return shaped


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _unwrap(resp: httpx.Response) -> dict[str, Any]:
    if resp.status_code >= 400:
        body: Any
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        raise SwshError(
            _describe(resp.status_code, body),
            status=resp.status_code,
            body=body,
            url=str(resp.url),
        )
    if resp.status_code == 204 or not resp.content:
        return {}
    try:
        payload = resp.json()
    except Exception:
        return {"raw": resp.text}
    return payload if isinstance(payload, dict) else {"data": payload}


# The shapes the platform actually sends an error in. A validation failure is a
# *list of objects*, one per offending field, which `f"{body[key]}"` rendered as
# a Python repr:
#
#   error: [{'type': 'validation_error', 'code': 'missing_required_parameter',
#   'message': 'Encryption is required', 'attribute': 'encryption', 'url':
#   'https://developer.signalwire.com/...'}] (HTTP 422)
#
# Everything a person needs is in there and none of it is readable. The field
# name is the single most useful token, because it maps straight back to the
# `--set` key that caused it.
_ERROR_KEYS = ("message", "error", "detail", "errors", "error_message")


def _error_line(item: Any) -> str:
    """One problem, as a line: ``field: what is wrong (code)``."""
    if not isinstance(item, dict):
        return str(item)
    text = str(item.get("message") or item.get("detail") or item.get("error") or "").strip()
    field = item.get("attribute") or item.get("field") or item.get("parameter")
    code = item.get("code")
    if not text:
        # Nothing human in it; the code is better than an empty string.
        text = str(code or item)
        code = None
    # `Encryption is required` already names the field, so do not say it twice.
    if field and str(field).lower().replace("_", "") not in text.lower().replace("_", ""):
        text = f"{field}: {text}"
    if code and str(code) not in text:
        text = f"{text} ({code})"
    return text


def error_doc_urls(body: Any) -> list[str]:
    """Documentation links the platform attached, for a hint line.

    They belong under the message rather than inside it: a 200-character URL in
    the middle of a sentence is what made these unreadable in the first place.
    """
    if not isinstance(body, dict):
        return []
    items = next((body[k] for k in _ERROR_KEYS if k in body), None)
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return []
    seen: list[str] = []
    for item in items:
        url = item.get("url") if isinstance(item, dict) else None
        if url and url not in seen:
            seen.append(str(url))
    return seen


def _retry_after(resp: httpx.Response) -> float | None:
    """`Retry-After` in seconds, when the platform sent a usable one.

    The header is defined as either a number of seconds or an HTTP date. Only
    the numeric form is honoured here: a date needs clock agreement to mean
    anything, and every SignalWire 429 seen so far sends seconds. A value that
    is neither falls through to the backoff rather than being guessed at.
    """
    raw = resp.headers.get("retry-after")
    if not raw:
        return None
    try:
        seconds = float(raw.strip())
    except ValueError:
        return None
    # A server asking for ten minutes is not something to sit through silently.
    return seconds if 0 <= seconds <= 60 else None


def default_timeout() -> float:
    """Seconds to wait on the platform, from ``SWSH_TIMEOUT`` or 30."""
    raw = os.environ.get("SWSH_TIMEOUT", "").strip()
    try:
        value = float(raw)
    except ValueError:
        return 30.0
    return value if value > 0 else 30.0


def _give_it_a_timeout(rest: Any, seconds: float) -> None:
    """Put a timeout on the SDK's session, which ships without one.

    `RestClient` takes no timeout argument and its `requests.Session` is created
    bare, so an SDK-backed call waits for as long as the far end keeps the
    socket open: no output, no error, nothing to interrupt but the process.
    Since there is no supported seam, this wraps the session's own `request` and
    supplies a default the caller can still override.

    Reaching into another package's privates is a thing to do carefully, so it
    is best-effort by construction: if the SDK reshapes, the wrap is skipped and
    behaviour is exactly what it is today, rather than an AttributeError on the
    first call.
    """
    try:
        session = rest._http._session
        original = session.request
    except AttributeError:
        return

    if getattr(original, "_swsh_timed", False):
        return

    def request(method: str, url: str, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", seconds)
        return original(method, url, **kwargs)

    request._swsh_timed = True  # type: ignore[attr-defined]
    session.request = request  # type: ignore[method-assign]


def _describe(status: int, body: Any) -> str:
    """What went wrong, in words, whatever shape the platform said it in."""
    if isinstance(body, dict):
        for key in _ERROR_KEYS:
            if key not in body:
                continue
            value = body[key]
            if isinstance(value, list) and value:
                return "; ".join(_error_line(item) for item in value)
            if isinstance(value, dict):
                return _error_line(value)
            if value:
                return str(value)
    if status == 401:
        return "authentication failed: check project id and api token"
    if status == 403:
        return "forbidden: this token may lack the scope for that call"
    if status == 404:
        return "not found: check the resource id and that the space is correct"
    if status == 409:
        return "conflict: something with those values already exists"
    if status == 429:
        return "rate limited: too many requests"
    # Never a bare "request failed" over a body that said something. A 500 with
    # an HTML page is still more use than three words that name nothing.
    if isinstance(body, dict) and body:
        detail = body.get("raw") or body
        return f"HTTP {status}: {str(detail)[:200]}"
    if status and status >= 500:
        return "the platform returned a server error; try again shortly"
    return "request failed"


def _translate(exc: Exception, path: str) -> SwshError:
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    url = getattr(exc, "url", None)
    message = _describe(status, body) if status else f"{type(exc).__name__}: {exc}"
    return SwshError(f"{path}: {message}", status=status, body=body, url=url)


def _as_ref(ref: CallRef | str) -> CallRef:
    """Accept a bare identifier and guess its key space from the SID prefix."""
    if isinstance(ref, CallRef):
        return ref
    text = str(ref)
    if text.startswith("CA"):
        return CallRef(sid=text)
    return CallRef(call_id=text)
