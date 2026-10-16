"""The selector service — shared enumerable-field options.

One implementation feeds TUI dropdowns, CLI pickers and completion, so it must
resolve options through the registry, cache them, and filter numbers by channel.
"""

from __future__ import annotations

from swsh.client import SwshClient
from swsh.config import Profile
from swsh.selectors import Option, Selector

FAKE = Profile(name="t", project="p", token="k", space="example.signalwire.com")

NUMBERS = {
    "data": [
        {"number": "+15551110000", "name": "Main", "capabilities": ["voice", "sms", "mms", "fax"]},
        {"number": "+15552220000", "name": "SMS only", "capabilities": ["sms", "mms"]},
        {"number": "+15553330000", "name": "Fax only", "capabilities": ["fax"]},
    ]
}


def client_returning(payload):
    client = SwshClient(FAKE)
    calls = []

    async def fake_invoke(resource, op, **kw):
        calls.append((resource.key, op))
        return payload

    client.invoke = fake_invoke
    client._calls = calls
    return client


class TestOptions:
    async def test_resolves_options_from_a_list_path(self):
        client = client_returning(NUMBERS)
        opts = await client.selector.options(("numbers.list", "number", "name"))
        assert [o.value for o in opts] == ["+15551110000", "+15552220000", "+15553330000"]
        assert opts[0].label == "Main"

    async def test_labels_can_come_from_a_nested_field(self):
        # Fabric SIP endpoints keep the username under `sip_endpoint`; the
        # picker labels have to reach it or every option reads as a bare id.
        client = client_returning({"data": [
            {"id": "ep-1", "display_name": "deskphone", "sip_endpoint": {"username": "deskphone"}},
        ]})
        opts = await client.selector.options(("sip.list", "id", "sip_endpoint.username"))
        assert [(o.value, o.label) for o in opts] == [("ep-1", "deskphone")]

    async def test_display_combines_value_and_label(self):
        assert Option("+1555", "Main").display == "+1555  Main"
        assert Option("+1555", "").display == "+1555"

    async def test_results_are_cached(self):
        client = client_returning(NUMBERS)
        await client.selector.options(("numbers.list", "number", "name"))
        await client.selector.options(("numbers.list", "number", "name"))
        assert client._calls == [("numbers", "list")]  # only one API round trip

    async def test_refresh_bypasses_cache(self):
        client = client_returning(NUMBERS)
        await client.selector.options(("numbers.list", "number", "name"))
        await client.selector.options(("numbers.list", "number", "name"), refresh=True)
        assert len(client._calls) == 2

    async def test_a_failing_list_yields_empty_not_an_error(self):
        client = SwshClient(FAKE)

        async def boom(resource, op, **kw):
            raise RuntimeError("network down")

        client.invoke = boom
        assert await client.selector.options(("numbers.list", "number", "name")) == []

    async def test_rows_without_the_value_key_are_skipped(self):
        client = client_returning({"data": [{"name": "no number"}, {"number": "+1", "name": "x"}]})
        opts = await client.selector.options(("numbers.list", "number", "name"))
        assert [o.value for o in opts] == ["+1"]


class TestCapabilityFilter:
    async def test_message_send_only_offers_messaging_numbers(self):
        client = client_returning(NUMBERS)
        opts = await client.selector.options(("numbers.list", "number", "name"))
        capable = Selector.capable(opts, "message")
        assert [o.value for o in capable] == ["+15551110000", "+15552220000"]

    async def test_fax_send_only_offers_fax_numbers(self):
        client = client_returning(NUMBERS)
        opts = await client.selector.options(("numbers.list", "number", "name"))
        capable = Selector.capable(opts, "fax")
        assert [o.value for o in capable] == ["+15551110000", "+15553330000"]

    def test_numbers_with_unknown_capabilities_are_kept(self):
        opts = [Option("+1", "x")]  # no capabilities
        assert Selector.capable(opts, "fax") == opts


class TestClientCaches:
    def test_client_exposes_one_selector(self):
        client = SwshClient(FAKE)
        assert client.selector is client.selector
