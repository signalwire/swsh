"""Search for and buy phone numbers.

Buying a number is the one create flow that cannot start from a blank form:
you do not know the number until the platform offers you one. So `n` on the
numbers view opens this instead, which searches inventory first and buys the
row you pick.

Filters and result fields are taken from the live search API:
``areacode``, ``contains``, ``region``, ``city`` (only valid together with
``region``), ``number_type`` and ``max_results``.
"""

from __future__ import annotations

from typing import Any

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from ..client import SwshClient, SwshError

# Search uses `local` / `toll-free`. Note this is a *different* vocabulary from
# the `number_type` on an owned number, which reads back as `longcode`; sending
# `longcode` to search is a 400.
NUMBER_TYPES = ("local", "toll-free")
COLUMNS = ("number", "formatted", "region", "rate center", "capabilities")

# The digit-pattern filters the search API accepts. Each maps a friendly label
# to its API parameter; all three want 3-7 digits (the platform rejects shorter,
# longer, or wildcarded values), so one shared rule covers them.
MATCH_MODES = {
    "contains": "contains",
    "starts with": "starts_with",
    "ends with": "ends_with",
}
PATTERN_MIN, PATTERN_MAX = 3, 7


class NumberSearchScreen(ModalScreen[str | None]):
    """Search available inventory, then return the chosen E.164 number."""

    BINDINGS = [
        Binding("escape", "cancel", "cancel"),
        Binding("ctrl+s", "search", "search"),
    ]

    def __init__(self, client: SwshClient):
        super().__init__()
        self.client = client
        self.results: list[dict[str, Any]] = []
        self.searching = False

    def compose(self) -> ComposeResult:
        with Vertical(id="numsearch-box"):
            with Horizontal(id="form-header"):
                yield Label("buy a phone number", id="form-title")
                yield Button("✕", id="numsearch-close", classes="close-x")
            # Row 1: type drives which geographic filters make sense. Toll-free
            # numbers have no area code / region / city, so those grey out.
            with Horizontal(id="numsearch-filters"):
                with Vertical():
                    yield Label("type", classes="form-label")
                    yield Select(
                        [(t, t) for t in NUMBER_TYPES],
                        value="local", id="f-type", allow_blank=False,
                    )
                with Vertical(id="wrap-areacode"):
                    yield Label("area code", classes="form-label")
                    yield Input(placeholder="205", id="f-areacode")
                with Vertical(id="wrap-region"):
                    yield Label("region", classes="form-label")
                    yield Input(placeholder="AL", id="f-region")
                with Vertical(id="wrap-city"):
                    yield Label("city (needs region)", classes="form-label")
                    yield Input(placeholder="Birmingham", id="f-city")
            # Row 2: a single digit pattern with a match mode, so "ends with",
            # "starts with" and "contains" are all reachable from one field.
            with Horizontal(id="numsearch-filters2"):
                with Vertical():
                    yield Label("digits", classes="form-label")
                    yield Input(placeholder="3-7 digits", id="f-pattern")
                with Vertical():
                    yield Label("match", classes="form-label")
                    yield Select(
                        [(m, m) for m in MATCH_MODES],
                        value="contains", id="f-match", allow_blank=False,
                    )
                with Vertical():
                    yield Label("max results", classes="form-label")
                    yield Input(value="25", type="integer", id="f-max")

            yield Static("", id="numsearch-status")
            yield DataTable(id="numsearch-results", cursor_type="row")
            with Horizontal(id="form-buttons"):
                yield Button("search  (ctrl+s)", variant="primary", id="search")
                yield Button("buy selected", variant="success", id="buy")
                yield Button("cancel  (esc)", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#numsearch-results", DataTable).add_columns(*COLUMNS)
        self._apply_type()
        self.query_one("#f-areacode", Input).focus()
        self._status("set filters and press search  ·  digits box does "
                     "contains / starts with / ends with")

    def _status(self, message: str) -> None:
        self.query_one("#numsearch-status", Static).update(message)

    @on(Select.Changed, "#f-type")
    def _type_changed(self) -> None:
        self._apply_type()

    def _apply_type(self) -> None:
        """Grey out geography for toll-free, which has none.

        Rather than let someone type an area code that the API will reject, the
        fields that cannot apply to the current type are disabled outright.
        """
        tollfree = self.query_one("#f-type", Select).value == "toll-free"
        for wrap_id, field_id in (("wrap-areacode", "f-areacode"),
                                  ("wrap-region", "f-region"),
                                  ("wrap-city", "f-city")):
            self.query_one(f"#{field_id}", Input).disabled = tollfree
            self.query_one(f"#{wrap_id}").set_class(tollfree, "-muted")

    # ------------------------------------------------------------------ search

    def action_search(self) -> None:
        kind = self.query_one("#f-type", Select).value
        is_tollfree = kind == "toll-free"
        params: dict[str, Any] = {"number_type": kind}

        # Geography only for local numbers; toll-free has none.
        if not is_tollfree:
            for field, key in (("f-areacode", "areacode"), ("f-region", "region"),
                               ("f-city", "city")):
                value = self.query_one(f"#{field}", Input).value.strip()
                if value:
                    params[key] = value

        # The digit pattern maps to contains / starts_with / ends_with.
        pattern = self.query_one("#f-pattern", Input).value.strip()
        if pattern:
            if not pattern.isdigit() or not (PATTERN_MIN <= len(pattern) <= PATTERN_MAX):
                self._status(f"digits must be {PATTERN_MIN}-{PATTERN_MAX} digits, "
                             "no letters or wildcards")
                return
            mode = self.query_one("#f-match", Select).value
            params[MATCH_MODES[mode]] = pattern

        limit = self.query_one("#f-max", Input).value.strip()
        params["max_results"] = int(limit) if limit.isdigit() else 25

        if "city" in params and "region" not in params:
            self._status("city only works together with a region")
            return
        # Local needs at least one narrowing filter; toll-free may be searched
        # bare (the platform returns available toll-free inventory).
        if not is_tollfree and not any(
            k in params for k in ("areacode", "region", "city", "contains",
                                  "starts_with", "ends_with")
        ):
            self._status("add an area code, a region, or a digit pattern")
            return

        self._run_search(params)

    @work(exclusive=True, group="numsearch")
    async def _run_search(self, params: dict[str, Any]) -> None:
        self.searching = True
        self._status("searching...")
        try:
            payload = await self.client.call_sdk("phone_numbers.search", **params)
        except SwshError as exc:
            self.searching = False
            self._status(f"search failed: {exc}")
            return
        finally:
            self.searching = False

        rows = payload.get("data", []) if isinstance(payload, dict) else list(payload or [])
        self.results = [r for r in rows if isinstance(r, dict)]

        table = self.query_one("#numsearch-results", DataTable)
        table.clear()
        for row in self.results:
            table.add_row(
                row.get("e164", "-"),
                row.get("national_number_formatted", "-"),
                row.get("region", "-"),
                row.get("rate_center", "-"),
                ", ".join(row.get("capabilities") or []),
                key=row.get("e164"),
            )
        if self.results:
            self._status(f"{len(self.results)} available. Select one and press buy.")
            table.focus()
        else:
            self._status("nothing matched those filters")

    # --------------------------------------------------------------------- buy

    def _selected(self) -> str | None:
        table = self.query_one("#numsearch-results", DataTable)
        if not table.row_count or table.cursor_row < 0:
            return None
        try:
            return str(table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value)
        except Exception:
            return None

    @on(Input.Submitted)
    def filter_submitted(self) -> None:
        self.action_search()

    @on(Button.Pressed, "#search")
    def search_pressed(self) -> None:
        self.action_search()

    @on(Button.Pressed, "#buy")
    def buy_pressed(self) -> None:
        number = self._selected()
        if not number:
            self._status("select a number first")
            return
        # Buying bills the account, so hand the choice back and let the caller
        # put a confirmation in front of the purchase.
        self.dismiss(number)

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#numsearch-close")
    def close_pressed(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
