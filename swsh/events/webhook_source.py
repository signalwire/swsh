"""HTTP sink for status callbacks.

SignalWire delivers call, message, recording and conference status as HTTP POSTs
to URLs you configure per resource. This module receives them, normalises them
onto the shared bus, and can also forward them to a second URL so swsh can sit
in front of an application you are already developing.

Bodies arrive form-encoded on the LaML surface and as JSON elsewhere, so both
are accepted on every route.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl

import httpx
from fastapi import FastAPI, Request, Response

from ..client import event_from_callback
from ..models import CallEvent, MessageEvent, Source
from .bus import EventBus


class WebhookSink:
    """A small ASGI app that turns status callbacks into bus events."""

    def __init__(
        self,
        bus: EventBus,
        *,
        auth_token: str | None = None,
        verify_signatures: bool = False,
        forward_to: str | None = None,
        on_request: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        self.bus = bus
        self.auth_token = auth_token
        self.verify_signatures = verify_signatures
        self.forward_to = forward_to
        self.on_request = on_request
        self.received = 0
        self.rejected = 0
        self.public_url: str | None = None
        # Strong references to in-flight forward tasks. asyncio only holds weak
        # references, so without this a forward can be garbage collected before
        # it completes.
        self._forwards: set[asyncio.Task[None]] = set()
        self._app = self._build()

    @property
    def app(self):
        return self._app

    def url_for(self, path: str) -> str:
        if not self.public_url:
            raise RuntimeError("sink has no public URL yet")
        return f"{self.public_url.rstrip('/')}/{path.lstrip('/')}"

    def _build(self) -> FastAPI:
        app = FastAPI(title="swsh callback sink", docs_url=None, redoc_url=None)

        @app.get("/health")
        async def health() -> dict[str, Any]:
            return {
                "ok": True,
                "received": self.received,
                "rejected": self.rejected,
                "public_url": self.public_url,
            }

        @app.post("/cb/{channel}")
        async def callback(channel: str, request: Request) -> Response:
            payload = await _read_body(request)

            if self.verify_signatures and not self._signature_ok(request, payload):
                self.rejected += 1
                return Response(status_code=403, content="bad signature")

            self.received += 1
            if self.on_request is not None:
                try:
                    self.on_request(channel, payload)
                except Exception:
                    pass

            self._publish(channel, payload)
            if self.forward_to:
                task = asyncio.create_task(
                    self._forward(channel, payload, dict(request.headers))
                )
                self._forwards.add(task)
                task.add_done_callback(self._forwards.discard)

            # An empty 204 tells SignalWire "received, no instructions".
            # Returning cXML here would change call behaviour, which a monitor
            # must never do.
            return Response(status_code=204)

        return app

    def _publish(self, channel: str, payload: dict[str, Any]) -> None:
        lowered = {str(k).lower(): v for k, v in payload.items()}

        if "messagesid" in lowered or "messagestatus" in lowered or channel == "message":
            self.bus.publish(
                MessageEvent(
                    sid=str(lowered.get("messagesid") or lowered.get("smssid") or ""),
                    state=str(
                        lowered.get("messagestatus") or lowered.get("smsstatus") or "unknown"
                    ),
                    source=Source.CALLBACK,
                    direction=lowered.get("direction"),
                    from_number=lowered.get("from"),
                    to_number=lowered.get("to"),
                    body=lowered.get("body"),
                    error=lowered.get("errormessage"),
                    raw=dict(payload),
                )
            )
            return

        event: CallEvent = event_from_callback(payload)
        # Preserve which hook fired, so the feed can show "recording" rather
        # than a generic state change.
        if channel not in ("voice", "call"):
            event.kind = channel
        self.bus.publish(event)

    async def _forward(self, channel: str, payload: dict[str, Any],
                       headers: dict[str, str]) -> None:
        """Relay the callback onward, so swsh can sit in front of a real app."""
        target = f"{self.forward_to.rstrip('/')}/{channel}"
        passthrough = {
            k: v for k, v in headers.items()
            if k.lower() in ("content-type", "x-twilio-signature", "x-signalwire-signature")
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                await http.post(target, data=payload, headers=passthrough)
        except Exception:
            pass

    def _signature_ok(self, request: Any, payload: dict[str, Any]) -> bool:
        """Twilio-compatible HMAC-SHA1 validation.

        SignalWire's compat surface signs the way Twilio does: the full request
        URL, then each POST parameter sorted by key and concatenated, HMAC-SHA1
        with the auth token, base64 encoded.

        Unverified against a live project. Off by default for that reason; turn
        it on with --verify-signatures once you have confirmed it against real
        traffic.
        """
        if not self.auth_token:
            return False
        header = request.headers.get("x-twilio-signature") or request.headers.get(
            "x-signalwire-signature"
        )
        if not header:
            return False

        url = str(request.url)
        if self.public_url:
            # Rebuild the URL as SignalWire saw it: it signed the public URL,
            # not the local one the tunnel forwarded to.
            url = f"{self.public_url.rstrip('/')}{request.url.path}"
            if request.url.query:
                url = f"{url}?{request.url.query}"

        buffer = url
        for key in sorted(payload):
            buffer += f"{key}{payload[key]}"
        digest = hmac.new(
            self.auth_token.encode("utf-8"), buffer.encode("utf-8"), hashlib.sha1
        ).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, header)


async def _read_body(request: Request) -> dict[str, Any]:
    """Accept form-encoded or JSON, since which one arrives depends on the API.

    Status callbacks are ``application/x-www-form-urlencoded``, which is parsed
    directly here rather than through Starlette's ``request.form()``. Starlette
    asserts on ``python-multipart`` being installed even for urlencoded bodies,
    and this is the hot path for every callback swsh receives.
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "json" in content_type:
        try:
            data = await request.json()
        except Exception:
            return {}
        return data if isinstance(data, dict) else {"data": data}

    if "x-www-form-urlencoded" in content_type:
        raw = await request.body()
        try:
            pairs = parse_qsl(raw.decode("utf-8"), keep_blank_values=True)
        except Exception:
            return {}
        return dict(pairs)

    # Multipart, or anything unexpected. Needs python-multipart; if it is not
    # installed the callback is still acknowledged, just not decoded.
    try:
        form = await request.form()
    except Exception:
        return {}
    return dict(form)


async def serve_sink(sink: WebhookSink, port: int, host: str = "127.0.0.1") -> asyncio.Task[None]:
    """Run the sink under uvicorn as a background task."""
    import uvicorn

    config = uvicorn.Config(sink.app, host=host, port=port, log_level="warning",
                            access_log=False)
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve(), name="swsh-sink")

    # Wait for the socket to actually be listening before callers wire URLs to it.
    for _ in range(100):
        if getattr(server, "started", False):
            break
        await asyncio.sleep(0.05)
    return task
