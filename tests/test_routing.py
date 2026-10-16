"""`get --full`: following a number's routing to what it actually points at.

The whole feature exists because a phone number's row is misleading on its own.
It keeps every pointer it has ever had, so the only field that says what happens
on the next call is ``call_handler`` — everything else is a candidate. These
tests pin that the handler picks, that the sediment is reported as sediment, and
that following a URL off the space never carries the project's credentials.

The HTTP boundary is respx, so none of it needs a live space. The fixture shapes
mirror real responses, with invented values; `TestVerifiedAgainstLiveProject`
in test_resources.py pins the facts they depend on.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from swsh import cli, resources, routing

runner = CliRunner()

BASE = "https://example.signalwire.com"
PROJECT = "proj-abc123"
NUMBER_ID = "bbbbbbbb-0000-4000-8000-000000000001"
WEBHOOK_ID = "cccccccc-0000-4000-8000-000000000001"
SCRIPT_ID = "dddddddd-0000-4000-8000-000000000001"
BIN_ID = "eeeeeeee-0000-4000-8000-000000000001"
CXML = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>\n  <Dial>+15550100002</Dial>\n</Response>")


@pytest.fixture(autouse=True)
def creds(monkeypatch):
    monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", PROJECT)
    monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "tok")
    monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
    for var in ("PROJECT_ID", "REST_API_TOKEN", "SWSH_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    cli.Ctx.as_json = False
    cli.Ctx.profile_name = None


def number(**overrides):
    """A phone number row, on a hosted cXML bin for voice by default."""
    row = {
        "id": NUMBER_ID, "number": "+14405550168", "name": "Fax Number",
        "call_handler": "laml_webhooks",
        "calling_handler_resource_id": WEBHOOK_ID,
        "call_request_url": f"{BASE}/laml-bins/{BIN_ID}",
        "call_status_callback_url": None,
        "message_handler": "laml_webhooks",
        "messaging_handler_resource_id": None,
        "message_request_url": None,
    }
    row.update(overrides)
    return row


def webhook_resource(url):
    return {"id": WEBHOOK_ID, "display_name": url, "type": "cxml_webhook",
            "cxml_webhook": {"id": "cccccccc-0000-4000-8000-000000000002",
                             "name": url, "used_for": "calling",
                             "primary_request_url": url,
                             "primary_request_method": "POST",
                             "fallback_request_url": None}}


def cxml_listing():
    return {"data": [{"id": SCRIPT_ID, "display_name": "hide my caller id",
                      "type": "cxml_script",
                      "cxml_script": {"id": BIN_ID, "name": "hide my caller id",
                                      "script_type": "calling", "contents": CXML}}]}


def mock_number(row):
    respx.get(f"{BASE}/api/relay/rest/phone_numbers/{NUMBER_ID}").mock(
        return_value=httpx.Response(200, json=row))


def expand(row):
    """Run the expansion the way the command does, and hand back the result."""
    import asyncio

    from swsh.client import SwshClient
    from swsh.config import resolve

    async def go():
        async with SwshClient(resolve()) as client:
            return await routing.expand(client, resources.get("numbers"), row)

    return asyncio.run(go())


class TestTheHandlerDecides:
    """A row carries every pointer it has ever had; one field says which is live."""

    @respx.mock
    def test_only_the_live_handlers_fields_are_settings(self):
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200, json=webhook_resource(f"{BASE}/laml-bins/{BIN_ID}")))
        respx.get(f"{BASE}/api/fabric/resources/cxml_scripts").mock(
            return_value=httpx.Response(200, json=cxml_listing()))

        result = expand(number())
        voice = result.channels[0]
        assert voice.name == "voice" and voice.handler == "laml_webhooks"
        assert "call_request_url" in voice.live
        # relay_script's field belongs to a handler that is not in effect
        assert "call_relay_script_url" not in voice.live

    @respx.mock
    def test_a_pointer_from_an_earlier_configuration_is_reported_as_unused(self):
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200, json=webhook_resource("https://example.test/hook")))
        respx.get("https://example.test/hook").mock(
            return_value=httpx.Response(200, headers={"content-type": "text/xml"}, text=CXML))

        # On relay_script, but still carrying the cXML application it used to use.
        result = expand(number(call_handler="relay_script",
                               call_relay_script_url="https://example.test/hook",
                               call_laml_application_id="ffffffff-0000-4000-8000-000000000001"))
        # Both the cXML application *and* the webhook URL it used before that:
        # every handler this number has ever worn leaves its field behind.
        assert result.unused == {
            "call_request_url": f"{BASE}/laml-bins/{BIN_ID}",
            "call_laml_application_id": "ffffffff-0000-4000-8000-000000000001"}
        assert set(result.channels[0].live) == {"call_relay_script_url"}

    @respx.mock
    def test_an_unset_pointer_says_so_rather_than_showing_nothing(self):
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200, json=webhook_resource("https://example.test/hook")))
        respx.get("https://example.test/hook").mock(return_value=httpx.Response(204))

        result = expand(number())
        messaging = result.channels[1]
        assert messaging.target is None
        assert messaging.note == "this handler names no target resource"


class TestFollowingTheRouting:
    @respx.mock
    def test_a_hosted_bin_resolves_to_its_script_and_its_document(self):
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200, json=webhook_resource(f"{BASE}/laml-bins/{BIN_ID}")))
        listing = respx.get(f"{BASE}/api/fabric/resources/cxml_scripts").mock(
            return_value=httpx.Response(200, json=cxml_listing()))

        target = expand(number()).channels[0].target
        assert target.kind == "cxml_webhook"
        # A bin URL carries the script's *inner* id, which no route accepts, so
        # the only way through is the listing.
        assert listing.called
        script = target.child
        assert script.kind == "cxml_script" and script.id == SCRIPT_ID
        assert [d.label for d in script.documents] == ["contents"]
        assert script.documents[0].language == "xml"
        assert script.documents[0].text == CXML

    @respx.mock
    def test_a_bin_with_no_matching_script_says_which_id_was_missing(self):
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200, json=webhook_resource(f"{BASE}/laml-bins/{BIN_ID}")))
        respx.get(f"{BASE}/api/fabric/resources/cxml_scripts").mock(
            return_value=httpx.Response(200, json={"data": []}))

        child = expand(number()).channels[0].target.child
        assert child.id == BIN_ID and "no script" in child.note
        assert not child.documents

    @respx.mock
    def test_a_script_resource_carries_its_own_document_and_is_not_followed(self):
        # A swml_script's request_url is its own bin URL; following it would loop.
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200, json={
                "id": WEBHOOK_ID, "display_name": "greeting", "type": "swml_script",
                "swml_script": {"id": "0000a001", "display_name": "greeting",
                                "request_url": f"{BASE}/relay-bins/0000a001",
                                "contents": {"version": "1.0.0", "sections": {"main": []}}}}))

        target = expand(number()).channels[0].target
        assert target.child is None
        assert target.documents[0].language == "json"
        assert json.loads(target.documents[0].text)["version"] == "1.0.0"

    @respx.mock
    def test_a_deleted_target_is_reported_not_raised(self):
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(404, json={"errors": []}))

        target = expand(number()).channels[0].target
        assert target.kind == "unknown" and "deleted" in target.note

    @respx.mock
    def test_a_scalar_list_stays_a_setting(self):
        # codecs and ciphers as a six-line JSON block would bury the settings
        # beside them; only a structure with shape is a document.
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200, json={
                "id": WEBHOOK_ID, "display_name": "reception", "type": "sip_endpoint",
                "sip_endpoint": {"id": "0000a002", "username": "reception",
                                 "codecs": ["PCMA", "PCMU"], "encryption": "optional"}}))

        target = expand(number()).channels[0].target
        assert target.fields["codecs"] == ["PCMA", "PCMU"]
        assert not target.documents


class TestFetchingOffTheSpace:
    """External webhooks are followed too. One rule applies."""

    @respx.mock
    def test_the_project_token_never_leaves_the_space(self):
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200,
                                        json=webhook_resource("https://tunnel.test/hook")))
        external = respx.get("https://tunnel.test/hook").mock(
            return_value=httpx.Response(200, headers={"content-type": "text/xml"}, text=CXML))

        result = expand(number())
        assert result.channels[0].target.child.documents[0].text == CXML
        # The whole point: somebody else's server is handed no credentials.
        sent = external.calls[0].request
        assert "authorization" not in {k.lower() for k in sent.headers}

    @respx.mock
    def test_an_error_page_is_a_status_not_a_document(self):
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200,
                                        json=webhook_resource("https://tunnel.test/hook")))
        respx.get("https://tunnel.test/hook").mock(
            return_value=httpx.Response(404, headers={"content-type": "text/html"},
                                        text="<html>" + "x" * 5000 + "</html>"))

        child = expand(number()).channels[0].target.child
        assert child.fields["status"] == 404
        assert child.note == "HTTP 404 — no document returned"
        assert not child.documents  # 5kB of somebody's 404 page helps nobody

    @respx.mock
    def test_a_tunnel_that_is_down_reports_the_failure_and_carries_on(self):
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200,
                                        json=webhook_resource("https://tunnel.test/hook")))
        respx.get("https://tunnel.test/hook").mock(side_effect=httpx.ConnectError("refused"))

        result = expand(number())
        assert "could not be fetched" in result.channels[0].target.child.note
        assert len(result.channels) == 2  # the messaging channel still resolved


class TestTheCommand:
    @respx.mock
    def test_full_renders_the_tree_with_the_document_in_it(self):
        mock_number(number())
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200, json=webhook_resource(f"{BASE}/laml-bins/{BIN_ID}")))
        respx.get(f"{BASE}/api/fabric/resources/cxml_scripts").mock(
            return_value=httpx.Response(200, json=cxml_listing()))

        result = runner.invoke(cli.app, ["numbers", "get", NUMBER_ID, "--full"])
        assert result.exit_code == 0, result.output
        assert "VOICE" in result.output and "laml_webhooks" in result.output
        assert "cxml_script" in result.output
        assert "+15550100002" in result.output  # the document itself

    @respx.mock
    def test_full_json_is_one_nested_object(self):
        mock_number(number())
        respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200, json=webhook_resource(f"{BASE}/laml-bins/{BIN_ID}")))
        respx.get(f"{BASE}/api/fabric/resources/cxml_scripts").mock(
            return_value=httpx.Response(200, json=cxml_listing()))

        result = runner.invoke(cli.app, ["numbers", "get", NUMBER_ID, "--full", "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["id"] == NUMBER_ID
        assert [c["channel"] for c in payload["channels"]] == ["voice", "messaging"]
        document = payload["channels"][0]["points_to"]["points_to"]["documents"][0]
        assert document["text"] == CXML

    @respx.mock
    def test_without_full_nothing_is_followed(self):
        mock_number(number())
        fabric = respx.get(f"{BASE}/api/fabric/resources/{WEBHOOK_ID}").mock(
            return_value=httpx.Response(200, json=webhook_resource("https://tunnel.test/hook")))

        result = runner.invoke(cli.app, ["numbers", "get", NUMBER_ID])
        assert result.exit_code == 0, result.output
        assert not fabric.called  # plain `get` stays one request

    def test_the_flag_exists_only_where_routing_is_declared(self):
        assert "--full" in runner.invoke(cli.app, ["numbers", "get", "--help"]).output
        assert "--full" not in runner.invoke(cli.app, ["queues", "get", "--help"]).output
        declared = {r.key for r in resources.RESOURCES if r.routing}
        assert declared == {"numbers"}

    def test_every_route_names_real_fields(self):
        for resource in resources.RESOURCES:
            names = {f.name for f in resource.fields}
            for route in resource.routing:
                assert route.handler in names, (resource.key, route.handler)
                # The pointer is followed, not edited, so it need not be a field;
                # when it is one, it has to be spelled the same way.
                assert route.pointer, (resource.key, route.channel)
