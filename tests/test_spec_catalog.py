"""The spec catalog is swsh's baseline of the authoritative API surface.

These tests pin what the generator produced so a regeneration that drops or
mangles operations fails loudly, and assert the specific operations swsh's
coverage depends on (e911, whatsapp, the CRUD verbs) are present and correctly
shaped.
"""

from __future__ import annotations

import re

from swsh import spec


class TestBaseline:
    def test_total_matches_the_known_surface(self):
        # 332 operations across 15 APIs, from the compiled OpenAPI. This was 331
        # across 14; regenerating against the current specs added exactly one
        # callable operation, ai-api:chat_methods, and removed none.
        assert spec.total() == 332
        assert len(spec.operations()) == 332

    def test_every_expected_api_is_present(self):
        expected = {
            "ai-api", "calling-api", "chat-api", "compatibility-api",
            "datasphere-api", "fabric-api", "fax-api", "logs-api", "message-api",
            "project-api", "projects-api", "pubsub-api", "relay-rest",
            "video-api", "voice-api",
        }
        assert set(spec.apis()) == expected

    def test_inbound_callbacks_are_not_in_the_catalog(self):
        # The specs also declare webhooks — things the platform POSTs *to you*.
        # They are not callable, so the generator filters them out; without that
        # they inflate the surface with operations that can be neither covered
        # nor sensibly excluded.
        assert "webhooks" not in spec.apis()
        assert "emitters" not in spec.apis()
        # Named individually: a `_webhook` suffix is not the tell, because
        # cxml_webhooks and swml_webhooks are real, callable Fabric resources.
        ids = {op.operation_id for op in spec.operations()}
        for callback in ("ai_debug_webhook", "inbound_call_webhook",
                         "sms_status_callback", "voice_status_callback",
                         "ai_post_prompt_callback", "message_status_callback"):
            assert callback not in ids, callback

    def test_fabric_is_the_largest_surface(self):
        counts = {a: m["operations"] for a, m in spec.apis().items()}
        assert counts["fabric-api"] == 108
        assert counts["relay-rest"] == 72
        assert counts["compatibility-api"] == 79

    def test_operation_keys_are_unique(self):
        # operation_id alone is NOT unique — it collides across APIs
        # (create_message is in compat and message-api). The api:op key is.
        keys = [op.key for op in spec.operations()]
        assert len(keys) == len(set(keys)) == 332

    def test_operation_ids_do_collide_across_apis(self):
        # Pin the collision so the api-qualified key stays necessary.
        ids = [op.operation_id for op in spec.operations()]
        assert len(set(ids)) < len(ids)
        assert spec.get("create_message") is None  # ambiguous -> must qualify
        assert spec.get("create_message", api="message-api").method == "POST"

    def test_every_api_has_a_base_route(self):
        for api, meta in spec.apis().items():
            assert meta["base_route"].startswith("/api/"), api


class TestBasePaths:
    def test_known_base_paths(self):
        bases = {a: m["base_route"] for a, m in spec.apis().items()}
        assert bases["fabric-api"] == "/api/fabric"
        assert bases["relay-rest"] == "/api/relay/rest"
        assert bases["message-api"] == "/api/messaging"
        assert bases["video-api"] == "/api/video"
        # compat's base comes from its @server URL, not an @route
        assert bases["compatibility-api"] == "/api/laml/2010-04-01"


class TestExactRoutes:
    """The catalog is generated from compiled OpenAPI, so routes are exact.

    The previous generator regex-scraped TypeSpec and got 41 paths and 2 methods
    wrong, because `@operationId` and the verb decorator appear in either order
    and interface routes are declared relative to a parent. These pin the cases
    that were actually wrong.
    """

    def test_e911_operations_are_correct(self):
        assign = spec.get("assign_e911_address", api="relay-rest")
        assert assign.method == "POST"
        assert assign.path == "/api/relay/rest/phone_numbers/{id}/e911_address"
        create = spec.get("create_address", api="relay-rest")
        assert create.method == "POST"
        assert create.path == "/api/relay/rest/addresses"

    def test_the_json_rpc_endpoints_are_post_not_get(self):
        # Both were GET in the regex-built catalog. A GET would simply not work.
        assert spec.get("call-commands", api="calling-api").method == "POST"
        assert spec.get("call-commands", api="calling-api").path == "/api/calling/calls"
        assert spec.get("chat_methods", api="ai-api").method == "POST"
        assert spec.get("chat_methods", api="ai-api").path == "/api/ai/chat"

    def test_the_campaign_registry_carries_its_beta_prefix(self):
        # The 10DLC surface lives under /registry/beta. The old catalog dropped
        # it, so every brand and campaign call went to a path that does not exist.
        for oid in ("list_brands", "create_brand", "list_campaigns", "retrieve_order"):
            op = spec.get(oid, api="relay-rest")
            assert "/registry/beta/" in op.path, f"{oid} -> {op.path}"

    def test_sip_profile_is_a_singleton(self):
        # Not /sip_profile/{id}: the project has exactly one.
        for oid in ("retrieve_sip_profile", "update_sip_profile"):
            assert spec.get(oid, api="relay-rest").path == "/api/relay/rest/sip_profile"

    def test_subscriber_sub_resources_keep_their_collection_prefix(self):
        op = spec.get("list_subscriber_sip_credentials", api="fabric-api")
        assert op.path == (
            "/api/fabric/resources/subscribers/{fabric_subscriber_id}/sip_endpoints"
        )

    def test_no_path_has_a_duplicate_placeholder(self):
        for op in spec.operations():
            names = re.findall(r"\{([^}]+)\}", op.path)
            assert len(names) == len(set(names)), f"{op.key} -> {op.path}"

    def test_every_path_starts_at_its_api_base(self):
        for op in spec.operations():
            assert op.path.startswith(op.base_route), f"{op.key} -> {op.path}"


class TestRequestParameters:
    """The catalog now carries request parameters, which is what the field audit
    checks registry `Field` definitions against."""

    def test_e911_create_declares_its_nine_required_parameters(self):
        op = spec.get("create_address", api="relay-rest")
        required = {p.name for p in op.required_params}
        assert required == {
            "label", "country", "first_name", "last_name", "street_number",
            "street_name", "city", "state", "postal_code",
        }

    def test_optional_parameters_carry_defaults(self):
        op = spec.get("create_address", api="relay-rest")
        by_name = {p.name: p for p in op.params}
        assert by_name["emergency_enabled"].default is False
        assert by_name["auto_correct_address"].default is True

    def test_enumerated_values_are_captured(self):
        op = spec.get("create_address", api="relay-rest")
        by_name = {p.name: p for p in op.params}
        assert "Suite" in by_name["address_type"].enum

    def test_a_meaningful_number_of_operations_have_parameters(self):
        with_params = [op for op in spec.operations() if op.params]
        assert len(with_params) >= 100


class TestLookups:
    def test_get_returns_none_for_unknown(self):
        assert spec.get("no_such_operation") is None

    def test_by_api_partitions_cleanly(self):
        assert sum(len(spec.by_api(a)) for a in spec.apis()) == spec.total()


