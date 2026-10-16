"""Headless checks on the cockpit.

Textual can drive the app without a terminal, so the layout, the key bindings
and the store-to-table path are all testable. The profile here points at a host
that does not resolve, which doubles as a check that a dead poller degrades
quietly instead of taking the interface down.
"""

from __future__ import annotations

from textual.widgets import Button, ContentSwitcher, DataTable, Input, Static

from swsh import resources as res
from swsh.client import SwshError
from swsh.config import Profile
from swsh.models import CallEvent, CallRef, CallState, Source
from swsh.tui.app import SwshApp

FAKE = Profile(name="test", project="proj-1", token="tok", space="nowhere.invalid")


def rendered_text(widget) -> str:
    """Flatten a widget's renderable to plain text.

    The detail pane holds a rich Group (heading plus highlighted JSON), so
    str() on it says nothing useful.
    """
    from io import StringIO

    from rich.console import Console

    console = Console(file=StringIO(), width=200, no_color=True)
    console.print(widget.content)
    return console.file.getvalue()


def call_event(sid: str, state: CallState, **kw) -> CallEvent:
    return CallEvent(ref=CallRef(sid=sid), kind="state", source=Source.POLL, state=state, **kw)


async def test_app_starts_and_lays_out():
    app = SwshApp(profile=FAKE)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#calls")
        assert app.query_one("#feed")
        assert app.query_one("#statusbar")


async def test_calls_reaching_the_store_render_in_the_table():
    app = SwshApp(profile=FAKE)
    async with app.run_test() as pilot:
        app.action_go_calls()          # the app opens on the dashboard
        app.store.apply(
            call_event("CA1", CallState.ANSWERED, from_number="+15551112222",
                       to_number="+15553334444")
        )
        await pilot.pause()

        table = app.query_one("#calls")
        assert table.row_count == 1


async def test_ended_calls_hide_until_toggled():
    app = SwshApp(profile=FAKE)
    async with app.run_test() as pilot:
        app.action_go_calls()
        app.store.apply(call_event("CA1", CallState.ANSWERED))
        app.store.apply(call_event("CA2", CallState.ANSWERED))
        app.store.apply(call_event("CA2", CallState.ENDED))
        await pilot.pause()

        table = app.query_one("#calls")
        assert table.row_count == 1  # only the live one

        await pilot.press("f")
        await pilot.pause()
        assert table.row_count == 2


async def test_detail_pane_follows_the_cursor():
    app = SwshApp(profile=FAKE)
    async with app.run_test() as pilot:
        app.action_go_calls()
        app.store.apply(
            call_event("CA1", CallState.ANSWERED, from_number="+15551112222")
        )
        await pilot.pause()
        rendered = str(app.query_one("#detail").content)
        assert "CA1" in rendered
        assert "+15551112222" in rendered


async def test_detail_explains_when_native_control_is_unavailable():
    """A compat-only call cannot be transferred; the pane should say so rather
    than letting the keystroke fail with no explanation."""
    app = SwshApp(profile=FAKE)
    async with app.run_test() as pilot:
        app.action_go_calls()
        app.store.apply(call_event("CA1", CallState.ANSWERED))
        await pilot.pause()
        assert "native call id" in str(app.query_one("#detail").content)


async def test_control_key_without_selection_is_harmless():
    app = SwshApp(profile=FAKE)
    async with app.run_test() as pilot:
        await pilot.press("h")
        await pilot.pause()
        assert app.is_running


async def test_dead_poller_does_not_kill_the_app():
    """The fake space never resolves, so the poller errors on its first tick."""
    app = SwshApp(profile=FAKE, poll_interval=0.05)
    async with app.run_test() as pilot:
        await pilot.pause(0.4)
        assert app.is_running
        assert not app.poller.connected
        assert app.poller.last_error is not None
        assert "poll: error" in app.poller.status


async def test_relay_stays_off_without_topics():
    app = SwshApp(profile=FAKE)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.relay is None
        assert "relay: off" in str(app.query_one("#statusbar").content)


async def test_feed_clears_on_keypress():
    app = SwshApp(profile=FAKE)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        assert app.is_running


class TestNavigation:
    """The cockpit covers every namespace, not only live calls."""

    async def test_switch_to_a_resource_changes_the_pane(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("numbers")
            await pilot.pause()
            assert app.view == "rows"
            assert app.resource.key == "numbers"
            assert app.query_one("#main", ContentSwitcher).current == "rows"

    async def test_prefixes_resolve(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("agen")
            await pilot.pause()
            assert app.resource.key == "agents"

    async def test_unknown_resource_leaves_the_view_alone(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("definitely-not-real")
            await pilot.pause()
            assert app.view == "home"

    async def test_escape_steps_back_out_to_the_dashboard(self):
        # It used to land on the live calls table from anywhere, which was a
        # habit of that being the start-up view rather than a hierarchy.
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("numbers")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app.view == "home"
            assert app.query_one("#main", ContentSwitcher).current == "home"

    async def test_failed_load_surfaces_instead_of_hanging(self):
        """The fake space never resolves, so every namespace load fails."""
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("numbers")
            await pilot.pause(0.5)
            assert app.is_running
            assert not app.loading
            assert app.load_error is not None
            assert "error" in str(app.query_one("#pane-title").content)

    async def test_command_line_opens_and_dispatches(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.press("colon")
            await pilot.pause()
            command = app.query_one("#command", Input)
            assert command.display

            command.value = "queues"
            await command.action_submit()
            await pilot.pause()
            assert app.resource.key == "queues"
            assert not command.display

    async def test_resource_rows_render_with_discovered_columns(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("agents")
            await pilot.pause(0.4)
            # Injected as if the load had succeeded, using field names that do
            # not match the registry's guesses.
            app.rows = [{"uuid": "ag-1", "label": "Support"},
                        {"uuid": "ag-2", "label": "Billing"}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()

            table = app.query_one("#rows", DataTable)
            assert table.row_count == 2
            assert "uuid" in app.columns

    async def test_nested_fabric_fields_render_as_cells(self):
        """A SIP endpoint's username lives under `sip_endpoint`; the table
        must show it rather than a row of ids."""
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            app.switch_to("sip")
            await pilot.pause(0.4)
            app.rows = [{"id": "ep-1", "display_name": "deskphone",
                         "created_at": "2026-07-17T20:06:29Z",
                         "sip_endpoint": {"username": "deskphone", "send_as": "+15550100001"}}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            assert "sip_endpoint.username" in app.columns
            table = app.query_one("#rows", DataTable)
            cells = [str(table.get_cell_at((0, i))) for i in range(len(app.columns))]
            assert "deskphone" in cells and "+15550100001" in cells

    async def test_detail_shows_json_for_a_resource_row(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("agents")
            await pilot.pause(0.4)
            app.rows = [{"id": "ag-1", "name": "Support"}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            assert app.query_one("#detail").content is not None

    async def test_delete_is_refused_where_the_api_offers_none(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("logs")  # voice logs are read-only
            await pilot.pause(0.3)
            app.rows = [{"id": "log-1"}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            # No confirmation modal was pushed, and nothing crashed.
            assert app.is_running
            assert len(app.screen_stack) == 1

    async def test_call_actions_are_inert_on_a_resource_view(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("numbers")
            await pilot.pause(0.3)
            for key in ("h", "t", "p", "R"):
                await pilot.press(key)
            await pilot.pause()
            assert app.is_running
            assert len(app.screen_stack) == 1

    async def test_capability_letters_appear_in_the_pane_title(self):
        """The title advertises what the API permits, so key hints are honest."""
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("logs")
            await pilot.pause(0.4)
            assert "R" in str(app.query_one("#pane-title").content)

            app.switch_to("queues")
            await pilot.pause(0.4)
            assert "CRUD" in str(app.query_one("#pane-title").content)

    async def test_write_only_namespace_still_opens(self):
        """Project tokens have no list, but must remain creatable."""
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("tokens")
            await pilot.pause(0.3)
            assert app.resource.key == "tokens"
            assert not app.loading
            assert app.load_error is None  # not an error, just unlistable
            title = str(app.query_one("#pane-title").content)
            assert "nothing to list" in title and "n to create" in title

    async def test_action_only_namespace_points_at_x(self):
        """MFA has nothing to list or create; its whole surface is under x."""
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("mfa")
            await pilot.pause(0.3)
            title = str(app.query_one("#pane-title").content)
            assert "x for actions" in title and "n to create" not in title
            assert not app.query_one("#act-extra", Button).disabled

    async def test_detail_leads_with_the_row_name(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("agents")
            await pilot.pause(0.4)
            app.rows = [{"id": "ag-1", "display_name": "Support Bot", "type": "ai_agent"}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            assert "Support Bot" in rendered_text(app.query_one("#detail"))

    async def test_clicking_a_row_opens_it(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("agents")
            await pilot.pause(0.4)
            app.rows = [{"id": "ag-1", "name": "Support"}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            app.query_one("#rows", DataTable).action_select_cursor()
            await pilot.pause()
            assert "Support" in rendered_text(app.query_one("#detail"))

    async def test_detail_pane_scrolls_rather_than_truncating(self):
        """A long payload must stay reachable, not get clipped at the fold."""
        from textual.containers import VerticalScroll

        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(140, 40)) as pilot:
            app.switch_to("agents")
            await pilot.pause(0.4)
            app.rows = [{"id": "ag-1", "name": "Support",
                         **{f"field_{i}": f"value {i}" for i in range(40)}}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            content = app.query_one("#detail")
            viewport = app.query_one("#detail-scroll", VerticalScroll)
            assert content.size.height > viewport.size.height

    async def test_jump_modal_lists_every_resource(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.press("ctrl+r")
            await pilot.pause()
            # A dropdown of every resource, clickable, not a typed prompt.
            ids = {b.id for b in app.screen.query(".drop-item")}
            for key in ("numbers", "agents", "videorooms", "queues", "datasphere"):
                assert f"drop-{key}" in ids


class TestMenuAndActionBar:
    """Menu-first, mouse-first: clickable navigation and CRUD."""

    async def test_menu_bar_has_a_button_per_group(self):
        from swsh import resources as res
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.pause()
            ids = {b.id for b in app.query("#menubar Button")}
            assert "menu-calls" in ids
            for g in res.GROUPS:
                assert f"menu-{g}" in ids

    async def test_clicking_a_group_drops_down_its_resources(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#menu-messaging")
            await pilot.pause(0.3)
            from swsh.tui.app import DropdownMenu
            assert isinstance(app.screen, DropdownMenu)
            # it lists that group's resources as clickable items
            ids = {b.id for b in app.screen.query(".drop-item")}
            assert "drop-send" in ids or "drop-watemplates" in ids

    async def test_dropdown_has_a_clickable_close_control(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#menu-messaging")
            await pilot.pause(0.3)
            from swsh.tui.app import DropdownMenu
            assert isinstance(app.screen, DropdownMenu)
            # a visible ✕ closes it without needing escape
            assert app.screen.query("#drop-close")
            await pilot.click("#drop-close")
            await pilot.pause(0.3)
            assert not isinstance(app.screen, DropdownMenu)

    async def test_dropdown_items_are_uniform_full_width(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#menu-fabric")
            await pilot.pause(0.3)
            items = list(app.screen.query(".drop-item"))
            assert len(items) > 1
            # every item is one row tall and the same rendered width, so the
            # list lines up flush instead of staggering by label length
            heights = {i.size.height for i in items}
            widths = {i.size.width for i in items}
            assert heights == {1}
            assert len(widths) == 1

    async def test_clicking_calls_menu_returns_to_calls(self):
        app = SwshApp(profile=FAKE)
        # Wide enough to reach the Calls button, which now sits at the far end
        # of the bar rather than the near one.
        async with app.run_test(size=(180, 50)) as pilot:
            app.switch_to("numbers")
            await pilot.pause(0.3)
            await pilot.click("#menu-calls")
            await pilot.pause()
            assert app.view == "calls"

    async def test_action_bar_buttons_reflect_capabilities(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("logs")  # read-only
            await pilot.pause(0.4)
            assert app.query_one("#act-new", Button).disabled
            assert app.query_one("#act-delete", Button).disabled

            app.switch_to("queues")  # full CRUD
            await pilot.pause(0.4)
            assert not app.query_one("#act-new", Button).disabled

    async def test_clicking_new_opens_the_create_form(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(140, 45)) as pilot:
            app.switch_to("queues")
            await pilot.pause(0.4)
            btn = app.query_one("#act-new", Button)
            assert not btn.disabled
            btn.press()  # same path as a mouse click
            await pilot.pause(0.3)
            from swsh.tui.forms import FormScreen
            assert isinstance(app.screen, FormScreen)


class TestDrills:
    """Multi-extra resources (call-flow versions/deploy/addresses, video session
    members/recordings) must be reachable by mouse — the reported gap was that
    'More' only flashed unbound key hints."""

    async def test_more_opens_a_clickable_menu_of_drills(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            app.switch_to("flows")  # has several extras: versions, deploy, addresses
            await pilot.pause(0.4)
            app.rows = [{"id": "cf-1", "name": "Main"}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            app.action_extra()
            await pilot.pause(0.3)
            from swsh.tui.app import ContextMenu
            assert isinstance(app.screen, ContextMenu)
            labels = {str(b.label) for b in app.screen.query(".ctx-item")}
            assert len(labels) >= 2  # more than one drill, all shown as buttons

    async def test_escape_steps_back_from_a_drill_to_the_parent_list(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            app.switch_to("flows")
            await pilot.pause(0.4)
            app._drill = "versions"
            app.resource = __import__("swsh.resources", fromlist=["get"]).get("flows")
            app._refresh_view()
            await pilot.pause()
            app.action_go_calls()  # escape
            await pilot.pause(0.4)
            assert app._drill is None          # back out of the drill
            assert app.view == "rows"          # but still on the parent resource
            assert app.resource.key == "flows"


class TestActions:
    """Extras that write: a form when they need input, a confirmation when they
    change something, and a result or a reload afterwards. These were the 28
    operations that counted as covered while no keystroke reached them."""

    async def _rows(self, app, pilot, key, rows):
        app.switch_to(key)
        await pilot.pause(0.4)
        app.rows = rows
        app.load_error = None
        app._refresh_view()
        await pilot.pause()

    async def test_an_action_with_fields_opens_a_form_named_after_it(self):
        from swsh.tui.forms import FormScreen
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            await self._rows(app, pilot, "numbers", [{"id": "pn-1", "number": "+15550001111"}])
            assign = next(e for e in app.resource.extras if e.method == "assign_e911_address")
            app._start_extra(assign, "pn-1")
            await pilot.pause(0.3)
            assert isinstance(app.screen, FormScreen)
            assert str(app.screen.query_one("#form-title").content) == "assign E911 address"
            # The form collects only what this action takes, not the number's own fields.
            assert app.screen.query("#field-e911_address_id")
            assert not app.screen.query("#field-call_handler")

    async def test_a_confirmed_action_asks_first(self):
        from swsh.tui.app import ConfirmScreen
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            await self._rows(app, pilot, "numbers", [{"id": "pn-1", "number": "+15550001111"}])
            remove = next(e for e in app.resource.extras if e.method == "remove_e911_address")
            app._start_extra(remove, "pn-1")
            await pilot.pause(0.3)
            assert isinstance(app.screen, ConfirmScreen)
            assert "remove E911 address pn-1" in app.screen.question

    async def test_a_row_action_without_a_row_says_so_instead_of_opening_anything(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            await self._rows(app, pilot, "numbers", [])
            assign = next(e for e in app.resource.extras if e.method == "assign_e911_address")
            app._start_extra(assign, None)
            await pilot.pause(0.2)
            assert app.screen is app.screen_stack[0]

    async def test_drill_bound_actions_appear_only_inside_their_drill(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            await self._rows(app, pilot, "groups", [{"id": "grp-1", "name": "Sales"}])
            top = {e.label for e in app._available_extras()}
            assert "memberships" in top and "add member" in top
            assert "remove member" not in top and "show member" not in top

            app._drill = "memberships"
            app.rows = [{"id": "mem-1", "phone_number_id": "pn-1"}]
            app._refresh_view()
            await pilot.pause()
            inside = {e.label for e in app._available_extras()}
            assert inside == {"remove member", "show member"}
            assert ("extra", "More…") in app._context_actions()

    async def test_a_write_returning_an_object_shows_it_as_a_drill(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            await self._rows(app, pilot, "mfa", [])

            async def fake_invoke(resource, op, *, resource_id=None, body=None, **params):
                fake_invoke.calls.append((op, resource_id, body))
                return {"id": "req-1", "success": True, "to": body["to"]}

            fake_invoke.calls = []
            app.client.invoke = fake_invoke
            sms = next(e for e in app.resource.extras if e.method == "sms")
            app._run_extra(sms, None, {"to": "+15550002222"})
            await pilot.pause(0.4)
            assert fake_invoke.calls == [("sms", None, {"to": "+15550002222"})]
            assert app._drill == "send code by SMS"
            assert app.rows == [{"id": "req-1", "success": True, "to": "+15550002222"}]

    async def test_a_write_with_nothing_to_show_reloads_the_list(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            await self._rows(app, pilot, "numbers", [{"id": "pn-1", "number": "+15550001111"}])
            seen = []

            async def fake_invoke(resource, op, *, resource_id=None, body=None, **params):
                seen.append(op)
                return None if op == "remove_e911_address" else {"data": [{"id": "pn-1"}]}

            app.client.invoke = fake_invoke
            remove = next(e for e in app.resource.extras if e.method == "remove_e911_address")
            app._run_extra(remove, "pn-1")
            await pilot.pause(0.5)
            assert seen == ["remove_e911_address", "list"]
            assert app._drill is None

    async def test_an_action_inside_a_drill_refetches_that_drill(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            await self._rows(app, pilot, "groups", [{"id": "grp-1", "name": "Sales"}])
            seen = []

            async def fake_invoke(resource, op, *, resource_id=None, body=None, **params):
                seen.append((op, resource_id))
                if op == "list_memberships":
                    return {"data": [{"id": "mem-2"}]}
                return None

            app.client.invoke = fake_invoke
            memberships = next(e for e in app.resource.extras if e.method == "list_memberships")
            app._run_extra(memberships, "grp-1")
            await pilot.pause(0.4)
            assert app._drill == "memberships" and app._drill_parent == "grp-1"

            remove = next(e for e in app.resource.extras if e.method == "remove_member")
            app._run_extra(remove, "mem-1")
            await pilot.pause(0.5)
            assert seen == [("list_memberships", "grp-1"), ("remove_member", "mem-1"),
                            ("list_memberships", "grp-1")]
            assert app._drill == "memberships"
            assert app.rows == [{"id": "mem-2"}]


class TestDialFromTheCockpit:
    async def test_n_on_the_live_view_opens_the_new_call_form(self):
        from swsh.tui.forms import FormScreen
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            app.action_go_calls()
            await pilot.pause()
            assert app.view == "calls"
            assert not app.query_one("#act-new", Button).disabled
            assert ("dial", "New call") in app._context_actions()
            await pilot.press("n")
            await pilot.pause(0.3)
            assert isinstance(app.screen, FormScreen)
            assert str(app.screen.query_one("#form-title").content) == "new call"
            for name in ("from_", "to", "url", "say"):
                assert app.screen.query(f"#field-{name}"), name

    async def test_the_form_places_the_call_through_the_client(self):
        from swsh.tui.forms import FormScreen
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            placed = []

            async def fake_dial(**kw):
                placed.append(kw)

            app.client.dial = fake_dial
            app.action_dial()
            await pilot.pause(0.3)
            form = app.screen
            assert isinstance(form, FormScreen)
            form.dismiss({"from_": "+15550001111", "to": "+15550002222", "say": "hello"})
            await pilot.pause(0.4)
            assert placed == [{"to": "+15550002222", "from_": "+15550001111",
                               "url": None, "say": "hello"}]

    async def test_a_call_with_nothing_to_run_is_refused_locally(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 45)) as pilot:
            placed = []

            async def fake_dial(**kw):
                placed.append(kw)

            app.client.dial = fake_dial
            app.action_dial()
            await pilot.pause(0.3)
            app.screen.dismiss({"from_": "+15550001111", "to": "+15550002222"})
            await pilot.pause(0.3)
            assert placed == []


class TestPolish:
    async def test_detail_renders_fields_not_raw_json(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("agents")
            await pilot.pause(0.4)
            app.rows = [{"id": "ag-1", "display_name": "Support", "record": True}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            text = rendered_text(app.query_one("#detail"))
            assert "Support" in text
            assert "yes" in text  # bool rendered as yes/no, not "True"

    async def test_message_detail_shows_body_fetched_from_url(self):
        """The logs API omits the body; the detail pane must fetch it from the
        row's LaML url and show the actual content, not just metadata."""
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            async def fake_rest_call(method, url, **kw):
                assert "/Messages/" in url
                return {"body": "your appointment is confirmed"}
            app.client.rest_call = fake_rest_call

            app.switch_to("messages")
            await pilot.pause(0.4)
            app.rows = [{
                "id": "m-1", "from": "+1", "to": "+2", "direction": "inbound",
                "status": "received",
                "url": "https://example.signalwire.com/api/laml/2010-04-01/Accounts/a/Messages/m-1",
            }]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()       # first paint: body shows "loading…", fetch starts
            await pilot.pause(0.3)    # worker returns, detail repaints with the body
            text = rendered_text(app.query_one("#detail"))
            assert "your appointment is confirmed" in text
            assert app._body_cache["m-1"] == "your appointment is confirmed"

    async def test_sparkline_samples_live_call_count(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.store.apply(call_event("CA1", CallState.ANSWERED))
            app._sample_vitals()
            spark = app.query_one("#vitals")
            assert spark.data[-1] == 1

    async def test_context_menu_lists_valid_actions(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("queues")
            await pilot.pause(0.4)
            app.rows = [{"id": "q-1", "name": "support"}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            app.action_context()
            await pilot.pause(0.3)
            from swsh.tui.app import ContextMenu
            assert isinstance(app.screen, ContextMenu)
            ids = {b.id for b in app.screen.query("Button")}
            assert {"ctx-new", "ctx-edit", "ctx-delete"} <= ids

    async def test_context_menu_on_read_only_resource_omits_writes(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("logs")
            await pilot.pause(0.4)
            app.rows = [{"id": "l-1"}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            actions = {a for a, _ in app._context_actions()}
            assert "new" not in actions and "delete" not in actions
            assert "inspect" in actions


class TestClickableDialogs:
    async def test_confirm_has_yes_no_buttons(self):
        from swsh.tui.app import ConfirmScreen
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("queues")
            await pilot.pause(0.4)
            app.rows = [{"id": "q-1", "name": "s"}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            app.action_delete()
            await pilot.pause(0.3)
            assert isinstance(app.screen, ConfirmScreen)
            ids = {b.id for b in app.screen.query("Button")}
            assert {"confirm-yes", "confirm-no"} <= ids

    async def test_clicking_yes_confirms(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.switch_to("queues")
            await pilot.pause(0.4)
            app.rows = [{"id": "q-1", "name": "s"}]
            app.load_error = None
            app._refresh_view()
            await pilot.pause()
            recorder = []
            async def fake(resource, op, **kw):
                recorder.append((op, kw.get("resource_id")))
                return {}
            app.client.invoke = fake
            app.action_delete()
            await pilot.pause(0.3)
            app.screen.query_one("#confirm-yes", Button).press()
            await pilot.pause(0.3)
            assert ("delete", "q-1") in recorder

    async def test_jump_list_is_clickable_not_typed(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.press("ctrl+r")
            await pilot.pause(0.3)
            # no text input to type into; navigation is by clicking a button
            assert not app.screen.query("#jump-input")
            app.screen.query_one("#drop-numbers", Button).press()
            await pilot.pause(0.3)
            assert app.resource is not None and app.resource.key == "numbers"


class TestRightPaneAndMenus:
    """Screenshot review, 2026-09-10: one thing looked like three, and the
    events feed crowded the detail on views that have no events."""

    async def test_voice_dropdown_does_not_repeat_the_calls_button(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.click("#menu-voice")
            await pilot.pause()
            ids = {b.id for b in app.screen.query(".drop-item")}
            assert "drop-calls" not in ids
            assert "drop-queues" in ids  # voice logs moved to the Logs menu

    async def test_dropdown_entries_start_with_a_capital(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.click("#menu-fabric")
            await pilot.pause()
            labels = [str(b.label) for b in app.screen.query(".drop-item")]
            assert labels and all(label[0].isupper() for label in labels)
            assert "CXML scripts" in labels  # only the first letter changes

    async def test_detail_takes_the_column_off_the_live_view(self):
        from textual.widgets import RichLog

        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 50)) as pilot:
            app.action_go_calls()
            await pilot.pause()
            assert app.query_one("#feed", RichLog).display is True
            app.switch_to("agents")
            await pilot.pause()
            assert app.query_one("#feed", RichLog).display is False
            assert app.query_one("#events-title").display is False
            assert str(app.query_one("#detail-scroll").styles.height) == "1fr"
            app.action_go_calls()
            await pilot.pause()
            assert app.query_one("#feed", RichLog).display is True

    async def test_meter_reads_as_a_count_not_a_menu_item(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 50)) as pilot:
            app.store.apply(call_event("CA1", CallState.ANSWERED))
            app._sample_vitals()
            await pilot.pause()
            assert "live calls 1" in rendered_text(app.query_one("#vitals-label"))


class TestDetailShowsEverything:
    """Screenshot review, 2026-09-10: an AI agent's prompt lives inside a nested
    object, and the detail pane cut nested objects off at 200 characters."""

    async def test_nested_fields_are_flattened_and_never_truncated(self):
        prompt = "You are a patient airline agent. " * 20  # well past 200 chars
        row = {
            "id": "ag-1", "display_name": "Example Air", "type": "ai_agent",
            "ai_agent": {"prompt": {"text": prompt, "temperature": 0.3},
                         "languages": [{"code": "en-US", "voice": "polly.Joanna"}],
                         "post_prompt": {"text": ""}},
        }
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(200, 60)) as pilot:
            app.view = "rows"
            app.resource = __import__("swsh.resources", fromlist=["get"]).get("agents")
            app.rows = [row]
            app._render_rows()
            app._render_detail()
            await pilot.pause()
            text = rendered_text(app.query_one("#detail"))
            flat = " ".join(text.split())
            assert "ai_agent.prompt.text" in flat
            assert prompt.strip() in flat, "the prompt must appear whole"
            assert "…" not in flat
            assert "ai_agent.prompt.temperature" in flat and "0.3" in flat
            assert "polly.Joanna" in flat  # lists of objects are printed in full


class TestDetailFormats:
    """`v`: the same three readings of a row that the CLI prints.

    `fields` is sw reading it for you, `json` is the row sw holds, `raw` is the
    record the API returns when asked for that row on its own. The third is the
    one that needed wiring: a list response is a summary, and the pane had no
    way to show the rest.
    """

    ROW = {"id": "q-1", "name": "support", "max_size": 100}
    RECORD = {"id": "q-1", "name": "support", "max_size": 100,
              "undocumented_field": "only in the record", "created_at": "2026-09-01"}

    async def ready(self, app, pilot, key="queues", rows=None):
        app.view = "rows"
        app.resource = res.get(key)
        app.rows = rows if rows is not None else [self.ROW]
        app.loading = False
        app.load_error = None
        app._render_rows()
        app._render_detail()
        await pilot.pause()

    async def test_v_cycles_fields_json_raw_and_back(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(200, 60)) as pilot:
            await self.ready(app, pilot)
            assert app.detail_mode == "fields"
            for expected in ("json", "raw", "fields"):
                app.action_detail_mode()
                await pilot.pause()
                assert app.detail_mode == expected

    async def test_json_is_the_row_sw_holds(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(200, 60)) as pilot:
            await self.ready(app, pilot)
            app.action_detail_mode()
            await pilot.pause()
            text = rendered_text(app.query_one("#detail"))
            assert '"max_size": 100' in text  # a JSON document, not a field table
            assert "json" in text

    async def test_raw_fetches_the_record_and_shows_what_the_row_lacked(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(200, 60)) as pilot:
            await self.ready(app, pilot)
            asked: list[tuple] = []

            async def fake_invoke(resource, op, *, resource_id=None, **kw):
                asked.append((resource.key, op, resource_id))
                return self.RECORD

            app.client.invoke = fake_invoke
            app.detail_mode = "raw"
            app._render_detail()
            await pilot.pause(0.3)

            assert asked == [("queues", "read", "q-1")]
            text = rendered_text(app.query_one("#detail"))
            assert "undocumented_field" in text
            # and it is kept: moving away and back must not re-ask
            app._render_detail()
            await pilot.pause()
            assert len(asked) == 1

    async def test_a_failed_read_is_a_line_not_a_crash(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(200, 60)) as pilot:
            await self.ready(app, pilot)

            async def boom(resource, op, **kw):
                raise SwshError("404 not found")

            app.client.invoke = boom
            app.detail_mode = "raw"
            app._render_detail()
            await pilot.pause(0.3)
            text = rendered_text(app.query_one("#detail"))
            assert "404 not found" in text
            assert "support" in text  # the row is still shown under the error

    async def test_a_drill_shows_its_own_row_without_asking_the_parents_route(self):
        """A membership is not a number group; reading it by the parent's route
        is the same wrong request `e` was withheld for."""
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(200, 60)) as pilot:
            await self.ready(app, pilot, key="groups", rows=[{"id": "m-1", "number_id": "n-9"}])
            app._drill = "memberships"
            asked: list[tuple] = []

            async def fake_invoke(resource, op, **kw):
                asked.append((resource.key, op))
                return {}

            app.client.invoke = fake_invoke
            app.detail_mode = "raw"
            app._render_detail()
            await pilot.pause(0.3)
            assert asked == []
            text = rendered_text(app.query_one("#detail"))
            assert "from the list response" in text
            assert "n-9" in text

    async def test_routing_and_the_formats_are_alternatives(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(200, 60)) as pilot:
            await self.ready(app, pilot, key="numbers",
                             rows=[{"id": "pn-1", "number": "+15551234567",
                                    "call_handler": "laml_webhooks"}])
            app.detail_mode = "json"
            app._routing = ("pn-1", object())
            app.action_detail_mode()
            await pilot.pause()
            assert app._routing is None      # the tree is not shown under a format
            app.action_routing()
            await pilot.pause()
            assert app.detail_mode == "fields"

    async def test_the_live_view_formats_a_call_too(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(200, 60)) as pilot:
            app.action_go_calls()
            app.store.apply(call_event("CA1", CallState.ANSWERED,
                                       from_number="+15551112222"))
            await pilot.pause()
            app.query_one("#calls", DataTable).move_cursor(row=0)
            app.detail_mode = "json"
            app._render_detail()
            await pilot.pause()
            text = rendered_text(app.query_one("#detail"))
            assert '"state": "answered"' in text

    async def test_the_footer_offers_it_wherever_there_is_a_row(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(200, 60)) as pilot:
            await pilot.pause()
            assert app.check_action("detail_mode", ()) is False   # the dashboard
            app.action_go_calls()
            await pilot.pause()
            assert app.check_action("detail_mode", ()) is True
            await self.ready(app, pilot)
            assert app.check_action("detail_mode", ()) is True


class TestFullRouting:
    """`F`: the `get --full` expansion, in the detail pane.

    The expansion itself is pinned in test_routing.py; what matters here is
    that it runs off the paint loop, that it belongs to the row it was opened
    on, and that it toggles back.
    """

    ROW = {"id": "pn-1", "number": "+15551234567", "name": "Fax",
           "call_handler": "laml_webhooks", "calling_handler_resource_id": "wh-1"}
    OTHER = {"id": "pn-2", "number": "+15559999999", "name": "Other",
             "call_handler": "relay_script", "calling_handler_resource_id": None}

    def _result(self):
        from swsh import routing

        return routing.Routing(
            row=self.ROW,
            channels=[routing.Channel(
                "voice", "laml_webhooks", {"call_request_url": "https://x/y"},
                routing.Node(kind="cxml_script", id="sc-1", name="hide my caller id",
                             documents=[routing.Document("contents", "xml",
                                                         "<Response><Dial/></Response>")]))],
            unused={"call_laml_application_id": "app-9"},
        )

    def _app(self, monkeypatch, expand=None):
        from swsh import resources
        from swsh.tui import app as appmod

        async def fake_expand(client, resource, row):
            return (expand or self._result)()

        monkeypatch.setattr(appmod.routing, "expand", fake_expand)
        app = SwshApp(profile=FAKE)
        app.view = "rows"
        app.resource = resources.get("numbers")
        app.rows = [self.ROW, self.OTHER]
        return app

    async def test_f_shows_the_routing_tree(self, monkeypatch):
        app = self._app(monkeypatch)
        async with app.run_test(size=(160, 50)) as pilot:
            app._render_rows()
            await pilot.press("F")
            await pilot.pause()
            await pilot.pause()
            text = " ".join(rendered_text(app.query_one("#detail")).split())
            assert "VOICE laml_webhooks" in text
            assert "cxml_script" in text
            assert "<Response><Dial/></Response>" in text
            # the sediment is named, which is the point of the view
            assert "NOT IN USE" in text and "call_laml_application_id" in text

    async def test_f_again_returns_to_the_field_table(self, monkeypatch):
        app = self._app(monkeypatch)
        async with app.run_test(size=(160, 50)) as pilot:
            app._render_rows()
            await pilot.press("F")
            await pilot.pause()
            await pilot.pause()
            await pilot.press("F")
            await pilot.pause()
            text = " ".join(rendered_text(app.query_one("#detail")).split())
            assert "VOICE" not in text
            assert "call_handler laml_webhooks" in text

    async def test_moving_off_the_row_drops_the_tree(self, monkeypatch):
        # A tree built for one number must never be shown against another.
        app = self._app(monkeypatch)
        async with app.run_test(size=(160, 50)) as pilot:
            app._render_rows()
            await pilot.press("F")
            await pilot.pause()
            await pilot.pause()
            app.query_one("#rows", DataTable).cursor_coordinate = (1, 0)
            app._render_detail()
            await pilot.pause()
            text = " ".join(rendered_text(app.query_one("#detail")).split())
            assert "VOICE" not in text
            assert app._routing is None

    async def test_a_slow_expansion_says_so_and_never_blocks(self, monkeypatch):
        import asyncio

        from swsh.tui import app as appmod

        started = asyncio.Event()
        release = asyncio.Event()

        async def slow(client, resource, row):
            started.set()
            await release.wait()
            return self._result()

        app = self._app(monkeypatch, expand=None)
        monkeypatch.setattr(appmod.routing, "expand", slow)
        async with app.run_test(size=(160, 50)) as pilot:
            app._render_rows()
            await pilot.press("F")
            await asyncio.wait_for(started.wait(), 2)
            await pilot.pause()
            text = " ".join(rendered_text(app.query_one("#detail")).split())
            assert "following the routing" in text
            assert app.is_running  # the paint loop is still going
            release.set()
            await pilot.pause()
            await pilot.pause()
            assert "cxml_script" in rendered_text(app.query_one("#detail"))

    async def test_a_failure_notifies_rather_than_crashing(self, monkeypatch):
        from swsh.tui import app as appmod

        async def boom(client, resource, row):
            raise RuntimeError("space is on fire")

        app = self._app(monkeypatch)
        monkeypatch.setattr(appmod.routing, "expand", boom)
        async with app.run_test(size=(160, 50)) as pilot:
            app._render_rows()
            await pilot.press("F")
            await pilot.pause()
            await pilot.pause()
            assert app.is_running
            assert app._routing is None and app._routing_loading is None
            assert "call_handler laml_webhooks" in " ".join(
                rendered_text(app.query_one("#detail")).split())

    async def test_a_resource_with_no_routing_says_so(self, monkeypatch):
        from swsh import resources

        app = self._app(monkeypatch)
        app.resource = resources.get("queues")
        app.rows = [{"id": "q-1", "friendly_name": "support"}]
        async with app.run_test(size=(160, 50)) as pilot:
            app._render_rows()
            await pilot.press("F")
            await pilot.pause()
            assert app._routing is None
            assert app.is_running

    async def test_the_context_menu_offers_it_only_where_it_applies(self, monkeypatch):
        from swsh import resources

        app = self._app(monkeypatch)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause()
            assert ("routing", "Full routing") in app._context_actions()
            app.resource = resources.get("queues")
            assert ("routing", "Full routing") not in app._context_actions()


import pytest  # noqa: E402

from swsh import config  # noqa: E402


@pytest.fixture
def profiles(tmp_path, monkeypatch):
    """Two stored profiles in a sandboxed config file, no real env vars."""
    cfg = tmp_path / "config.toml"
    monkeypatch.setattr(config, "config_path", lambda: cfg)
    legacy = [a for aliases in config.ENV_ALIASES.values() for a in aliases]
    for var in (config.ENV_PROJECT, config.ENV_TOKEN, config.ENV_SPACE, "SWSH_PROFILE", *legacy):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(config, "_keyring_set", lambda *a, **k: False)
    monkeypatch.setattr(config, "_keyring_get", lambda *a, **k: None)
    monkeypatch.setattr(config, "load_dotenv", lambda path=None: {})
    config.save_profile("test", "proj-1", "tok", "nowhere.invalid")
    config.save_profile("scratch", "proj-2", "tok2", "elsewhere.invalid", make_default=False)
    config.set_default("test")
    return cfg


class TestProfileManager:
    """Requested 2026-09-10: add, edit, remove and switch profiles inside the
    TUI, the way `sw profile use` does from the shell."""

    async def test_ctrl_p_lists_profiles_and_marks_the_one_in_use(self, profiles):
        from swsh.tui.app import ProfileScreen

        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("ctrl+p")
            await pilot.pause()
            assert isinstance(app.screen, ProfileScreen)
            options = app.screen.query_one("#profile-list")
            prompts = [str(options.get_option_at_index(i).prompt)
                       for i in range(options.option_count)]
            assert any("scratch" in p for p in prompts)
            assert any("test" in p and "(in use)" in p for p in prompts)

    async def test_menu_button_opens_the_same_screen(self, profiles):
        from swsh.tui.app import ProfileScreen

        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.click("#menu-profile")
            await pilot.pause()
            assert isinstance(app.screen, ProfileScreen)

    async def test_choosing_a_profile_switches_the_cockpit_and_the_cli_default(self, profiles):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 50)) as pilot:
            old_client = app.client
            app._profile_chosen("scratch")
            await pilot.pause()
            for _ in range(20):
                if app.profile.name == "scratch":
                    break
                await pilot.pause(0.05)
            assert app.profile.name == "scratch"
            assert app.profile.host == "elsewhere.invalid"
            assert app.client is not old_client and app.client.profile.project == "proj-2"
            assert app.poller.client is app.client  # the pipeline follows the profile
            assert config.default_profile_name() == "scratch"  # `sw` picks it up too
            assert "scratch" in rendered_text(app.query_one("#statusbar"))

    async def test_new_profile_form_saves_without_switching(self, profiles):
        from textual.widgets import Input

        from swsh.tui.app import ProfileFormScreen, ProfileScreen

        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.press("ctrl+p")
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            assert isinstance(app.screen, ProfileFormScreen)
            for key, value in (("name", "third"), ("project", "proj-3"),
                               ("token", "tok3"), ("space", "third.invalid")):
                app.screen.query_one(f"#pf-{key}", Input).value = value
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert isinstance(app.screen, ProfileScreen)
            assert "third" in config.list_profiles()
            assert config.default_profile_name() == "test"
            assert app.profile.name == FAKE.name

    async def test_form_refuses_blanks(self, profiles):
        from swsh.tui.app import ProfileFormScreen

        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 50)) as pilot:
            app.push_screen(ProfileFormScreen())
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert isinstance(app.screen, ProfileFormScreen)
            assert "required" in rendered_text(app.screen.query_one("#pf-error"))

    async def test_delete_asks_then_removes(self, profiles):
        from swsh.tui.app import ConfirmScreen, ProfileScreen

        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(160, 50)) as pilot:
            app.push_screen(ProfileScreen(active="test"))
            await pilot.pause()
            options = app.screen.query_one("#profile-list")
            options.highlighted = [str(options.get_option_at_index(i).id)
                                   for i in range(options.option_count)].index("scratch")
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)
            await pilot.press("y")
            await pilot.pause()
            assert config.list_profiles() == ["test"]


def test_subprojects_is_the_name_people_see():
    from swsh import resources as res

    assert res.get("projects").title == "subprojects"


class TestMenuLayout:
    """Menu review, 2026-09-10: logs together, AI its own group, Fabric read as
    Resources with SWML first and cXML last, and a way to buy a number."""

    async def test_menu_bar_reads_as_people_name_things(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause()
            labels = [str(b.label) for b in app.query("#menubar .menu-item")]
            # Calls is last: it is a place rather than a resource group, and it
            # stays beside the live-call meter. There is no Lab item — the
            # phone is a panel on Calls, so the way to one is the way to both.
            assert labels == ["Numbers", "Voice", "Messaging", "AI Agents",
                              "Resources", "Video", "Logs", "Other", "Profile",
                              "Calls"]
            assert "Lab" not in labels

    async def test_every_log_lives_under_logs(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.click("#menu-logs")
            await pilot.pause()
            ids = [b.id for b in app.screen.query(".drop-item")]
            assert ids == ["drop-logs", "drop-conflogs", "drop-messages", "drop-fax",
                           "drop-vlogs"]

    async def test_ai_group_holds_agents_and_datasphere(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.click("#menu-ai")
            await pilot.pause()
            items = {b.id: str(b.label) for b in app.screen.query(".drop-item")}
            # Chunks are not here: every route they have needs a document id,
            # so they are a drill off Datasphere rather than a screen.
            assert list(items) == ["drop-agents", "drop-datasphere"]
            assert items["drop-datasphere"] == "Datasphere"
            assert res.get("chunks").drill_from == "datasphere"

    async def test_resources_lead_with_swml_and_end_with_cxml(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.click("#menu-fabric")
            await pilot.pause()
            ids = [b.id for b in app.screen.query(".drop-item")]
            assert ids[:2] == ["drop-swml", "drop-swmlhooks"]
            assert ids[-3:] == ["drop-cxml", "drop-cxmlhooks", "drop-cxmlapps"]
            assert "drop-agents" not in ids

    async def test_numbers_menu_offers_buying_first(self):
        from swsh.tui.numbers import NumberSearchScreen

        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.click("#menu-numbers")
            await pilot.pause()
            items = list(app.screen.query(".drop-item"))
            assert items[0].id == "drop-buy-numbers"
            assert str(items[0].label) == "Buy numbers"
            items[0].press()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, NumberSearchScreen)
            assert app.resource is not None and app.resource.key == "numbers"


def test_docs_group_headings_match_the_menu():
    from swsh.cli import _render_docs

    text = _render_docs()
    assert "## Resources" in text and "## AI Agents" in text and "## Logs" in text
    assert "## fabric" not in text


class TestTheMenuBarReadsInOrderOfUse:
    """Numbers leads; the live calls view trails.

    Calls led the bar because it was the app's first view, which put the one
    screen that is only occasionally interesting ahead of the eight people
    navigate by. A phone number is what a project starts with, so Numbers
    leads and the channels it routes to follow.
    """

    async def test_the_groups_read_numbers_voice_messaging_agents(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.pause()
            labels = [str(b.label) for b in app.query("#menubar Button")]
            assert labels[:4] == ["Numbers", "Voice", "Messaging", "AI Agents"]

    async def test_calls_is_last_beside_the_meter_that_counts_them(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.pause()
            buttons = list(app.query("#menubar Button"))
            assert buttons[-1].id == "menu-calls"
            # and it still navigates, from wherever the cursor happens to be
            app.switch_to("agents")
            await pilot.pause()
            buttons[-1].press()
            await pilot.pause()
            assert app.view == "calls"


class TestTheFooterOffersOnlyWhatTheViewCanDo:
    """A key that does nothing is worse than a key that is not there.

    Every binding used to show on every view: `F routing` on AI agents, which
    declare none, `t transfer` over a table of SIP endpoints, `n new` on a
    read-only log. `check_action` is the one place that decides, and the
    footer, the action bar and the `.` menu all read from the same facts.
    """

    @staticmethod
    def _keys(app) -> set[str]:
        return {b.binding.description
                for b in app.screen.active_bindings.values() if b.binding.show}

    async def _on(self, pilot, app, key: str) -> set[str]:
        app.switch_to(key)
        await pilot.pause()
        return self._keys(app)

    async def test_routing_shows_only_where_a_resource_declares_it(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.pause()
            # numbers declares Route(...); agents declares nothing
            assert "routing" in await self._on(pilot, app, "numbers")
            assert "routing" not in await self._on(pilot, app, "agents")
            assert res.get("agents").routing == ()

    async def test_a_read_only_resource_offers_no_crud_keys(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.pause()
            keys = await self._on(pilot, app, "logs")
            assert not {"new", "edit", "delete"} & keys
            assert "refresh" in keys

    async def test_call_controls_belong_to_the_calls_view_alone(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.action_go_calls()
            await pilot.pause()
            controls = {"hangup", "transfer", "say", "dtmf", "record",
                        "show ended", "clear feed"}
            assert controls <= self._keys(app)          # the live view
            assert not controls & await self._on(pilot, app, "sip")
            # and not on the dashboard either
            app.action_go_home()
            await pilot.pause()
            assert not controls & self._keys(app)

    async def test_the_way_back_is_offered_only_when_there_is_one(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.pause()
            # the dashboard is the root: there is nowhere further out
            assert "back" not in self._keys(app)
            assert "back" in await self._on(pilot, app, "numbers")

    async def test_the_footer_agrees_with_the_action_bar_and_context_menu(self):
        # Three surfaces, one set of facts. They drifted before because each
        # decided for itself what was available.
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await pilot.pause()
            for key in ("numbers", "agents", "logs", "mfa"):
                keys = await self._on(pilot, app, key)
                menu = {label for _, label in app._context_actions()}
                assert ("new" in keys) == ("New" in menu), key
                assert ("edit" in keys) == ("Edit" in menu), key
                assert ("delete" in keys) == ("Delete" in menu), key
                assert ("routing" in keys) == ("Full routing" in menu), key
                for btn_id, desc in (("act-new", "new"), ("act-edit", "edit"),
                                     ("act-delete", "delete")):
                    button = app.query_one(f"#{btn_id}", Button)
                    assert button.disabled == (desc not in keys), (key, btn_id)


class TestAScreenOffersOnlyWhatTheItemCanDo:
    """Review, 2026-09-16: every surface reads the same capabilities.

    The footer, the action bar, the `.` menu and the `x` menu each used to
    decide for themselves, and all four promised things the route could not
    deliver — `e` and `d` on project tokens, which the API gives no list to
    select from; a Campaigns screen whose every route needs a brand id; a
    Number lookup screen that could do nothing at all.
    """

    async def _open(self, app, pilot, key):
        app.switch_to(key)
        await pilot.pause(0.4)
        return ({b.binding.description
                 for b in app.screen.active_bindings.values() if b.binding.show},
                {label for _, label in app._context_actions()},
                {b.id.removeprefix("act-") for b in app.query("#actionbar Button")
                 if not b.disabled})

    async def test_a_create_only_namespace_offers_create_and_nothing_else(self):
        # Project tokens can be updated and deleted by id, but the API publishes
        # no list, so the browser can never put one under the cursor.
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            keys, menu, bar = await self._open(app, pilot, "tokens")
            assert "new" in keys and bar == {"new"}
            assert not {"edit", "delete", "refresh"} & keys
            assert menu == {"New"}
            # the capability itself is untouched — this is about reachability
            assert res.get("tokens").caps == "CUD"

    async def test_an_action_only_namespace_offers_its_actions(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            keys, menu, _ = await self._open(app, pilot, "mfa")
            assert "more" in keys and menu == {"More…"}
            assert not {"new", "edit", "delete"} & keys
            assert {e.label for e in app._available_extras()} == {
                "send code by call", "send code by SMS", "verify code"}

    async def test_the_lookup_screen_can_actually_look_a_number_up(self):
        # `/lookup/phone_number/{e164_number}`: the number is the route, so the
        # only way to ask is to type one. The screen had no way to do that.
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            keys, menu, _ = await self._open(app, pilot, "lookup")
            assert "more" in keys and menu == {"More…"}
            extra = next(e for e in app._available_extras())
            assert extra.label == "look up a number"
            assert [f.name for f in extra.fields] == ["e164_number"]

    async def test_an_extra_that_needs_a_row_is_withheld_where_none_can_exist(self):
        # `x` on a create-only screen must not list actions that want the
        # highlighted row: subscriber tokens offers its four minting actions,
        # and would offer nothing that needed an id.
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            keys, _, _ = await self._open(app, pilot, "subtokens")
            assert "more" in keys and "new" in keys
            offered = app._available_extras()
            assert offered and all(not e.needs_id for e in offered)

    async def test_a_singleton_shows_its_record_instead_of_an_empty_table(self):
        # One project-wide SIP profile: `GET /sip_profile` takes no id, so there
        # is a record to show and an `e` that can find it.
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            seen = []

            async def fake_invoke(resource, op, *, resource_id=None, body=None, **params):
                seen.append((op, resource_id))
                return {"id": "sp-1", "domain": "acme", "username": "u"}

            app.client.invoke = fake_invoke
            keys, menu, _ = await self._open(app, pilot, "sipprofile")
            assert seen == [("read", None)]
            assert app.rows == [{"id": "sp-1", "domain": "acme", "username": "u"}]
            assert "edit" in keys and "Edit" in menu
            assert "delete" not in keys      # caps are RU
            assert "nothing to list" not in str(
                app.query_one("#pane-title", Static).content)


class TestDrillOnlyResourcesAreNotMenuEntries:
    """A campaign lives under a brand; a chunk under a document.

    Every route they have needs the parent's id, so their own screen could only
    ever be an empty table. They stay reachable as drills, and by name from the
    CLI where the id can be typed — what they stop being is a door onto a wall.
    """

    async def test_they_are_absent_from_the_group_menu_and_the_jump_list(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.click("#menu-messaging")
            await pilot.pause(0.3)
            assert "drop-campaigns" not in {b.id for b in app.screen.query(".drop-item")}
            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause(0.3)
            listed = {b.id for b in app.screen.query(".drop-item")}
            for key in ("campaigns", "subcreds", "chunks", "vstreams"):
                assert f"drop-{key}" not in listed, key
            assert "drop-numbers" in listed

    async def test_typing_the_name_lands_on_the_parent_that_has_the_rows(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause()
            app.switch_to("campaigns")
            await pilot.pause(0.4)
            assert app.resource is not None and app.resource.key == "brands"


class TestADrillDoesNotInheritTheParentsCrud:
    """Inside `groups > memberships` the rows are memberships, not groups.

    `e` and `d` there resolved the membership's id and sent it to the
    number-group update and delete routes — a well-formed request against the
    wrong object, which is worse than a key that fails. Acting on a drill's
    rows is what an `Extra` with `on_drill` is for, and those still show.
    """

    async def _drill_into(self, app, pilot, parent, method):
        app.switch_to(parent)
        await pilot.pause(0.3)

        async def fake(resource, op, *, resource_id=None, body=None, **params):
            return {"data": [{"id": "child-1"}]}

        app.client.invoke = fake
        extra = next(e for e in app.resource.extras if e.method == method)
        app._run_extra(extra, "parent-1")
        await pilot.pause(0.5)
        return {b.binding.description
                for b in app.screen.active_bindings.values() if b.binding.show}

    async def test_the_parents_crud_keys_are_withheld_in_a_drill(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause()
            keys = await self._drill_into(app, pilot, "groups", "list_memberships")
            assert app._drill == "memberships"
            assert app.resource.caps == "LCRUD"      # the parent can do all of it
            assert not {"new", "edit", "delete"} & keys
            # what the drill's own rows support is still there
            assert "more" in keys
            assert {e.label for e in app._available_extras()} == {
                "show member", "remove member"}
            assert [label for _, label in app._context_actions()] == ["Inspect", "More…"]

    async def test_stepping_back_out_restores_them(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause()
            await self._drill_into(app, pilot, "groups", "list_memberships")
            app.action_refresh()          # a drill's refresh returns to the parent
            await pilot.pause(0.4)
            assert app._drill is None
            keys = {b.binding.description
                    for b in app.screen.active_bindings.values() if b.binding.show}
            assert {"new", "edit", "delete"} <= keys


class TestTheCockpitOpensOnADashboard:
    """The cockpit used to open on the live calls table.

    On a quiet project that is an empty table and no sign of what else is
    there — the worst first screen the app had. The dashboard names the space
    and profile in play and counts what the project holds, and the calls view
    is one keystroke away rather than the front door.
    """

    async def test_it_is_the_landing_view_and_the_calls_table_is_not(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause()
            assert app.view == "home"
            assert app.query_one("#main", ContentSwitcher).current == "home"
            assert app.resource is None

    async def test_the_banner_names_the_space_and_profile(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause()
            from swsh.tui import home as home_mod

            rendered = rendered_text(app.query_one("#home-body", Static))
            # the wordmark is block glyphs, so match the rows themselves
            assert all(row.strip() in rendered for row in home_mod._logo_rows())
            assert FAKE.host in rendered
            assert FAKE.name in rendered

    async def test_a_narrow_terminal_gets_the_wordmark_not_wrapped_blocks(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(50, 30)) as pilot:
            await pilot.pause()
            rendered = rendered_text(app.query_one("#home-body", Static))
            assert "SignalWire" in rendered
            assert "█" not in rendered

    async def test_the_dashboard_takes_the_whole_width(self):
        # No selection to detail and no live feed to run, so the right column
        # would be two empty panes next to the banner.
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause()
            assert app.query_one("#right").display is False
            app.action_go_calls()
            await pilot.pause()
            assert app.query_one("#right").display is True

    async def test_something_holds_focus_so_keys_reach_the_app(self):
        # The hidden `:` input is the first focusable widget. Left focused, it
        # swallowed every keystroke, including the `:` meant to summon it.
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause()
            assert app.focused is not None and app.focused.id == "home"
            await pilot.press("colon")
            await pilot.pause()
            assert app.query_one("#command", Input).display

    async def test_the_live_calls_tile_is_counted_from_the_store(self):
        # Free and exact, so it does not wait on a request.
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause()
            app.store.apply(call_event("CA1", CallState.ANSWERED))
            app.store.apply(call_event("CA2", CallState.ANSWERED))
            app._render_home()
            await pilot.pause()
            assert "2" in rendered_text(app.query_one("#home-body", Static))

    async def test_counts_come_from_the_registry_and_survive_a_failure(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause()
            asked = []

            async def fake_invoke(resource, op, *, resource_id=None, body=None, **params):
                asked.append((resource.key, op))
                if resource.key == "agents":
                    raise SwshError("nope")
                return {"data": [{"id": "a"}, {"id": "b"}]}

            async def fake_calls(*, limit=50, lookback=None, **filters):
                return []

            app.client.invoke = fake_invoke
            app.client.recent_calls = fake_calls
            app.load_metrics()
            await pilot.pause(0.5)
            assert ("numbers", "list") in asked and ("sip", "list") in asked
            assert app._metrics["phone numbers"].value == 2
            # one failure does not take the others, or the banner, down
            assert app._metrics["AI agents"].error
            assert "1 of" in app._metrics_note
            rendered = rendered_text(app.query_one("#home-body", Static))
            assert FAKE.host in rendered

    async def test_every_metric_names_a_real_resource(self):
        from swsh.tui import home as home_mod

        for metric in home_mod.METRICS:
            if metric.source in ("store", "calls"):
                continue
            resource = res.get(metric.source)
            assert resource is not None, metric.source
            assert resource.can_list, metric.source

    async def test_refresh_refetches_the_tiles_rather_than_a_table(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause()
            runs = []
            app.load_metrics = lambda: runs.append(1)
            app.action_refresh()
            assert runs == [1]


class TestTheKeysAreDiscoverable:
    """`check_action` *hides* a binding that does not apply rather than greying
    it, so most of the app's keys are invisible most of the time, and `j`/`k`
    are `show=False` and were advertised nowhere at all. The only hint the app
    printed went to the event feed, which is hidden on the view it opens on."""

    async def test_question_mark_shows_the_keys(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.press("question_mark")
            await pilot.pause(0.3)
            body = str(app.screen.query_one("#help-body").content)
            assert "getting around" in body
            assert "j / k" in body, "the one pair shown nowhere else"
            assert "hand the mouse back" in body

    async def test_it_closes_on_escape(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.press("question_mark")
            await pilot.pause(0.3)
            await pilot.press("escape")
            await pilot.pause(0.3)
            assert not app.screen.query("#help-body")

    def test_every_section_key_is_a_real_binding_or_a_documented_range(self):
        """A help screen that lists a key the app does not have is worse than
        no help screen."""
        from swsh.tui.app import HelpScreen

        real = {b.key for b in SwshApp.BINDINGS}
        spelled = {"j / k": ("j", "k"), "n / e / d": ("n", "e", "d"),
                   "t / p / s / R": ("t", "p", "s", "R"),
                   "u / a": ("u", "a"), "0-9 * #": (), ":": ("colon",),
                   "/": ("slash",), "?": ("question_mark",), ".": ("full_stop",)}
        for _, keys in HelpScreen.SECTIONS:
            for key, _what in keys:
                for actual in spelled.get(key, (key,)):
                    assert actual in real, (key, actual)


class TestRowsCanBeNarrowedOnScreen:
    """The cockpit had no equivalent of the CLI's `--match`: the only text
    input on the view selected a *resource*, not rows."""

    async def test_slash_filters_the_rows_already_held(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 40)):
            app.resource = res.get("queues")
            app.rows = [{"id": "q-1", "friendly_name": "support"},
                        {"id": "q-2", "friendly_name": "sales"},
                        {"id": "q-3", "friendly_name": "support overflow"}]
            app.view = "rows"
            app.row_filter = "support"
            assert len(app.visible_rows()) == 2

    async def test_an_empty_filter_shows_everything(self):
        """Different from no filter, and both must show every row."""
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 40)):
            app.resource = res.get("queues")
            app.rows = [{"id": "q-1", "friendly_name": "support"}]
            for value in (None, ""):
                app.row_filter = value
                assert len(app.visible_rows()) == 1

    async def test_the_title_says_both_numbers(self):
        """A filtered count alone reads as the collection having shrunk."""
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(140, 40)) as pilot:
            app.resource = res.get("queues")
            app.rows = [{"id": f"q-{i}", "friendly_name": f"q{i}"} for i in range(9)]
            app.view = "rows"
            app.row_filter = "q1"
            app._refresh_view()
            await pilot.pause()
            title = str(app.query_one("#pane-title").content)
            assert "1 of 9" in title and "/q1" in title

    async def test_it_does_not_survive_a_move_to_another_resource(self):
        """`/` narrows a listing; it is not a mode."""
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 40)) as pilot:
            app.row_filter = "support"
            app.switch_to("sip")
            for _ in range(20):
                await pilot.pause(0.05)
                if app.row_filter is None:
                    break
            assert app.row_filter is None


class TestTheCockpitOpensWithoutCredentials:
    """`sw sh` used to fail two lines before the app was built, and the app
    contains the very form that fixes it — reachable with ctrl+p, but only once
    you already have working credentials. The one screen able to solve the
    problem was behind the problem."""

    async def test_it_opens_on_the_profile_form(self):
        blank = Profile(name="", project="", token="", space="")
        app = SwshApp(profile=blank, onboarding=True)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.3)
            assert app.screen.query("#pf-project"), "the form that collects them"

    async def test_dismissing_it_says_what_is_needed(self):
        blank = Profile(name="", project="", token="", space="")
        app = SwshApp(profile=blank, onboarding=True)
        notes: list[str] = []
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.3)
            app.notify = lambda message, **kw: notes.append(str(message))
            await pilot.press("escape")
            await pilot.pause(0.3)
            assert any("API token" in n for n in notes), notes

    async def test_a_normal_start_does_not_open_it(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.3)
            assert not app.screen.query("#pf-project")
