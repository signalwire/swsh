"""The command tree is noun-first and generated from the registry.

`sw numbers list`, `sw swml delete <id>`, `sw numbers assign-e911-address <id>`.
There is one path to each operation: no verb-first `sw get numbers`, and no
alias groups. These tests pin the shape so a registry change cannot silently
drop a command, and so nobody reintroduces the second spelling.
"""

from __future__ import annotations

import json

import pytest
import typer
from typer.testing import CliRunner

from swsh import cli, resources

runner = CliRunner()

# Phone number ids are uuids on the platform, and sw now reads that shape to
# decide whether an identifier is an id or a handle to resolve. A stand-in has
# to look like the real thing or these tests exercise the wrong path;
# TestIdentifiersAndMatching is where the handle path is pinned.
PN1 = "aaaaaaaa-0000-4000-8000-0000000000a1"
PN2 = "aaaaaaaa-0000-4000-8000-0000000000a2"


@pytest.fixture(autouse=True)
def never_touch_the_real_config(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.config, "config_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cli.config, "load_dotenv", lambda path=None: {})
    monkeypatch.setattr(cli.config, "_keyring_set", lambda *a, **k: False)
    monkeypatch.setattr(cli.config, "_keyring_get", lambda *a, **k: None)
    for var in ("SIGNALWIRE_PROJECT_ID", "SIGNALWIRE_API_TOKEN", "SIGNALWIRE_SPACE",
                "PROJECT_ID", "REST_API_TOKEN", "SWSH_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    cli.Ctx.as_json = False
    cli.Ctx.profile_name = None


def _root():
    return typer.main.get_command(cli.app)


def _group(key: str):
    grp = _root().commands.get(key)
    assert grp is not None, f"no `sw {key}` group"
    return grp


def _commands(key: str) -> set[str]:
    return set(_group(key).commands)


class TestShape:
    def test_every_reachable_resource_is_a_command_group(self):
        root = _root().commands
        for r in resources.RESOURCES:
            if r.key == "calls":  # the live view has its own hand-written group
                assert "calls" in root
                continue
            if cli._cli_ops(r) or r.extras:
                assert r.key in root, r.key

    def test_the_verb_first_commands_are_gone(self):
        root = _root().commands
        for old in ("get", "create", "update", "delete", "msg"):
            assert old not in root, old
        # `sw resources` used to print the registry table; now it is the Fabric
        # resources noun group, and the table lives at `sw docs --list`.
        assert "list" in _commands("resources")

    def test_crud_verbs_follow_the_capabilities(self):
        for r in resources.RESOURCES:
            if r.key == "calls" or not (cli._cli_ops(r) or r.extras):
                continue
            have = _commands(r.key)
            for op in cli._cli_ops(r):
                assert r.verb(op) in have, (r.key, op)
            # and nothing the resource cannot do
            for op, letter in (("list", "L"), ("create", "C"), ("read", "R"),
                               ("update", "U"), ("delete", "D")):
                if not r.can(letter) and op not in r.rest_ops:
                    assert r.verb(op) not in have, (r.key, op)

    def test_numbers_use_domain_verbs_not_generic_ones(self):
        have = _commands("numbers")
        assert {"list", "get", "buy", "update", "release", "search",
                "assign-e911-address", "remove-e911-address"} <= have
        assert "create" not in have and "delete" not in have

    def test_every_extra_is_a_subcommand(self):
        for r in resources.RESOURCES:
            if r.key == "calls":
                continue
            crud = {r.rest_ops.get(op) for op in cli._cli_ops(r)}
            for e in r.extras:
                if e.spec_op and e.spec_op in crud:
                    continue  # the same operation `get` reaches; no alias
                assert e.command in _commands(r.key), (r.key, e.command)

    def test_a_detail_drill_does_not_duplicate_get(self):
        assert "log-detail" not in _commands("logs")
        assert "log-detail" not in _commands("messages")
        assert "get" in _commands("logs")

    def test_hand_written_commands_win_over_generated_ones(self):
        # `numbers search` keeps its flags; the registry extra of the same
        # name is not registered a second time.
        out = runner.invoke(cli.app, ["numbers", "search", "--help"]).output
        assert "--area-code" in out
        assert [c.name for c in cli.numbers_app.registered_commands].count("search") == 1
        # `logs events` shapes its columns; the "event timeline" extra is it.
        assert "events" in _commands("logs") and "event-timeline" not in _commands("logs")

    def test_root_help_groups_nouns_by_registry_group(self):
        out = runner.invoke(cli.app, ["--help"]).output
        for title in ("Numbers", "Voice", "Resources", "Logs"):
            assert title in out, title

    def test_extra_command_names_are_kebab_case(self):
        for r in resources.RESOURCES:
            for e in r.extras:
                assert e.command == e.command.lower()
                assert " " not in e.command and "_" not in e.command


class TestPrefixes:
    def test_a_unique_prefix_resolves_and_reports_the_full_name(self):
        result = runner.invoke(cli.app, ["num", "--help"])
        assert result.exit_code == 0, result.output
        assert "sw numbers" in result.output

    def test_an_ambiguous_prefix_names_the_candidates(self):
        result = runner.invoke(cli.app, ["s", "--help"])
        assert result.exit_code == 2
        assert "ambiguous" in result.output
        assert "swml" in result.output and "subscribers" in result.output

    def test_an_unknown_noun_is_still_an_error(self):
        result = runner.invoke(cli.app, ["phone_numbers", "list"])
        assert result.exit_code == 2


class TestGeneratedVerbs:
    @pytest.fixture
    def captured(self, monkeypatch):
        calls: list[dict] = []

        async def fake_invoke(self, resource, op, *, resource_id=None, body=None, **params):
            calls.append({"key": resource.key, "op": op, "id": resource_id, "body": body})
            if op == "list":
                return {"data": [{"id": "a", "number": "+1", "name": "x",
                                  "call_handler": "ai_agent", "call_status_callback_url": None},
                                 {"id": "b", "number": "+2", "name": "y",
                                  "call_handler": "ai_agent", "call_status_callback_url": None}]}
            if op == "read":
                return {"id": resource_id, "number": "+1"}
            if op == "create":
                return {"id": "new-1", **(body or {})}
            return {}

        monkeypatch.setattr(cli.SwshClient, "invoke", fake_invoke)
        return calls

    def test_list_honours_limit_and_json(self, captured):
        result = runner.invoke(cli.app, ["numbers", "list", "-n", "1", "--json"])
        assert result.exit_code == 0, result.output
        assert len(json.loads(result.output)) == 1
        assert captured[0]["op"] == "list"

    def test_get_prints_the_row_as_a_field_value_table(self, captured):
        result = runner.invoke(cli.app, ["queues", "get", "q-1"])
        assert result.exit_code == 0, result.output
        assert "field" in result.output and "value" in result.output
        assert "q-1" in result.output
        # The read is the last call, not the first: `q-1` is not id-shaped, so
        # it is tried as a handle against `friendly_name` before falling
        # through to the read route. A uuid costs no lookup at all.
        assert captured[-1] == {"key": "queues", "op": "read", "id": "q-1", "body": None}

    def test_get_json_is_still_the_raw_row(self, captured):
        result = runner.invoke(cli.app, ["queues", "get", "q-1", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["id"] == "q-1"

    def test_verbs_take_a_unique_prefix_too(self, captured):
        result = runner.invoke(cli.app, ["num", "li", "-n", "1", "--json"])
        assert result.exit_code == 0, result.output
        assert captured[0]["op"] == "list"
        result = runner.invoke(cli.app, ["numbers", "re", "pn-1", "-y"])
        assert result.exit_code == 2  # release or remove-e911-address: ambiguous
        assert "ambiguous" in result.output

    def test_buy_is_create_and_says_so(self, captured):
        result = runner.invoke(cli.app, ["numbers", "buy", "--set", "number=+15551234567"])
        assert result.exit_code == 0, result.output
        assert captured[0]["op"] == "create"
        assert captured[0]["body"] == {"number": "+15551234567"}
        assert "bought new-1" in result.output

    def test_release_asks_with_the_domain_verb(self, captured, monkeypatch):
        asked: list[str] = []

        def fake_confirm(text, abort=False, **kw):
            asked.append(text)
            raise typer.Abort()

        monkeypatch.setattr(cli.typer, "confirm", fake_confirm)
        result = runner.invoke(cli.app, ["numbers", "release", PN1])
        assert result.exit_code != 0
        assert asked == ["release 1 phone number?"]
        assert captured == []  # nothing was sent

    def test_release_with_yes_skips_the_question(self, captured):
        result = runner.invoke(cli.app, ["numbers", "release", PN1, PN2, "-y"])
        assert result.exit_code == 0, result.output
        assert [c["id"] for c in captured] == [PN1, PN2]
        assert all(c["op"] == "delete" for c in captured)
        assert "released" in result.output

    def test_release_of_a_missing_id_fails_the_command(self, captured, monkeypatch):
        from swsh.client import SwshError

        async def flaky_invoke(self, resource, op, *, resource_id=None, body=None, **params):
            if resource_id == "gone":
                raise SwshError("not found (HTTP 404)")
            captured.append({"key": resource.key, "op": op, "id": resource_id, "body": body})
            return {}

        monkeypatch.setattr(cli.SwshClient, "invoke", flaky_invoke)
        result = runner.invoke(cli.app, ["numbers", "release", PN1, "gone", "-y"])
        assert result.exit_code == 1, result.output
        # "gone" is not id-shaped, so sw tries to resolve it as a handle first,
        # finds nothing, and lets the release route report its own 404.
        assert [c["id"] for c in captured if c["op"] == "delete"] == [PN1]
        assert "released" in result.output and "gone: not found" in result.output

    def test_release_json_is_a_summary_object(self, captured):
        result = runner.invoke(cli.app, ["numbers", "release", PN1, "-y", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {"released": [PN1], "failed": {}}

    def test_update_sends_the_typed_body(self, captured):
        result = runner.invoke(cli.app, ["numbers", "update", PN1,
                                         "--set", "call_handler=ai_agent"])
        assert result.exit_code == 0, result.output
        assert captured[0] == {"key": "numbers", "op": "update", "id": PN1,
                               "body": {"call_handler": "ai_agent"}}

    def test_update_rejects_a_bad_choice_locally(self, captured):
        result = runner.invoke(cli.app, ["numbers", "update", PN1,
                                         "--set", "call_handler=bogus"])
        assert result.exit_code == 2
        assert captured == []


class TestNoGeneratedCommandCanBeUnusable:
    """A verb whose route needs an id it cannot accept is worse than a missing
    one: it reads as a broken tool rather than as a thing reached another way.

    `sw orders list` and `sw campaigns list` were both generated from
    `rest_ops` and answered `needs a resource id` on every invocation, for
    every user, on every project — their routes are
    `/registry/beta/campaigns/{id}/orders` and `/registry/beta/brands/{id}/campaigns`.
    """

    def test_no_listing_or_create_needs_an_id_it_cannot_take(self):
        offenders = [
            (r.key, op) for r in resources.RESOURCES for op in cli._cli_ops(r)
            if op not in cli._ID_TAKING
            and resources.route_placeholders(r.rest_ops.get(op, ""), r.api)
        ]
        assert offenders == []

    def test_the_four_that_used_to_exist_are_gone(self):
        for group, verb in (("orders", "list"), ("orders", "create"),
                            ("campaigns", "list"), ("campaigns", "create")):
            result = runner.invoke(cli.app, [group, verb, "--help"])
            assert result.exit_code != 0, (group, verb)

    def test_but_the_listings_are_still_reachable_from_the_parent(self):
        """Dropping a command is only right if the capability survives."""
        out = runner.invoke(cli.app, ["brands", "--help"]).output
        assert "campaigns" in out
        assert "orders" in out

    def test_an_id_taking_verb_keeps_its_placeholder_route(self):
        """`sw orders get <id>` is fine: the placeholder *is* the argument."""
        assert "read" in cli._cli_ops(resources.get("orders"))
        assert runner.invoke(cli.app, ["orders", "get", "--help"]).exit_code == 0


class TestIdentifiersAndMatching:
    """`get` takes a handle, not only a uuid, and `list` can be filtered.

    Nobody remembers a phone number's uuid. They remember the number, and they
    named it, so both have to resolve. The rules that matter: an id-shaped
    identifier never costs a list call, an exact hit beats every substring hit,
    and several substring hits are an error naming them rather than a guess.
    """

    NUMBERS = [
        {"id": "aaaaaaaa-0000-4000-8000-000000000001", "number": "+12095550183",
         "name": None, "call_handler": "laml_webhooks", "call_status_callback_url": None},
        {"id": "aaaaaaaa-0000-4000-8000-000000000002", "number": "+14405550168",
         "name": "Fax Number", "call_handler": "laml_webhooks",
         "call_status_callback_url": None},
        {"id": "aaaaaaaa-0000-4000-8000-000000000003", "number": "+14405550159",
         "name": "Fax Number backup", "call_handler": "relay_script",
         "call_status_callback_url": None},
    ]

    @pytest.fixture
    def captured(self, monkeypatch):
        calls: list[dict] = []

        async def fake_invoke(self, resource, op, *, resource_id=None, body=None, **params):
            calls.append({"key": resource.key, "op": op, "id": resource_id,
                          "params": params})
            if op == "list":
                rows = TestIdentifiersAndMatching.NUMBERS
                # Stand in for the platform's own substring filters.
                for name, value in params.items():
                    field = {"filter_number": "number", "filter_name": "name"}[name]
                    rows = [r for r in rows
                            if r[field] and value.casefold() in str(r[field]).casefold()]
                return {"data": rows}
            if op == "read":
                return next((r for r in TestIdentifiersAndMatching.NUMBERS
                             if r["id"] == resource_id), {"id": resource_id})
            return {}

        monkeypatch.setattr(cli.SwshClient, "invoke", fake_invoke)
        return calls

    def _ops(self, captured):
        return [c["op"] for c in captured]

    def test_a_uuid_is_read_directly_with_no_lookup(self, captured):
        uuid = self.NUMBERS[0]["id"]
        result = runner.invoke(cli.app, ["numbers", "get", uuid, "--json"])
        assert result.exit_code == 0, result.output
        assert self._ops(captured) == ["read"]
        assert captured[0]["id"] == uuid

    def test_an_e164_number_resolves_to_the_id(self, captured):
        result = runner.invoke(cli.app, ["numbers", "get", "+12095550183", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["id"] == self.NUMBERS[0]["id"]
        assert captured[-1] == {"key": "numbers", "op": "read",
                                "id": self.NUMBERS[0]["id"], "params": {}}

    def test_a_number_typed_without_the_country_code_or_punctuation(self, captured):
        for typed in ("2095550183", "(209) 555-0183", "209-555-0183"):
            captured.clear()
            result = runner.invoke(cli.app, ["numbers", "get", typed, "--json"])
            assert result.exit_code == 0, (typed, result.output)
            assert json.loads(result.output)["id"] == self.NUMBERS[0]["id"], typed

    def test_a_friendly_name_resolves(self, captured):
        result = runner.invoke(cli.app, ["numbers", "get", "Fax Number", "--json"])
        assert result.exit_code == 0, result.output
        # "Fax Number" is also a prefix of "Fax Number backup"; the exact hit wins.
        assert json.loads(result.output)["id"] == self.NUMBERS[1]["id"]

    def test_the_name_match_is_case_insensitive(self, captured):
        result = runner.invoke(cli.app, ["numbers", "get", "fax number", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["id"] == self.NUMBERS[1]["id"]

    def test_an_ambiguous_handle_names_the_candidates_instead_of_guessing(self, captured):
        result = runner.invoke(cli.app, ["numbers", "get", "Fax"])
        assert result.exit_code == 2
        assert "matches 2 phone numbers" in result.output
        assert "read" not in self._ops(captured)
        assert "+14405550168" in result.output and "+14405550159" in result.output

    def test_an_unrecognised_handle_still_reaches_the_read_route(self, captured):
        # It may be an id whose shape sw does not know; the API says 404, not sw.
        result = runner.invoke(cli.app, ["numbers", "get", "pn-legacy-1", "--json"])
        assert result.exit_code == 0, result.output
        assert captured[-1]["op"] == "read" and captured[-1]["id"] == "pn-legacy-1"

    def test_match_filters_the_listing_server_side(self, captured):
        result = runner.invoke(cli.app, ["numbers", "list", "--match", "440", "--json"])
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        assert {r["number"] for r in rows} == {"+14405550168", "+14405550159"}
        assert {c["op"] for c in captured} == {"list"}
        assert {"filter_number": "440"} in [c["params"] for c in captured]
        assert {"filter_name": "440"} in [c["params"] for c in captured]

    def test_match_is_available_on_every_list_command(self):
        for key in ("numbers", "swml", "sip", "queues"):
            out = runner.invoke(cli.app, [key, "list", "--help"]).output
            assert "--match" in out, key

    def test_update_takes_a_handle_and_names_both(self, captured):
        result = runner.invoke(cli.app, ["numbers", "update", "+14405550168",
                                         "--set", "name=Fax"])
        assert result.exit_code == 0, result.output
        write = [c for c in captured if c["op"] == "update"]
        assert write == [{"key": "numbers", "op": "update", "id": self.NUMBERS[1]["id"],
                          "params": {}}]
        # The handle they typed and the id that was written, both.
        assert "+14405550168" in result.output and self.NUMBERS[1]["id"] in result.output

    def test_release_resolves_every_handle_before_asking(self, captured, monkeypatch):
        asked: list[str] = []

        def fake_confirm(text, abort=False, **kw):
            asked.append(text)
            raise typer.Abort()

        monkeypatch.setattr(cli.typer, "confirm", fake_confirm)
        result = runner.invoke(cli.app, ["numbers", "release", "+12095550183", "Fax Number"])
        assert result.exit_code != 0
        assert asked == ["release 2 phone numbers?"]
        # The confirmation shows what each handle resolved to, so the question
        # is answerable, and nothing was sent.
        assert f"+12095550183  \u2192  {self.NUMBERS[0]['id']}" in result.output
        assert f"Fax Number  \u2192  {self.NUMBERS[1]['id']}" in result.output
        assert not [c for c in captured if c["op"] == "delete"]

    def test_an_ambiguous_handle_stops_a_release_before_anything_goes(self, captured):
        result = runner.invoke(cli.app, ["numbers", "release", "+12095550183", "Fax", "-y"])
        assert result.exit_code == 2
        assert "matches 2 phone numbers" in result.output
        # Not even the unambiguous one: resolution happens before the first delete.
        assert not [c for c in captured if c["op"] == "delete"]

    def test_an_extra_on_the_resources_own_rows_takes_a_handle(self, captured):
        result = runner.invoke(cli.app, ["numbers", "remove-e911-address",
                                         "+14405550168", "--yes"])
        assert result.exit_code == 0, result.output
        acted = [c for c in captured if c["op"] == "remove_e911_address"]
        assert [c["id"] for c in acted] == [self.NUMBERS[1]["id"]]

    def test_an_extra_bound_to_a_drill_never_resolves_against_the_parent(self):
        # `remove-member` takes a membership id, not a number group's handle,
        # so it must not be matched against the parent's lookup fields.
        out = runner.invoke(cli.app, ["groups", "remove-member", "--help"]).output
        assert "ID" in out
        extra = next(e for e in resources.get("groups").extras if e.command == "remove-member")
        assert extra.on_drill

    def test_every_verb_that_takes_an_id_advertises_the_handles(self):
        for verb in ("get", "update", "release", "assign-e911-address",
                     "remove-e911-address"):
            out = runner.invoke(cli.app, ["numbers", verb, "--help"]).output
            assert "ID|NUMBER|NAME" in out, verb

    def test_a_resource_with_no_filters_matches_client_side(self, monkeypatch):
        rows = [{"id": "q-1", "friendly_name": "support"},
                {"id": "q-2", "friendly_name": "sales"}]
        seen: list[dict] = []

        async def fake_invoke(self, resource, op, *, resource_id=None, body=None, **params):
            seen.append(params)
            return {"data": rows}

        monkeypatch.setattr(cli.SwshClient, "invoke", fake_invoke)
        result = runner.invoke(cli.app, ["queues", "list", "-m", "supp", "--json"])
        assert result.exit_code == 0, result.output
        assert [r["id"] for r in json.loads(result.output)] == ["q-1"]
        assert seen == [{}]  # one unfiltered page, sifted here


class TestGeneratedExtras:
    @pytest.fixture
    def captured(self, monkeypatch):
        calls: list[dict] = []

        async def fake_invoke(self, resource, op, *, resource_id=None, body=None, **params):
            calls.append({"key": resource.key, "op": op, "id": resource_id, "body": body})
            if op == "list_memberships":
                return {"data": [{"id": "m-1", "phone_number_id": "pn-1"}]}
            return None  # a 204

        monkeypatch.setattr(cli.SwshClient, "invoke", fake_invoke)
        return calls

    def test_an_action_takes_its_fields_as_flags(self, captured):
        result = runner.invoke(cli.app, ["numbers", "assign-e911-address", PN1,
                                         "--e911-address-id", "addr-1"])
        assert result.exit_code == 0, result.output
        assert captured == [{"key": "numbers", "op": "assign_e911_address", "id": PN1,
                             "body": {"e911_address_id": "addr-1"}}]
        assert "assign E911 address" in result.output

    def test_a_missing_required_field_names_its_flag(self, captured):
        result = runner.invoke(cli.app, ["numbers", "assign-e911-address", PN1, "--json"])
        assert result.exit_code == 2
        assert "--e911-address-id" in result.output
        assert captured == []

    def test_a_confirming_action_asks_unless_yes(self, captured, monkeypatch):
        asked: list[str] = []

        def fake_confirm(text, abort=False, **kw):
            asked.append(text)
            raise typer.Abort()

        monkeypatch.setattr(cli.typer, "confirm", fake_confirm)
        result = runner.invoke(cli.app, ["numbers", "remove-e911-address", PN1])
        assert result.exit_code != 0 and asked == [f"remove E911 address {PN1}?"]
        assert captured == []

        result = runner.invoke(cli.app, ["numbers", "remove-e911-address", PN1, "--yes"])
        assert result.exit_code == 0, result.output
        assert captured[0]["op"] == "remove_e911_address" and captured[0]["body"] is None

    def test_a_drill_lists_its_rows(self, captured):
        result = runner.invoke(cli.app, ["groups", "memberships", "g-1", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == [{"id": "m-1", "phone_number_id": "pn-1"}]
        assert captured[-1] == {"key": "groups", "op": "list_memberships", "id": "g-1",
                                "body": None}

    def test_an_action_on_a_drill_row_takes_that_row_id(self, captured):
        result = runner.invoke(cli.app, ["groups", "remove-member", "m-1", "-y"])
        assert result.exit_code == 0, result.output
        assert captured[0]["op"] == "remove_member" and captured[0]["id"] == "m-1"

    def test_a_from_field_is_the_from_flag(self):
        out = runner.invoke(cli.app, ["mfa", "send-code-by-sms", "--help"]).output
        assert "--from " in out or "--from\n" in out
        assert "--from_" not in out
        # bool and int fields get real controls, not free text
        assert "--no-allow-alphas" in out
        assert "<int>" in out


def test_docs_list_is_the_command_table():
    result = runner.invoke(cli.app, ["docs", "--list", "--json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert {"command", "resource", "group", "ops", "api"} <= set(rows[0])
    assert any(r["command"] == "sw numbers" for r in rows)


class TestAnyRowCanBeFoundByName:
    """`lookup` was declared on `numbers` and nowhere else, so every other
    resource took a uuid and nothing but — and finding one meant a `list -m`
    and a copy-paste. The name-like columns a resource already declares answer
    "what is this row called" without a second declaration per resource."""

    @pytest.fixture
    def captured(self, monkeypatch):
        calls: list[dict] = []

        async def fake_invoke(self, resource, op, *, resource_id=None, body=None, **params):
            calls.append({"key": resource.key, "op": op, "id": resource_id, "body": body})
            if op == "list":
                return {"data": [{"id": "q-9", "friendly_name": "support"}]}
            return {"id": resource_id}

        monkeypatch.setattr(cli.SwshClient, "invoke", fake_invoke)
        return calls

    def test_most_of_the_registry_is_addressable_by_name(self):
        named = [r.key for r in resources.RESOURCES if r.lookup_fields]
        assert len(named) > 30, named

    def test_an_explicit_lookup_still_wins(self):
        assert resources.get("numbers").lookup_fields == ("number", "name")

    def test_logs_and_tokens_have_no_handle_because_they_have_no_name(self):
        for key in ("logs", "messages", "recordings", "chattoken", "vstreams"):
            assert not resources.get(key).lookup_fields, key

    def test_a_date_is_never_a_handle(self):
        """Resolving an identifier has to fail rather than match the wrong row,
        and `created_at` contains "2026" for almost everything."""
        for r in resources.RESOURCES:
            assert not any(f.endswith("_at") or f == "status"
                           for f in r.lookup_fields), r.key

    def test_the_help_says_what_it_will_accept(self):
        out = runner.invoke(cli.app, ["sip", "get", "--help"]).output
        assert "display_name" in out or "username" in out

    def test_a_uuid_costs_no_lookup(self, captured):
        """The short-circuit that keeps the common case one request."""
        result = runner.invoke(cli.app, ["queues", "get", PN1, "--json"])
        assert result.exit_code == 0, result.output
        assert [c["op"] for c in captured] == ["read"]
