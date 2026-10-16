"""The coverage gate — completeness as a checked invariant.

Asserts every spec operation is covered, excluded, or backlog; that the three
partition the surface exactly; and that coverage only ratchets up. When a build
step lands a screen, its operations move to covered and MIN_COVERED is raised;
this test fails if coverage regresses or if the partition ever develops a hole.
"""

from __future__ import annotations

from swsh import coverage, spec


class TestPartition:
    def test_three_buckets_partition_the_surface_exactly(self):
        covered = coverage.covered_keys()
        excluded = set(coverage.excluded())
        backlog = coverage.not_yet()
        allkeys = spec.keys()

        assert covered | excluded | backlog == allkeys
        assert covered.isdisjoint(excluded)
        assert covered.isdisjoint(backlog)
        assert excluded.isdisjoint(backlog)

    def test_every_bucket_key_is_a_real_operation(self):
        allkeys = spec.keys()
        for bucket in (coverage.covered_keys(), set(coverage.excluded()), coverage.not_yet()):
            assert bucket <= allkeys


class TestRatchet:
    def test_coverage_only_grows(self):
        assert len(coverage.covered_keys()) >= coverage.MIN_COVERED

    def test_ratchet_is_not_stale(self):
        # If this fails high, someone added coverage without raising the ratchet;
        # raise MIN_COVERED to lock the gain in.
        assert len(coverage.covered_keys()) <= coverage.MIN_COVERED + 15


class TestExclusions:
    def test_exclusions_are_only_the_known_categories(self):
        # compat, dialogflow, imperative calling, and the Fabric-superseded
        # relay-rest SIP endpoints — each with a stated reason.
        for key, reason in coverage.excluded().items():
            api = key.split(":", 1)[0]
            allowed = (
                api in ("compatibility-api", "calling-api")
                or "dialogflow" in key
                or (key.startswith("relay-rest:") and "sip_endpoint" in key)
            )
            assert allowed, key
            assert reason

    def test_compat_is_fully_excluded(self):
        compat = {op.key for op in spec.by_api("compatibility-api")}
        assert compat <= set(coverage.excluded())


class TestCoverageIsDerivedFromTheRegistry:
    """Coverage has one source: the operation ids resources actually name.

    There used to be a second map here (resource key -> spec interface route)
    granting CRUD credit by matching interface and verb name. Two sources could
    disagree, and the interface-matching one silently broke when the catalog
    started carrying exact paths. These tests pin the single-source property.
    """

    def test_every_credited_operation_is_reachable_by_a_verb_or_a_keystroke(self):
        # Covered means a person can get there: a CRUD verb in rest_ops (sw
        # get/create/update/delete, the TUI's list/n/e/d) or an Extra (x).
        from swsh import resources as res

        reachable = set()
        for r in res.RESOURCES:
            if not r.api:
                continue
            crud = [r.rest_ops[op] for op in coverage.CRUD_OPS if op in r.rest_ops]
            for op_id in crud + [e.spec_op for e in r.extras if e.spec_op]:
                hit = spec.get(op_id, api=r.api)
                if hit:
                    reachable.add(hit.key)
        assert coverage.covered_keys() == reachable

    def test_rest_ops_hold_only_crud_verbs(self):
        # The loophole this closes: an op filed under any other key in rest_ops
        # counted as covered while nothing in the CLI or TUI could reach it.
        # Anything beyond CRUD is an Extra, which `x` reaches.
        from swsh import resources as res

        strays = [(r.key, op) for r in res.RESOURCES
                  for op in r.rest_ops if op not in coverage.CRUD_OPS]
        assert strays == []

    def test_the_formerly_unreachable_actions_are_extras_now(self):
        from swsh import resources as res

        by_extra = {spec.get(e.spec_op, api=r.api).key
                    for r in res.RESOURCES if r.api
                    for e in r.extras if e.spec_op}
        for key in (
            "relay-rest:assign_e911_address", "relay-rest:remove_e911_address",
            "relay-rest:request_mfa_call", "relay-rest:request_mfa_sms",
            "relay-rest:verify_mfa_token",
            "relay-rest:create_number_group_membership",
            "relay-rest:delete_number_group_membership",
            "relay-rest:retrieve_number_group_membership",
            "relay-rest:delete_number_assignment",
            "fabric-api:create_subscriber_guest_token",
            "fabric-api:create_subscriber_invite_token",
            "fabric-api:refresh_subscriber_token", "fabric-api:create_guest_embed_token",
            "fabric-api:list_resource_addresses",
            "fabric-api:assign_resource_domain_application",
            "fabric-api:assign_resource_phone_route",
            "fabric-api:assign_resource_to_sip_credential",
            "video-api:create_room_stream", "video-api:create_room_token",
            "video-api:get_room_by_name", "video-api:list_room_session_events",
            "video-api:list_room_recording_events",
            "video-api:create_conference_stream", "video-api:list_conference_streams",
            "video-api:list_conference_tokens", "video-api:get_conference_token",
            "video-api:reset_conference_token",
        ):
            assert key in by_extra, key
            assert key in coverage.covered_keys(), key

    def test_core_crud_resources_are_covered(self):
        # A spot check that the derivation actually credits the everyday surface.
        for key in ("fabric-api:list_subscribers", "fabric-api:create_ai_agent",
                    "relay-rest:list_phone_numbers", "relay-rest:create_address",
                    "video-api:list_rooms", "datasphere-api:list_documents"):
            assert key in coverage.covered_keys(), key


class TestFullParity:
    def test_every_backlog_entry_is_declared_with_a_reason(self):
        # The backlog is allowed to be non-empty — regenerating the catalog
        # against newer specs is how new operations arrive. What is not allowed
        # is an entry nobody decided about, so each one must be declared.
        undeclared = coverage.not_yet() - set(coverage.BACKLOG)
        assert undeclared == set(), f"backlog entries with no reason: {undeclared}"
        for key, reason in coverage.BACKLOG.items():
            assert reason.strip(), f"{key} has an empty reason"

    def test_backlog_only_shrinks(self):
        assert len(coverage.not_yet()) <= coverage.MAX_BACKLOG

    def test_declared_backlog_entries_are_real_operations(self):
        for key in coverage.BACKLOG:
            assert key in spec.keys(), f"{key} is not a real operation"

    def test_the_formerly_missing_surfaces_are_now_covered(self):
        covered = coverage.covered_keys()
        for key in ("relay-rest:assign_e911_address",
                    "relay-rest:remove_e911_address",
                    "message-api:list_whatsapp_numbers",
                    "message-api:create_whatsapp_template",
                    "message-api:create_message",
                    "relay-rest:list_campaigns",
                    "projects-api:rotate_signing_key",
                    "relay-rest:lookup_phone_number"):
            assert key in covered, key

    def test_backlog_count_matches_partition(self):
        assert len(coverage.not_yet()) == sum(
            len(v) for v in coverage.backlog_by_api().values()
        )
