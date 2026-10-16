"""Tests for the three-channel merge.

This is the part of swsh most likely to be subtly wrong: the same call arrives
from RELAY keyed by UUID, from a status callback keyed by CA SID, and from a
poll carrying both, in no guaranteed order.
"""

from __future__ import annotations

from swsh.client import event_from_callback, event_from_relay
from swsh.events.bus import CallStore, EventBus
from swsh.models import CallEvent, CallRef, CallState, Source, parse_state


def make_store() -> CallStore:
    return CallStore(EventBus())


def state_event(state: CallState, *, sid=None, call_id=None, source=Source.POLL, **kw) -> CallEvent:
    return CallEvent(
        ref=CallRef(sid=sid, call_id=call_id), kind="state", source=source, state=state, **kw
    )


class TestStateParsing:
    def test_compat_folds_end_reason_out_of_status(self):
        assert parse_state("in-progress", dialect="compat") == (CallState.ANSWERED, None)
        assert parse_state("completed", dialect="compat") == (CallState.ENDED, "hangup")
        assert parse_state("busy", dialect="compat") == (CallState.ENDED, "busy")
        assert parse_state("no-answer", dialect="compat") == (CallState.ENDED, "noAnswer")

    def test_relay_states_pass_through(self):
        assert parse_state("answered", dialect="relay") == (CallState.ANSWERED, None)
        assert parse_state("ended", dialect="relay") == (CallState.ENDED, None)

    def test_unknown_is_not_an_exception(self):
        assert parse_state("something-new") == (CallState.UNKNOWN, None)
        assert parse_state(None) == (CallState.UNKNOWN, None)

    def test_only_live_states_count_as_live(self):
        assert CallState.ANSWERED.is_live
        assert CallState.RINGING.is_live
        assert not CallState.ENDED.is_live
        assert not CallState.UNKNOWN.is_live


class TestOrdering:
    def test_state_never_regresses(self):
        """A poll in flight when a call ends must not resurrect it."""
        store = make_store()
        store.apply(state_event(CallState.ANSWERED, sid="CA1"))
        store.apply(state_event(CallState.ENDED, sid="CA1", source=Source.RELAY))
        store.apply(state_event(CallState.ANSWERED, sid="CA1"))  # stale poll lands late

        call = store.get("CA1")
        assert call.state is CallState.ENDED
        assert not call.is_live

    def test_forward_progress_applies(self):
        store = make_store()
        store.apply(state_event(CallState.CREATED, sid="CA1"))
        store.apply(state_event(CallState.RINGING, sid="CA1"))
        store.apply(state_event(CallState.ANSWERED, sid="CA1"))
        assert store.get("CA1").state is CallState.ANSWERED

    def test_unknown_state_does_not_clobber(self):
        store = make_store()
        store.apply(state_event(CallState.ANSWERED, sid="CA1"))
        store.apply(state_event(CallState.UNKNOWN, sid="CA1", from_number="+15551112222"))
        call = store.get("CA1")
        assert call.state is CallState.ANSWERED
        assert call.from_number == "+15551112222"  # detail still merged


class TestIdentityFusion:
    def test_uuid_and_sid_fuse_into_one_call(self):
        """The core dedupe: RELAY sees a UUID, a callback sees a SID, then a
        poll proves they are the same call."""
        store = make_store()
        store.apply(state_event(CallState.RINGING, call_id="uuid-1", source=Source.RELAY))
        store.apply(state_event(CallState.RINGING, sid="CA1", source=Source.CALLBACK))
        assert len(store.all()) == 2  # not yet known to be the same

        store.apply(state_event(CallState.ANSWERED, sid="CA1", call_id="uuid-1"))

        assert len(store.all()) == 1
        call = store.all()[0]
        assert call.ref.sid == "CA1"
        assert call.ref.call_id == "uuid-1"
        assert call.state is CallState.ANSWERED

    def test_both_identifiers_resolve_after_fusion(self):
        store = make_store()
        store.apply(state_event(CallState.RINGING, call_id="uuid-1"))
        store.apply(state_event(CallState.RINGING, sid="CA1"))
        store.apply(state_event(CallState.ANSWERED, sid="CA1", call_id="uuid-1"))

        assert store.get("CA1") is store.get("uuid-1")

    def test_fusion_preserves_earliest_first_seen(self):
        store = make_store()
        store.apply(state_event(CallState.RINGING, call_id="uuid-1"))
        first = store.get("uuid-1").first_seen
        store.apply(state_event(CallState.RINGING, sid="CA1"))
        store.get("CA1").first_seen = first + 100
        store.apply(state_event(CallState.ANSWERED, sid="CA1", call_id="uuid-1"))
        assert store.all()[0].first_seen == first

    def test_sources_accumulate_across_channels(self):
        store = make_store()
        store.apply(state_event(CallState.RINGING, sid="CA1", source=Source.POLL))
        store.apply(state_event(CallState.ANSWERED, sid="CA1", source=Source.CALLBACK))
        store.apply(state_event(CallState.ENDED, sid="CA1", source=Source.RELAY))
        assert store.get("CA1").sources == {Source.POLL, Source.CALLBACK, Source.RELAY}

    def test_unidentifiable_event_is_dropped(self):
        store = make_store()
        assert store.apply(state_event(CallState.ANSWERED)) is None
        assert store.all() == []


class TestPayloadDecoding:
    def test_status_callback_body(self):
        event = event_from_callback(
            {
                "CallSid": "CA123",
                "CallStatus": "completed",
                "From": "+15551112222",
                "To": "+15553334444",
                "Direction": "inbound",
            }
        )
        assert event.ref.sid == "CA123"
        assert event.state is CallState.ENDED
        assert event.source is Source.CALLBACK
        assert event.from_number == "+15551112222"

    def test_callback_field_casing_is_forgiving(self):
        """LaML casing varies between endpoints, so lookups ignore case."""
        event = event_from_callback({"callsid": "CA9", "callstatus": "ringing"})
        assert event.ref.sid == "CA9"
        assert event.state is CallState.RINGING

    def test_relay_event_with_nested_device(self):
        event = event_from_relay(
            {
                "event_type": "calling.call.state",
                "params": {
                    "call_id": "uuid-7",
                    "call_state": "answered",
                    "direction": "inbound",
                    "node_id": "node-1",
                    "device": {
                        "type": "phone",
                        "params": {"from_number": "+15551112222", "to_number": "+15553334444"},
                    },
                },
            }
        )
        assert event.ref.call_id == "uuid-7"
        assert event.ref.node_id == "node-1"
        assert event.state is CallState.ANSWERED
        assert event.to_number == "+15553334444"
        assert event.source is Source.RELAY

    def test_relay_end_reason_is_kept(self):
        event = event_from_relay(
            {"event_type": "calling.call.state",
             "params": {"call_id": "u1", "call_state": "ended", "end_reason": "busy"}}
        )
        assert event.state is CallState.ENDED
        assert event.end_reason == "busy"


class TestLifecycle:
    def test_live_excludes_ended(self):
        store = make_store()
        store.apply(state_event(CallState.ANSWERED, sid="CA1"))
        store.apply(state_event(CallState.ANSWERED, sid="CA2"))
        store.apply(state_event(CallState.ENDED, sid="CA2"))
        assert [c.ref.sid for c in store.live()] == ["CA1"]

    def test_ended_calls_are_eventually_forgotten(self):
        store = CallStore(EventBus(), retain_ended=3)
        for i in range(10):
            sid = f"CA{i}"
            store.apply(state_event(CallState.ANSWERED, sid=sid))
            store.apply(state_event(CallState.ENDED, sid=sid))
        assert len(store.all()) == 3

    def test_prefix_resolution(self):
        store = make_store()
        store.apply(state_event(CallState.ANSWERED, sid="CAabcdef123"))
        assert store.resolve("CAabc").ref.sid == "CAabcdef123"

    def test_ambiguous_prefix_resolves_to_nothing(self):
        store = make_store()
        store.apply(state_event(CallState.ANSWERED, sid="CAabc1"))
        store.apply(state_event(CallState.ANSWERED, sid="CAabc2"))
        assert store.resolve("CAabc") is None

    def test_change_listener_fires_only_on_change(self):
        store = make_store()
        seen = []
        store.on_change(lambda call, event: seen.append(call.state))
        store.apply(state_event(CallState.ANSWERED, sid="CA1", source=Source.POLL))
        store.apply(state_event(CallState.ANSWERED, sid="CA1", source=Source.POLL))
        assert seen == [CallState.ANSWERED]


class TestBus:
    def test_subscriber_receives_published_events(self):
        bus = EventBus()
        sub = bus.subscribe()
        event = state_event(CallState.RINGING, sid="CA1")
        bus.publish(event)
        assert sub._queue.get_nowait() is event

    def test_overflow_drops_oldest_rather_than_blocking(self):
        bus = EventBus()
        sub = bus.subscribe(maxsize=2)
        for i in range(5):
            bus.publish(state_event(CallState.RINGING, sid=f"CA{i}"))
        assert sub.dropped == 3
        assert sub._queue.qsize() == 2

    def test_kind_filter(self):
        bus = EventBus()
        sub = bus.subscribe(kinds={"record"})
        bus.publish(state_event(CallState.RINGING, sid="CA1"))
        assert sub._queue.qsize() == 0
