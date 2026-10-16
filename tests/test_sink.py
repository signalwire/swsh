"""The callback sink, driven end to end over real HTTP."""

from __future__ import annotations

import base64
import hashlib
import hmac
from asyncio import QueueEmpty

import httpx
import pytest

from swsh.events.bus import EventBus
from swsh.events.webhook_source import WebhookSink
from swsh.models import CallEvent, CallState, MessageEvent, Source


def client_for(sink: WebhookSink) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=sink.app), base_url="http://sink"
    )


async def test_form_encoded_call_callback_reaches_the_bus():
    bus = EventBus()
    sub = bus.subscribe()
    sink = WebhookSink(bus)

    async with client_for(sink) as http:
        resp = await http.post(
            "/cb/voice",
            data={
                "CallSid": "CA123",
                "CallStatus": "completed",
                "From": "+15551112222",
                "To": "+15553334444",
                "Direction": "inbound",
            },
        )

    assert resp.status_code == 204
    event = sub._queue.get_nowait()
    assert isinstance(event, CallEvent)
    assert event.ref.sid == "CA123"
    assert event.state is CallState.ENDED
    assert event.source is Source.CALLBACK
    assert sink.received == 1


async def test_json_bodies_are_accepted_too():
    bus = EventBus()
    sub = bus.subscribe()
    sink = WebhookSink(bus)

    async with client_for(sink) as http:
        resp = await http.post("/cb/voice", json={"CallSid": "CA9", "CallStatus": "ringing"})

    assert resp.status_code == 204
    assert sub._queue.get_nowait().state is CallState.RINGING


async def test_message_callbacks_become_message_events():
    bus = EventBus()
    sub = bus.subscribe()
    sink = WebhookSink(bus)

    async with client_for(sink) as http:
        await http.post(
            "/cb/message",
            data={"MessageSid": "SM1", "MessageStatus": "delivered", "To": "+15551112222"},
        )

    event = sub._queue.get_nowait()
    assert isinstance(event, MessageEvent)
    assert event.sid == "SM1"
    assert event.state == "delivered"


async def test_channel_names_the_event_kind():
    """A recording hook should read as 'recording' in the feed, not 'state'."""
    bus = EventBus()
    sub = bus.subscribe()
    sink = WebhookSink(bus)

    async with client_for(sink) as http:
        await http.post("/cb/recording", data={"CallSid": "CA1", "CallStatus": "completed"})

    assert sub._queue.get_nowait().kind == "recording"


async def test_sink_never_returns_call_instructions():
    """A monitor must not alter call behaviour, so the body is always empty."""
    bus = EventBus()
    sink = WebhookSink(bus)
    async with client_for(sink) as http:
        resp = await http.post("/cb/voice", data={"CallSid": "CA1", "CallStatus": "ringing"})
    assert resp.status_code == 204
    assert resp.content == b""


async def test_health_reports_counters():
    bus = EventBus()
    sink = WebhookSink(bus)
    sink.public_url = "https://example.ngrok.app"
    async with client_for(sink) as http:
        await http.post("/cb/voice", data={"CallSid": "CA1", "CallStatus": "ringing"})
        health = (await http.get("/health")).json()
    assert health == {
        "ok": True, "received": 1, "rejected": 0, "public_url": "https://example.ngrok.app"
    }


class TestSignatureVerification:
    def sign(self, token: str, url: str, params: dict[str, str]) -> str:
        buffer = url + "".join(f"{k}{params[k]}" for k in sorted(params))
        digest = hmac.new(token.encode(), buffer.encode(), hashlib.sha1).digest()
        return base64.b64encode(digest).decode()

    async def test_valid_signature_passes(self):
        bus = EventBus()
        sink = WebhookSink(bus, auth_token="tok", verify_signatures=True)
        sink.public_url = "https://example.ngrok.app"
        params = {"CallSid": "CA1", "CallStatus": "ringing"}
        signature = self.sign("tok", "https://example.ngrok.app/cb/voice", params)

        async with client_for(sink) as http:
            resp = await http.post(
                "/cb/voice", data=params, headers={"X-Twilio-Signature": signature}
            )
        assert resp.status_code == 204
        assert sink.rejected == 0

    async def test_bad_signature_is_rejected(self):
        bus = EventBus()
        sub = bus.subscribe()
        sink = WebhookSink(bus, auth_token="tok", verify_signatures=True)
        sink.public_url = "https://example.ngrok.app"

        async with client_for(sink) as http:
            resp = await http.post(
                "/cb/voice",
                data={"CallSid": "CA1", "CallStatus": "ringing"},
                headers={"X-Twilio-Signature": "nope"},
            )
        assert resp.status_code == 403
        assert sink.rejected == 1
        with pytest.raises(QueueEmpty):
            sub._queue.get_nowait()  # nothing published

    async def test_missing_signature_is_rejected_when_verifying(self):
        sink = WebhookSink(EventBus(), auth_token="tok", verify_signatures=True)
        async with client_for(sink) as http:
            resp = await http.post("/cb/voice", data={"CallSid": "CA1"})
        assert resp.status_code == 403
