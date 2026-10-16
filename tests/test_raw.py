"""`--raw`: the response the platform sent, not sw's view of it.

`--json` is sw's own shape — rows lifted out of an envelope, `--limit` applied,
a call flattened to the fields the registry models. `--raw` is the body of the
one call the command is about, byte for byte as far as the client parsed it.

These pin the three things that make it trustworthy: nothing sw renders leaks
into the document, the response shown is the one the command is *about* (not the
lookup it needed first), and a command with no single response refuses before it
does any work rather than printing a shaped answer that looks raw.
"""

from __future__ import annotations

import json

import pytest
import typer
from typer.testing import CliRunner

from swsh import cli

runner = CliRunner()

PN1 = "aaaaaaaa-0000-4000-8000-0000000000a1"
PN2 = "aaaaaaaa-0000-4000-8000-0000000000a2"

# An envelope with everything --json drops: the paging links, and a field the
# registry does not model.
ENVELOPE = {
    "data": [
        {"id": PN1, "number": "+12095550183", "name": "Fax Number", "undocumented": 1},
        {"id": PN2, "number": "+14405550168", "name": "Support", "undocumented": 2},
    ],
    "links": {"self": "https://x/api/numbers?page=1",
              "next": "https://x/api/numbers?page=2"},
}


@pytest.fixture(autouse=True)
def clean_context(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.config, "config_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cli.config, "load_dotenv", lambda path=None: {})
    for var in ("SIGNALWIRE_PROJECT_ID", "SIGNALWIRE_API_TOKEN", "SIGNALWIRE_SPACE",
                "PROJECT_ID", "REST_API_TOKEN", "SWSH_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    cli.Ctx.as_json = False
    cli.Ctx.raw = False
    cli.Ctx.raw_emitted = False
    cli.Ctx.profile_name = None


@pytest.fixture
def captured(monkeypatch):
    calls: list[dict] = []

    async def fake_invoke(self, resource, op, *, resource_id=None, body=None, **params):
        calls.append({"key": resource.key, "op": op, "id": resource_id, "body": body})
        if op.startswith("list"):  # the CRUD verb and every listing extra
            return ENVELOPE
        if op == "read":
            return {"id": resource_id, "number": "+12095550183", "undocumented": 1}
        if op == "create":
            return {"id": "new-1", "undocumented": 1, **(body or {})}
        if op == "update":
            return {"id": resource_id, "updated": True}
        return {}

    async def fake_rest_call(self, method, path, *, params=None, body=None):
        """The second page of ENVELOPE, and the last.

        Needed because resolving a handle now walks the whole collection — a
        lookup that stopped at page one could answer "no such number" about a
        number that exists. `--raw` must still show the *read*, not this.
        """
        calls.append({"key": "page", "op": "list", "id": None, "body": None})
        return {"data": [], "links": {"self": path}}

    monkeypatch.setattr(cli.SwshClient, "invoke", fake_invoke)
    monkeypatch.setattr(cli.SwshClient, "rest_call", fake_rest_call)
    return calls


class TestItIsTheResponse:
    def test_list_is_the_envelope_paging_links_and_all(self, captured):
        result = runner.invoke(cli.app, ["numbers", "list", "--raw"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == ENVELOPE

    def test_json_is_still_sws_shape(self, captured):
        """The contrast that justifies the flag existing."""
        result = runner.invoke(cli.app, ["numbers", "list", "--json", "-n", "1"])
        assert json.loads(result.output) == [ENVELOPE["data"][0]]

    def test_limit_does_not_apply_to_a_raw_page(self, captured):
        result = runner.invoke(cli.app, ["numbers", "list", "--raw", "-n", "1"])
        assert len(json.loads(result.output)["data"]) == 2

    def test_get_is_the_record_and_nothing_else(self, captured):
        result = runner.invoke(cli.app, ["queues", "get", "q-1", "--raw"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {"id": "q-1", "number": "+12095550183",
                                             "undocumented": 1}

    def test_the_response_shown_is_the_one_the_command_is_about(self, captured):
        """A handle costs a list call first; the document is still the read."""
        result = runner.invoke(cli.app, ["numbers", "get", "Fax Number", "--raw"])
        assert result.exit_code == 0, result.output
        assert captured[0]["op"] == "list" and captured[-1]["op"] == "read"
        assert json.loads(result.output)["id"] == PN1

    def test_create_and_update_show_what_came_back(self, captured):
        created = runner.invoke(cli.app, ["queues", "create", "--set", "name=support",
                                          "--raw"])
        assert json.loads(created.output) == {"id": "new-1", "undocumented": 1,
                                              "name": "support"}
        updated = runner.invoke(cli.app, ["queues", "update", "q-1", "--set", "name=x",
                                          "--raw"])
        assert json.loads(updated.output) == {"id": "q-1", "updated": True}

    def test_delete_answers_once_per_id_in_the_order_given(self, captured):
        one = runner.invoke(cli.app, ["numbers", "release", PN1, "-y", "--raw"])
        assert json.loads(one.output) == {}
        several = runner.invoke(cli.app, ["numbers", "release", PN1, PN2, "-y", "--raw"])
        assert json.loads(several.output) == [{}, {}]

    def test_an_extra_shows_its_payload_undrilled(self, captured):
        result = runner.invoke(cli.app, ["groups", "memberships", "g-1", "--raw"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == ENVELOPE  # not ENVELOPE["data"]

    def test_nothing_rendered_leaks_into_the_document(self, captured):
        """Every byte on stdout has to be the response, or `| jq` breaks."""
        for argv in (["numbers", "list", "--raw"],
                     ["numbers", "get", "Fax Number", "--raw"],
                     ["numbers", "buy", "--set", "number=+15551234567", "--raw"],
                     ["numbers", "release", PN1, "-y", "--raw"]):
            result = runner.invoke(cli.app, argv)
            assert result.exit_code == 0, (argv, result.output)
            json.loads(result.output)  # the whole of stdout, not a prefix of it


class TestItRefusesRatherThanMislead:
    def test_match_is_refused_because_it_spans_requests(self, captured):
        result = runner.invoke(cli.app, ["numbers", "list", "--raw", "-m", "209"])
        assert result.exit_code == 2
        assert "--match" in result.output

    def test_full_is_refused_and_before_the_read(self, captured):
        result = runner.invoke(cli.app, ["numbers", "get", PN1, "--full", "--raw"])
        assert result.exit_code == 2
        assert "--full" in result.output
        assert captured == []

    def test_a_command_with_no_single_response_says_so(self, captured):
        for argv in (["calls", "list", "--raw"], ["doctor", "--raw"],
                     ["profile", "list", "--raw"], ["docs", "--list", "--raw"]):
            result = runner.invoke(cli.app, argv)
            assert result.exit_code == 2, (argv, result.output)
            assert "--raw" in result.output

    def test_it_refuses_before_the_command_does_any_work(self, captured, monkeypatch):
        """`listen` opens a tunnel and rewrites every number's status callback.
        A refusal afterwards is not a refusal."""
        monkeypatch.setattr(cli.prompts, "interactive", lambda: False)
        result = runner.invoke(cli.app, ["listen", "--raw"])
        assert result.exit_code == 2
        assert captured == []


class TestItBehavesLikeTheOtherGlobalFlags:
    def test_every_command_advertises_it(self):
        for argv in (["numbers", "list", "--help"], ["whoami", "--help"],
                     ["queues", "create", "--help"], ["profile", "list", "--help"]):
            assert "--raw" in runner.invoke(cli.app, argv).output, argv

    def test_order_is_irrelevant_and_the_root_does_not_take_it(self, captured):
        assert runner.invoke(cli.app, ["numbers", "list", "--raw"]).exit_code == 0
        # on the root it is a usage error, exactly like --json
        assert runner.invoke(cli.app, ["--raw", "numbers", "list"]).exit_code == 2

    def test_it_implies_json_so_a_missing_field_errors_instead_of_prompting(
            self, captured, monkeypatch):
        monkeypatch.setattr(cli.prompts, "interactive", lambda: True)
        result = runner.invoke(cli.app, ["queues", "create", "--raw"])
        assert result.exit_code == 2
        assert captured == []

    def test_the_flag_does_not_leak_between_invocations(self, captured):
        runner.invoke(cli.app, ["numbers", "list", "--raw"])
        assert cli.Ctx.raw is False or runner.invoke(
            cli.app, ["numbers", "list", "--json", "-n", "1"]).exit_code == 0
        result = runner.invoke(cli.app, ["numbers", "list", "--json", "-n", "1"])
        assert json.loads(result.output) == [ENVELOPE["data"][0]]

    def test_sw_api_is_raw_already_and_stays_that_way(self, monkeypatch):
        # `sw api` builds the URL from the profile, so this one needs credentials.
        monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "p")
        monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "t")
        monkeypatch.setenv("SIGNALWIRE_SPACE", "nowhere.invalid")
        body = '{"hello":"world"}'

        class Response:
            status_code = 200
            text = body
            headers: dict[str, str] = {}

            def json(self):
                return json.loads(body)

        async def fake_raw_request(self, method, path, **kw):
            return Response()

        monkeypatch.setattr(cli.SwshClient, "raw_request", fake_raw_request)
        result = runner.invoke(cli.app, ["api", "/api/relay/rest/queues", "--raw"])
        assert result.exit_code == 0, result.output
        assert result.output.strip() == body


def test_raw_capable_is_the_only_way_a_command_opts_in():
    """A new command gets the refusal for free; it has to claim the capability."""
    @cli.raw_capable
    def marked() -> None:
        pass

    def unmarked() -> None:
        pass

    cli.Ctx.raw = True
    cli._raw_guard(marked)  # no raise
    with pytest.raises(typer.Exit):
        cli._raw_guard(unmarked)
