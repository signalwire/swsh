"""The create/edit form modal, driven headlessly.

The governing rule: every field gets a real control. Nobody types a JSON object
to tick a flag or choose a codec. The only editor in the system is for a value
that genuinely is a document, and even that is validated before sending.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Checkbox, Input, Select, Static, TextArea

from swsh import resources as res
from swsh.tui.forms import FormScreen
from swsh.tui.widgets import GrowingArea

SIP_DOMAIN = "example-0123456789ab.sip.signalwire.com"


class Host(App[None]):
    """Minimal host so the modal can be pushed in isolation."""

    CSS_PATH = "../swsh/tui/app.css"

    def compose(self) -> ComposeResult:
        yield Static("host")


async def open_form(resource, mode, initial=None):
    app = Host()
    result: dict = {}
    async with app.run_test() as pilot:
        app.push_screen(FormScreen(resource, mode, initial), lambda r: result.update(got=r))
        await pilot.pause()
        yield app, pilot, result


def error_of(app) -> str:
    return str(app.screen.query_one("#form-error", Static).content)


class TestNoJsonTyping:
    """No form asks for hand-written JSON except a genuine document field."""

    def test_the_code_editor_is_only_for_genuine_documents(self):
        """`code` is the one control that asks someone to type structured text.

        It is allowed only where the value really is a document, and each entry
        below has to be justifiable from the API's own description:

          swml.contents         a SWML script
          chattoken.channels    "user-defined channel names with read/write
          pubsubtoken.channels   permissions, max of 500" — an arbitrary map
          chattoken.state       "an arbitrary JSON object available to store
          pubsubtoken.state      stateful application information in"

        Anything else with a fixed or enumerable shape gets a real control, so a
        new entry here needs a reason, not just a passing test.
        """
        allowed = {
            ("swml", "contents"),
            ("chattoken", "channels"), ("chattoken", "state"),
            ("pubsubtoken", "channels"), ("pubsubtoken", "state"),
        }
        code_fields = {
            (r.key, f.name) for r in res.RESOURCES for f in r.fields if f.kind == "code"
        }
        assert code_fields == allowed

    def test_no_field_anywhere_is_a_raw_json_blob(self):
        for resource in res.RESOURCES:
            for field_def in resource.fields:
                assert field_def.kind in res.KINDS, (resource.key, field_def.name)
                assert field_def.kind != "json", (resource.key, field_def.name)

    async def test_the_form_has_no_json_tab(self):
        async for app, pilot, _ in open_form(res.get("queues"), "create"):
            assert not app.screen.query("#form-tabs")
            assert not app.screen.query("#form-json")


class TestControls:
    async def test_bool_renders_a_checkbox(self):
        async for app, pilot, _ in open_form(res.get("confrooms"), "create"):
            assert isinstance(app.screen.query_one("#field-record"), Checkbox)

    async def test_choice_renders_a_select(self):
        async for app, pilot, _ in open_form(res.get("numbers"), "update"):
            assert isinstance(app.screen.query_one("#field-call_handler"), Select)

    async def test_multi_renders_one_checkbox_per_option(self):
        async for app, pilot, _ in open_form(res.get("sip"), "create"):
            boxes = app.screen.query("#field-codecs .group-item")
            assert len(boxes) == len(res.CODECS)

    async def test_textarea_for_prose(self):
        async for app, pilot, _ in open_form(res.get("agents"), "create"):
            assert isinstance(app.screen.query_one("#field-prompt_text"), TextArea)

    async def test_int_input_is_typed(self):
        async for app, pilot, _ in open_form(res.get("queues"), "create"):
            assert app.screen.query_one("#field-max_size", Input).type == "integer"


class TestTextBoxesGrow:
    """A pasted webhook URL has to be readable, not scrolled past sideways.

    Every long value in these forms is a URL. A single-line `Input` shows about
    thirty characters of one and hides the query string, which is the part that
    is usually wrong.
    """

    URL = ("https://example.signalwire.com/laml-bins/"
           "eeeeeeee-0000-4000-8000-000000000001?token=" + "a" * 90)

    async def test_a_text_box_starts_one_line_tall(self):
        """One line of *content*.

        These used to assert on `styles.height`, which is the outer height and
        includes the border — so "1" meant a content area of zero rows and a
        box that could never show anything. The number that matters is how many
        lines of text are visible.
        """
        async for app, pilot, _ in open_form(res.get("numbers"), "update"):
            box = app.screen.query_one("#field-name", GrowingArea)
            assert box.content_size.height == 1
            assert box.styles.height.value == 1 + box.gutter.height

    async def test_it_grows_to_fit_what_is_pasted(self):
        async for app, pilot, _ in open_form(
                res.get("numbers"), "update", {"call_handler": "laml_webhooks"}):
            box = app.screen.query_one("#field-call_request_url", GrowingArea)
            box.value = self.URL
            await pilot.pause()
            await pilot.pause()
            assert box.wrapped_document.height > 1
            assert box.content_size.height == box.wrapped_document.height
            assert box.value == self.URL  # and nothing was truncated to fit

    async def test_it_stops_growing_so_one_field_cannot_fill_the_form(self):
        async for app, pilot, _ in open_form(
                res.get("numbers"), "update", {"call_handler": "laml_webhooks"}):
            box = app.screen.query_one("#field-call_request_url", GrowingArea)
            box.value = "https://example.test/" + "x" * 4000
            await pilot.pause()
            await pilot.pause()
            assert box.wrapped_document.height > box.max_lines
            assert box.content_size.height == box.max_lines

    async def test_enter_moves_on_rather_than_breaking_the_value(self):
        # A newline inside a webhook URL is never meant, and it would be sent.
        async for app, pilot, _ in open_form(res.get("numbers"), "update"):
            box = app.screen.query_one("#field-name", GrowingArea)
            box.value = "Fax Number"
            box.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert box.value == "Fax Number"

    async def test_a_show_if_on_a_text_field_still_reacts(self):
        # The text controls are TextAreas now, so visibility has to listen for
        # TextArea.Changed as well as Input.Changed.
        async for app, pilot, _ in open_form(res.get("numbers"), "update"):
            handler = app.screen.query_one("#field-call_handler", Select)
            handler.value = "laml_webhooks"
            await pilot.pause()
            assert app.screen.query_one("#wrap-call_request_url").display
            handler.value = "relay_script"
            await pilot.pause()
            assert not app.screen.query_one("#wrap-call_request_url").display


class TestCheckboxes:
    async def test_ticked_boxes_become_a_list(self):
        async for app, pilot, result in open_form(res.get("sip"), "create"):
            app.screen.query_one("#field-username", GrowingArea).value = "alice"
            app.screen.query_one("#field-password", GrowingArea).value = "s3cret"
            for box in app.screen.query("#field-codecs .group-item").results(Checkbox):
                if str(box.label) in ("OPUS", "PCMU"):
                    box.value = True
            app.screen.action_submit()
            await pilot.pause()
            assert sorted(result["got"]["codecs"]) == ["OPUS", "PCMU"]

    async def test_open_ended_group_accepts_values_outside_the_list(self):
        """A known-incomplete option set must never block a valid request."""
        async for app, pilot, result in open_form(res.get("sip"), "create"):
            app.screen.query_one("#field-username", GrowingArea).value = "alice"
            app.screen.query_one("#field-password", GrowingArea).value = "s3cret"
            app.screen.query_one("#field-codecs--other", GrowingArea).value = "AMR-WB, SILK"
            app.screen.action_submit()
            await pilot.pause()
            assert sorted(result["got"]["codecs"]) == ["AMR-WB", "SILK"]

    async def test_unticked_group_is_omitted_not_emptied(self):
        async for app, pilot, result in open_form(res.get("sip"), "create"):
            app.screen.query_one("#field-username", GrowingArea).value = "alice"
            app.screen.query_one("#field-password", GrowingArea).value = "s3cret"
            app.screen.action_submit()
            await pilot.pause()
            assert "codecs" not in result["got"]

    async def test_edit_preticks_existing_values(self):
        row = {"id": "s-1", "username": "alice", "codecs": ["OPUS", "G722"]}
        async for app, pilot, _ in open_form(res.get("sip"), "update", initial=row):
            ticked = {
                str(b.label)
                for b in app.screen.query("#field-codecs .group-item").results(Checkbox)
                if b.value
            }
            assert ticked == {"OPUS", "G722"}

    async def test_edit_puts_unknown_existing_values_in_the_other_box(self):
        row = {"id": "s-1", "username": "alice", "codecs": ["OPUS", "AMR-WB"]}
        async for app, pilot, _ in open_form(res.get("sip"), "update", initial=row):
            assert app.screen.query_one("#field-codecs--other", GrowingArea).value == "AMR-WB"

    async def test_checkbox_false_is_sent_not_dropped(self):
        """Unticking a boolean is a real value, unlike an empty text field."""
        async for app, pilot, result in open_form(res.get("confrooms"), "create"):
            app.screen.query_one("#field-name", GrowingArea).value = "standup"
            app.screen.query_one("#field-record", Checkbox).value = False
            app.screen.action_submit()
            await pilot.pause()
            assert result["got"]["record"] is False


class TestListField:
    async def test_comma_separated_becomes_a_list(self):
        async for app, pilot, result in open_form(res.get("datasphere"), "create"):
            app.screen.query_one("#field-url", GrowingArea).value = "https://example.com/policy"
            app.screen.query_one("#field-tags", GrowingArea).value = "billing, refunds , support"
            app.screen.action_submit()
            await pilot.pause()
            assert result["got"]["tags"] == ["billing", "refunds", "support"]


class TestNestedPaths:
    async def test_flat_prompt_box_produces_a_nested_body(self):
        async for app, pilot, result in open_form(res.get("agents"), "create"):
            app.screen.query_one("#field-name", GrowingArea).value = "Support"
            app.screen.query_one("#field-prompt_text", TextArea).text = "Be helpful."
            app.screen.action_submit()
            await pilot.pause()
            assert result["got"] == {"name": "Support", "prompt": {"text": "Be helpful."}}

    async def test_edit_reads_the_nested_value_back_into_the_box(self):
        row = {"id": "a-1", "name": "Support", "prompt": {"text": "Be helpful."}}
        async for app, pilot, _ in open_form(res.get("agents"), "update", initial=row):
            assert app.screen.query_one("#field-prompt_text", TextArea).text == "Be helpful."


class TestDocumentField:
    async def test_valid_swml_is_parsed_into_an_object(self):
        async for app, pilot, result in open_form(res.get("swml"), "create"):
            app.screen.query_one("#field-name", GrowingArea).value = "greeting"
            app.screen.query_one("#field-contents", TextArea).text = (
                '{"sections": {"main": [{"play": "say:hello"}]}}'
            )
            app.screen.action_submit()
            await pilot.pause()
            assert result["got"]["contents"] == {
                "sections": {"main": [{"play": "say:hello"}]}
            }

    async def test_broken_swml_is_caught_here_with_a_line_number(self):
        async for app, pilot, result in open_form(res.get("swml"), "create"):
            app.screen.query_one("#field-name", GrowingArea).value = "greeting"
            app.screen.query_one("#field-contents", TextArea).text = '{"sections": '
            app.screen.action_submit()
            await pilot.pause()
            assert "got" not in result
            message = error_of(app)
            assert "not valid JSON" in message
            assert "line" in message

    async def test_cxml_script_is_plain_text_not_json(self):
        async for app, pilot, result in open_form(res.get("cxml"), "create"):
            app.screen.query_one("#field-name", GrowingArea).value = "greeting"
            app.screen.query_one("#field-contents", TextArea).text = (
                "<Response><Say>Hello</Say></Response>"
            )
            app.screen.action_submit()
            await pilot.pause()
            assert result["got"]["contents"] == (
                "<Response><Say>Hello</Say></Response>"
            )


class TestValidation:
    async def test_missing_required_field_blocks_and_explains(self):
        async for app, pilot, result in open_form(res.get("queues"), "create"):
            app.screen.action_submit()
            await pilot.pause()
            assert "got" not in result
            assert "required" in error_of(app)

    async def test_update_does_not_demand_required_fields(self):
        row = {"id": "q-1", "name": "support", "max_size": 10}
        async for app, pilot, result in open_form(res.get("queues"), "update", initial=row):
            app.screen.query_one("#field-max_size", Input).value = "99"
            app.screen.action_submit()
            await pilot.pause()
            assert result["got"]["max_size"] == 99

    async def test_blank_text_is_omitted_so_edits_stay_partial(self):
        row = {"id": "q-1", "name": "support", "max_size": 10}
        async for app, pilot, result in open_form(res.get("queues"), "update", initial=row):
            app.screen.query_one("#field-name", GrowingArea).value = ""
            app.screen.query_one("#field-max_size", Input).value = "99"
            app.screen.action_submit()
            await pilot.pause()
            assert result["got"] == {"max_size": 99}


class TestDismissal:
    async def test_escape_cancels_without_a_body(self):
        async for _app, pilot, result in open_form(res.get("queues"), "create"):
            await pilot.press("escape")
            await pilot.pause()
            assert result["got"] is None


class TestDynamicOptions:
    """Some choices come from the project, not from a fixed list."""

    def test_send_as_is_sourced_from_purchased_numbers(self):
        send_as = next(f for f in res.get("sip").fields if f.name == "send_as")
        assert send_as.kind == "choice"
        assert send_as.options_from == ("numbers.list", "number", "name")

    def test_caller_id_stays_free_text_for_sip_to_sip(self):
        caller_id = next(f for f in res.get("sip").fields if f.name == "caller_id")
        assert caller_id.kind == "text"
        assert caller_id.options_from is None
        assert "SIP-to-SIP" in caller_id.help

    async def test_options_are_populated_from_the_live_list(self):
        class Stub:
            async def invoke(self, resource, op, **kw):
                assert resource.key == "numbers" and op == "list"
                return {"data": [
                    {"number": "+15550100003", "name": "Main line"},
                    {"number": "+14155550101", "name": "Support"},
                ]}

        app = Host()
        async with app.run_test() as pilot:
            app.push_screen(FormScreen(res.get("sip"), "create", client=Stub()))
            await pilot.pause(0.4)
            select = app.screen.query_one("#field-send_as", Select)
            values = [v for _, v in select._options] if hasattr(select, "_options") else []
            if not values:  # Textual keeps options internally; read the widget API
                values = [str(o.value) for o in select._select_options]
            assert "+15550100003" in values

    async def test_a_failed_lookup_reports_instead_of_offering_nothing(self):
        class Broken:
            async def invoke(self, resource, op, **kw):
                raise RuntimeError("network down")

        app = Host()
        async with app.run_test() as pilot:
            app.push_screen(FormScreen(res.get("sip"), "create", client=Broken()))
            await pilot.pause(0.4)
            helps = [str(n.content) for n in app.screen.query("#wrap-send_as .form-help")]
            # Short, and about the field. Not which call failed and why.
            assert any("none available" in h for h in helps)
            assert not any("Error" in h or "load failed" in h for h in helps)

    async def test_no_client_leaves_the_form_usable(self):
        app = Host()
        async with app.run_test() as pilot:
            app.push_screen(FormScreen(res.get("sip"), "create"))
            await pilot.pause(0.3)
            assert app.screen.query_one("#field-username", GrowingArea)


class TestAFormIsReadyToTypeInto:
    """Opening a form and typing has to put the text in the first field.

    Two defects made that false, and together they are why the lab's SIP
    device could not be filled in by hand. Both are cheap to reintroduce, so
    both are pinned here.
    """

    async def test_the_first_field_has_focus_not_the_close_button(self):
        """Textual focuses the first focusable widget, which is the header `✕`.

        The form then looks ready and is not: keystrokes go to a button, and
        the first box is three tabs away (close, the scroll container, the
        field).
        """
        app = Host()
        async with app.run_test() as pilot:
            app.push_screen(FormScreen(res.get("sip"), "create"))
            await pilot.pause()
            assert app.focused is not None
            assert app.focused.id == "field-username"

    async def test_typing_reaches_a_growing_text_box(self):
        """`GrowingArea._on_key` overrides a coroutine.

        Declared `def`, its `super()._on_key(event)` built a coroutine nobody
        awaited, so every key but `enter` reached a handler that never ran.
        Python reports that as a RuntimeWarning on stderr, which a full-screen
        app has already taken over, so it failed in silence.
        """
        import inspect

        assert inspect.iscoroutinefunction(GrowingArea._on_key)

        app = Host()
        async with app.run_test() as pilot:
            app.push_screen(FormScreen(res.get("sip"), "create"))
            await pilot.pause()
            box = app.screen.query_one("#field-caller_id", GrowingArea)
            box.focus()
            await pilot.pause()
            for ch in "desk":
                await pilot.press(ch)
            await pilot.pause()
            assert box.value == "desk"


class TestPickingAnOptionFillsWhatTheRowKnows:
    """`prefill`: a chosen option answers for its siblings.

    Picking a SIP endpoint already says what its domain is, and the row is in
    hand from the picker, so making somebody read it off the dashboard and
    retype it is work the form can do. What the row does not carry is left
    alone — the endpoint's password is the live case, and blanking the box
    would be worse than not filling it.
    """

    def _resource(self):
        """The lab's real SIP-device form, which is what declares `prefill`."""
        from swsh.config import Profile
        from swsh.tui.app import SwshApp

        return SwshApp(profile=Profile(name="t", project="p", token="tok",
                                       space="example.signalwire.com"))._device_form()

    class _Rows:
        async def invoke(self, resource, op, **kw):
            return {"data": [{"display_name": "desk phone",
                              "sip_endpoint": {"username": "1001", "domain": SIP_DOMAIN}}]}

    async def test_a_present_key_is_filled_in(self):
        app = Host()
        async with app.run_test() as pilot:
            app.push_screen(FormScreen(self._resource(), "create", client=self._Rows()))
            await pilot.pause(0.4)
            app.screen.query_one("#field-username", Select).value = "1001"
            await pilot.pause()
            assert app.screen.query_one("#field-domain", GrowingArea).value == SIP_DOMAIN

    async def test_a_key_the_api_withholds_leaves_the_box_alone_silently(self):
        """No commentary about which API returned what.

        An empty box somebody can type into already says everything they need;
        a line explaining that the platform withholds a password is the
        application talking about itself.
        """
        app = Host()
        async with app.run_test() as pilot:
            app.push_screen(FormScreen(self._resource(), "create", client=self._Rows()))
            await pilot.pause(0.4)
            app.screen.query_one("#field-username", Select).value = "1001"
            await pilot.pause()
            # a masked Input now, because it is a password
            assert app.screen.query_one("#field-password", Input).value == ""
            shown = [str(n.render()) for n in app.screen.query(".form-help") if n.display]
            assert shown == [], f"the form is explaining itself: {shown}"

    async def test_the_selector_keeps_the_row_it_promises(self):
        """`Option` documented a row it did not keep, so reading one more key
        off a listed row meant fetching the row again."""
        from swsh.selectors import Selector

        sel = Selector(self._Rows())
        opts = await sel.options(("sip.list", "sip_endpoint.username", "display_name"))
        assert opts and opts[0].row["sip_endpoint"]["domain"] == SIP_DOMAIN


class TestWhatIsTypedIsVisible:
    """A box that takes input and shows none of it reads as a broken box."""

    @staticmethod
    def painted(app) -> str:
        """Everything the compositor would put on the terminal, as plain text."""
        return "\n".join("".join(seg.text for seg in strip)
                         for strip in app.screen._compositor.render_strips())

    async def test_a_text_box_has_room_for_its_line(self):
        """`height` is the outer height — box-sizing is `border-box`.

        Setting it to the wrapped line count alone gave the border's two rows
        out of a total of one, so the content area was zero rows tall: every
        keystroke was accepted and stored, and none of it was ever drawn.
        """
        app = Host()
        async with app.run_test(size=(100, 40)) as pilot:
            app.push_screen(FormScreen(res.get("sip"), "create"))
            await pilot.pause()
            box = app.screen.query_one("#field-caller_id", GrowingArea)
            box.focus()
            await pilot.pause()
            for ch in "hello":
                await pilot.press(ch)
            await pilot.pause()
            assert box.value == "hello"
            assert box.content_size.height >= 1
            assert "hello" in self.painted(app)

    async def test_typing_into_a_filled_box_carries_on_from_the_end(self):
        """Focus put the cursor at 0, so the first key landed in front of the
        value: typing into a filled domain gave `-xacme-…`."""
        app = Host()
        async with app.run_test(size=(100, 40)) as pilot:
            app.push_screen(FormScreen(res.get("sip"), "create",
                                       {"caller_id": "desk"}))
            await pilot.pause()
            box = app.screen.query_one("#field-caller_id", GrowingArea)
            box.focus()
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            assert box.value == "desk1"

    async def test_a_secret_is_masked_but_still_shows_it_is_taking_input(self):
        """The one field that must not be legible, and must not look dead."""
        from swsh.config import Profile
        from swsh.tui.app import SwshApp

        device = SwshApp(profile=Profile(name="t", project="p", token="tok",
                                         space="example.signalwire.com"))._device_form()
        password = next(f for f in device.fields if f.name == "password")
        assert password.secret is True

        app = Host()
        async with app.run_test(size=(100, 40)) as pilot:
            app.push_screen(FormScreen(device, "create"))
            await pilot.pause()
            box = app.screen.query_one("#field-password", Input)
            assert box.password is True
            box.focus()
            await pilot.pause()
            for ch in "s3cret":
                await pilot.press(ch)
            await pilot.pause()
            screen = self.painted(app)
            assert box.value == "s3cret"          # the value is what gets sent
            assert "s3cret" not in screen         # but never legible on screen
            assert "•" * 6 in screen         # one mark per keystroke


class TestAFormSaysOnlyWhatItNeedsTo:
    """Chrome costs rows, and rows are why the fields below scroll off."""

    async def test_a_picker_names_itself_rather_than_saying_loading(self):
        """`prompt` shows whenever nothing is selected, not just while loading.

        Set to "loading...", it said so for as long as the field was empty —
        which is until somebody picks something, i.e. for good.
        """
        class Rows:
            async def invoke(self, resource, op, **kw):
                return {"data": [{"display_name": "desk",
                                  "sip_endpoint": {"username": "1001"}}]}

        from swsh.config import Profile
        from swsh.tui.app import SwshApp

        device = SwshApp(profile=Profile(name="t", project="p", token="tok",
                                         space="example.signalwire.com"))._device_form()
        app = Host()
        async with app.run_test() as pilot:
            app.push_screen(FormScreen(device, "create", client=Rows()))
            await pilot.pause(0.4)
            select = app.screen.query_one("#field-username", Select)
            assert str(select.prompt) == "SIP endpoint"
            assert "loading" not in str(select.prompt).lower()

    async def test_a_field_with_no_help_costs_no_row(self):
        """The node stays so a load failure can still be reported, but hidden.

        Declaring no help has to mean nothing under the box — not a blank line
        under it, which is a row out of the scroll viewport for every field.
        """
        from swsh.config import Profile
        from swsh.tui.app import SwshApp

        device = SwshApp(profile=Profile(name="t", project="p", token="tok",
                                         space="example.signalwire.com"))._device_form()
        assert all(not f.help for f in device.fields)

        app = Host()
        async with app.run_test() as pilot:
            app.push_screen(FormScreen(device, "create"))
            await pilot.pause()
            helps = app.screen.query(".form-help")
            assert helps  # the slots exist
            assert not any(node.display for node in helps)  # and none take a row

    async def test_a_secret_box_carries_no_placeholder(self):
        from swsh.config import Profile
        from swsh.tui.app import SwshApp

        device = SwshApp(profile=Profile(name="t", project="p", token="tok",
                                         space="example.signalwire.com"))._device_form()
        app = Host()
        async with app.run_test() as pilot:
            app.push_screen(FormScreen(device, "create"))
            await pilot.pause()
            assert app.screen.query_one("#field-password", Input).placeholder == ""
