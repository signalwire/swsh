"""Interactive prompting: ask for missing bits, offer enumerable values as lists.

The picker is driven by monkeypatching typer.prompt/echo, so the numbered-choice
logic and the non-interactive strictness are tested without a real terminal.
"""

from __future__ import annotations

import pytest
import typer

from swsh import prompts
from swsh import resources as res
from swsh.selectors import Option


@pytest.fixture
def answers(monkeypatch):
    """Feed scripted answers to typer.prompt; capture echoed lines."""
    lines: list[str] = []
    monkeypatch.setattr(typer, "echo", lambda msg="", *a, **k: lines.append(str(msg)))
    queue: list[str] = []

    def fake_prompt(text, default=None, **kw):
        return queue.pop(0) if queue else (default if default is not None else "")

    monkeypatch.setattr(typer, "prompt", fake_prompt)
    return queue, lines


class FakeSelector:
    def __init__(self, opts):
        self._opts = opts

    async def options(self, source, **kw):
        return self._opts


class FakeClient:
    def __init__(self, opts):
        self.selector = FakeSelector(opts)


# A write whose one required field is enumerable, the shape `sw create` has to
# prompt for. Shaped like E911 assignment, which is now an extra on `numbers`
# rather than a resource of its own.
E911 = res.Resource(
    key="e911-test", title="E911", namespace="", caps="C", transport="rest",
    api="relay-rest", rest_ops={"create": "assign_e911_address"},
    fields=(res.Field("e911_address_id", required=True, kind="choice",
                      options_from=("addresses.list", "id", "name")),),
)


class TestPick:
    def test_returns_the_chosen_value(self, answers):
        queue, _ = answers
        queue.append("2")
        val = prompts.pick("From?", [Option("+1", "A"), Option("+2", "B")])
        assert val == "+2"

    def test_default_first_when_blank(self, answers):
        _queue, _ = answers  # empty queue -> default "1"
        val = prompts.pick("From?", [Option("+1", "A"), Option("+2", "B")])
        assert val == "+1"

    def test_rejects_out_of_range_then_accepts(self, answers):
        queue, lines = answers
        queue.extend(["9", "1"])
        val = prompts.pick("From?", [Option("+1", "A")])
        assert val == "+1"
        assert any("out of range" in ln for ln in lines)

    def test_empty_without_allow_other_returns_none(self, answers):
        assert prompts.pick("x", []) is None

    def test_empty_with_allow_other_prompts_free_text(self, answers):
        queue, _ = answers
        queue.append("typed-value")
        assert prompts.pick("x", [], allow_other=True) == "typed-value"


class TestFillMissing:
    async def test_prompts_for_a_missing_required_enumerable_field(self, answers):
        queue, _ = answers
        queue.append("1")  # choose the first address
        e911 = E911
        client = FakeClient([Option("addr-1", "HQ"), Option("addr-2", "Branch")])
        body = await prompts.fill_missing(e911, "create", {}, client,
                                          allow_prompt=True)
        # e911's required field is e911_address_id (a choice)
        assert body["e911_address_id"] == "addr-1"

    async def test_non_interactive_raises_instead_of_prompting(self):
        e911 = E911
        client = FakeClient([Option("addr-1", "HQ")])
        with pytest.raises(typer.BadParameter):
            await prompts.fill_missing(e911, "create", {}, client, allow_prompt=False)

    async def test_already_supplied_fields_are_not_prompted(self, answers):
        _queue, lines = answers
        e911 = E911
        client = FakeClient([Option("addr-1", "HQ")])
        body = await prompts.fill_missing(
            e911, "create", {"e911_address_id": "addr-9"}, client, allow_prompt=True)
        assert body["e911_address_id"] == "addr-9"
        assert lines == []  # nothing prompted


class TestChooseNumber:
    async def test_filters_to_capable_numbers(self, answers):
        queue, lines = answers
        queue.append("1")
        client = FakeClient([
            Option("+1", "voice+sms", ("voice", "sms")),
            Option("+2", "fax only", ("fax",)),
        ])
        # message channel -> only the sms-capable number is offered
        val = await prompts.choose_number(client, channel="message")
        assert val == "+1"
        shown = "\n".join(lines)
        assert "+1" in shown and "+2" not in shown

    async def test_raises_when_no_capable_number(self):
        client = FakeClient([Option("+2", "fax only", ("fax",))])
        with pytest.raises(typer.BadParameter):
            await prompts.choose_number(client, channel="message")
