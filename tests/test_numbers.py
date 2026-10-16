"""Buying a phone number.

You cannot type an E.164 you have never seen, so `n` on the numbers view
searches inventory first and buys the row you pick. The SDK call is stubbed
here; what matters is the filters sent, the guards, and that nothing is
purchased without a confirmation.
"""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Input, Select, Static

from swsh.config import Profile
from swsh.tui.app import SwshApp
from swsh.tui.numbers import NUMBER_TYPES, NumberSearchScreen

FAKE = Profile(name="test", project="p", token="t", space="nowhere.invalid")

SAMPLE = {
    "data": [
        {"e164": "+12055550128", "national_number_formatted": "(205) 555-0128",
         "region": "AL", "rate_center": "DORA", "capabilities": ["voice", "sms"]},
        {"e164": "+12055550129", "national_number_formatted": "(205) 555-0129",
         "region": "AL", "rate_center": "DORA", "capabilities": ["voice"]},
    ]
}


class Recorder:
    def __init__(self, result: Any = None):
        self.calls: list[tuple[str, tuple, dict]] = []
        self.result = SAMPLE if result is None else result

    async def __call__(self, path: str, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((path, args, kwargs))
        return self.result


class HttpRecorder:
    """Stands in for SwshClient.rest_call. Buying a number is a REST create now,
    so the assertion is on the method and URL rather than a dotted SDK path."""

    def __init__(self, result: Any = None):
        self.calls: list[tuple[str, str, dict, dict]] = []
        self.result = {"id": "pn-1"} if result is None else result

    async def __call__(self, method: str, path: str, *, params: Any = None,
                       body: Any = None) -> Any:
        self.calls.append((method, path, dict(params or {}), dict(body or {})))
        return self.result

    def routes(self) -> list[tuple[str, str]]:
        return [(c[0], c[1]) for c in self.calls]


class Host(App[None]):
    CSS_PATH = "../swsh/tui/app.css"

    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield Static("host")


async def open_search(recorder):
    class _C:
        call_sdk = recorder

    app = Host(_C())
    result: dict = {}
    async with app.run_test() as pilot:
        app.push_screen(NumberSearchScreen(_C()), lambda r: result.update(got=r))
        await pilot.pause()
        yield app, pilot, result


def status_of(app) -> str:
    return str(app.screen.query_one("#numsearch-status", Static).content)


class TestSearchVocabulary:
    def test_search_uses_local_not_longcode(self):
        """`longcode` is the owned-number vocabulary; search 400s on it."""
        assert NUMBER_TYPES == ("local", "toll-free")
        assert "longcode" not in NUMBER_TYPES


class TestFilters:
    async def test_area_code_search_sends_the_right_params(self):
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-areacode", Input).value = "205"
            app.screen.action_search()
            await pilot.pause(0.3)

            path, _, params = recorder.calls[0]
            assert path == "phone_numbers.search"
            assert params["areacode"] == "205"
            assert params["number_type"] == "local"
            assert params["max_results"] == 25

    async def test_results_render(self):
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-areacode", Input).value = "205"
            app.screen.action_search()
            await pilot.pause(0.3)
            assert app.screen.query_one("#numsearch-results", DataTable).row_count == 2
            assert "2 available" in status_of(app)

    async def test_city_without_region_is_refused_before_calling(self):
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-city", Input).value = "Birmingham"
            app.screen.action_search()
            await pilot.pause(0.2)
            assert recorder.calls == []  # the API would 422; catch it locally
            assert "region" in status_of(app)

    async def test_toll_free_disables_geography_fields(self):
        """Toll-free has no area code / region / city, so rather than let someone
        type a value the API rejects, those fields are disabled outright."""
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-type", Select).value = "toll-free"
            await pilot.pause(0.2)
            assert app.screen.query_one("#f-areacode", Input).disabled
            assert app.screen.query_one("#f-region", Input).disabled
            assert app.screen.query_one("#f-city", Input).disabled
            # switching back to local re-enables them
            app.screen.query_one("#f-type", Select).value = "local"
            await pilot.pause(0.2)
            assert not app.screen.query_one("#f-areacode", Input).disabled

    async def test_empty_search_is_refused(self):
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.action_search()
            await pilot.pause(0.2)
            assert recorder.calls == []

    async def test_bare_toll_free_search_is_allowed(self):
        """Toll-free has no geography, so type alone is a valid search — the
        platform returns available toll-free inventory."""
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-type", Select).value = "toll-free"
            app.screen.action_search()
            await pilot.pause(0.3)
            assert recorder.calls
            _, _, params = recorder.calls[0]
            assert params["number_type"] == "toll-free"
            assert "areacode" not in params

    async def test_no_matches_says_so(self):
        recorder = Recorder(result={"data": []})
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-pattern", Input).value = "1234"
            app.screen.action_search()
            await pilot.pause(0.3)
            assert "nothing matched" in status_of(app)


class TestDigitPattern:
    """The digit box must reach contains / starts_with / ends_with — the
    reported gap was that you could not search 'ends with' at all."""

    async def test_ends_with_maps_to_ends_with_param(self):
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-pattern", Input).value = "1234"
            app.screen.query_one("#f-match", Select).value = "ends with"
            app.screen.action_search()
            await pilot.pause(0.3)
            _, _, params = recorder.calls[0]
            assert params["ends_with"] == "1234"
            assert "contains" not in params

    async def test_starts_with_maps_to_starts_with_param(self):
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-pattern", Input).value = "205"
            app.screen.query_one("#f-match", Select).value = "starts with"
            app.screen.action_search()
            await pilot.pause(0.3)
            _, _, params = recorder.calls[0]
            assert params["starts_with"] == "205"

    async def test_pattern_must_be_three_to_seven_digits(self):
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-pattern", Input).value = "12"  # too short
            app.screen.action_search()
            await pilot.pause(0.2)
            assert recorder.calls == []
            assert "digits" in status_of(app)


class TestSearchTriggers:
    """Every obvious gesture must run the search.

    The original report was "search never lists anything". Two causes: the
    default type was `longcode`, which the search API rejects with a 400, and
    the status line rendered at zero height so the error was invisible. Enter
    was also unbound, so typing an area code and pressing return did nothing.
    """

    async def test_enter_in_a_filter_searches(self):
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-areacode", Input).value = "205"
            app.screen.filter_submitted()
            await pilot.pause(0.3)
            assert recorder.calls

    async def test_the_search_button_searches(self):
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-areacode", Input).value = "205"
            app.screen.search_pressed()
            await pilot.pause(0.3)
            assert recorder.calls

    async def test_default_type_is_accepted_by_the_search_api(self):
        """`longcode` is a 400 here; `local` is the search vocabulary."""
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-areacode", Input).value = "205"
            app.screen.action_search()
            await pilot.pause(0.3)
            assert recorder.calls[0][2]["number_type"] == "local"

    async def test_status_line_is_actually_visible(self):
        """It was height 1 with vertical padding, leaving zero content rows."""
        recorder = Recorder()
        async for app, pilot, _ in open_search(recorder):
            app.screen.query_one("#f-areacode", Input).value = "205"
            app.screen.action_search()
            await pilot.pause(0.3)
            assert app.screen.query_one("#numsearch-status", Static).size.height >= 1


class TestBuying:
    async def test_buy_returns_the_selected_number(self):
        recorder = Recorder()
        async for app, pilot, result in open_search(recorder):
            app.screen.query_one("#f-areacode", Input).value = "205"
            app.screen.action_search()
            await pilot.pause(0.3)
            app.screen.buy_pressed()
            await pilot.pause(0.2)
            assert result["got"] == "+12055550128"

    async def test_buy_without_a_selection_does_nothing(self):
        recorder = Recorder()
        async for app, pilot, result in open_search(recorder):
            app.screen.buy_pressed()
            await pilot.pause(0.2)
            assert "got" not in result
            assert "select a number" in status_of(app)


class TestAppIntegration:
    async def test_new_on_numbers_opens_search_not_a_blank_form(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("numbers")
            await pilot.pause(0.4)
            app.action_new()
            await pilot.pause(0.3)
            assert isinstance(app.screen, NumberSearchScreen)

    async def test_purchase_is_gated_behind_a_confirmation(self):
        """Buying bills the project, so it must never happen on one keystroke."""
        from swsh.tui.app import ConfirmScreen

        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("numbers")
            await pilot.pause(0.4)
            recorder = HttpRecorder()
            app.client.rest_call = recorder

            app.action_new()
            await pilot.pause(0.3)
            app.screen.dismiss("+12055550128")
            await pilot.pause(0.4)

            assert isinstance(app.screen, ConfirmScreen)
            purchase = ("POST", "/api/relay/rest/phone_numbers")
            assert purchase not in recorder.routes()  # nothing bought yet

            await pilot.press("y")
            await pilot.pause(0.4)
            create = next(c for c in recorder.calls if (c[0], c[1]) == purchase)
            assert create[3] == {"number": "+12055550128"}
