"""A listing is the whole collection, not the first page of it.

`--limit` used to be a slice applied to whatever one request returned, and the
API's `next` link was read in exactly three places, none of them a resource
listing. Two things followed, both silent and both found live:

    sw logs list -n 200 --json | jq length   ->  50    (the API returns 200)
    sw resources list -m "Test AI API"       ->  "no rows"

The second is the one that matters. That resource existed — row 80 of 134 — and
`sw` said it did not. A search that confidently reports "not found" about a
record that is present is the worst answer the tool can give, because there is
nothing about it to notice.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from swsh import cli

runner = CliRunner()


def envelope(rows: list[dict], next_link: str | None) -> dict:
    links = {"self": "https://x/api/p0"}
    if next_link:
        links["next"] = next_link
    return {"data": rows, "links": links}


def row(index: int) -> dict:
    return {"id": f"id-{index:03d}", "name": f"row-{index:03d}",
            "display_name": f"row-{index:03d}"}


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
def paged(monkeypatch):
    """A collection of 134 rows served 50 at a time, like the real thing.

    Records every request so a test can assert on how many pages were walked,
    which is the difference between "correct" and "correct but pathological".
    """
    total = 134
    page = 50
    requests: list[str] = []

    def slice_at(offset: int) -> dict:
        rows = [row(i) for i in range(offset, min(offset + page, total))]
        nxt = f"/api/x?offset={offset + page}" if offset + page < total else None
        return envelope(rows, nxt)

    async def fake_invoke(self, resource, op, *, resource_id=None, body=None, **params):
        if op == "list":
            requests.append("/api/x?offset=0")
            return slice_at(0)
        return {"id": resource_id or "x"}

    async def fake_rest_call(self, method, path, *, params=None, body=None):
        requests.append(path)
        return slice_at(int(path.rsplit("=", 1)[1]))

    monkeypatch.setattr(cli.SwshClient, "invoke", fake_invoke)
    monkeypatch.setattr(cli.SwshClient, "rest_call", fake_rest_call)
    monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "p")
    monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "t")
    monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
    return requests


class TestLimitMeansWhatItSays:
    def test_it_pages_past_the_first_response(self, paged):
        result = runner.invoke(cli.app, ["resources", "list", "-n", "120", "--json"])
        assert result.exit_code == 0, result.output
        assert len(json.loads(result.output)) == 120

    def test_a_limit_inside_one_page_costs_one_request(self, paged):
        result = runner.invoke(cli.app, ["resources", "list", "-n", "10", "--json"])
        assert len(json.loads(result.output)) == 10
        assert len(paged) == 1, "no reason to fetch a second page for ten rows"

    def test_a_limit_past_the_end_gets_everything_there_is(self, paged):
        result = runner.invoke(cli.app, ["resources", "list", "-n", "500", "--json"])
        assert len(json.loads(result.output)) == 134

    def test_it_stops_as_soon_as_the_limit_is_met(self, paged):
        runner.invoke(cli.app, ["resources", "list", "-n", "60", "--json"])
        assert len(paged) == 2, "60 rows needs two 50-row pages, not three"

    def test_a_collection_with_no_next_link_is_one_request(self, monkeypatch):
        seen: list[str] = []

        async def one_page(self, resource, op, **kw):
            seen.append(op)
            return envelope([row(i) for i in range(3)], None)

        monkeypatch.setattr(cli.SwshClient, "invoke", one_page)
        monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "p")
        monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "t")
        monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
        result = runner.invoke(cli.app, ["resources", "list", "-n", "200", "--json"])
        assert len(json.loads(result.output)) == 3
        assert seen == ["list"]


class TestASearchCannotReportAFalseNegative:
    def test_it_finds_a_row_beyond_the_first_page(self, paged):
        """`row-080` is the shape of the live case this was found in."""
        result = runner.invoke(cli.app, ["resources", "list", "-m", "row-080", "--json"])
        assert result.exit_code == 0, result.output
        found = json.loads(result.output)
        assert [r["display_name"] for r in found] == ["row-080"]

    def test_it_walks_the_whole_collection_regardless_of_limit(self, paged):
        runner.invoke(cli.app, ["resources", "list", "-m", "row-133", "-n", "5", "--json"])
        assert len(paged) == 3, "a search that stops early can answer 'no rows' wrongly"

    def test_a_genuine_miss_is_still_a_miss(self, paged):
        result = runner.invoke(cli.app, ["resources", "list", "-m", "nothing-here",
                                         "--json"])
        assert json.loads(result.output) == []


class TestTheWalkIsBounded:
    def test_a_repeating_next_link_does_not_loop_forever(self, monkeypatch):
        """A malformed envelope is a bug on the platform, not a hang here."""
        calls: list[str] = []

        async def same_page(self, resource, op, **kw):
            calls.append("invoke")
            return envelope([row(0)], "/api/loop")

        async def rest_call(self, method, path, *, params=None, body=None):
            calls.append(path)
            return envelope([row(0)], "/api/loop")

        monkeypatch.setattr(cli.SwshClient, "invoke", same_page)
        monkeypatch.setattr(cli.SwshClient, "rest_call", rest_call)
        monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "p")
        monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "t")
        monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
        result = runner.invoke(cli.app, ["resources", "list", "-n", "500", "--json"])
        assert result.exit_code == 0, result.output
        assert len(calls) == 2, "the second page repeats the first; stop there"

    def test_an_endless_collection_stops_at_the_cap(self, monkeypatch):
        seq = {"n": 0}

        async def invoke(self, resource, op, **kw):
            return envelope([row(0)], "/api/x?offset=1")

        async def rest_call(self, method, path, *, params=None, body=None):
            seq["n"] += 1
            return envelope([row(seq["n"])], f"/api/x?offset={seq['n'] + 1}")

        monkeypatch.setattr(cli.SwshClient, "invoke", invoke)
        monkeypatch.setattr(cli.SwshClient, "rest_call", rest_call)
        monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "p")
        monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "t")
        monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
        result = runner.invoke(cli.app, ["resources", "list", "-m", "row", "--json"])
        assert result.exit_code == 0, result.output
        assert seq["n"] == cli._PAGE_CAP


class TestTheCockpitCountsWhatItHolds:
    """The pane title printed `len(self.rows)` after one request, so a 134-row
    collection read as `50` — a ceiling presented as a total."""

    async def _loaded(self, monkeypatch, total: int, cap: int | None = None):
        from swsh.client import SwshClient
        from swsh.config import Profile
        from swsh.tui.app import SwshApp

        page = 50

        def slice_at(offset: int) -> dict:
            rows = [row(i) for i in range(offset, min(offset + page, total))]
            nxt = f"/api/x?offset={offset + page}" if offset + page < total else None
            return envelope(rows, nxt)

        async def invoke(self, resource, op, **kw):
            return slice_at(0)

        async def rest_call(self, method, path, *, params=None, body=None):
            return slice_at(int(path.rsplit("=", 1)[1]))

        monkeypatch.setattr(SwshClient, "invoke", invoke)
        monkeypatch.setattr(SwshClient, "rest_call", rest_call)
        app = SwshApp(profile=Profile(name="t", project="p", token="tok",
                                      space="nowhere.invalid"))
        if cap is not None:
            monkeypatch.setattr(SwshApp, "PAGE_CAP", cap)
        return app

    async def test_it_holds_every_row_not_the_first_page(self, monkeypatch):
        app = await self._loaded(monkeypatch, total=134)
        async with app.run_test(size=(140, 40)) as pilot:
            app.switch_to("resources")
            for _ in range(40):
                await pilot.pause(0.05)
                if len(app.rows) >= 134:
                    break
            assert len(app.rows) == 134
            assert app.rows_capped is False

    async def test_a_capped_walk_says_so_in_the_count(self, monkeypatch):
        """`100+` is honest about a ceiling; `100` would not be."""
        app = await self._loaded(monkeypatch, total=1000, cap=1)
        async with app.run_test(size=(140, 40)) as pilot:
            app.switch_to("resources")
            for _ in range(40):
                await pilot.pause(0.05)
                if app.rows:
                    break
            assert app.rows_capped is True
            assert "+" in str(app.query_one("#pane-title").content)
