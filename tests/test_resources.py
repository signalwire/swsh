"""The resource registry and its envelope handling.

Field names across the Fabric, RELAY-REST and LaML surfaces are inconsistent and
several are unverified, so the important property is that an unexpected payload
shape degrades to something useful rather than to an empty table.
"""

from __future__ import annotations

import re

from swsh import resources as res
from swsh import spec


class TestLookup:
    def test_exact_key(self):
        assert res.get("numbers").title == "phone numbers"

    def test_unique_prefix_resolves(self):
        assert res.get("num").key == "numbers"
        assert res.get("agent").key == "agents"

    def test_unknown_returns_none(self):
        assert res.get("nonsense") is None

    def test_every_key_is_unique(self):
        keys = [r.key for r in res.RESOURCES]
        assert len(keys) == len(set(keys))

    def test_every_resource_has_a_known_group(self):
        for resource in res.RESOURCES:
            assert resource.group in res.GROUPS

    def test_namespace_present_unless_rest_or_live(self):
        # sdk resources need a dotted namespace; rest resources and the live
        # calls view legitimately have none.
        for r in res.RESOURCES:
            if r.transport == "rest" or r.key == "calls":
                continue
            assert r.namespace, r.key

    def test_paths_derive_from_the_namespace(self):
        numbers = res.get("numbers")
        assert numbers.list_path == "phone_numbers.list"
        assert numbers.create_path == "phone_numbers.create"
        assert numbers.update_path == "phone_numbers.update"
        assert numbers.delete_path == "phone_numbers.delete"

    def test_required_fields_only_where_a_write_exists(self):
        # A required field needs somewhere to be sent: either the resource can
        # create, or it exposes a write action via rest_ops (e911 assign, send).
        for resource in res.RESOURCES:
            if any(f.required for f in resource.fields):
                assert resource.can_create or resource.rest_ops, resource.key


class TestCapabilitiesMatchTheSDK:
    """The registry claims what each namespace supports. Verify against the SDK.

    ``caps`` was produced by introspecting the installed client, so this guards
    against drift when signalwire-sdk is upgraded: a namespace that gains or
    loses an operation should fail here rather than surface as a dead keystroke.
    """

    def sdk_namespaces(self):
        from signalwire.rest import RestClient

        client = RestClient(project="p", token="t", host="example.signalwire.com")
        for resource in res.RESOURCES:
            # rest-transport resources are served by raw REST, not the SDK.
            if resource.transport == "rest" or not resource.namespace:
                continue
            target = client
            for part in resource.namespace.split("."):
                target = getattr(target, part, None)
                if target is None:
                    break
            yield resource, target

    def test_every_namespace_exists_on_the_client(self):
        for resource, target in self.sdk_namespaces():
            assert target is not None, f"{resource.key} -> {resource.namespace}"

    def test_declared_capabilities_are_really_implemented(self):
        ops = {res.LIST: "list", res.CREATE: "create", res.READ: "get",
               res.UPDATE: "update", res.DELETE: "delete"}
        op_names = {res.LIST: "list", res.CREATE: "create", res.READ: "read",
                    res.UPDATE: "update", res.DELETE: "delete"}
        for resource, target in self.sdk_namespaces():
            for letter, method in ops.items():
                if not resource.can(letter):
                    continue
                # A cap the resource serves over REST (e.g. addresses.update,
                # which the SDK lacks) is not required to exist on the SDK.
                if op_names[letter] in resource.rest_ops:
                    continue
                assert callable(getattr(target, method, None)), (
                    f"{resource.key} claims {letter} but {resource.namespace}"
                    f".{method} is missing"
                )

    def test_no_capability_is_silently_missed(self):
        ops = {res.LIST: "list", res.CREATE: "create", res.READ: "get",
               res.UPDATE: "update", res.DELETE: "delete"}
        for resource, target in self.sdk_namespaces():
            for letter, method in ops.items():
                if callable(getattr(target, method, None)):
                    assert resource.can(letter), (
                        f"{resource.namespace}.{method} exists but {resource.key} "
                        f"does not advertise {letter}"
                    )

    def test_extras_reference_real_methods(self):
        for resource, target in self.sdk_namespaces():
            for extra in resource.extras:
                assert callable(getattr(target, extra.method, None)), (
                    f"{resource.key}: {resource.namespace}.{extra.method} missing"
                )


class TestRenamedKeysKeepWorking:
    """Five keys were renamed after the test-plan pass; the old spellings stay
    usable so scripts and muscle memory survive."""

    def test_every_alias_resolves_to_the_renamed_resource(self):
        for old, new in res.KEY_ALIASES.items():
            assert res.get(old) is res.get(new), old
            assert res.get(new).key == new

    def test_no_alias_shadows_a_live_key(self):
        assert set(res.KEY_ALIASES) & set(res.BY_KEY) == set()

    def test_the_new_names_read_as_what_they_are(self):
        assert res.get("datasphere").title == "Datasphere"
        assert res.get("videorooms").title == "video rooms"
        assert res.get("confrooms").title == "conference rooms"
        assert res.get("resources").title == "fabric resources"
        assert res.get("fabricaddresses").title == "fabric addresses"

    def test_exact_key_still_beats_a_prefix_collision(self):
        # `resources` sits next to `recordings` and `relayapps`; the full words
        # resolve exactly, and the shared prefix does not pick `resources`.
        assert res.get("resources").key == "resources"
        assert res.get("recordings").key == "recordings"
        assert res.get("re") is not res.get("resources")


class TestExtrasAreWellFormed:
    """An Extra is a keystroke and, when it takes input, a form. Each of those
    has to be sound before anyone presses it."""

    def test_keys_are_unique_within_a_resource_and_usable_as_widget_ids(self):
        # ContextMenu builds a Button with id "ctx-<key>", and a Textual id
        # cannot start with a digit.
        for r in res.RESOURCES:
            keys = [e.key for e in r.extras]
            assert len(keys) == len(set(keys)), (r.key, keys)
            for key in keys:
                assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key), (r.key, key)

    def test_an_extra_bound_to_a_drill_names_a_sibling_drill(self):
        # "remove member" appears inside the "memberships" drill. If the label
        # it names does not exist there is no screen it can ever appear on.
        for r in res.RESOURCES:
            drills = {e.label for e in r.extras if not e.on_drill}
            for e in r.extras:
                if e.on_drill:
                    assert e.on_drill in drills, (r.key, e.key, e.on_drill)

    def test_form_options_come_from_registered_resources(self):
        for r in res.RESOURCES:
            for e in r.extras:
                for f in e.fields:
                    if f.options_from:
                        source = f.options_from[0].split(".", 1)[0]
                        assert res.get(source) is not None, (r.key, e.key, f.name)
        for f in res.DIAL.fields:
            if f.options_from:
                assert res.get(f.options_from[0].split(".", 1)[0]) is not None

    def test_every_field_an_action_collects_is_one_its_operation_accepts(self):
        # A form field the API does not read is either a typo or a route
        # placeholder. Both are checked against the catalog.
        for r in res.RESOURCES:
            if not r.api:
                continue
            for e in r.extras:
                if not e.fields:
                    continue
                op = spec.get(e.spec_op, api=r.api)
                accepted = {p.name for p in op.params}
                placeholders = set(re.findall(r"\{([^}]+)\}", op.path))
                for f in e.fields:
                    assert f.target in accepted | placeholders, (r.key, e.key, f.target)

    def test_the_dial_form_is_an_extra_that_needs_no_row(self):
        assert isinstance(res.DIAL, res.Extra)
        assert not res.DIAL.needs_id
        assert {f.name for f in res.DIAL.fields} == {"from_", "to", "url", "say"}
        assert [f.name for f in res.DIAL.fields if f.required] == ["from_", "to"]


class TestVerifiedAgainstLiveProject:
    """Values confirmed against a real SignalWire space and its dashboard.

    Each assertion here replaced a wrong guess. They are pinned so a future
    edit cannot quietly reintroduce the guess.
    """

    def test_codecs_match_the_live_sip_form(self):
        assert res.CODECS == (
            "OPUS", "OPUS@48000H@20I", "OPUS@24000H@20I", "OPUS@16000H@20I",
            "OPUS@8000H@20I", "G722", "PCMU", "PCMA", "G729", "VP8", "H264",
        )
        assert "VP9" not in res.CODECS  # guessed once; not offered by the platform

    def test_sip_endpoint_and_gateway_encryption_differ(self):
        """A gateway can forbid encryption; an endpoint can defer to default."""
        assert res.SIP_ENDPOINT_ENCRYPTION == ("default", "required", "optional")
        assert res.SIP_GATEWAY_ENCRYPTION == ("required", "optional", "forbidden")

    def test_a_sip_gateway_needs_encryption_ciphers_and_codecs(self):
        """Probed live on 2026-09-22. `sw gateways create` with only a name and
        a uri — the two the registry marked required — is refused three times
        over: 422 `missing_required_parameter` on encryption, then
        `missing_sip_configuration` naming ciphers, then the same naming
        codecs. `default` is still not a gateway encryption value; the field
        audit's claim that it is comes from the shared enum, not this route.
        """
        fields = {f.name: f for f in res.get("gateways").fields}
        for name in ("encryption", "ciphers", "codecs"):
            assert fields[name].required, name

    def test_what_the_create_routes_actually_require(self):
        """Probed with `scripts/probe_fields.py` on 2026-09-22: each of these
        was declared optional or not at all, and the route answered 422
        `missing_required_parameter` for it.

        The field *audit* over-reports — it reads a shared schema and
        claims `sip` needs three more fields, when a SIP endpoint creates fine
        from a name, a username and a password. Only what the platform refused
        is recorded here.
        """
        required = {
            "relayapps": "name",
            "connectors": "token",
            "datasphere": "url",
            "domains": "identifier",
            "vconf": "display_name",
        }
        for key, name in required.items():
            fields = {f.name: f for f in res.get(key).form_fields("create")}
            assert name in fields, (key, name)
            assert fields[name].required, (key, name)

    def test_a_call_flow_is_created_by_title_not_by_name(self):
        """`{"title": "..."}` alone creates one. `name` was refused with
        `Title is required`, and flow_data/relayml/document_version — which the
        audit calls required — are not."""
        fields = [f.name for f in res.get("flows").form_fields("create")]
        assert "title" in fields
        assert "name" not in fields

    def test_a_video_room_caps_members_not_participants(self):
        """`max_participants=7` was accepted and came back `max_members: 20`,
        the default: the value was taken, dropped, and never mentioned."""
        fields = [f.name for f in res.get("videorooms").form_fields("create")]
        assert "max_members" in fields
        assert "max_participants" not in fields

    def test_a_video_conference_is_sized_not_counted(self):
        """A conference row carries no participant cap at all; `size` is the
        control, and `xlarge` is refused."""
        fields = {f.name: f for f in res.get("vconf").form_fields("create")}
        assert "max_participants" not in fields
        assert fields["size"].choices == res.VIDEO_CONFERENCE_SIZES
        assert res.VIDEO_CONFERENCE_SIZES == ("small", "medium", "large")

    def test_the_sip_profile_is_named_after_what_it_carries(self):
        """It declared `username` and `default_caller_id`; the record has
        neither, so editing either sent a value nowhere and reported success.
        The real caller id is `default_send_as`."""
        fields = {f.name for f in res.get("sipprofile").fields}
        assert "username" not in fields and "default_caller_id" not in fields
        assert {"domain_identifier", "default_send_as", "default_encryption",
                "default_codecs", "default_ciphers"} <= fields

    def test_a_subscriber_really_does_spell_it_time_zone(self):
        """The audit says the documented name is `timezone` and wants this
        changed. The live row carries `time_zone`; the audit is wrong, and this
        is here so nobody 'fixes' it into a field that goes nowhere."""
        fields = {f.name for f in res.get("subscribers").fields}
        assert "time_zone" in fields
        assert "timezone" not in fields

    def test_token_scopes_match_the_live_token_form(self):
        assert set(res.TOKEN_SCOPES) == {
            "calling", "messaging", "video", "fax", "chat", "pubsub", "numbers",
            "storage", "tasking", "datasphere", "management", "fsa",
        }

    def test_phone_number_list_filters_exist_and_match_substrings(self):
        """`sw numbers get +1...` works because the list endpoint filters.

        Probed live: ``filter_number`` and ``filter_name`` both do a
        case-insensitive substring match, and ``filter_number=2095550183``
        finds ``+12095550183`` without the country code. No other list endpoint
        has a verified filter, so none declares one — a filter the API ignores
        would silently return the whole collection and resolve to the wrong row.
        """
        numbers = res.get("numbers")
        assert numbers.lookup == ("number", "name")
        assert numbers.list_filters == {"number": "filter_number", "name": "filter_name"}
        assert all(set(r.list_filters) <= set(r.lookup) for r in res.RESOURCES)

    def test_call_handlers_cover_the_spec_enum_and_the_dashboard(self):
        """Nine of the thirteen handlers were listed; four were on live numbers.

        `relay_sip_endpoint`, `relay_context`, `relay_connector` and
        `relay_verto_endpoint` are all in the spec's enum and were all seen in
        use on this project, but `--set call_handler=relay_sip_endpoint` was
        rejected locally because the choice list was short. `ai_agent` and
        `call_flow` go the other way: the dashboard sets them and the spec does
        not declare them.
        """
        from swsh import spec

        operation = spec.get("update_phone_number", api="relay-rest")
        documented = next(p for p in operation.params if p.name == "call_handler")
        assert set(documented.enum) <= set(res.CALL_HANDLERS)
        for seen_live in ("relay_sip_endpoint", "relay_context", "call_flow", "ai_agent"):
            assert seen_live in res.CALL_HANDLERS, seen_live

    def test_every_handler_that_reads_a_field_declares_it(self):
        """`get --full` splits a row by `show_if`, so a handler with no field
        declared shows an empty channel and its pointer as "not in use"."""
        numbers = res.get("numbers")
        declared = {f.show_if[0]: set() for f in numbers.fields if f.show_if}
        for f in numbers.fields:
            if f.show_if:
                declared[f.show_if[0]].update(f.show_if[1])
        # Handlers that genuinely read nothing but the resource they point at.
        points_only = {"ai_agent", "call_flow", "dialogflow", "relay_application"}
        for handler in res.CALL_HANDLERS:
            if handler in points_only:
                continue
            assert handler in declared["call_handler"], handler

    def test_relay_application_uses_topic_not_reference(self):
        """The dashboard's form field is `reference`; the REST API rejects it
        and asks for `topic`. The API wins: that is what swsh calls."""
        names = {f.name for f in res.get("relayapps").fields}
        assert "topic" in names
        assert "reference" not in names

    def test_script_document_field_is_contents(self):
        """Same divergence: the dashboard posts `call_handler_script`, the REST
        API validates on `contents`."""
        for key in ("swml", "cxml"):
            names = {f.name for f in res.get(key).fields}
            assert "contents" in names, key
            assert "call_handler_script" not in names, key

    def test_hosted_scripts_offer_no_url_field(self):
        """A hosted script is served by SignalWire, which mints the URL. An
        endpoint you host is a different resource entirely."""
        for key in ("swml", "cxml"):
            names = {f.name for f in res.get(key).fields}
            assert not any(
                "request_url" in n or (n.endswith("_url") and "status" not in n)
                for n in names
            ), key
        assert "primary_request_url" in {f.name for f in res.get("swmlhooks").fields}

    def test_number_handler_fields_are_conditional(self):
        """Showing every companion field at once invites sending the wrong one."""
        fields = {f.name: f for f in res.get("numbers").fields}
        assert fields["call_request_url"].show_if == ("call_handler", ("laml_webhooks",))
        assert fields["call_relay_topic"].show_if == ("call_handler", ("relay_topic",))
        assert fields["calling_handler_resource_id"].show_if == (
            "call_handler", ("ai_agent", "call_flow", "video_room")
        )

    def test_visibility_evaluates_against_current_values(self):
        fields = {f.name: f for f in res.get("numbers").fields}
        url = fields["call_request_url"]
        assert url.visible_for({"call_handler": "laml_webhooks"})
        assert not url.visible_for({"call_handler": "ai_agent"})
        assert not url.visible_for({})

    def test_subscriber_detail_is_read_from_a_nested_object(self):
        email = next(f for f in res.get("subscribers").fields if f.name == "email")
        assert email.source == "subscriber.email"  # list response nests it
        assert email.target == "email"             # create takes it flat

    def test_phone_numbers_have_no_ai_agent_or_flow_id_field(self):
        """The read model routes those handlers via calling_handler_resource_id."""
        names = {f.name for f in res.get("numbers").fields}
        assert "call_ai_agent_id" not in names
        assert "call_flow_id" not in names
        assert "calling_handler_resource_id" in names

    def test_brand_fields_match_the_live_payload(self):
        names = {f.name for f in res.get("brands").fields}
        assert {"name", "contact_email", "legal_entity_type", "ein"} <= names
        assert not names & {"display_name", "entity_type", "email", "phone", "website"}


class TestRewriteFields:
    """The routing table in `sw listen`, taken from a live number payload."""

    def test_routing_fields_match_the_live_read_model(self):
        from swsh.events.rewrite import ROUTING_FIELDS

        assert "calling_handler_resource_id" in ROUTING_FIELDS
        assert "call_relay_context_status_callback_url" in ROUTING_FIELDS
        # These do not exist on a phone number payload.
        assert "call_ai_agent_id" not in ROUTING_FIELDS
        assert "call_flow_id" not in ROUTING_FIELDS

    def test_relay_context_has_its_own_callback_field(self):
        """Pointing it at the topic field would write, then 'restore', the
        wrong key."""
        from swsh.events.rewrite import STATUS_FIELD_BY_HANDLER

        assert STATUS_FIELD_BY_HANDLER["relay_context"] == (
            "call_relay_context_status_callback_url"
        )
        assert STATUS_FIELD_BY_HANDLER["relay_topic"] == (
            "call_relay_topic_status_callback_url"
        )

    def test_every_status_field_is_a_known_routing_field(self):
        from swsh.events.rewrite import ROUTING_FIELDS, STATUS_FIELD_BY_HANDLER

        for handler, field_name in STATUS_FIELD_BY_HANDLER.items():
            if field_name is not None:
                assert field_name in ROUTING_FIELDS, handler


class TestNoDestructiveProbe:
    def test_client_has_no_encoding_probe_that_creates_resources(self):
        """The old probe created and deleted a LaML bin to discover the
        encoding. A check must not change the project it checks, and both
        encodings are accepted, so the probe is gone for good."""
        from swsh.client import SwshClient

        assert not hasattr(SwshClient, "probe_compat_encoding")
        assert hasattr(SwshClient, "verify_compat")


class TestFormBodies:
    def test_text_and_int_coercion(self):
        assert res.coerce(res.Field("n", kind="int"), "42") == 42
        assert res.coerce(res.Field("n"), " hi ") == "hi"

    def test_blank_means_unset_not_empty_string(self):
        """A partial edit must not blank fields the user never touched."""
        assert res.coerce(res.Field("n"), "   ") is None

    def test_bool_accepts_common_spellings(self):
        for text in ("true", "yes", "1", "on", "Y"):
            assert res.coerce(res.Field("b", kind="bool"), text) is True
        assert res.coerce(res.Field("b", kind="bool"), "no") is False

    def test_code_field_parses_json_documents(self):
        assert res.coerce(res.Field("j", kind="code"), '{"a": 1}') == {"a": 1}

    def test_bad_document_is_reported_not_swallowed(self):
        import pytest

        with pytest.raises(ValueError, match="not valid JSON"):
            res.coerce(res.Field("j", kind="code"), "{nope}")

    def test_non_json_document_stays_text(self):
        field_def = res.Field("contents", kind="code", language="xml")
        assert res.coerce(field_def, "<Response/>") == "<Response/>"

    def test_list_field_splits_and_trims(self):
        assert res.coerce(res.Field("t", kind="list"), " a, b ,c ") == ["a", "b", "c"]

    def test_list_field_accepts_an_actual_list(self):
        assert res.coerce(res.Field("t", kind="multi"), ["x", "y"]) == ["x", "y"]

    def test_empty_selection_is_unset_rather_than_an_empty_list(self):
        """Omitting beats clearing: an untouched group must not wipe the field."""
        assert res.coerce(res.Field("t", kind="multi"), []) is None
        assert res.coerce(res.Field("t", kind="list"), "  ") is None

    def test_checkbox_false_is_a_real_value(self):
        assert res.coerce(res.Field("b", kind="bool"), False) is False
        assert res.coerce(res.Field("b", kind="bool"), True) is True

    def test_nested_path_builds_a_nested_body(self):
        resource = res.get("agents")
        body = res.build_body(resource, "create",
                              {"name": "Support", "prompt_text": "Be helpful."})
        assert body == {"name": "Support", "prompt": {"text": "Be helpful."}}

    def test_two_fields_can_share_a_nested_parent(self):
        field_a = res.Field("a", path="outer.a")
        field_b = res.Field("b", path="outer.b")
        resource = res.Resource(key="t", title="t", namespace="n", caps="C",
                                fields=(field_a, field_b))
        body = res.build_body(resource, "create", {"a": "1", "b": "2"})
        assert body == {"outer": {"a": "1", "b": "2"}}

    def test_unflatten_reads_nested_values_back(self):
        resource = res.get("agents")
        row = {"id": "a-1", "name": "Support", "prompt": {"text": "Be helpful."}}
        assert res.unflatten(resource, row, "update") == {
            "name": "Support", "prompt_text": "Be helpful."
        }

    def test_unflatten_reaches_fabric_wrapped_fields(self):
        # A Fabric list row nests the type's fields under its type key, while
        # the form declares them at the top level. Editing must still see them.
        resource = res.get("swml")
        row = {"id": "s-1", "display_name": "ivr", "created_at": "2026-01-01",
               "swml_script": {"contents": '{"version": "1.0.0"}',
                               "status_callback_url": "https://x.invalid/cb"}}
        flat = res.unflatten(resource, row, "update")
        assert flat["contents"] == '{"version": "1.0.0"}'
        assert flat["status_callback_url"] == "https://x.invalid/cb"

    def test_unflatten_prefers_the_declared_path_over_a_nested_copy(self):
        resource = res.get("swml")
        row = {"id": "s-1", "name": "top", "swml_script": {"name": "nested"}}
        assert res.unflatten(resource, row, "update")["name"] == "top"

    def test_unflatten_tolerates_a_missing_branch(self):
        resource = res.get("agents")
        assert res.unflatten(resource, {"name": "Support"}, "update") == {"name": "Support"}

    def test_field_problems_are_reported_together(self):
        import pytest

        resource = res.get("queues")
        with pytest.raises(ValueError, match="whole number"):
            res.build_body(resource, "create", {"name": "q", "max_size": "lots"})

    def test_open_ended_groups_only_where_the_option_list_may_be_short(self):
        for resource in res.RESOURCES:
            for field_def in resource.fields:
                if field_def.open_ended:
                    assert field_def.kind == "multi", (resource.key, field_def.name)
                if field_def.kind in ("choice", "multi"):
                    # A choice either ships a fixed list or loads one live.
                    assert field_def.choices or field_def.options_from, (
                        resource.key, field_def.name
                    )
                if field_def.options_from:
                    assert field_def.kind == "choice", (resource.key, field_def.name)
                    assert len(field_def.options_from) == 3, field_def.name

    def test_bad_int_is_reported(self):
        import pytest

        with pytest.raises(ValueError, match="whole number"):
            res.coerce(res.Field("n", kind="int"), "abc")

    def test_build_body_drops_unset_fields(self):
        resource = res.get("queues")
        body = res.build_body(resource, "create", {"name": "support", "max_size": ""})
        assert body == {"name": "support"}

    def test_build_body_enforces_required_on_create(self):
        import pytest

        with pytest.raises(ValueError, match="required"):
            res.build_body(res.get("queues"), "create", {"name": ""})

    def test_update_does_not_demand_required_fields(self):
        """Editing one field should not force resending every required one."""
        body = res.build_body(res.get("queues"), "update", {"name": "", "max_size": "50"})
        assert body == {"max_size": 50}

    def test_create_only_fields_are_excluded_from_update(self):
        numbers = res.get("numbers")
        assert "number" in {f.name for f in numbers.form_fields("create")}
        assert "number" not in {f.name for f in numbers.form_fields("update")}


class TestUnwrap:
    def test_data_envelope(self):
        assert res.unwrap({"data": [{"id": 1}, {"id": 2}]}) == [{"id": 1}, {"id": 2}]

    def test_bare_list(self):
        assert res.unwrap([{"id": 1}]) == [{"id": 1}]

    def test_laml_style_named_collection(self):
        """LaML names the collection after the resource, not 'data'."""
        assert res.unwrap({"calls": [{"sid": "CA1"}], "page": 0}) == [{"sid": "CA1"}]

    def test_alternate_keys(self):
        assert res.unwrap({"items": [{"id": 1}]}) == [{"id": 1}]
        assert res.unwrap({"results": [{"id": 1}]}) == [{"id": 1}]

    def test_single_object_becomes_one_row(self):
        assert res.unwrap({"id": "x", "name": "y"}) == [{"id": "x", "name": "y"}]

    def test_empty_inputs(self):
        assert res.unwrap(None) == []
        assert res.unwrap({}) == []
        assert res.unwrap([]) == []

    def test_non_dict_entries_are_dropped(self):
        assert res.unwrap({"data": [{"id": 1}, "junk", None]}) == [{"id": 1}]

    def test_ambiguous_multiple_lists_falls_through(self):
        """Two list-valued keys is not enough to guess, so treat it as one row."""
        payload = {"calls": [{"sid": "CA1"}], "errors": [{"m": "x"}]}
        assert res.unwrap(payload) == [payload]


class TestColumns:
    def test_preferred_columns_when_present(self):
        resource = res.get("numbers")
        rows = [{"number": "+1555", "name": "main", "call_handler": "ai_agent", "id": "x"}]
        assert res.columns_for(resource, rows)[:2] == ["number", "name"]

    def test_falls_back_to_discovered_keys_when_guesses_miss(self):
        """The whole point: a wrong field-name guess still renders a table."""
        resource = res.get("agents")
        rows = [{"uuid": "a", "label": "Support", "nested": {"x": 1}}]
        columns = res.columns_for(resource, rows)
        assert columns
        assert "uuid" in columns
        assert "nested" not in columns  # nested objects make poor columns

    def test_partial_match_keeps_only_present_fields(self):
        resource = res.get("numbers")
        rows = [{"number": "+1555", "id": "x"}]
        assert res.columns_for(resource, rows) == ["number", "id"]

    def test_a_null_value_keeps_its_column(self):
        # `sw get numbers -n 1` drew number/call_handler/id while the full list
        # drew five columns, because the one row on the page had a null name
        # and callback URL. The key is there; the value is just empty.
        resource = res.get("numbers")
        full = [
            {"number": "+1555", "name": None, "call_handler": "laml_webhooks",
             "id": "a", "created_at": None},
            {"number": "+1556", "name": "main", "call_handler": "relay_script",
             "id": "b", "created_at": "2026-01-01T00:00:00Z"},
        ]
        assert res.columns_for(resource, full[:1]) == res.columns_for(resource, full)
        assert res.columns_for(resource, full[:1]) == [
            "number", "name", "call_handler", "id", "created_at"
        ]

    def test_has_key_follows_dots_and_distinguishes_null_from_absent(self):
        row = {"id": "x", "name": None, "sip_endpoint": {"username": None}}
        assert res.has_key(row, "name")
        assert res.has_key(row, "sip_endpoint.username")
        assert not res.has_key(row, "created_at")
        assert not res.has_key(row, "sip_endpoint.send_as")
        assert not res.has_key(row, "id.deeper")

    def test_empty_rows_use_the_preference(self):
        assert res.columns_for(res.get("numbers"), [])[0] == "number"

    def test_column_count_is_bounded(self):
        rows = [{f"f{i}": i for i in range(30)}]
        assert len(res.columns_for(res.get("agents"), rows)) <= 7

    def test_id_sorts_first_when_discovering(self):
        rows = [{"zeta": 1, "id": "x", "alpha": 2}]
        assert res.columns_for(res.get("agents"), rows)[0] == "id"

    def test_cell_follows_dotted_paths_and_tolerates_gaps(self):
        row = {"id": "x", "sip_endpoint": {"username": "deskphone"}}
        assert res.cell(row, "id") == "x"
        assert res.cell(row, "sip_endpoint.username") == "deskphone"
        assert res.cell(row, "sip_endpoint.missing") is None
        assert res.cell(row, "nothing.here") is None
        assert res.cell({"sip_endpoint": "flat"}, "sip_endpoint.username") is None

    def test_fabric_rows_show_the_nested_name_not_a_lone_id(self):
        # The shape every Fabric list returns, verified live: the type's own
        # fields sit one level down. `sw get sip` used to render only `id`.
        rows = [{"id": "ep-1", "display_name": "deskphone", "created_at": "2026-07-17T20:06:29Z",
                 "sip_endpoint": {"username": "deskphone", "send_as": "+15550100001"}}]
        columns = res.columns_for(res.get("sip"), rows)
        assert columns == ["id", "display_name", "sip_endpoint.username",
                           "sip_endpoint.send_as", "created_at"]

    def test_only_identifiers_matching_is_padded_with_discovered_fields(self):
        # A table of bare ids is what the test-plan pass called useless.
        rows = [{"id": "q-1", "friendly_name": "support", "max_size": 5,
                 "date_created": "2026-09-09T19:51:06Z", "uri": "/x"}]
        stale = res.Resource(key="stale", title="stale", namespace="", caps="L",
                             columns=("id", "name", "created_at"))
        columns = res.columns_for(stale, rows)
        assert columns[0] == "id"
        assert "friendly_name" in columns and "max_size" in columns
        assert "name" not in columns

    def test_queue_and_recording_columns_match_the_live_shapes(self):
        queue = {"id": "q", "friendly_name": "support", "current_size": 0, "max_size": 5,
                 "average_wait_time": 0, "date_created": "2026-09-09T19:51:06Z"}
        assert res.columns_for(res.get("queues"), [queue])[:2] == ["id", "friendly_name"]
        recording = {"id": "r", "status": "completed", "duration_in_seconds": 12,
                     "relay_pstn_leg_id": "leg", "created_at": "2026-08-13T15:50:16Z"}
        assert "status" in res.columns_for(res.get("recordings"), [recording])


class TestRestTransportIsComplete:
    """After the SDK-to-REST migration, the registry is the only route source.

    These are the invariants that make that safe. They catch the two failure
    modes the migration can produce: an operation id that does not resolve, and
    a capability letter the resource cannot actually perform.
    """

    def test_every_rest_op_resolves_to_a_real_operation(self):
        for r in res.RESOURCES:
            if r.transport != "rest":
                continue
            for op, operation_id in r.rest_ops.items():
                assert spec.get(operation_id, api=r.api) is not None, (
                    f"{r.key}.{op} -> {r.api}:{operation_id} does not resolve"
                )

    def test_every_capability_letter_has_a_route(self):
        # caps drives which verbs the CLI offers and which TUI buttons enable.
        # A letter with no route is a command that fails when someone presses it.
        for r in res.RESOURCES:
            if r.transport != "rest":
                continue
            for op, letter in (("list", "L"), ("create", "C"), ("read", "R"),
                               ("update", "U"), ("delete", "D")):
                if letter in r.caps:
                    assert op in r.rest_ops, f"{r.key} caps has {letter} but no '{op}' route"

    def test_no_rest_route_has_a_duplicate_placeholder(self):
        # The catalog's parent-route extraction bug produced
        # /api/fabric/{id}/addresses/{id}. Repaired in spec._ROUTE_FIXES; this
        # keeps a regeneration from reintroducing it through a live resource.
        for r in res.RESOURCES:
            if r.transport != "rest":
                continue
            for op, operation_id in r.rest_ops.items():
                op_def = spec.get(operation_id, api=r.api)
                names = re.findall(r"\{([^}]+)\}", op_def.path)
                assert len(names) == len(set(names)), f"{r.key}.{op} -> {op_def.path}"

    def test_every_extra_on_a_rest_resource_resolves(self):
        # An Extra carries the SDK method name in `method` and the spec id in
        # `spec_op`. Migrating a resource to rest makes `spec_op` load-bearing,
        # and a drill with neither a resolvable spec_op nor a matching rest_op is
        # a keystroke that raises. This is what the migration broke first.
        for r in res.RESOURCES:
            if r.transport != "rest":
                continue
            for extra in r.extras:
                operation_id = r.rest_ops.get(extra.method) or extra.spec_op or extra.method
                assert spec.get(operation_id, api=r.api) is not None, (
                    f"{r.key} extra '{extra.key}' ({extra.method}) -> "
                    f"{r.api}:{operation_id} does not resolve"
                )

    def test_only_the_documented_resources_remain_on_the_sdk(self):
        # calls is a live view with no namespace; cxmlapps keeps an SDK-only
        # create the spec does not declare. Anything else is an oversight.
        remaining = {r.key for r in res.RESOURCES if r.transport == "sdk"}
        assert remaining == {"calls", "cxmlapps"}


class TestEveryResourceCanBeReachedFromItsOwnScreen:
    """What the browser may offer an item, derived from the routes.

    `standalone` is read from the spec catalog, not declared: a resource whose
    every route needs an id it has no way to obtain cannot have a screen. That
    is the fact the TUI's menus, footer and action bar all read, so it has to
    stay true as resources are added.
    """

    def test_a_drill_only_resource_names_the_parent_it_lives_under(self):
        for r in res.RESOURCES:
            if r.key == "calls":  # a live view, not a namespace; own menu button
                continue
            assert bool(r.drill_from) == (not r.standalone), r.key

    def test_the_named_parent_exists_and_actually_drills_to_it(self):
        """Follow the chain to a screen, rather than demanding one hop.

        `brands > campaigns > orders` is three deep, because the routes are:
        a campaign needs a brand and an order needs a campaign. Requiring the
        immediate parent to be standalone said that hierarchy was illegal,
        which is how `orders` ended up standalone with a `list` route it could
        never call.
        """
        for r in res.RESOURCES:
            if not r.drill_from:
                continue
            seen: list[str] = []
            node = r
            while node.drill_from:
                assert node.drill_from not in seen, (r.key, "cycle", seen)
                seen.append(node.drill_from)
                parent = res.get(node.drill_from)
                assert parent is not None, (r.key, node.drill_from)
                # each hop has to offer a drill, or the child is unreachable
                drills = [e for e in parent.extras
                          if spec.get(e.spec_op, parent.api)
                          and spec.get(e.spec_op, parent.api).method == "GET"]
                assert drills, (r.key, node.drill_from)
                node = parent
            assert node.standalone, (r.key, "chain ends nowhere", seen)

    def test_a_singleton_reads_without_an_identifier(self):
        singletons = [r for r in res.RESOURCES if r.is_singleton]
        assert [r.key for r in singletons] == ["sipprofile"]
        for r in singletons:
            assert not r.can_list
            assert not res.route_placeholders(r.rest_ops["read"], r.api)

    def test_an_action_screen_collects_every_id_its_route_needs(self):
        # mfa, subtokens and lookup are reached with nothing selected, so each
        # of their actions has to supply its own route placeholders from the
        # form. A missing field would be a keystroke that 404s.
        for key in ("mfa", "subtokens", "lookup"):
            r = res.get(key)
            assert not r.can_list and r.standalone, key
            assert any(r.serves_itself(e) for e in r.extras), key

    def test_route_placeholders_ignores_the_account_the_client_fills_in(self):
        # Every compatibility route carries {AccountSid}, and it comes from the
        # profile rather than from the screen. Counting it would make all 75 of
        # them look like they needed an id nobody could supply. No registry
        # resource is on that surface today — `sw api` covers it — so this
        # checks the rule at the source.
        compat = spec.get("create_a_call", "compatibility-api")
        assert compat is not None and "{AccountSid}" in compat.path
        assert res.route_placeholders("create_a_call", "compatibility-api") == ()
