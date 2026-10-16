"""Every rest-backed resource op must resolve to a real, well-formed route.

The registry names spec operation ids in ``rest_ops`` and in rest extras. If any
of those is a typo or belongs to the wrong API, the resource is dead on arrival.
This resolves every one through the same path the client uses, catching drift
between the registry and the spec catalog without a live project.
"""

from __future__ import annotations

import pytest

from swsh import resources as res
from swsh import spec
from swsh.client import SwshClient, SwshError
from swsh.config import Profile

FAKE = Profile(name="t", project="p", token="k", space="example.signalwire.com")


def rest_resources():
    return [r for r in res.RESOURCES if r.transport == "rest" or r.rest_ops]


def test_there_are_rest_resources():
    assert len(rest_resources()) >= 15  # e911, whatsapp, campaigns, projects, ...


def test_every_rest_op_resolves_to_a_spec_operation():
    for resource in rest_resources():
        for op_name, op_id in resource.rest_ops.items():
            op = spec.get(op_id, api=resource.api)
            assert op is not None, f"{resource.key}.{op_name} -> {resource.api}:{op_id}"


def test_every_rest_op_has_a_well_formed_path():
    for resource in rest_resources():
        for op_name, op_id in resource.rest_ops.items():
            op = spec.get(op_id, api=resource.api)
            assert op.path.startswith("/api/"), f"{resource.key}.{op_name}"
            assert "//" not in op.path, f"{resource.key}.{op_name}"
            assert op.method in ("GET", "POST", "PUT", "PATCH", "DELETE")


def test_rest_extras_reference_real_operations():
    for resource in rest_resources():
        for extra in resource.extras:
            if not extra.spec_op:
                continue
            assert spec.get(extra.spec_op, api=resource.api) is not None, \
                f"{resource.key}: extra {extra.key} -> {extra.spec_op}"


class TestInvokeResolvesRestPaths:
    """Drive client.invoke for each rest op with the network stubbed, asserting
    the method + path it would issue are exactly the spec's."""

    async def _capture(self, resource, op, **kw):
        client = SwshClient(FAKE)
        seen = {}

        async def fake_rest(method, path, *, params=None, body=None):
            seen.update(method=method, path=path)
            return {}

        client.rest_call = fake_rest
        await client.invoke(resource, op, **kw)
        return seen

    async def test_e911_assign_and_remove_act_on_a_phone_number(self):
        # E911 is an action on the number row, so it is an extra on `numbers`
        # and resolves through spec_op, the same way the TUI's `x` runs it.
        numbers = res.get("numbers")
        assign = await self._capture(numbers, "assign_e911_address", resource_id="pn-1",
                                     body={"e911_address_id": "a"})
        assert assign == {"method": "POST",
                          "path": "/api/relay/rest/phone_numbers/pn-1/e911_address"}
        remove = await self._capture(numbers, "remove_e911_address", resource_id="pn-1")
        assert remove["method"] == "DELETE"

    async def test_a_body_value_naming_a_route_placeholder_fills_the_route(self):
        # The MFA verify form collects the request id alongside the code. The
        # id is the route, not part of the body, and must not be sent twice.
        client = SwshClient(FAKE)
        seen = {}

        async def fake_rest(method, path, *, params=None, body=None):
            seen.update(method=method, path=path, body=body)
            return {}

        client.rest_call = fake_rest
        await client.invoke(res.get("mfa"), "verify",
                            body={"mfa_request_id": "req-1", "token": "123456"})
        assert seen["path"] == "/api/relay/rest/mfa/req-1/verify"
        assert seen["body"] == {"token": "123456"}

        await client.invoke(res.get("videorooms"), "by_name", body={"name": "lobby"})
        assert seen["path"] == "/api/video/rooms/lobby"
        assert seen["body"] == {}

    async def test_group_membership_add_fills_the_oddly_named_placeholder(self):
        seen = await self._capture(res.get("groups"), "add_member", resource_id="grp-1",
                                   body={"phone_number_id": "pn-1"})
        assert seen == {"method": "POST",
                        "path": "/api/relay/rest/number_groups/grp-1/number_group_memberships"}

    async def test_whatsapp_templates_crud_paths(self):
        wa = res.get("watemplates")
        listing = await self._capture(wa, "list")
        assert listing == {"method": "GET",
                           "path": "/api/messaging/whatsapp/templates"}
        one = await self._capture(wa, "read", resource_id="tmpl-1")
        assert one["path"] == "/api/messaging/whatsapp/templates/tmpl-1"

    async def test_projects_list_is_not_doubled(self):
        seen = await self._capture(res.get("projects"), "list")
        assert seen["path"] == "/api/projects"  # not /api/projects/api/projects

    async def test_lookup_fills_named_placeholder(self):
        seen = await self._capture(res.get("lookup"), "read",
                                   resource_id="+15551234567")
        assert seen["path"].endswith("/lookup/phone_number/+15551234567")

    async def test_missing_id_raises_before_calling(self):
        with pytest.raises(SwshError):
            await self._capture(res.get("watemplates"), "read")
