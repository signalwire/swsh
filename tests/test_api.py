"""`sw api`: the raw-request escape hatch.

Two things carry this command. It has to resolve *exactly* the request the caller
asked for, because it bypasses every other guard in the tool, and its output has
to be the response verbatim so it composes with jq. Both are pinned here.

The HTTP boundary is mocked with respx, so none of this needs a live space. That
also means these tests prove the right request is issued, not that the platform
accepts it.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from swsh import cli, client, spec

runner = CliRunner()

BASE = "https://example.signalwire.com"
PROJECT = "proj-abc123"


@pytest.fixture(autouse=True)
def creds(monkeypatch):
    """A resolvable profile, with no real credentials and no stored config."""
    monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", PROJECT)
    monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "tok")
    monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
    for var in ("PROJECT_ID", "REST_API_TOKEN", "SWSH_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    # `sw api` refuses a write with no TTY unless --force. Tests that exercise
    # the interactive path opt in explicitly.
    monkeypatch.setattr(cli.prompts, "interactive", lambda: False)


def run(*args: str):
    return runner.invoke(cli.app, ["api", *args])


def run_json(*args: str):
    # `--json` goes after the command; `sw --json api ...` is a usage error.
    return runner.invoke(cli.app, ["api", *args, "--json"])


class TestEndpointResolution:
    @respx.mock
    def test_a_full_path_is_used_as_given(self):
        route = respx.get(f"{BASE}/api/relay/rest/phone_numbers").mock(
            return_value=httpx.Response(200, json={"data": []}))
        assert run("/api/relay/rest/phone_numbers").exit_code == 0
        assert route.called

    @respx.mock
    def test_a_leading_slash_is_optional(self):
        route = respx.get(f"{BASE}/api/relay/rest/phone_numbers").mock(
            return_value=httpx.Response(200, json={"data": []}))
        assert run("api/relay/rest/phone_numbers").exit_code == 0
        assert route.called

    @respx.mock
    def test_an_operation_id_resolves_its_own_method_and_path(self):
        # The point of carrying the catalog: no URL and no -X needed.
        route = respx.get(f"{BASE}/api/fabric/resources/subscribers").mock(
            return_value=httpx.Response(200, json={"data": []}))
        assert run("list_subscribers").exit_code == 0
        assert route.called

    @respx.mock
    def test_an_api_qualified_id_disambiguates(self):
        route = respx.post(f"{BASE}/api/relay/rest/queues").mock(
            return_value=httpx.Response(200, json={"id": "q-1"}))
        result = run("relay-rest:create_queue", "-f", "name=support", "--force")
        assert result.exit_code == 0
        assert route.called

    def test_a_colliding_id_names_its_candidates(self):
        # create_token is in three APIs. Failing blankly would leave the caller
        # with nowhere to go, so the error has to list them.
        result = run("create_token")
        assert result.exit_code == 2
        assert "create_token" in result.output
        for op in spec.candidates("create_token"):
            assert op.key in result.output

    def test_an_unknown_id_points_at_the_listing(self):
        result = run("no_such_operation")
        assert result.exit_code == 2
        assert "--list" in result.output

    def test_an_unknown_api_on_list_names_the_known_ones(self):
        result = run("--list", "not-an-api")
        assert result.exit_code == 2
        assert "fabric-api" in result.output


class TestPlaceholders:
    @respx.mock
    def test_account_sid_fills_from_the_profile(self):
        # 52 of the 79 compat operations carry {AccountSid}; asking for it every
        # time would make the whole surface tedious.
        route = respx.get(
            f"{BASE}/api/laml/2010-04-01/Accounts/{PROJECT}/Faxes").mock(
            return_value=httpx.Response(200, json={"faxes": []}))
        assert run("list_all_faxes").exit_code == 0
        assert route.called

    @respx.mock
    def test_a_named_param_fills_a_placeholder(self):
        route = respx.get(
            f"{BASE}/api/fabric/resources/subscribers/sub-1/sip_endpoints/ep-2"
        ).mock(return_value=httpx.Response(200, json={}))
        result = run("get_subscriber_sip_credential",
                     "-p", "fabric_subscriber_id=sub-1", "-p", "id=ep-2")
        assert result.exit_code == 0
        assert route.called

    @respx.mock
    def test_a_bare_argument_fills_a_single_remaining_placeholder(self):
        route = respx.get(
            f"{BASE}/api/laml/2010-04-01/Accounts/{PROJECT}/Faxes/FX123").mock(
            return_value=httpx.Response(200, json={"sid": "FX123"}))
        assert run("retrieve_fax", "FX123").exit_code == 0
        assert route.called

    def test_an_unfilled_placeholder_says_which_one(self):
        result = run("get_subscriber_sip_credential")
        assert result.exit_code == 2
        assert "fabric_subscriber_id" in result.output


class TestBodyEncoding:
    @respx.mock
    def test_the_laml_surface_gets_form_encoding(self):
        route = respx.post(
            f"{BASE}/api/laml/2010-04-01/Accounts/{PROJECT}/Faxes").mock(
            return_value=httpx.Response(201, json={"sid": "FX1"}))
        result = run("send_fax", "-f", "To=+15551234567",
                     "-f", "From=+15559876543", "--force")
        assert result.exit_code == 0
        sent = route.calls[0].request
        assert sent.headers["content-type"].startswith("application/x-www-form-urlencoded")
        assert b"To=%2B15551234567" in sent.content

    @respx.mock
    def test_a_repeated_field_becomes_repeated_keys(self):
        # How LaML wants StatusCallbackEvent and friends.
        route = respx.post(f"{BASE}/api/laml/2010-04-01/Accounts/{PROJECT}/Calls").mock(
            return_value=httpx.Response(201, json={}))
        result = run("/api/laml/2010-04-01/Accounts/{AccountSid}/Calls",
                     "-X", "POST",
                     "-f", "StatusCallbackEvent=initiated",
                     "-f", "StatusCallbackEvent=answered", "--force")
        assert result.exit_code == 0
        body = route.calls[0].request.content.decode()
        assert body.count("StatusCallbackEvent=") == 2

    @respx.mock
    def test_a_fabric_path_gets_json(self):
        route = respx.post(f"{BASE}/api/fabric/resources/subscribers").mock(
            return_value=httpx.Response(201, json={"id": "s-1"}))
        result = run("create_subscriber", "-f", "email=a@b.com", "--force")
        assert result.exit_code == 0
        sent = route.calls[0].request
        assert sent.headers["content-type"].startswith("application/json")
        assert json.loads(sent.content) == {"email": "a@b.com"}

    @respx.mock
    def test_json_body_flag_overrides_the_laml_default(self):
        route = respx.post(f"{BASE}/api/laml/2010-04-01/Accounts/{PROJECT}/Faxes").mock(
            return_value=httpx.Response(201, json={}))
        result = run("send_fax", "-f", "To=+1", "--json-body", "--force")
        assert result.exit_code == 0
        assert route.calls[0].request.headers["content-type"].startswith("application/json")

    @respx.mock
    def test_form_flag_overrides_the_json_default(self):
        route = respx.post(f"{BASE}/api/fabric/resources/subscribers").mock(
            return_value=httpx.Response(201, json={}))
        result = run("create_subscriber", "-f", "email=a@b.com", "--form", "--force")
        assert result.exit_code == 0
        assert route.calls[0].request.headers["content-type"].startswith(
            "application/x-www-form-urlencoded")

    def test_both_encoding_flags_is_a_usage_error(self):
        result = run("create_subscriber", "--form", "--json-body", "--force")
        assert result.exit_code == 2


class TestFieldTyping:
    @respx.mock
    def _post(self, args: list[str]):
        route = respx.post(f"{BASE}/api/fabric/resources/subscribers").mock(
            return_value=httpx.Response(201, json={}))
        result = runner.invoke(cli.app, ["api", "create_subscriber", *args, "--force"])
        assert result.exit_code == 0, result.output
        return json.loads(route.calls[0].request.content)

    def test_typed_fields_become_real_json_types(self):
        body = self._post(["-F", "n=1", "-F", "ok=true", "-F", "no=false", "-F", "f=1.5"])
        assert body == {"n": 1, "ok": True, "no": False, "f": 1.5}

    def test_raw_fields_stay_strings(self):
        body = self._post(["-f", "n=1", "-f", "ok=true"])
        assert body == {"n": "1", "ok": "true"}

    @respx.mock
    def test_a_typed_null_is_sent_as_json_null(self):
        # _clean drops None from dict bodies, so an explicit null must survive as
        # a deliberate value rather than being silently dropped.
        route = respx.post(f"{BASE}/api/fabric/resources/subscribers").mock(
            return_value=httpx.Response(201, json={}))
        result = run("create_subscriber", "-F", "x=null", "-F", "keep=1", "--force")
        assert result.exit_code == 0
        assert json.loads(route.calls[0].request.content) == {"keep": 1}

    def test_at_file_reads_the_file(self, tmp_path):
        doc = tmp_path / "prompt.txt"
        doc.write_text("hello from a file")
        body = self._post(["-F", f"text=@{doc}"])
        assert body == {"text": "hello from a file"}

    def test_an_unreadable_at_file_is_a_usage_error(self):
        result = run("create_subscriber", "-F", "text=@/no/such/file", "--force")
        assert result.exit_code == 2

    def test_a_field_without_an_equals_is_a_usage_error(self):
        result = run("create_subscriber", "-f", "novalue", "--force")
        assert result.exit_code == 2


class TestGuardrails:
    @respx.mock
    def test_dry_run_sends_nothing_and_shows_the_resolved_request(self):
        route = respx.post(f"{BASE}/api/laml/2010-04-01/Accounts/{PROJECT}/Faxes").mock(
            return_value=httpx.Response(201))
        result = run("send_fax", "-f", "To=+15551234567", "--dry-run")
        assert result.exit_code == 0
        assert not route.called
        assert "POST" in result.output
        assert f"Accounts/{PROJECT}/Faxes" in result.output
        assert "form" in result.output

    @respx.mock
    def test_a_write_without_force_refuses_when_there_is_no_terminal(self):
        route = respx.post(f"{BASE}/api/fabric/resources/subscribers").mock(
            return_value=httpx.Response(201))
        result = run("create_subscriber", "-f", "email=a@b.com")
        assert result.exit_code == 2
        assert not route.called
        assert "--force" in result.output

    @respx.mock
    def test_force_lets_the_write_through(self):
        route = respx.post(f"{BASE}/api/fabric/resources/subscribers").mock(
            return_value=httpx.Response(201, json={}))
        assert run("create_subscriber", "-f", "email=a@b.com", "--force").exit_code == 0
        assert route.called

    @respx.mock
    def test_a_read_never_prompts(self):
        route = respx.get(f"{BASE}/api/fabric/resources/subscribers").mock(
            return_value=httpx.Response(200, json={"data": []}))
        assert run("list_subscribers").exit_code == 0
        assert route.called

    @respx.mock
    def test_declining_the_confirmation_sends_nothing(self, monkeypatch):
        monkeypatch.setattr(cli.prompts, "interactive", lambda: True)
        monkeypatch.setattr(cli.typer, "confirm", lambda *a, **k: False)
        route = respx.delete(f"{BASE}/api/fabric/resources/subscribers/s-1").mock(
            return_value=httpx.Response(204))
        result = run("delete_subscriber", "s-1")
        assert result.exit_code == 0
        assert not route.called

    @respx.mock
    def test_accepting_the_confirmation_sends_it(self, monkeypatch):
        monkeypatch.setattr(cli.prompts, "interactive", lambda: True)
        monkeypatch.setattr(cli.typer, "confirm", lambda *a, **k: True)
        route = respx.delete(f"{BASE}/api/fabric/resources/subscribers/s-1").mock(
            return_value=httpx.Response(204))
        assert run("delete_subscriber", "s-1").exit_code == 0
        assert route.called


class TestOutput:
    @respx.mock
    def test_the_body_is_returned_verbatim(self):
        # Byte-identical, so `| jq` sees what the platform sent and nothing else
        # re-serialises or reshapes it.
        raw = '{"data":[{"id":"pn-1","number":"+15551234567"}],"links":{"self":"/x"}}'
        respx.get(f"{BASE}/api/relay/rest/phone_numbers").mock(
            return_value=httpx.Response(200, text=raw,
                                        headers={"content-type": "application/json"}))
        result = run("/api/relay/rest/phone_numbers")
        assert result.exit_code == 0
        assert result.output.strip() == raw

    @respx.mock
    def test_a_top_level_array_is_not_wrapped(self):
        # rest_call's _unwrap turns a bare array into {"data": [...]}. The escape
        # hatch must not do that.
        raw = '[{"id":"a"},{"id":"b"}]'
        respx.get(f"{BASE}/api/relay/rest/things").mock(
            return_value=httpx.Response(200, text=raw,
                                        headers={"content-type": "application/json"}))
        result = run("/api/relay/rest/things")
        assert result.output.strip() == raw

    @respx.mock
    def test_include_prints_the_status_and_headers(self):
        respx.get(f"{BASE}/api/relay/rest/things").mock(
            return_value=httpx.Response(200, json={"data": []},
                                        headers={"x-request-id": "req-9"}))
        result = run("/api/relay/rest/things", "-i")
        assert result.exit_code == 0
        assert "HTTP 200" in result.output
        assert "x-request-id" in result.output

    @respx.mock
    def test_silent_suppresses_the_body(self):
        respx.get(f"{BASE}/api/relay/rest/things").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "a"}]}))
        result = run("/api/relay/rest/things", "--silent")
        assert result.exit_code == 0
        assert "id" not in result.output

    @respx.mock
    def test_a_204_prints_nothing_and_succeeds(self):
        respx.delete(f"{BASE}/api/fabric/resources/subscribers/s-1").mock(
            return_value=httpx.Response(204))
        result = run("delete_subscriber", "s-1", "--force")
        assert result.exit_code == 0

    @respx.mock
    def test_an_error_prints_the_body_and_exits_one(self):
        respx.post(f"{BASE}/api/fabric/resources/subscribers").mock(
            return_value=httpx.Response(422, json={"errors": [{"detail": "email taken"}]}))
        result = run("create_subscriber", "-f", "email=a@b.com", "--force")
        assert result.exit_code == 1
        assert "email taken" in result.output


class TestPagination:
    @respx.mock
    def test_relay_links_next_is_followed_and_pages_merge(self):
        # One route with a response sequence, because a respx route registered
        # without `params` also matches the ?page=2 follow-up and would answer
        # it with page one.
        route = respx.get(f"{BASE}/api/relay/rest/things").mock(side_effect=[
            httpx.Response(200, json={
                "data": [{"id": "a"}],
                "links": {"next": "/api/relay/rest/things?page=2"},
            }),
            httpx.Response(200, json={"data": [{"id": "b"}], "links": {}}),
        ])
        result = run("/api/relay/rest/things", "--paginate")
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert [row["id"] for row in payload["data"]] == ["a", "b"]
        # the link was followed with its query string intact
        assert route.call_count == 2
        assert route.calls[1].request.url.query == b"page=2"
        # the links describe pages already walked, so they are dropped
        assert "links" not in payload

    @respx.mock
    def test_compat_next_page_uri_is_followed(self):
        respx.get(f"{BASE}/api/laml/2010-04-01/Accounts/{PROJECT}/Faxes").mock(
            return_value=httpx.Response(200, json={
                "data": [{"sid": "FX1"}],
                "next_page_uri": "/api/laml/2010-04-01/More",
            }))
        respx.get(f"{BASE}/api/laml/2010-04-01/More").mock(
            return_value=httpx.Response(200, json={"data": [{"sid": "FX2"}]}))
        result = run("list_all_faxes", "--paginate")
        assert result.exit_code == 0
        assert [r["sid"] for r in json.loads(result.output)["data"]] == ["FX1", "FX2"]

    @respx.mock
    def test_a_self_referencing_next_link_does_not_loop(self):
        route = respx.get(f"{BASE}/api/relay/rest/things").mock(
            return_value=httpx.Response(200, json={
                "data": [{"id": "a"}],
                "links": {"next": "/api/relay/rest/things"},
            }))
        result = run("/api/relay/rest/things", "--paginate")
        assert result.exit_code == 0
        assert route.call_count == 1

    @respx.mock
    def test_without_paginate_only_one_request_is_made(self):
        route = respx.get(f"{BASE}/api/relay/rest/things").mock(
            return_value=httpx.Response(200, json={
                "data": [{"id": "a"}],
                "links": {"next": "/api/relay/rest/things?page=2"},
            }))
        assert run("/api/relay/rest/things").exit_code == 0
        assert route.call_count == 1


class TestQueryAndHeaders:
    @respx.mock
    def test_query_parameters_are_sent(self):
        route = respx.get(f"{BASE}/api/relay/rest/phone_numbers",
                          params={"filter_number": "+1555"}).mock(
            return_value=httpx.Response(200, json={"data": []}))
        assert run("list_phone_numbers", "-q", "filter_number=+1555").exit_code == 0
        assert route.called

    @respx.mock
    def test_headers_are_sent(self):
        route = respx.get(f"{BASE}/api/relay/rest/things").mock(
            return_value=httpx.Response(200, json={}))
        assert run("/api/relay/rest/things", "-H", "X-Trace: abc").exit_code == 0
        assert route.calls[0].request.headers["x-trace"] == "abc"

    def test_a_malformed_header_is_a_usage_error(self):
        result = run("/api/relay/rest/things", "-H", "NoColonHere")
        assert result.exit_code == 2


class TestInput:
    @respx.mock
    def test_a_json_file_becomes_the_body(self, tmp_path):
        doc = tmp_path / "body.json"
        doc.write_text('{"name":"from-file"}')
        route = respx.post(f"{BASE}/api/fabric/resources/subscribers").mock(
            return_value=httpx.Response(201, json={}))
        result = run("create_subscriber", "--input", str(doc), "--force")
        assert result.exit_code == 0
        assert json.loads(route.calls[0].request.content) == {"name": "from-file"}

    def test_invalid_json_on_input_is_a_usage_error(self, tmp_path):
        doc = tmp_path / "bad.json"
        doc.write_text("{not json")
        result = run("create_subscriber", "--input", str(doc), "--force")
        assert result.exit_code == 2


class TestDiscovery:
    def test_list_covers_the_whole_catalog(self):
        result = run_json("--list")
        assert result.exit_code == 0
        assert len(json.loads(result.output)) == spec.total()

    def test_list_can_be_scoped_to_one_api(self):
        result = run_json("--list", "compatibility-api")
        rows = json.loads(result.output)
        assert rows and all(r["api"] == "compatibility-api" for r in rows)
        # the compat surface is the reason this command exists
        assert any(r["operation"] == "send_fax" for r in rows)

    def test_list_carries_the_method_and_path(self):
        rows = json.loads(run_json("--list", "fax-api").output)
        by_id = {r["operation"]: r for r in rows}
        assert by_id["list_fax_logs"]["method"] == "GET"
        assert by_id["list_fax_logs"]["path"] == "/api/fax/logs"

    def test_no_endpoint_and_no_list_is_a_usage_error(self):
        result = run()
        assert result.exit_code == 2

    def test_the_operation_completer_is_pure_and_prefix_filtered(self):
        # Completion must not hit the network; it reads the checked-in catalog.
        every = cli._complete_operation("")
        assert every
        fax = cli._complete_operation("send_fax")
        assert [name for name, _ in fax] == ["send_fax"]


class TestNextPageHelper:
    """`next_page` is transport knowledge, so it lives in client, not the CLI."""

    def test_relay_shape(self):
        assert client.next_page({"links": {"next": "/p2"}}) == "/p2"

    def test_compat_shape(self):
        assert client.next_page({"next_page_uri": "/p2"}) == "/p2"

    def test_absent_and_empty_both_mean_the_end(self):
        assert client.next_page({"data": []}) is None
        assert client.next_page({"links": {"next": ""}}) is None
        assert client.next_page({"next_page_uri": None}) is None

    def test_a_non_dict_payload_is_tolerated(self):
        assert client.next_page([{"id": "a"}]) is None
        assert client.next_page("text") is None
