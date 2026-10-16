"""The transport abstraction: one `invoke`, two backends.

`client.invoke(resource, op, ...)` dispatches by the resource's transport — a
dotted SDK method for `sdk` resources, a spec-resolved REST route for `rest`
resources. Both are exercised here with the network stubbed, so the routing and
path composition are checked without a live project.
"""

from __future__ import annotations

from typing import Any

import pytest

from swsh import resources as res
from swsh.client import SwshClient, SwshError
from swsh.config import Profile

FAKE = Profile(name="t", project="proj-1", token="tok", space="example.signalwire.com")

# A rest-backed resource covering the real e911 surface, keyed to spec op ids.
E911 = res.Resource(
    key="e911", title="E911 addresses", namespace="", caps="LCR", group="numbers",
    transport="rest", api="relay-rest",
    rest_ops={
        "list": "list_addresses",
        "create": "create_address",
        "read": "get_address",
        "assign": "assign_e911_address",
        "remove": "remove_e911_address",
    },
)

# An sdk-backed resource (the normal case).
AGENTS = res.Resource(
    key="agents", title="AI agents", namespace="fabric.ai_agents", caps="LCRUD",
    api="fabric-api",
)


class Recorder:
    """Captures whatever the client would have sent."""

    def __init__(self, result: Any = None):
        self.calls: list[tuple] = []
        self.result = result if result is not None else {"ok": True}


class TestSdkTransport:
    async def test_invoke_calls_the_dotted_sdk_method(self):
        client = SwshClient(FAKE)
        rec = Recorder()

        async def fake_call_sdk(path, *args, **kwargs):
            rec.calls.append((path, args, kwargs))
            return rec.result

        client.call_sdk = fake_call_sdk
        await client.invoke(AGENTS, "list")
        await client.invoke(AGENTS, "read", resource_id="ag-1")
        await client.invoke(AGENTS, "create", body={"name": "Support"})

        assert rec.calls[0] == ("fabric.ai_agents.list", (), {})
        assert rec.calls[1] == ("fabric.ai_agents.get", ("ag-1",), {})
        assert rec.calls[2] == ("fabric.ai_agents.create", (), {"name": "Support"})

    async def test_sdk_method_override(self):
        r = res.Resource(key="x", title="x", namespace="ns", caps="L",
                         sdk_ops={"list": "list_all"})
        client = SwshClient(FAKE)
        seen = []
        async def fake(path, *a, **k):
            seen.append(path)
            return {}
        client.call_sdk = fake
        await client.invoke(r, "list")
        assert seen == ["ns.list_all"]


class TestRestTransport:
    async def test_list_resolves_the_spec_route(self):
        client = SwshClient(FAKE)
        rec = Recorder({"data": []})

        async def fake_rest(method, path, *, params=None, body=None):
            rec.calls.append((method, path, params, body))
            return rec.result

        client.rest_call = fake_rest
        await client.invoke(E911, "list")
        assert rec.calls[0][:2] == ("GET", "/api/relay/rest/addresses")

    async def test_e911_assign_fills_id_and_body(self):
        client = SwshClient(FAKE)
        rec = Recorder()
        async def fake(m, p, *, params=None, body=None):
            rec.calls.append((m, p, params, body))
            return rec.result
        client.rest_call = fake
        await client.invoke(E911, "assign", resource_id="pn-9",
                            body={"e911_address_id": "addr-1"})
        method, path, _params, body = rec.calls[0]
        assert method == "POST"
        assert path == "/api/relay/rest/phone_numbers/pn-9/e911_address"
        assert body == {"e911_address_id": "addr-1"}

    async def test_e911_remove_is_a_delete_on_the_same_path(self):
        client = SwshClient(FAKE)
        rec = Recorder()
        async def fake(m, p, *, params=None, body=None):
            rec.calls.append((m, p))
            return rec.result
        client.rest_call = fake
        await client.invoke(E911, "remove", resource_id="pn-9")
        assert rec.calls[0] == ("DELETE", "/api/relay/rest/phone_numbers/pn-9/e911_address")

    async def test_missing_id_on_an_id_route_is_an_error(self):
        client = SwshClient(FAKE)
        async def fake(*a, **k): return {}
        client.rest_call = fake
        with pytest.raises(SwshError, match="needs a resource id"):
            await client.invoke(E911, "assign", body={"e911_address_id": "a"})

    async def test_unknown_op_is_an_error(self):
        client = SwshClient(FAKE)
        async def fake(*a, **k): return {}
        client.rest_call = fake
        with pytest.raises((SwshError, KeyError)):
            await client.invoke(E911, "nonsense")

    async def test_named_placeholder_filled_from_params(self):
        """A route like /lookup/{e164_number} fills from a kwarg, not resource_id."""
        lookup = res.Resource(
            key="lookup", title="lookup", namespace="", caps="R", api="relay-rest",
            transport="rest", rest_ops={"read": "lookup_phone_number"},
        )
        client = SwshClient(FAKE)
        seen = {}
        async def fake_rest(method, path, *, params=None, body=None):
            seen.update(method=method, path=path, params=params)
            return {}
        client.rest_call = fake_rest
        await client.invoke(lookup, "read", e164_number="+15551234567")
        assert seen["path"] == "/api/relay/rest/lookup/phone_number/+15551234567"
        assert "e164_number" not in (seen["params"] or {})


class TestBackwardCompatibility:
    def test_existing_resources_default_to_sdk(self):
        # Every current registry resource is sdk-backed unless it opts into rest.
        for r in res.RESOURCES:
            assert r.transport in ("sdk", "rest")
            if r.transport == "rest":
                assert r.api, r.key
                # A rest resource has routes, or is action-only (MFA) and has
                # extras that carry theirs in spec_op.
                assert r.rest_ops or any(e.spec_op for e in r.extras), r.key

    def test_sdk_method_defaults(self):
        r = res.get("agents")
        assert r.sdk_method("list") == "list"
        assert r.sdk_method("read") == "get"
        assert r.sdk_method("delete") == "delete"
