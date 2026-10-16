"""Live calls come from the voice logs API, not the compat ``Calls`` list.

Pinned after a live check on 2026-09-09: a SIP endpoint dialling out through
SWML was up, ``sw calls list --live`` said "no calls", because the compat list
only carries LaML legs. ``/api/voice/logs`` lists every leg while it is up
(``initiated`` / ``in-progress`` / ``joined`` were all observed live) and keeps
the row with a terminal status once it ends. Everything here follows from that
shape.
"""

from __future__ import annotations

import time

import httpx
import pytest
import respx
from rich.console import Console
from rich.table import Table

from swsh import ui
from swsh.client import SwshClient, SwshError, call_from_voice_log
from swsh.config import Profile
from swsh.events.bus import CallStore, EventBus
from swsh.events.poll_source import PollSource
from swsh.models import CallState, parse_state

FAKE = Profile(name="t", project="proj-1", token="tok", space="example.signalwire.com")
LOGS = "https://example.signalwire.com/api/voice/logs"


def row(identifier: str, status: str, *, source: str = "realtime_api",
        kind: str = "relay_sip_call", duration=None, **extra) -> dict:
    return {
        "id": identifier, "status": status, "source": source, "type": kind,
        "from": "reception", "to": "+14405550166", "direction": "inbound",
        "duration": duration, "created_at": "2026-09-09T20:47:48.146Z", **extra,
    }


class TestVoiceLogVocabulary:
    def test_every_engine_word_seen_live_maps_to_a_live_state(self):
        # LaML legs, RELAY legs and a PSTN leg parked in a video room each
        # spell "up" differently. All three were observed on a live project.
        assert parse_state("initiated", dialect="voicelog")[0] is CallState.CREATED
        assert parse_state("in-progress", dialect="voicelog")[0] is CallState.ANSWERED
        assert parse_state("answered", dialect="voicelog")[0] is CallState.ANSWERED
        assert parse_state("joined", dialect="voicelog")[0] is CallState.ANSWERED
        assert parse_state("ringing", dialect="voicelog")[0] is CallState.RINGING

    def test_terminal_words_keep_their_reason(self):
        assert parse_state("ended", dialect="voicelog") == (CallState.ENDED, None)
        assert parse_state("completed", dialect="voicelog") == (CallState.ENDED, "hangup")
        assert parse_state("failed", dialect="voicelog") == (CallState.ENDED, "error")


class TestRowNormalisation:
    def test_laml_leg_keeps_its_id_in_the_compat_slot(self):
        # A LaML id is not usable by the calling API ("must not point to a
        # cXML call"), so it must not masquerade as a native call id.
        call = call_from_voice_log(row("0000c001", "in-progress", source="laml",
                                       kind="laml_call"))
        assert call.ref.sid == "0000c001"
        assert call.ref.call_id is None
        assert call.call_type == "laml_call"

    def test_native_leg_carries_the_calling_api_id(self):
        call = call_from_voice_log(row("ca000001", "answered"))
        assert call.ref.call_id == "ca000001"
        assert call.ref.sid is None

    def test_live_row_ticks_from_created_at_rather_than_a_stale_snapshot(self):
        call = call_from_voice_log(row("x", "in-progress", duration=14))
        assert call.is_live
        assert call.duration_reported is None
        assert call.started_at is not None
        assert call.duration > 0

    def test_ended_row_reports_its_final_duration_and_end_time(self):
        call = call_from_voice_log(row("x", "ended", duration=66))
        assert not call.is_live
        assert call.duration == 66
        assert call.ended_at == call.started_at + 66


class TestLiveCalls:
    @respx.mock
    async def test_live_reads_the_voice_log_window_and_keeps_only_live_rows(self):
        route = respx.get(LOGS).mock(return_value=httpx.Response(200, json={"data": [
            row("live-1", "answered"),
            row("laml-1", "in-progress", source="laml", kind="laml_call"),
            row("parked", "joined", kind="video_room_pstn_leg"),
            row("done", "ended", duration=3),
            row("bad", "failed"),
        ]}))
        client = SwshClient(FAKE)
        live = await client.live_calls()

        assert {str(c.ref) for c in live} == {"live-1", "laml-1", "parked"}
        params = route.calls.last.request.url.params
        assert "created_after" in params  # bounded, so no paging through history
        assert params["page_size"] == "200"

    @respx.mock
    async def test_status_filter_accepts_engine_words_and_normalised_states(self):
        respx.get(LOGS).mock(return_value=httpx.Response(200, json={"data": [
            row("a", "in-progress", source="laml", kind="laml_call"),
            row("b", "answered"),
            row("c", "ended", duration=1),
        ]}))
        client = SwshClient(FAKE)
        assert [str(c.ref) for c in await client.list_calls(status="in-progress")] == ["a"]
        assert {str(c.ref) for c in await client.list_calls(status="answered")} == {"a", "b"}

    @respx.mock
    async def test_show_resolves_any_engine_id_through_the_voice_log(self):
        respx.get(f"{LOGS}/ca000001").mock(
            return_value=httpx.Response(200, json=row("ca000001", "ended", duration=66)))
        call = await SwshClient(FAKE).get_call("ca000001")
        assert call.ref.call_id == "ca000001"
        assert call.call_type == "relay_sip_call"

    @respx.mock
    async def test_show_falls_back_to_compat_for_a_leg_the_log_lacks(self):
        respx.get(f"{LOGS}/CA1").mock(return_value=httpx.Response(404, json={}))
        respx.get("https://example.signalwire.com/api/laml/2010-04-01/Accounts/proj-1/Calls/CA1.json"
                  ).mock(return_value=httpx.Response(200, json={
                      "sid": "CA1", "status": "in-progress", "from": "+1", "to": "+2"}))
        call = await SwshClient(FAKE).get_call("CA1")
        assert call.ref.sid == "CA1"
        assert call.state is CallState.ANSWERED


class FakeClient:
    """Feeds the poller successive voice-log snapshots."""

    LIVE_LOOKBACK_SECONDS = 60

    def __init__(self, *snapshots: list[dict]):
        self.snapshots = list(snapshots)

    async def recent_calls(self, **_: object):
        rows = self.snapshots.pop(0) if len(self.snapshots) > 1 else self.snapshots[0]
        return [call_from_voice_log(r) for r in rows]


class TestPoller:
    async def _run(self, *snapshots):
        bus = EventBus()
        store = CallStore(bus)
        events = []
        bus.subscribe()  # a passive subscriber, so publish has somewhere to go
        poller = PollSource(FakeClient(*snapshots), bus)  # type: ignore[arg-type]
        for _ in snapshots:
            await poller._tick()
        for event in bus.history():
            store.apply(event)
            events.append(event)
        return store, events

    async def test_history_is_not_replayed_as_events(self):
        # Rows that were already over when the poller first looked are the
        # project's past, not something that just happened.
        store, events = await self._run([row("old", "ended", duration=3)])
        assert events == []
        assert store.all() == []

    async def test_a_live_leg_is_published_once_per_state_change(self):
        store, events = await self._run(
            [row("c1", "ringing")],
            [row("c1", "ringing")],
            [row("c1", "answered")],
        )
        assert [e.state for e in events] == [CallState.RINGING, CallState.ANSWERED]
        assert store.get("c1").is_live

    async def test_the_row_turning_terminal_ends_the_call_with_its_reason(self):
        store, events = await self._run(
            [row("c1", "in-progress", source="laml", kind="laml_call")],
            [row("c1", "completed", source="laml", kind="laml_call", duration=42)],
            [row("c1", "completed", source="laml", kind="laml_call", duration=42)],
        )
        assert [e.state for e in events] == [CallState.ANSWERED, CallState.ENDED]
        call = store.get("c1")
        assert not call.is_live
        assert call.end_reason == "hangup"
        assert call.duration == 42
        # The terminal row is reported exactly once, not on every later poll.
        assert len(events) == 2

    async def test_a_leg_that_leaves_the_window_is_ended_without_a_reason(self):
        store, events = await self._run([row("c1", "answered")], [])
        assert [e.state for e in events] == [CallState.ANSWERED, CallState.ENDED]
        assert events[-1].detail == "disappeared between polls"
        assert events[-1].ref.call_id == "c1"  # the remembered ref, not a guess
        assert not store.get("c1").is_live


class TestRendering:
    def test_the_id_leads_the_row_and_is_never_truncated(self):
        call = call_from_voice_log(row("ca000000-0000-4000-8000-000000000001", "ended",
                                       duration=66))
        cells = ui.call_row(call, compact=False)
        assert cells[0] == "ca000000-0000-4000-8000-000000000001"
        assert cells[4] == time.strftime("%m-%d %H:%M:%S", time.localtime(call.started_at))
        assert len(cells) == len(ui.CALL_COLUMNS)

    def test_compact_timestamps_keep_the_date_on_anything_but_today(self):
        """Today loses the date to save eight columns; an older call must not."""
        today = time.time()
        older = today - 3 * 86400
        assert ui.when_text(today, compact=True) == time.strftime("%H:%M:%S",
                                                                  time.localtime(today))
        assert ui.when_text(older, compact=True) == time.strftime("%m-%d %H:%M:%S",
                                                                  time.localtime(older))
        assert ui.when_text(None, compact=True) == "-"

    def test_a_narrow_terminal_sheds_decoration_before_it_sheds_facts(self):
        call = call_from_voice_log(row("ca000000-0000-4000-8000-000000000001", "ended",
                                       duration=66))
        wide = ui.calls_table([call], width=200)
        assert [c.header for c in wide.columns] == list(ui.CALL_COLUMNS)
        assert wide.box is not None

        # The box goes before any column does, and it is worth 9 columns: Rich
        # reserves a separator cell per column even for a box that draws none.
        boxless = ui.calls_table([call], width=131)
        assert [c.header for c in boxless.columns] == list(ui.CALL_COLUMNS)
        assert boxless.box is None

        without_ended = ui.calls_table([call], width=120)
        assert [c.header for c in without_ended.columns] == [
            c for c in ui.CALL_COLUMNS if c != "ended"]
        # The id survives every width: it is the one cell people paste elsewhere.
        assert without_ended.columns[0].min_width == 36

    def test_a_terminal_too_narrow_for_columns_stacks_instead_of_dropping_them(self):
        """Rich pays for an over-budget table by deleting columns. Never that."""
        call = call_from_voice_log(row("ca000000-0000-4000-8000-000000000001", "ended",
                                       duration=66))
        stacked = ui.calls_table([call], width=80)
        assert not isinstance(stacked, Table)

        console = Console(width=80, record=True, theme=ui.SWSH_THEME)
        console.print(stacked)
        out = console.export_text()
        assert "ca000000-0000-4000-8000-000000000001" in out  # never truncated
        for fact in (call.from_number, call.to_number, "ended"):
            assert fact in out
        assert max(len(line) for line in out.splitlines()) <= 80

    def test_an_empty_table_still_fills_every_column(self):
        for width in (200, 120):
            table = ui.calls_table([], width=width)
            assert len(table.rows) == 1
            assert all(len(c._cells) == 1 for c in table.columns)

    def test_an_empty_list_says_so_at_every_width(self):
        for width in (200, 120, 80):
            console = Console(width=width, record=True, theme=ui.SWSH_THEME)
            console.print(ui.calls_table([], width=width))
            assert "no calls" in console.export_text()


class TestDial:
    """The cockpit and `sw calls dial --tts` share one entry point."""

    @respx.mock
    async def test_say_is_inlined_as_a_cxml_document(self):
        route = respx.post(
            "https://example.signalwire.com/api/laml/2010-04-01/Accounts/proj-1/Calls.json"
        ).mock(return_value=httpx.Response(201, json={"sid": "CA1", "status": "queued",
                                                      "from": "+1", "to": "+2"}))
        call = await SwshClient(FAKE).dial(to="+2", from_="+1", say="hi & bye")
        assert call.ref.sid == "CA1"
        from urllib.parse import parse_qs

        sent = parse_qs(route.calls.last.request.content.decode())
        assert sent["Twiml"] == ["<Response><Say>hi &amp; bye</Say></Response>"]
        assert "Url" not in sent

    async def test_a_call_needs_a_url_or_something_to_say(self):
        with pytest.raises(SwshError):
            await SwshClient(FAKE).dial(to="+2", from_="+1")


class TestControlRouting:
    """Every id is a UUID, so the engine has to be looked up, not guessed."""

    @respx.mock
    async def test_hangup_on_a_laml_leg_goes_through_compat(self):
        respx.get(f"{LOGS}/leg").mock(return_value=httpx.Response(
            200, json=row("leg", "in-progress", source="laml", kind="laml_call")))
        compat = respx.post(
            "https://example.signalwire.com/api/laml/2010-04-01/Accounts/proj-1/Calls/leg.json"
        ).mock(return_value=httpx.Response(200, json={"sid": "leg", "status": "completed"}))
        client = SwshClient(FAKE)
        sdk_calls = []

        async def fake_call_sdk(path, *args, **kwargs):
            sdk_calls.append(path)

        client.call_sdk = fake_call_sdk
        await client.hangup("leg")
        assert compat.called
        assert sdk_calls == []  # never calling.end, which 422s on a cXML call

    @respx.mock
    async def test_hangup_on_a_native_leg_uses_the_calling_api(self):
        respx.get(f"{LOGS}/leg").mock(return_value=httpx.Response(200, json=row("leg", "answered")))
        client = SwshClient(FAKE)
        sdk_calls = []

        async def fake_call_sdk(path, *args, **kwargs):
            sdk_calls.append((path, args, kwargs))
            return {}

        client.call_sdk = fake_call_sdk
        await client.hangup("leg")
        assert sdk_calls == [("calling.end", ("leg",), {"reason": "hangup"})]

    @respx.mock
    async def test_native_only_commands_explain_a_laml_leg_up_front(self):
        respx.get(f"{LOGS}/leg").mock(return_value=httpx.Response(
            200, json=row("leg", "in-progress", source="laml", kind="laml_call")))
        client = SwshClient(FAKE)
        try:
            await client.play_tts("leg", "hello")
        except Exception as exc:
            assert "LaML" in str(exc) and "hangup and record still work" in str(exc)
        else:
            raise AssertionError("play on a LaML leg should be refused locally")
