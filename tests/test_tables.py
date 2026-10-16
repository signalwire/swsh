"""What a list table owes the person reading it.

From the live pass over all 40 listings: the uuid was elided on every wide
resource while short columns were padded out with the spare width, four
different spellings of "a moment in time" appeared across four listings, and
twelve empty collections each drew one row of dashes that reads exactly like a
record whose every field is null.
"""

from __future__ import annotations

import re

from rich.console import Console

from swsh import ui


def render(table, width: int = 120) -> str:
    console = Console(file=__import__("io").StringIO(), width=width, no_color=True)
    console.print(table)
    return console.file.getvalue()


class TestAnIdentifierSurvivesTheTable:
    """A uuid ending in `…` is the one value in the row that cannot be pasted
    into the next command, so eliding it is the same as not printing it."""

    ROWS = [
        {"id": "bbbbbbbb-0000-4000-8000-000000000004", "number": "+12095550183",
         "name": "Fax Number", "call_handler": "laml_webhooks",
         "created_at": "2026-08-12T16:39:53Z"},
        {"id": "bbbbbbbb-0000-4000-8000-000000000003", "number": "+14405550168",
         "name": "Support", "call_handler": "relay_sip_endpoint",
         "created_at": "2024-03-21T20:58:45Z"},
    ]
    COLUMNS = ("number", "name", "call_handler", "id", "created_at")

    def test_the_uuid_is_never_elided(self):
        text = render(ui.rows_table(self.ROWS, self.COLUMNS))
        for row in self.ROWS:
            assert row["id"] in text

    def test_it_survives_a_narrow_terminal_too(self):
        """Something has to give at 100 columns; it is not the identifier."""
        text = render(ui.rows_table(self.ROWS, self.COLUMNS), width=100)
        for row in self.ROWS:
            assert row["id"] in text

    def test_a_foreign_key_counts_as_an_identifier(self):
        """`relay_pstn_leg_id` on a recording is what joins it to the call."""
        rows = [{"id": "a" * 36, "relay_pstn_leg_id": "b" * 36, "status": "no_input"}]
        text = render(ui.rows_table(rows, ("id", "status", "relay_pstn_leg_id")))
        assert "b" * 36 in text

    def test_a_short_id_column_does_not_reserve_a_uuid_of_width(self):
        """The width comes from the rows, not from a constant."""
        rows = [{"id": "q-1", "name": "x" * 90}]
        text = render(ui.rows_table(rows, ("id", "name")))
        assert "x" * 80 in text  # the name got the width the id did not need


class TestOneSpellingOfAMoment:
    """Fabric sends ISO-8601 with a Z, the voice log adds milliseconds, and the
    compatibility surface sends RFC 2822 — three listings, three spellings of
    the same instant, none of them in the reader's timezone."""

    def test_every_shape_the_platform_sends_reads_the_same(self):
        shapes = ["2026-09-09T20:40:56Z", "2026-09-21T18:44:51.835Z",
                  "Wed, 13 Aug 2025 15:50:16 +0000"]
        rendered = [ui.local_time(s) for s in shapes]
        assert all(r is not None for r in rendered)
        assert all(re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \S+$", r)
                   for r in rendered)

    def test_a_listing_converts_them_like_the_detail_view_does(self):
        rows = [{"id": "a", "created_at": "2026-09-09T20:40:56Z"}]
        assert ui._cell(rows[0]["created_at"]) == ui.local_time("2026-09-09T20:40:56Z")

    def test_a_timestamp_column_is_not_folded_across_two_rows(self):
        """It costs a screen row per record to say what fits in one."""
        rows = [{"id": "a" * 36, "name": "n" * 40, "created_at": "2026-09-09T20:40:56Z"}]
        text = render(ui.rows_table(rows, ("id", "name", "created_at")))
        stamp = ui.local_time("2026-09-09T20:40:56Z")
        assert any(stamp in line for line in text.splitlines())

    def test_something_that_is_not_a_time_is_left_alone(self):
        assert ui._cell("sw-test-2") == "sw-test-2"
        assert ui.local_time("2026") is None


class TestAnEmptyCollectionSaysSo:
    def test_it_does_not_draw_a_row_of_dashes(self):
        """Indistinguishable from one real record whose every field is null,
        and a dozen of a fresh project's collections are empty."""
        text = render(ui.rows_table([], ("id", "number", "verified", "created_at")))
        assert "no rows" in text
        assert not re.search(r"│ -\s+│ -\s+│", text)

    def test_the_columns_are_still_shown(self):
        """What the resource *would* hold is the useful half of the answer."""
        text = render(ui.rows_table([], ("id", "number", "verified")))
        for column in ("id", "number", "verified"):
            assert column in text
