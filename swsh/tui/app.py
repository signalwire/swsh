"""The swsh cockpit.

A full console over the project, not only the live call view. The left pane
switches between the event-driven calls view and a generic browser that can
render any namespace in ``swsh.resources``; the right pane shows detail for
the selection, with the unified event feed underneath it on the live calls view
only.

Navigation follows k9s: ``:`` opens a command line, resource names accept unique
prefixes, ``ctrl+r`` lists every resource and ``?`` shows every key. Adding a
namespace means adding a row to the registry, not writing a screen.

Every REST call runs in a worker. ``RestClient`` is synchronous, so touching it
on the event loop would freeze the interface.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from rich.console import Group
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Input,
    Label,
    OptionList,
    RichLog,
    Sparkline,
    Static,
)
from textual.widgets.option_list import Option

from .. import __version__, agentlab, config, routing, softphone, ui
from .. import resources as res
from ..client import SwshClient, SwshError
from ..client import next_page as client_next_page
from ..config import ConfigError, Profile
from ..events.bus import CallStore, EventBus
from ..events.poll_source import PollSource
from ..events.relay_source import RelaySource
from ..models import Call, CallEvent
from . import home
from . import lab as lab_view
from .forms import FormScreen
from .numbers import NumberSearchScreen

# What the detail pane can render, in the order `v` cycles them.
#
# `fields` is sw reading the row for you: nested objects flattened to dotted
# keys, empties dropped, timestamps and booleans made legible. `json` is the row
# as sw holds it, which is the same document `--json` prints. `raw` is the
# record the API returns for that row when asked for it on its own, which is
# where the fields no `Field` declares live — the list response is frequently a
# summary of the record, and the pane used to have no way to show the rest.
DETAIL_MODES = ("fields", "json", "raw")


class PromptScreen(ModalScreen[str | None]):
    """A one-line modal prompt, for transfer targets and TTS text."""

    BINDINGS = [Binding("escape", "cancel", "cancel")]

    def __init__(self, prompt: str, placeholder: str = "") -> None:
        super().__init__()
        self.prompt = prompt
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-box"):
            yield Label(self.prompt, id="prompt-label")
            yield Input(placeholder=self.placeholder, id="prompt-input")

    def on_mount(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    @on(Input.Submitted)
    def submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class HelpScreen(ModalScreen[None]):
    """Every key, grouped, because the footer only shows what currently applies.

    `check_action` *hides* a binding that does not apply rather than greying it,
    which keeps the footer honest and means most of the app's keys are invisible
    most of the time. `j` and `k` are `show=False` and were advertised nowhere
    at all. The one hint the app printed went to the event feed, which is hidden
    on the view it opens on.
    """

    BINDINGS = [
        Binding("escape", "close", "close"),
        Binding("question_mark", "close", "close"),
        Binding("q", "close", "close"),
    ]

    # Grouped the way someone looks for them: where am I, what is this row,
    # what is on the call. Kept here rather than derived from BINDINGS so the
    # order is the useful one rather than registration order, and so a key can
    # carry a fuller description than a footer cell has room for.
    SECTIONS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
        ("getting around", (
            (":", "command bar — type a resource name"),
            ("ctrl+r", "jump list of every resource"),
            ("/", "filter the rows on screen"),
            ("escape", "back one level"),
            ("j / k", "down / up, for vi hands"),
            ("r", "refresh"),
            ("ctrl+p", "profiles — switch space"),
            ("q", "quit"),
        )),
        ("this row", (
            ("enter", "inspect — drill into it"),
            ("n / e / d", "new / edit / delete"),
            ("x", "more actions for this resource"),
            (".", "actions for the row under the cursor"),
            ("v", "cycle the detail pane: fields, json, raw"),
            ("F", "routing — follow where a number points"),
        )),
        ("calls", (
            ("h", "hang up the selected leg"),
            ("t / p / s / R", "transfer / say / DTMF / record"),
            ("f", "show ended calls"),
            ("c", "clear the feed"),
        )),
        ("the phone", (
            ("H", "dial or hang up"),
            ("g", "register the device"),
            ("u / a", "stand up the agent / call it"),
            ("0-9 * #", "DTMF on a call; types the target off one"),
            ("y", "copy diagnostics"),
        )),
        ("the terminal", (
            ("m", "hand the mouse back, so text can be selected"),
        )),
    )

    def __init__(self, app_ref: SwshApp | None = None) -> None:
        super().__init__()
        self._app_ref = app_ref

    def compose(self) -> ComposeResult:
        body = Text()
        for index, (title, keys) in enumerate(self.SECTIONS):
            if index:
                body.append("\n")
            body.append(f"{title}\n", style="bold #40E0D0")
            for key, what in keys:
                body.append(f"  {key:<14}", style="#FFD700")
                body.append(f"{what}\n", style="grey70")
        body.append("\nescape or ? to close", style="grey42")
        with Vertical(id="help-box"):
            yield Label("keys", id="help-title")
            with VerticalScroll(id="help-scroll"):
                yield Static(body, id="help-body")

    def action_close(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    """Yes/no gate in front of anything destructive."""

    BINDINGS = [
        Binding("escape", "no", "no"),
        Binding("n", "no", "no"),
        Binding("y", "yes", "yes"),
    ]

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-box"):
            yield Label(self.question, id="prompt-label")
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes", variant="error", id="confirm-yes")
                yield Button("No", id="confirm-no")

    @on(Button.Pressed, "#confirm-yes")
    def _yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#confirm-no")
    def _no(self) -> None:
        self.dismiss(False)

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class DropdownMenu(ModalScreen[str | None]):
    """A menu-bar dropdown: the clicked group's resources, anchored beneath it.

    Positioned under the menu item (not a big centered pop-up); clicking outside
    or pressing escape closes it, clicking an item selects it.
    """

    BINDINGS = [Binding("escape", "cancel", "cancel")]

    def __init__(self, entries, *, anchor_x: int = 0, title: str = "") -> None:
        super().__init__()
        self.entries = entries
        self.anchor_x = anchor_x
        self.menu_title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="dropdown"):
            with Horizontal(classes="drop-header"):
                yield Static(self.menu_title or "menu", classes="drop-title")
                yield Button("✕", id="drop-close", classes="drop-close")
            with VerticalScroll(classes="drop-scroll"):
                for resource in self.entries:
                    yield Button(_cap(resource.title), id=f"drop-{resource.key}",
                                 classes="drop-item")

    def on_mount(self) -> None:
        # Anchor the dropdown just under the menu bar, at the item's x.
        self.query_one("#dropdown").styles.offset = (max(0, self.anchor_x), 1)

    @on(Button.Pressed, "#drop-close")
    def _close(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, ".drop-item")
    def _picked(self, event: Button.Pressed) -> None:
        self.dismiss(str(event.button.id).removeprefix("drop-"))

    def on_click(self, event) -> None:
        # A click that misses the panel (the transparent backdrop) closes it.
        if not self.query_one("#dropdown").region.contains(event.screen_x, event.screen_y):
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class MenuAction:
    """A dropdown entry that runs an action instead of opening a resource."""

    def __init__(self, key: str, title: str) -> None:
        self.key = key
        self.title = title


def _cap(title: str) -> str:
    """Menu entries and pane titles read as labels: first letter up, the rest
    as the registry spells it (so "cXML scripts" and "E911" survive)."""
    return title[:1].upper() + title[1:]


class ContextMenu(ModalScreen[str | None]):
    """The actions valid on the selected row, shown as a clickable list.

    Opened by right-click or `.`, so the available verbs are seen, not
    memorized — the mouse-first complement to the action bar.
    """

    BINDINGS = [Binding("escape", "cancel", "cancel")]

    def __init__(self, actions: list[tuple[str, str]]) -> None:
        super().__init__()
        self.actions = actions  # (action-id, label)

    def compose(self) -> ComposeResult:
        with Vertical(id="ctx-box"):
            for action_id, label in self.actions:
                yield Button(label, id=f"ctx-{action_id}", classes="ctx-item")

    @on(Button.Pressed)
    def _chosen(self, event: Button.Pressed) -> None:
        self.dismiss(str(event.button.id).removeprefix("ctx-"))

    def action_cancel(self) -> None:
        self.dismiss(None)


PROFILE_FIELDS = (
    ("name", "Profile name", False),
    ("project", "Project ID", False),
    ("token", "API token", True),
    ("space", "Space, e.g. example.signalwire.com (staging: example.swire.io)", False),
)


class ProfileFormScreen(ModalScreen[dict[str, str] | None]):
    """Add or edit one stored profile: the `sw login` prompts, as a form."""

    BINDINGS = [
        Binding("escape", "cancel", "cancel"),
        Binding("ctrl+s", "submit", "save"),
    ]

    def __init__(self, initial: dict[str, str] | None = None) -> None:
        super().__init__()
        self.initial = initial or {}
        self.is_edit = bool(initial)

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-box", classes="profile-form"):
            yield Label("Edit profile" if self.is_edit else "New profile", id="prompt-label")
            for key, label, secret in PROFILE_FIELDS:
                yield Label(label, classes="form-label")
                # The name is the key the profile is stored under; editing it
                # would be a rename, which is a different operation.
                yield Input(value=self.initial.get(key, ""), password=secret,
                            id=f"pf-{key}", disabled=self.is_edit and key == "name")
            yield Static("", id="pf-error")
            with Horizontal(id="confirm-buttons"):
                yield Button("Save", variant="primary", id="pf-save")
                yield Button("Cancel", id="pf-cancel")

    def on_mount(self) -> None:
        first = "pf-project" if self.is_edit else "pf-name"
        self.query_one(f"#{first}", Input).focus()

    @on(Button.Pressed, "#pf-save")
    def _save(self) -> None:
        self.action_submit()

    @on(Button.Pressed, "#pf-cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted)
    def _entered(self) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        values = {key: self.query_one(f"#pf-{key}", Input).value.strip()
                  for key, _, _ in PROFILE_FIELDS}
        missing = [label for key, label, _ in PROFILE_FIELDS if not values[key]]
        if missing:
            self.query_one("#pf-error", Static).update(
                Text(f"required: {', '.join(missing)}", style=ui.FUCHSIA))
            return
        try:
            config.check_space(values["space"])
        except config.ConfigError as exc:
            self.query_one("#pf-error", Static).update(Text(str(exc), style=ui.FUCHSIA))
            return
        self.dismiss(values)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ProfileScreen(ModalScreen[str | None]):
    """Switch, add, edit or delete stored profiles, like `sw profile`.

    Dismisses with the name of the profile to switch to, or None. Adding,
    editing and deleting are done here against the config file and only the
    switch is handed back, because switching means rebuilding the app's
    client and event pipeline.
    """

    BINDINGS = [
        Binding("escape", "cancel", "close"),
        Binding("u", "use", "use"),
        Binding("n", "new", "new"),
        Binding("e", "edit", "edit"),
        Binding("d", "delete", "delete"),
    ]

    def __init__(self, active: str) -> None:
        super().__init__()
        self.active = active

    def compose(self) -> ComposeResult:
        with Vertical(id="profile-box"):
            with Horizontal(classes="drop-header"):
                yield Static("Profiles", classes="drop-title")
                yield Button("✕", id="profile-close", classes="drop-close")
            yield OptionList(id="profile-list")
            yield Static("", id="profile-note")
            with Horizontal(id="profile-actions"):
                yield Button("Use", variant="primary", id="prof-use")
                yield Button("New", id="prof-new")
                yield Button("Edit", id="prof-edit")
                yield Button("Delete", variant="error", id="prof-delete")

    def on_mount(self) -> None:
        self._reload()
        self.query_one("#profile-list", OptionList).focus()

    def _reload(self) -> None:
        options = self.query_one("#profile-list", OptionList)
        options.clear_options()
        names = config.list_profiles()
        for name in names:
            mark = "●" if name == self.active else " "
            suffix = "  (in use)" if name == self.active else ""
            options.add_option(Option(f"{mark} {name}{suffix}", id=name))
        if names:
            options.highlighted = names.index(self.active) if self.active in names else 0
        note = Text()
        if not names:
            note.append("no stored profiles. ", style="grey58")
            note.append("n", style=ui.TURQUOISE)
            note.append(" creates one.\n", style="grey58")
        note.append(str(config.config_path()), style="grey42")
        shadow = {v for v in config.active_source_summary().values()
                  if v.startswith("env") or v.startswith(".env")}
        if shadow:
            # The same warning `sw profile use` prints: outside this TUI the
            # switch is invisible while a variable outranks the stored profile.
            note.append(f"\nnote: the CLI takes credentials from {', '.join(sorted(shadow))}, "
                        "which outranks a stored profile", style=ui.GOLD)
        self.query_one("#profile-note", Static).update(note)
        for btn_id in ("prof-use", "prof-edit", "prof-delete"):
            self.query_one(f"#{btn_id}", Button).disabled = not names

    def _selected(self) -> str | None:
        options = self.query_one("#profile-list", OptionList)
        if options.highlighted is None or not options.option_count:
            return None
        return str(options.get_option_at_index(options.highlighted).id)

    @on(OptionList.OptionSelected)
    def _picked(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id))

    @on(Button.Pressed, "#profile-close")
    def _close(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#prof-use")
    def action_use(self) -> None:
        name = self._selected()
        if name:
            self.dismiss(name)

    @on(Button.Pressed, "#prof-new")
    def action_new(self) -> None:
        self.app.push_screen(ProfileFormScreen(), self._saved)

    @on(Button.Pressed, "#prof-edit")
    def action_edit(self) -> None:
        name = self._selected()
        if not name:
            return
        try:
            stored = config.load_profile(name)
        except ConfigError as exc:
            self.notify(str(exc), severity="error")
            return
        initial = {"name": stored.name, "project": stored.project,
                   "token": stored.token, "space": stored.space}
        self.app.push_screen(ProfileFormScreen(initial), self._saved)

    def _saved(self, values: dict[str, str] | None) -> None:
        if not values:
            return
        # Saving never changes which profile is in effect: that is what Use is
        # for, and it needs the app to rebuild its client.
        config.save_profile(values["name"], values["project"], values["token"],
                            values["space"], make_default=False)
        self._reload()
        self.notify(f"saved profile {values['name']}")

    @on(Button.Pressed, "#prof-delete")
    def action_delete(self) -> None:
        name = self._selected()
        if not name:
            return

        def done(confirmed: bool | None) -> None:
            if not confirmed:
                return
            config.delete_profile(name)
            self._reload()
            if name == self.active:
                self.notify(f"deleted {name}; this session keeps using it until you "
                            "switch", severity="warning", timeout=6)
            else:
                self.notify(f"deleted profile {name}")

        self.app.push_screen(
            ConfirmScreen(f"Delete profile {name} and its API token from this machine?"),
            done)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SwshApp(App[None]):
    """Live, navigable view of a SignalWire project."""

    CSS_PATH = "app.css"
    TITLE = "sw"
    # Textual's command palette also lives on ctrl+p. This app navigates with
    # ':' and '?', so the palette is off and ctrl+p opens the profile manager.
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("q", "quit", "quit"),
        Binding("colon", "command", "command"),
        Binding("question_mark", "help", "keys"),
        Binding("slash", "filter", "filter"),
        Binding("ctrl+r", "jump", "resources"),
        Binding("escape", "back", "back"),
        Binding("r", "refresh", "refresh"),
        Binding("enter", "inspect", "inspect"),
        Binding("n", "new", "new"),
        Binding("e", "edit", "edit"),
        Binding("d", "delete", "delete"),
        Binding("x", "extra", "more"),
        Binding("F", "routing", "routing"),
        Binding("v", "detail_mode", "format"),
        # The phone, on the calls view. `H` is the hook and does whatever the
        # green/red button does, so there is one action rather than a dial key
        # and a hangup key that are each dead half the time.
        Binding("H", "hook", "dial/hangup"),
        Binding("g", "lab_register", "register"),
        Binding("u", "lab_standup", "stand up"),
        Binding("a", "lab_call", "call agent"),
        Binding("full_stop", "context", "actions"),
        Binding("h", "hangup", "hangup"),
        Binding("t", "transfer", "transfer"),
        Binding("p", "play", "say"),
        Binding("s", "digits", "dtmf"),
        Binding("R", "record", "record"),
        Binding("f", "toggle_ended", "show ended"),
        Binding("c", "clear_feed", "clear feed"),
        Binding("y", "copy_diagnostics", "copy diag"),
        Binding("m", "select_text", "select text"),
        Binding("ctrl+p", "profiles", "profiles"),
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
    ]

    show_ended: reactive[bool] = reactive(False)
    # Whether the mouse has been handed back to the terminal so text can be
    # selected. A mode, not a setting: while it is on, clicks do not reach the
    # app, so the status bar has to say so. See `action_select_text`.
    selecting: reactive[bool] = reactive(False)

    def __init__(self, profile: Profile, topics: list[str] | None = None,
                 poll_interval: float = 2.0, record_path: str | None = None,
                 onboarding: bool = False):
        super().__init__()
        self.profile = profile
        # There are no credentials yet, so open on the form that collects them
        # rather than on a dashboard of eight tiles that can only show dashes.
        self.onboarding = onboarding
        self.topics = topics or []
        self.poll_interval = poll_interval
        self.record_path = Path(record_path) if record_path else None

        self._build_pipeline()

        self.view: str = "home"
        self.resource: res.Resource | None = None
        self.rows: list[dict[str, Any]] = []
        # True when the walk stopped at PAGE_CAP with pages still to come, so
        # the title can say `400+` rather than pass a ceiling off as a total.
        self.rows_capped: bool = False
        # `/` text, applied to the rows already held. None means no filter at
        # all, which is different from "" — an empty filter someone is still
        # typing should show everything, not nothing.
        self.row_filter: str | None = None
        self.columns: list[str] = []
        self.loading = False
        self.load_error: str | None = None
        # Rolling concurrent-call count for the header sparkline.
        self._vitals: list[int] = [0]
        # Message bodies are not in the logs API; they are fetched once per id
        # from the row's LaML `url` and cached here so the detail pane can show
        # the actual content without re-hitting the API on every highlight.
        self._body_cache: dict[str, str] = {}
        # When a drill-down (e.g. a call flow's versions) is showing, this holds
        # its label so the pane title reads as a breadcrumb and escape/refresh
        # can step back to the parent list instead of losing the context.
        self._drill: str | None = None
        # The parent row the open drill was fetched for, so an action inside
        # the drill (remove a member) can refetch the same drill afterwards.
        self._drill_parent: str | None = None
        # `F` on a resource that declares routing: the expansion for one row,
        # kept as (row id, Routing) so moving the cursor drops back to the
        # plain field table instead of showing the previous row's tree.
        self._routing: tuple[str, Any] | None = None
        self._routing_loading: str | None = None
        # What the detail pane renders: the field table, sw's JSON of the row,
        # or the API's own record for it. See `action_detail_mode`.
        self.detail_mode: str = DETAIL_MODES[0]
        self._raw_cache: dict[str, Any] = {}
        self._raw_loading: str | None = None
        # Dashboard tiles, filled by `load_metrics` and kept across views so
        # coming back to home does not blank them while it refetches.
        # The lab: a SIP device and a local agent. Both are inert until used —
        # constructing them imports nothing and opens nothing.
        self.phone = softphone.Softphone(on_change=self._lab_changed)
        # How many of the phone's own log lines have reached the event feed.
        # The phone keeps a capped list rather than emitting events, so the
        # feed is caught up by index rather than subscribed to.
        self._phone_logged = 0
        self._dtmf_lock = asyncio.Lock()
        self.lab = agentlab.AgentLab(on_change=self._lab_changed)
        self._agent_spec = agentlab.AgentSpec()
        self._metrics: dict[str, home.Count] = {}
        self._metrics_note: str = ""

    def _build_pipeline(self) -> None:
        """Client, bus, store and sources for the current profile.

        Called once at start and again on every profile switch, so everything
        that talks to a project hangs off one place.
        """
        self.client = SwshClient(self.profile)
        self.bus = EventBus(record_to=self.record_path)
        self.store = CallStore(self.bus)
        self.poller = PollSource(self.client, self.bus, active_interval=self.poll_interval)
        self.relay: RelaySource | None = (
            RelaySource(self.profile, self.bus, self.topics) if self.topics else None
        )
        self._pump_worker = None

    def _start_pipeline(self) -> None:
        self.store.on_change(self._on_store_change)
        self._pump_worker = self.run_worker(self._pump(), name="pump")
        self.poller.start()
        if self.relay is not None:
            self.relay.start()

    async def _stop_pipeline(self) -> None:
        if self._pump_worker is not None:
            self._pump_worker.cancel()
        await self.poller.stop()
        if self.relay is not None:
            await self.relay.stop()
        # The lab goes down before the client does, and in this order: it has
        # rows on the platform to delete, and deleting them needs the client
        # that is about to close. A lab left behind is a SIP address and a
        # webhook resource pointing at a tunnel that no longer exists.
        await self.phone.stop()
        await self.lab.stop(client=self.client)
        await self.client.aclose()
        self.bus.close()

    # -------------------------------------------------------------------- layout

    def compose(self) -> ComposeResult:
        # Top menu bar: click a group and its resources drop down beneath it.
        with Horizontal(id="menubar"):
            for group in res.GROUPS:
                yield Button(res.group_title(group), id=f"menu-{group}",
                             classes="menu-item")
            yield Button("Profile", id="menu-profile", classes="menu-item")
            # Calls is last, not first. It led the bar because it was the app's
            # first view, which put the one screen that is only occasionally
            # interesting ahead of the eight people navigate by. It sits beside
            # the meter that counts live calls, so the count and the way into
            # them are the same corner of the screen. There is no Lab item:
            # the phone is a panel on Calls, so the way to the phone is the
            # way to the calls it makes.
            yield Button("Calls", id="menu-calls", classes="menu-item")
            # Not a menu item: a live meter of concurrent calls, plus a
            # two-minute sparkline of the same count.
            yield Static("live calls 0", id="vitals-label")
            yield Sparkline([0], summary_function=max, id="vitals")
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield Static("home", classes="pane-title", id="pane-title")
                with ContentSwitcher(initial="home", id="main"):
                    # The landing view. The cockpit opened straight onto the live
                    # calls table, which is empty on a quiet project and says
                    # nothing about what else is there.
                    with VerticalScroll(id="home"):
                        yield Static("", id="home-body")
                    yield DataTable(id="calls", cursor_type="row")
                    yield DataTable(id="rows", cursor_type="row")
                # The phone. Not a view in the switcher but a panel beneath it,
                # shown only on `calls`, because the thing worth watching while
                # a call connects is the event feed and that is on this view.
                with Vertical(id="phone"):
                    with Horizontal(id="phone-top"):
                        # Three captioned columns. The captions are the one
                        # piece of narration this panel earns: without them a
                        # grid of bare digits beside a text box reads as
                        # decoration, and the pad's two jobs are not guessable.
                        with Vertical(id="phone-dial"):
                            yield Static("call", classes="phone-caption")
                            yield Input(placeholder="number, name or sip: URI",
                                        id="phone-target")
                            # One button, not two. A phone has one hook: you
                            # cannot dial while on a call and cannot hang up
                            # when idle, so a pair of them meant one was always
                            # dead and the live one was never where you looked.
                            yield Button("Dial", id="phone-hook", classes="hook")
                        with Vertical(id="phone-pad"):
                            yield Static("keypad", classes="phone-caption")
                            with Grid(id="phone-keypad"):
                                # Labels carry the digit; ids would have to
                                # mangle `*` and `#` into words and map back.
                                for digit in "123456789*0#":
                                    yield Button(digit, classes="key")
                        with Vertical(id="phone-status"):
                            yield Static("status", classes="phone-caption")
                            yield Static("", id="phone-state")
                    with Horizontal(id="phone-buttons"):
                        yield Button("Device…", id="phone-device", classes="act")
                        yield Button("Register", id="phone-power", classes="act")
                        yield Button("Agent…", id="phone-agent", classes="act")
                        yield Button("Stand up", id="phone-standup", classes="act")
                        yield Button("Call agent", id="phone-agentcall",
                                     classes="act")
                # Action bar: clickable buttons for the actions valid on the
                # current resource — the mouse-first alternative to hotkeys.
                with Horizontal(id="actionbar"):
                    yield Button("New", id="act-new", classes="act")
                    yield Button("Edit", id="act-edit", classes="act")
                    yield Button("Delete", id="act-delete", classes="act")
                    yield Button("More", id="act-extra", classes="act")
                    yield Button("Refresh", id="act-refresh", classes="act")
            with Vertical(id="right"):
                yield Static("detail", classes="pane-title")
                with VerticalScroll(id="detail-scroll"):
                    yield Static("", id="detail")
                yield Static("events", classes="pane-title", id="events-title")
                yield RichLog(id="feed", wrap=False, markup=False, max_lines=2000)
        yield Input(placeholder="resource name, e.g. numbers", id="command")
        yield Static("", id="statusbar")
        yield Footer()

    @on(Button.Pressed, "#menubar .menu-item")
    def _menu_clicked(self, event: Button.Pressed) -> None:
        group = str(event.button.id).removeprefix("menu-")
        if group == "calls":
            self.action_go_calls()
            return
        if group == "profile":
            self.action_profiles()
            return
        # The live calls view has its own menu button; listing it again under
        # Voice would make one thing look like two. A drill-only resource (a
        # campaign, a subscriber's SIP credentials) is left out too: every route
        # it has needs a parent id, so its own screen could only ever be empty.
        entries: list[Any] = [r for r in res.in_group(group)
                              if r.key != "calls" and r.standalone]
        if group == "numbers":
            # Buying is the thing people come to Numbers for; it is a wizard,
            # not a resource, so it is added here rather than in the registry.
            entries.insert(0, MenuAction("buy-numbers", "buy numbers"))
        if not entries:
            return
        # Drop the group's resources down beneath the clicked menu item.
        anchor_x = event.button.region.x
        self.push_screen(
            DropdownMenu(entries, anchor_x=anchor_x, title=res.group_title(group)),
            self._menu_result)

    def _menu_result(self, choice: str | None) -> None:
        if choice == "buy-numbers":
            # Land on the numbers table first, so the purchase shows up in it.
            self.switch_to("numbers")
            self._buy_number(res.get("numbers"))
        elif choice:
            self.switch_to(choice)

    @on(Button.Pressed, "#actionbar Button")
    def _action_clicked(self, event: Button.Pressed) -> None:
        {"act-new": self.action_new, "act-edit": self.action_edit,
         "act-delete": self.action_delete, "act-extra": self.action_extra,
         "act-refresh": self.action_refresh}[str(event.button.id)]()

    def action_context(self) -> None:
        """Open a context menu of the actions valid for the current selection."""
        actions = self._context_actions()
        if not actions:
            return

        def run(choice: str | None) -> None:
            if choice:
                {"new": self.action_new, "edit": self.action_edit,
                 "delete": self.action_delete, "extra": self.action_extra,
                 "routing": self.action_routing,
                 "inspect": self.action_inspect, "dial": self.action_dial,
                 "hangup": self.action_hangup,
                 "transfer": self.action_transfer, "say": self.action_play,
                 "record": self.action_record}[choice]()

        self.push_screen(ContextMenu(actions), run)

    def _context_actions(self) -> list[tuple[str, str]]:
        """The (id, label) actions valid for the current view and selection."""
        if self.view == "calls":
            out = [("dial", "New call")]
            if self._selected_call() is not None:
                out += [("hangup", "Hangup"), ("transfer", "Transfer"),
                        ("say", "Say"), ("record", "Record")]
            return out
        r = self.resource
        if r is None:
            return []
        own = self._own_rows()
        out = [("inspect", "Inspect")] if self._rows_possible() else []
        if r.can_create and not self._drill:
            out.append(("new", "New"))
        if own and r.can_update:
            out.append(("edit", "Edit"))
        if own and r.can_delete:
            out.append(("delete", "Delete"))
        if own and r.routing:
            out.append(("routing", "Full routing"))
        if self._available_extras():
            out.append(("extra", "More…"))
        return out

    def on_mount(self) -> None:
        self.query_one("#calls", DataTable).add_columns(*ui.CALL_COLUMNS)
        self.query_one("#command", Input).display = False
        # Something has to hold focus or Textual gives it to the first
        # focusable widget, which is the hidden `:` input — and that swallows
        # every keystroke, including the `:` meant to summon it.
        self.query_one("#home", VerticalScroll).focus()

        self._start_pipeline()
        self.set_interval(1.0, self._tick)
        self._refresh_view()
        if self.onboarding:
            # Nothing to count and nothing to poll until there are credentials.
            self.call_after_refresh(self._first_run)
            return
        self.load_metrics()
        self._log_line(Text("sw started. ':' to switch resource, '?' for the keys.",
                            style="grey58"))

    def _first_run(self) -> None:
        """No credentials yet: open the form that collects them.

        Saving here *does* make the profile current, unlike the same form
        reached from `ctrl+p` where saving and using are deliberately separate.
        There is nothing to keep using, so asking someone to press Use on the
        only profile they have would be ceremony.
        """
        def saved(values: dict[str, str] | None) -> None:
            if not values:
                self.notify("sw needs a project id, an API token and a space. "
                            "Press ctrl+p to add them.", severity="warning", timeout=10)
                return
            name = values.get("name") or "default"
            config.save_profile(name, values["project"], values["token"],
                                values["space"], make_default=True)
            self.onboarding = False
            self.switch_profile(name)

        self.push_screen(ProfileFormScreen(None), saved)

    def _widget(self, selector: str, kind: type):
        """Find a widget on the *base* screen, tolerating a modal on top.

        `App.query_one` searches the active screen, so once a form or a
        confirmation is pushed every repaint would raise NoMatches. The
        periodic tick keeps running while a modal is open, so it has to reach
        past it rather than blow up once a second.
        """
        try:
            return self.screen_stack[0].query_one(selector, kind)
        except Exception:
            return None

    # ------------------------------------------------------------------- plumbing

    async def _pump(self) -> None:
        sub = self.bus.subscribe()
        try:
            while True:
                event = await sub.get()
                if isinstance(event, CallEvent):
                    self.store.apply(event)
                else:
                    self.store.apply_message(event)
                self._log_line(ui.event_line(event))
        finally:
            self.bus.unsubscribe(sub)

    def _on_store_change(self, call: Call, event: CallEvent) -> None:
        if self.view == "calls":
            self._refresh_view()

    def _tick(self) -> None:
        """Repaint on a timer so live durations advance and status stays fresh."""
        if self.view == "calls":
            self._render_calls()
            self._render_detail()
            self._render_phone()
        elif self.view == "home":
            # Only the live-calls tile moves between fetches, and it is counted
            # from the store, so this costs nothing.
            self._render_home()
        self._render_status()
        self._sample_vitals()

    def _sample_vitals(self) -> None:
        """Feed the header sparkline the current concurrent-call count."""
        live = len(self.store.live())
        self._vitals.append(live)
        self._vitals = self._vitals[-120:]
        spark = self._widget("#vitals", Sparkline)
        if spark is not None:
            spark.data = self._vitals
        label = self._widget("#vitals-label", Static)
        if label is not None:
            label.update(f"live calls {live}")

    def _log_line(self, text: Text) -> None:
        feed = self._widget("#feed", RichLog)
        if feed is not None:
            feed.write(text)

    def _refresh_view(self) -> None:
        if self.view == "home":
            self._render_home()
        elif self.view == "calls":
            self._render_calls()
            self._render_phone()
        else:
            self._render_rows()
        self._render_detail()
        self._render_status()
        self._sync_action_bar()
        # The footer caches what `check_action` last answered, so anything that
        # changes the view, the resource or the open drill has to say so here.
        self.refresh_bindings()
        self._layout_right()

    def _layout_right(self) -> None:
        """Give the detail pane the whole right column unless calls are showing.

        The event feed is the live-call timeline. On a resource view it has
        nothing to say, and the room is better spent showing the whole object.
        On the dashboard the right column goes away entirely: there is no
        selection to detail, and the banner and tiles want the width.
        """
        right = self._widget("#right", Vertical)
        if right is not None:
            # The dashboard has no selection to detail, and the banner and
            # tiles want the width.
            right.display = self.view != "home"
        live = self.view == "calls"
        # The phone travels with the calls view and only with it. On a resource
        # table it would be a dial pad under a list of SIP gateways, and the
        # rows want the rest of the column.
        phone = self._widget("#phone", Vertical)
        if phone is not None:
            phone.display = live
        feed = self._widget("#feed", RichLog)
        title = self._widget("#events-title", Static)
        scroll = self._widget("#detail-scroll", VerticalScroll)
        if feed is not None:
            feed.display = live
        if title is not None:
            title.display = live
        if scroll is not None:
            scroll.styles.height = "45%" if live else "1fr"

    # Keys that only mean something on the live calls view: the call controls,
    # plus the two that act on what that view alone shows — the ended-call
    # filter and the event feed.
    _CALLS_ONLY = frozenset({"hangup", "transfer", "play", "digits", "record",
                             "toggle_ended", "clear_feed"})
    # The phone's keys. They used to be withheld everywhere but the lab view;
    # the lab view is gone and the phone is a panel on `calls`, so this is the
    # same rule pointed at the view that now holds it.
    _PHONE_ONLY = frozenset({"lab_register", "lab_standup", "lab_call"})

    def _rows_possible(self) -> bool:
        """Whether this view can hold a row to act on.

        A listing can. A singleton's record can — there is exactly one and it
        is on screen. An open drill can. A create-only namespace cannot: the
        API gives project tokens and imported numbers no list route, so `e` and
        `d` there are keys that could never find anything to work on, and a
        drill-only resource opened on its own is the same story.
        """
        r = self.resource
        return (self.view == "rows" and r is not None
                and (r.can_list or r.is_singleton or bool(self._drill)))

    def _own_rows(self) -> bool:
        """Whether the table holds *this resource's* rows.

        A drill shows something else's — a group's memberships, a document's
        chunks, a brand's campaigns — and the parent's CRUD verbs do not apply
        to them. `e` inside `groups > memberships` resolved the membership's id
        and sent it to the number-group update route: a well-formed request
        against the wrong object, which is the failure mode worth preventing.
        Acting on a drill's rows is what an ``Extra`` with ``on_drill`` is for.
        """
        r = self.resource
        return (self.view == "rows" and r is not None and not self._drill
                and (r.can_list or r.is_singleton))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Which of BINDINGS apply to what is on screen.

        Textual asks this for every binding on every repaint and drops the ones
        that answer False, so this is the single place that decides what the
        footer offers. Without it the whole vocabulary was advertised
        everywhere: `F routing` on AI agents, which declare no routing at all;
        `t transfer` over a table of SIP endpoints; `n new` on a read-only log.
        A key that does nothing is worse than a missing key, because the person
        reading the footer has no way to tell the two apart until they press it.

        False hides the binding rather than greying it. A footer full of dead
        keys is the same promise in lighter text, and the row is the one piece
        of screen that should read as "here is what you can do *now*".
        """
        r = self.resource
        rows = self.view == "rows" and r is not None
        # CRUD acts on the resource's own rows, so it needs a list (or a
        # singleton's record) and no drill in the way. Inspecting and the
        # row-acting extras only need *a* row, which a drill has.
        own = self._own_rows()
        if action in self._PHONE_ONLY:
            return self.view == "calls"
        if action == "hook":
            # Offered whenever the phone could act: dial when idle, hang up
            # when not. Withheld with no device, where it has nothing to dial
            # from and the answer would be a toast telling you so.
            return self.view == "calls" and self.phone.device is not None
        if action in self._CALLS_ONLY:
            return self.view == "calls"
        if action == "new":
            # On the live view `n` places a call rather than creating a row.
            # A create-only namespace has no list, so `own` is not the test.
            return self.view == "calls" or (rows and not self._drill and r.can_create)
        if action == "edit":
            return own and r.can_update
        if action == "delete":
            return own and r.can_delete
        if action == "routing":
            return own and bool(r.routing)
        if action == "detail_mode":
            # It reformats whatever the pane is showing, so it needs a row —
            # any row, a drill's included — or the live view's calls.
            return self.view == "calls" or self._rows_possible()
        if action == "inspect":
            return self.view == "calls" or self._rows_possible()
        if action == "refresh":
            # Nothing to reload on a screen whose only route is a create; in a
            # drill it steps back to the list that was drilled from.
            return self.view in ("calls", "home") or self._rows_possible()
        if action == "extra":
            return bool(self._available_extras())
        if action == "back":
            # Out of a drill to its list, out of a list to the dashboard. On
            # the dashboard there is nowhere further out.
            return bool(self._drill) or self.view != "home"
        return True

    def _sync_action_bar(self) -> None:
        """Enable only the actions the current resource actually supports, so
        the clickable buttons never promise something the API cannot do."""
        r = self.resource
        rows_view = self.view == "rows" and r is not None
        own = self._own_rows()
        states = {
            # On the live view "New" places a call.
            "act-new": (rows_view and not self._drill and r.can_create)
                       or self.view == "calls",
            "act-edit": own and r.can_update,
            "act-delete": own and r.can_delete,
            "act-extra": bool(self._available_extras()),
            "act-refresh": self.view == "calls" or self._rows_possible(),
        }
        for btn_id, enabled in states.items():
            btn = self._widget(f"#{btn_id}", Button)
            if btn is not None:
                btn.disabled = not enabled

    # ------------------------------------------------------------- the dashboard

    def _render_home(self) -> None:
        body = self._widget("#home-body", Static)
        if body is None:
            return
        # The live-calls tile is free and exact, so it is filled from the store
        # on every repaint rather than waiting for the worker.
        counts = dict(self._metrics)
        counts["live calls"] = home.Count(value=len(self.store.live()))
        body.update(home.screen(
            version=__version__, profile=self.profile, counts=counts,
            width=self.size.width, note=self._metrics_note,
        ))
        self._set_title("Home")

    @work(exclusive=True, group="metrics")
    async def load_metrics(self) -> None:
        """Fill the dashboard tiles, one request per tile, in parallel.

        Every one of them is allowed to fail on its own: a project without
        video, a namespace this token cannot see, a space that is simply down.
        A tile that could not be counted shows a dash, and the dashboard still
        says which space and profile are in play — which is most of what it is
        for on a bad day.
        """
        wanted = [m for m in home.METRICS if m.source != "store"]
        self._metrics_note = ""
        for metric in wanted:
            self._metrics.setdefault(metric.label, home.Count())

        async def one(metric: home.Metric) -> tuple[str, home.Count]:
            try:
                if metric.source == "calls":
                    calls = await self.client.recent_calls(
                        limit=self.client.VOICE_LOG_PAGE_MAX, lookback=metric.window)
                    return metric.label, home.Count(
                        value=len(calls),
                        more=len(calls) >= self.client.VOICE_LOG_PAGE_MAX)
                resource = res.get(metric.source)
                if resource is None:  # pinned by test_tui
                    return metric.label, home.Count(error="unknown resource")
                payload = await self.client.invoke(resource, "list")
                rows = res.unwrap(payload, resource.data_key)
                return metric.label, home.Count(
                    value=len(rows), more=client_next_page(payload) is not None)
            except SwshError as exc:
                return metric.label, home.Count(error=str(exc))
            except Exception as exc:
                return metric.label, home.Count(error=f"{type(exc).__name__}: {exc}")

        results = await asyncio.gather(*(one(m) for m in wanted))
        for label, count in results:
            self._metrics[label] = count
        failed = [c for c in self._metrics.values() if c.error]
        if failed:
            # One line, and the first reason: when the space is unreachable all
            # eight fail for the same cause, and eight copies of it is a wall.
            why = failed[0].error
            self._metrics_note = (f"{len(failed)} of {len(wanted)} counts unavailable: "
                                  f"{why if len(why) <= 60 else why[:57] + '…'}")
        if self.view == "home":
            self._render_home()

    # ------------------------------------------------------------ the calls view

    def _visible_calls(self) -> list[Call]:
        return self.store.recent(200) if self.show_ended else self.store.live()

    def _render_calls(self) -> None:
        table = self._widget("#calls", DataTable)
        if table is None:
            return
        selected = self._selected_key(table)
        table.clear()

        calls = self._visible_calls()
        for call in calls:
            table.add_row(*ui.call_row(call), key=call.ref.key)
        self._restore_cursor(table, selected)

        label = "Calls (all)" if self.show_ended else "Calls (live)"
        self._set_title(f"{label}  ·  {len(calls)}")

    # --------------------------------------------------- the generic browser view

    def visible_rows(self) -> list[dict[str, Any]]:
        """The rows the table shows: everything held, less the `/` filter.

        Filtering happens over what is already in memory rather than by asking
        the platform again — the walk in `_all_rows` has been and got the
        collection, and a keystroke should not cost a round trip. It reuses the
        resource's own `search_fields`, so `/` looks in exactly what the CLI's
        `--match` looks in.
        """
        if not self.row_filter or self.resource is None:
            return self.rows
        fields = self.resource.search_fields
        return [r for r in self.rows if res.row_matches(r, self.row_filter, fields)]

    def _render_rows(self) -> None:
        table = self._widget("#rows", DataTable)
        if table is None:
            return
        selected = self._selected_key(table)
        table.clear(columns=True)

        resource = self.resource
        if resource is None:
            return

        visible = self.visible_rows()
        self.columns = res.columns_for(resource, visible)
        table.add_columns(*self.columns)

        for index, row in enumerate(visible):
            identifier = str(row.get(resource.id_field) or row.get("sid") or index)
            table.add_row(*[_cell(res.cell(row, c)) for c in self.columns], key=identifier)
        self._restore_cursor(table, selected)

        if self.loading:
            suffix = "loading"
        elif self.load_error:
            suffix = "error"
        elif not resource.can_list and (self._drill or resource.is_singleton):
            suffix = str(len(self.rows))
        elif not resource.can_list:
            # Say what *does* work here: create, the actions under x, or both.
            hints = []
            if resource.can_create:
                hints.append("n to create")
            if any(not e.on_drill for e in resource.extras):
                hints.append("x for actions")
            suffix = "nothing to list" + (", press " + " or ".join(hints) if hints else "")
        else:
            # `134` is a count; `134+` is "at least this many". The pane used to
            # print the first page's length as though it were the total.
            suffix = f"{len(self.rows)}{'+' if self.rows_capped else ''}"
            if self.row_filter:
                # Say both numbers. A filtered count alone reads as the whole
                # collection having shrunk.
                suffix = (f"{len(self.visible_rows())} of {suffix}"
                          f"  ·  /{self.row_filter}")
        # Advertise what this namespace actually permits, so the key hints in
        # the footer are not promises the API will refuse.
        ops = "".join(c for c in "CRUD" if resource.can(c)) or "read-only"
        if self._drill:
            # Breadcrumb: make it obvious this is a sub-view and how to get back.
            self._set_title(f"{_cap(resource.title)}  >  {self._drill}  ·  "
                            f"{suffix}  ·  esc to go back")
        else:
            self._set_title(f"{_cap(resource.title)}  ·  {suffix}  ·  {ops}")

    # The cockpit is scrolled, not paged, so a table that stops at the first
    # page is a table whose bottom row is a lie about where the data ends. This
    # walks far enough to be honest for anything a person scrolls through, and
    # says so in the title when it stops early rather than pretending.
    PAGE_CAP = 20

    async def _all_rows(self, resource: res.Resource) -> tuple[list[dict[str, Any]], bool]:
        """Every row the list route offers, and whether the walk was cut short."""
        payload = await self.client.invoke(resource, "list")
        rows = res.unwrap(payload, resource.data_key)
        seen: set[str] = set()
        for _ in range(self.PAGE_CAP):
            link = client_next_page(payload)
            if not link or link in seen:
                return rows, False
            seen.add(link)
            payload = await self.client.rest_call("GET", link)
            rows.extend(res.unwrap(payload, resource.data_key))
        return rows, client_next_page(payload) is not None

    @work(exclusive=True, group="load")
    async def _load(self, resource: res.Resource) -> None:
        """Fetch a namespace off the event loop and repaint."""
        self.rows = []
        self.rows_capped = False
        # A filter typed on one resource must not silently hide rows of the
        # next: `/` narrows a listing, it is not a mode.
        self.row_filter = None
        self.load_error = None
        self._drill_parent = None
        if not resource.can_list and not resource.is_singleton:
            # A few namespaces are write-only, e.g. project tokens. Show the
            # view anyway so create still works, and say why it is empty.
            self.loading = False
            self._refresh_view()
            return

        self.loading = True
        self._refresh_view()
        try:
            if resource.is_singleton:
                # One record, no collection: `GET /sip_profile` takes no id.
                # Reading it into a single row is what makes `e` work here, and
                # is a truer picture than an empty table of a thing that exists.
                payload = await self.client.invoke(resource, "read")
                self.rows = [payload] if isinstance(payload, dict) and payload else []
            else:
                self.rows, self.rows_capped = await self._all_rows(resource)
        except SwshError as exc:
            self.load_error = str(exc)
            self._log_line(Text(f"  {resource.key}: {exc}", style="red"))
        except Exception as exc:
            self.load_error = f"{type(exc).__name__}: {exc}"
        finally:
            self.loading = False
            self._refresh_view()

    # ----------------------------------------------------------------- selection

    def _table(self) -> DataTable | None:
        if self.view == "home":
            return None
        return self._widget("#calls" if self.view == "calls" else "#rows", DataTable)

    def _selected_key(self, table: DataTable | None = None) -> str | None:
        table = table or self._table()
        if table is None or not table.row_count or table.cursor_row < 0:
            return None
        try:
            return str(table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value)
        except Exception:
            return None

    def _restore_cursor(self, table: DataTable, key: str | None) -> None:
        """Keep the cursor on the same row across a rebuild."""
        if not key:
            return
        try:
            table.move_cursor(row=table.get_row_index(key))
        except Exception:
            pass

    def _selected_call(self) -> Call | None:
        key = self._selected_key()
        return self.store.get(key) if key else None

    def _selected_row(self) -> dict[str, Any] | None:
        key = self._selected_key()
        if key is None or self.resource is None:
            return None
        for index, row in enumerate(self.rows):
            identifier = str(row.get(self.resource.id_field) or row.get("sid") or index)
            if identifier == key:
                return row
        return None

    # -------------------------------------------------------------------- detail

    def _render_detail(self) -> None:
        panel = self._widget("#detail", Static)
        if panel is None:
            return
        if self.view == "calls":
            call = self._selected_call()
            if call is not None and self.detail_mode != "fields":
                panel.update(Group(
                    _mode_line(self.detail_mode),
                    ui.json_view(call.as_json() if self.detail_mode == "json"
                                 else call.raw)))
                return
            panel.update(self._call_detail())
            return

        if self.load_error:
            panel.update(Text(self.load_error, style="red"))
            return
        row = self._selected_row()
        if row is None:
            panel.update(Text("no row selected", style="grey42"))
            return

        # The message logs API omits the body; enrich it from the row's LaML
        # url. Show the cached body inline, or fetch it once and re-render.
        row = self._with_message_body(row)

        key = self._row_key(row)
        if self._routing_loading == key:
            panel.update(Group(_row_heading(row),
                               Text("following the routing…", style="grey58")))
            return
        if self._routing is not None and self._routing[0] == key:
            panel.update(Group(_row_heading(row), ui.routing_tree(self._routing[1])))
            return
        # The cursor moved off the expanded row; the tree belonged to that one.
        self._routing = None

        if self.detail_mode == "json":
            panel.update(Group(_row_heading(row), _mode_line("json"),
                               ui.json_view(row)))
            return
        if self.detail_mode == "raw":
            panel.update(Group(_row_heading(row), *self._raw_detail(row, key)))
            return

        # A rendered field table reads like the dashboard's detail panel, with
        # nested objects flattened to dotted keys so every field is shown.
        panel.update(Group(_row_heading(row), _row_detail(row)))

    def _raw_detail(self, row: dict[str, Any], key: str) -> list[Any]:
        """The API's own record for the selected row, fetched once and kept.

        A list response is often a summary: Fabric sends a phone number's row
        with a dozen fields and the record with forty. So raw asks the read
        route for this one row rather than reformatting what the table already
        had. A resource with no read route (or a row with no id) has nothing to
        ask, and its list row *is* the API's answer, which the note says.
        """
        cache_key = self._raw_key(key)
        if self._raw_loading == cache_key:
            return [_mode_line("raw"), Text("fetching the record…", style="grey58")]
        if cache_key in self._raw_cache:
            record = self._raw_cache[cache_key]
            if isinstance(record, str):  # the fetch failed; say so, keep the row
                return [_mode_line("raw"), Text(record, style="red"),
                        ui.json_view(row)]
            return [_mode_line("raw"), ui.json_view(record)]
        if not self._can_read_one(row):
            return [_mode_line("raw", "from the list response"), ui.json_view(row)]
        self._raw_loading = cache_key
        self._fetch_raw(key, row)
        return [_mode_line("raw"), Text("fetching the record…", style="grey58")]

    def _raw_key(self, row_key: str) -> str:
        """Cache key for a fetched record. Two resources can hold the same id."""
        return f"{self.resource.key if self.resource else '?'}:{row_key}"

    def _can_read_one(self, row: dict[str, Any]) -> bool:
        """Whether this row can be fetched on its own.

        A drill's rows belong to something else, so the parent's read route is
        the wrong question to ask about them — the same reason `e` is withheld
        there.
        """
        resource = self.resource
        return (resource is not None and not self._drill
                and "read" in resource.rest_ops
                and bool(res.cell(row, resource.id_field)))

    @work(group="raw-record", exclusive=True)
    async def _fetch_raw(self, key: str, row: dict[str, Any]) -> None:
        """Read one row's record. A `@work` worker: it is a request.

        Every network call in this app is one, and this one lands under the
        cursor, so a slow space must not freeze the 1 Hz repaint.
        """
        resource = self.resource
        if resource is None:
            self._raw_loading = None
            return
        cache_key = self._raw_key(key)
        identifier = str(res.cell(row, resource.id_field) or "")
        try:
            record = await self.client.invoke(resource, "read", resource_id=identifier)
        except Exception as exc:  # a 404 or a dead space is a line, not a crash
            record = f"{type(exc).__name__}: {exc}"
        self._raw_cache[cache_key] = record
        if self._raw_loading == cache_key:
            self._raw_loading = None
        # The cursor may have moved on; repaint only what is still on screen.
        current = self._selected_row()
        if current is not None and self._row_key(current) == key:
            self._render_detail()

    def _with_message_body(self, row: dict[str, Any]) -> dict[str, Any]:
        """Return the row with its message body filled in, fetching if needed.

        Message content lives on the LaML resource the log row's `url` points
        to, not in the log itself. This surfaces it as a plain `body` field, so
        the detail pane reads like the dashboard's message view.
        """
        if self.resource is None or self.resource.key != "messages":
            return row
        url = row.get("url")
        if not url:
            return row
        row_id = str(row.get("id") or row.get("sid") or "")
        if row_id in self._body_cache:
            body = self._body_cache[row_id]
            return {**row, "body": body} if body else row
        # Not fetched yet: show a placeholder and kick off the one-time fetch.
        self._fetch_message_body(row_id, url)
        return {**row, "body": "loading…"}

    @work(group="message-body", exclusive=False)
    async def _fetch_message_body(self, row_id: str, url: str) -> None:
        try:
            full = await self.client.rest_call("GET", url)
        except Exception:
            self._body_cache[row_id] = ""  # give up quietly; leave metadata as-is
            return
        self._body_cache[row_id] = str(full.get("body") or "") if isinstance(full, dict) else ""
        # If this row is still the selected one, repaint with the body in place.
        current = self._selected_row()
        if current and str(current.get("id") or current.get("sid") or "") == row_id:
            self._render_detail()

    def _call_detail(self) -> Text:
        call = self._selected_call()
        if call is None:
            return Text("no call selected", style="grey42")

        text = Text()

        def field(label: str, value: Any, style: str = "") -> None:
            text.append(f"{label:>12}  ", style="grey50")
            text.append(f"{value}\n", style=style)

        field("state", call.state.value, ui.STATE_STYLE.get(call.state.value, "grey35"))
        if call.raw.get("status") and call.raw.get("status") != call.state.value:
            field("status", call.raw["status"])
        field("sid", call.ref.sid or "-")
        field("call_id", call.ref.call_id or "-")
        # The list table no longer carries type, so give it its friendly name here.
        field("type", ui.call_type_text(call.call_type))
        field("direction", call.direction or "-")
        field("from", call.from_number or "-")
        field("to", call.to_number or "-")
        field("started", ui.when_text(call.started_at))
        if call.ended_at:
            field("ended", ui.when_text(call.ended_at))
        field("duration", ui.duration_text(call.duration))
        if call.end_reason:
            field("end reason", call.end_reason, ui.GOLD)
        text.append(f"{'seen by':>12}  ", style="grey50")
        text.append(ui.sources_text(call.sources))
        text.append("\n")

        # Say why a control is unavailable rather than letting the key fail.
        if not call.ref.call_id:
            text.append("\n  transfer, say and dtmf need the native call id,\n"
                        "  which this call has not exposed yet.\n", style="grey42")
        return text

    def _render_status(self) -> None:
        """Report which channels are actually live.

        Coverage genuinely differs between them, so this is the honest answer to
        "am I seeing everything?".
        """
        status = Text()
        if self.selecting:
            # First, and loud. Nothing else on screen explains why clicking
            # has stopped working, and a mode you cannot tell you are in is
            # indistinguishable from the app having hung.
            status.append(" SELECT ", style="bold #0a0c12 on #3ecf8e")
            status.append(" drag to select, copy, then m  ", style=ui.GOLD)
            status.append("·  ", style="grey30")
        if self.profile.name:
            status.append(self.profile.name, style=f"bold {ui.BLUE}")
            status.append("  ·  ", style="grey30")
        status.append(self.profile.project[:8], style=ui.BLUE)
        status.append("  ·  ", style="grey30")
        status.append(self.profile.host, style=ui.TURQUOISE)
        status.append("  ·  ", style="grey30")
        status.append(self.poller.status, style="red" if self.poller.last_error else "grey58")
        status.append("  ·  ", style="grey30")
        if self.relay is None:
            status.append("relay: off (no --topic)", style="grey42")
        else:
            status.append(self.relay.status,
                          style="red" if self.relay.last_error else ui.TURQUOISE)
        status.append("  ·  ", style="grey30")
        status.append(f"events: {self.bus.published}", style="grey58")
        bar = self._widget("#statusbar", Static)
        if bar is not None:
            bar.update(status)

    def _set_title(self, title: str) -> None:
        pane = self._widget("#pane-title", Static)
        if pane is not None:
            pane.update(title)

    # ---------------------------------------------------------------- navigation

    def switch_to(self, key: str) -> None:
        """Show a resource by name, accepting unique prefixes."""
        if key.strip().lower() in ("lab", "phone", "softphone"):
            # Not a registry resource, and no longer a view either. These are
            # the names people type for the softphone, and the softphone is a
            # panel on `calls`, so they land there rather than erroring on a
            # screen that used to exist.
            self.action_go_calls()
            return
        resource = res.get(key.strip())
        if resource is None:
            self.notify(f"unknown resource: {key}", severity="warning", timeout=3)
            return

        if resource.key == "calls":
            self.action_go_calls()
            return
        if resource.drill_from:
            self._send_to_parent(resource)
            return

        self.view = "rows"
        self.resource = resource
        self._drill = None
        self.query_one("#main", ContentSwitcher).current = "rows"
        self.query_one("#rows", DataTable).focus()
        # Lay the column out before fetching, not after. `_load` is a worker,
        # and leaving this to the `_refresh_view` at the end of it left the
        # phone panel sitting under an empty rows table for as long as the
        # request took.
        self._layout_right()
        self._load(resource)

    def _send_to_parent(self, resource: res.Resource) -> None:
        """Typed the name of a drill-only resource: go where its rows are.

        Opening it directly would give a table that can never fill, so land on
        the parent that owns them and say which key opens the drill. The name
        still resolves — it is the empty screen that does not.
        """
        parent = res.get(resource.drill_from)
        if parent is None:  # pinned by test_resources; do not lose the command
            self.notify(f"{resource.title} opens from {resource.drill_from}",
                        severity="warning", timeout=4)
            return
        self.notify(f"{_cap(resource.title)} open from {parent.title}: "
                    f"select one and press x", timeout=5)
        self.switch_to(parent.key)

    def action_back(self) -> None:
        """Escape: out one level.

        A drill is a sub-view of its list, so it steps back to that first
        rather than jumping all the way out; a list steps back to the
        dashboard. Landing on the live calls table from anywhere was a habit of
        the old start-up view, not a hierarchy.
        """
        if self._drill and self.resource is not None:
            parent = self.resource
            self._drill = None
            self._load(parent)
            return
        if self.view != "home":
            self.action_go_home()

    def action_go_home(self) -> None:
        self.view = "home"
        self.resource = None
        self._drill = None
        self.query_one("#main", ContentSwitcher).current = "home"
        self.query_one("#home", VerticalScroll).focus()
        self._refresh_view()
        self.load_metrics()

    def action_go_calls(self) -> None:
        if self._drill and self.resource is not None:
            parent = self.resource
            self._drill = None
            self._load(parent)
            return
        self.view = "calls"
        self.resource = None
        self.query_one("#main", ContentSwitcher).current = "calls"
        self.query_one("#calls", DataTable).focus()
        self._refresh_view()

    # --------------------------------------------------------------- the phone

    # A SIP phone and a local AI agent, in a panel on the calls view, because
    # each is how the other is tested and the feed beside them is how you see
    # it happen. Everything below is either a form (values in) or a `@work`
    # worker (a request out); the panel itself is rendered by `tui/lab.py` from
    # state and talks to nothing.

    def _render_phone(self) -> None:
        """Repaint the phone panel: its state column and its four labels."""
        state = self._widget("#phone-state", Static)
        if state is None:
            return
        available = softphone.available()
        state.update(lab_view.state(self.phone, self.lab, available=available))
        panel = self._widget("#phone", Vertical)
        if panel is not None:
            # The identity and the registration ride in the border, which is
            # the only full-width strip the panel has. See `lab_view.title`.
            panel.border_title = lab_view.title(self.phone, available=available)

        # The hook. Green to place a call, red to end one, and never both:
        # `on_call` is the whole condition, so the button cannot offer an
        # action the phone is in no position to take.
        hook = self._widget("#phone-hook", Button)
        if hook is not None:
            busy = self.phone.on_call
            hook.label = "Hang up" if busy else "Dial"
            hook.set_class(busy, "-busy")
        power = self._widget("#phone-power", Button)
        if power is not None:
            power.label = "Unregister" if self.phone.registered else "Register"
        standup = self._widget("#phone-standup", Button)
        if standup is not None:
            standup.label = "Tear down" if self.lab.running else "Stand up"
        # There is nothing to call until the agent is up, and a button for it
        # before then is a button whose only answer is "not yet".
        agentcall = self._widget("#phone-agentcall", Button)
        if agentcall is not None:
            agentcall.display = self.lab.running

    def _lab_changed(self) -> None:
        """Repaint the phone panel and put whatever it said into the feed.

        Called from stack and server callbacks, which run on this loop, so it
        is a plain repaint and never `call_from_thread`.

        The phone's own notes go to the same feed as the platform's call events
        on purpose. `registering`, `dialing sip:+1…`, `RTP established` and the
        voice log's `answered` for the same call are one story, and reading it
        in two places was what made the phone worth moving onto this view.
        """
        self._drain_phone_log()
        if self.view == "calls":
            self._render_phone()

    def _drain_phone_log(self) -> None:
        """Write the phone's unsent log lines to the event feed, oldest first."""
        entries = list(self.phone.log)
        # `Softphone.log` is capped, so it drops from the front. An index into
        # it is only valid while it is shorter than the cap; past that, catch
        # up from the tail rather than replaying or skipping.
        if len(entries) < self._phone_logged:
            self._phone_logged = 0
        for stamp, text in entries[self._phone_logged:]:
            line = Text()
            line.append(time.strftime("%H:%M:%S ", time.localtime(stamp)),
                        style="grey35")
            line.append("phone ", style=ui.GOLD)
            line.append(text, style="grey70")
            self._log_line(line)
        self._phone_logged = len(entries)

    # -------------------------------------------------------------- the device

    def _device_form(self) -> res.Extra:
        """The device form: a SIP endpoint's credentials, as fields.

        The username offers the project's own SIP endpoints, because that is
        where the answer is; the password cannot be offered, because Fabric
        never returns it. That asymmetry is the API's, not a gap here.
        """
        return res.Extra(
            "device", "SIP device", "register", needs_id=False,
            fields=(
                res.Field("username", label="SIP endpoint", required=True,
                          kind="choice",
                          options_from=("sip.list", "sip_endpoint.username",
                                        "display_name"),
                          prefill=(("domain", "sip_endpoint.domain"),
                                   ("password", "sip_endpoint.password"))),
                res.Field("password", required=True, secret=True),
                res.Field("domain", required=True),
                res.Field("audio", kind="choice", choices=softphone.AUDIO_DRIVERS),
                res.Field("auto_answer", kind="bool"),

                # Interop knobs. Hidden until `advanced` is ticked, because a
                # form that opens with twelve fields hides the five that are
                # always the answer — and because each of these is only ever
                # touched when a specific call has already failed.
                res.Field("advanced", label="show interop options", kind="bool"),
                # Left blank, this names no transport — which is the request
                # URI that routes. The picker's own blank is that state, so it
                # needs no extra option and no help line: every help line on
                # this form costs a row, and it overflowed once already.
                res.Field("transport", kind="choice", choices=softphone.TRANSPORTS,
                          show_if=("advanced", ("True",))),
                res.Field("codecs", kind="multi", choices=softphone.CODECS,
                          open_ended=True, show_if=("advanced", ("True",))),
                res.Field("dtmf_mode", label="DTMF", kind="choice",
                          choices=softphone.DTMF_MODES,
                          show_if=("advanced", ("True",))),
                res.Field("registrar", label="registrar / outbound proxy",
                          show_if=("advanced", ("True",))),
                res.Field("auth_user", label="auth username",
                          show_if=("advanced", ("True",))),
                res.Field("reg_interval", label="register every (s)", kind="int",
                          show_if=("advanced", ("True",))),
                res.Field("rtp_timeout", label="RTP timeout (s)", kind="int",
                          show_if=("advanced", ("True",))),
                res.Field("sip_trace", label="log SIP signalling", kind="bool",
                          show_if=("advanced", ("True",))),
                res.Field("net_interface", label="bind interface",
                          show_if=("advanced", ("True",))),
                res.Field("extra_config", label="extra baresip config",
                          kind="textarea", show_if=("advanced", ("True",))),
            ),
        )

    def action_lab_device(self) -> None:
        self._open_device_form()

    @work(group="lab-device", exclusive=True)
    async def _open_device_form(self) -> None:
        """Read the project's SIP domain, then open the form already filled in.

        A worker, because this is a request and the 1 Hz repaint is still
        running. The domain cannot be derived from the space — it carries a
        per-space SIP identifier — so the profile is the only place it exists,
        and guessing produced a domain that does not resolve.
        """
        blank = softphone.Device("", "", "")
        current = self.phone.device or blank
        # The domain comes off the project's SIP profile or not at all. It is
        # never guessed from the configured space: that form is missing the
        # space's SIP identifier, and a plausible wrong domain in the box is
        # worse than an empty one.
        domain = current.domain or await softphone.domain_of(self.client)
        initial = {
            "username": current.username,
            "password": current.password,
            "domain": domain,
            "audio": current.audio,
            "auto_answer": current.auto_answer,
            "advanced": current != blank and self._device_is_tweaked(current),
            "transport": current.transport,
            "codecs": list(current.codecs),
            "dtmf_mode": current.dtmf_mode,
            "registrar": current.registrar,
            "auth_user": current.auth_user,
            "reg_interval": current.reg_interval,
            "rtp_timeout": current.rtp_timeout,
            "sip_trace": current.sip_trace,
            "net_interface": current.net_interface,
            "extra_config": current.extra_config,
        }

        def done(values: dict[str, Any] | None) -> None:
            if not values:
                return

            def num(name: str, fallback: int) -> int:
                try:
                    return int(str(values.get(name) or fallback))
                except ValueError:
                    return fallback

            device = softphone.Device(
                username=str(values.get("username") or "").strip(),
                password=str(values.get("password") or ""),
                domain=str(values.get("domain") or "").strip(),
                audio=str(values.get("audio") or softphone.AUDIO_DRIVERS[0]),
                auto_answer=bool(values.get("auto_answer", True)),
                # Blank stays blank: it is the request URI with no transport
                # parameter, which is the shape that routes.
                transport=str(values.get("transport") or ""),
                codecs=tuple(values.get("codecs") or ()),
                dtmf_mode=str(values.get("dtmf_mode") or "rtpevent"),
                registrar=str(values.get("registrar") or "").strip(),
                auth_user=str(values.get("auth_user") or "").strip(),
                reg_interval=num("reg_interval", 600),
                rtp_timeout=num("rtp_timeout", 0),
                sip_trace=bool(values.get("sip_trace", False)),
                net_interface=str(values.get("net_interface") or "").strip(),
                extra_config=str(values.get("extra_config") or ""),
            )
            self._register_device(device)

        self.push_screen(FormScreen(self._device_form(), "create", initial,
                                    client=self.client, title="SIP device"), done)

    @staticmethod
    def _device_is_tweaked(device: Any) -> bool:
        """Whether a device has an interop knob off its default.

        Reopening the form on a device that was set up with, say, a registrar
        has to show that registrar, not hide it behind a tickbox nobody knows
        to tick.
        """
        blank = softphone.Device("", "", "")
        return any(getattr(device, name) != getattr(blank, name) for name in (
            "transport", "codecs", "dtmf_mode", "registrar", "auth_user",
            "reg_interval", "rtp_timeout", "sip_trace", "net_interface",
            "extra_config",
        ))

    def action_lab_register(self) -> None:
        """`g`: register the device, or unregister one that is up."""
        if self.view != "calls":
            return
        if not softphone.available():
            self.notify(softphone.unavailable_reason(), severity="warning", timeout=8)
            return
        if self.phone.state in (softphone.REGISTERED, softphone.REGISTERING):
            self._unregister_device()
            return
        if self.phone.device is None:
            self.action_lab_device()
            return
        self._register_device(self.phone.device)

    @work(group="softphone", exclusive=True)
    async def _register_device(self, device: Any) -> None:
        try:
            await self.phone.start(device)
        except softphone.SoftphoneError as exc:
            self.notify(str(exc), severity="error", timeout=8)
            # A registration that fails where it used to work is often the
            # network path, not a fault here, and that looks exactly like a
            # broken client. Say which edges are still answering, on which
            # transport, before anybody edits code.
            self._report_edges(device.registrar or device.domain)
        self._lab_changed()

    @work(group="softphone-edges", exclusive=True)
    async def _report_edges(self, domain: str) -> None:
        if not domain:
            return
        self.phone.note("checking which edges still answer...")
        self._lab_changed()
        try:
            lines = await softphone.edge_report(domain)
        except Exception as exc:
            self.phone.note(f"edge check failed: {type(exc).__name__}: {exc}")
        else:
            for line in lines:
                self.phone.note(line)
        self._lab_changed()

    @work(group="softphone", exclusive=True)
    async def _unregister_device(self) -> None:
        await self.phone.stop()
        self._lab_changed()

    def action_hook(self) -> None:
        """`H` and the one green/red button: dial what is typed, or hang up.

        Both halves are one action because a phone has one hook. Which half it
        is never needs deciding: `on_call` answers it, and the button's own
        label and colour are set from the same test, so what it says and what
        it does cannot disagree.
        """
        if self.view != "calls":
            return
        if self.phone.on_call:
            self._hangup_device()
            return
        target = self._widget("#phone-target", Input)
        self._dial_target(target.value if target is not None else "")

    def action_lab_call(self) -> None:
        """`a`: call the agent this lab stood up."""
        if self.view != "calls":
            return
        live = self.lab.live
        if live is None or not live.dial:
            self.notify("stand the agent up first", severity="warning", timeout=4)
            return
        self._dial_target(live.dial)

    @work(group="softphone-call", exclusive=True)
    async def _dial_target(self, target: str) -> None:
        if not self.phone.registered:
            self.notify("register the device first", severity="warning", timeout=4)
            return
        try:
            await self.phone.dial(target)
        except softphone.SoftphoneError as exc:
            self.notify(str(exc), severity="error", timeout=6)
        self._lab_changed()

    @work(group="softphone-call", exclusive=True)
    async def _hangup_device(self) -> None:
        try:
            await self.phone.hangup()
        except softphone.SoftphoneError as exc:
            self.notify(str(exc), severity="warning", timeout=4)
        self._lab_changed()

    # --------------------------------------------------------------- the agent

    def _agent_form(self) -> res.Extra:
        """The agent form: an `AgentSpec` as fields, so it is a form like any
        other rather than a file to edit."""
        return res.Extra(
            "agent", "AI agent", "standup", needs_id=False,
            fields=(
                res.Field("name", required=True,
                          help="Also the route, the resource name and the SIP user."),
                res.Field("prompt", kind="textarea", required=True,
                          help="What the agent is and does."),
                res.Field("greeting", help="The first thing it says."),
                res.Field("voice", help="e.g. rime.spore or polly.Joanna. "
                                        "Blank uses the platform default."),
                res.Field("skills", kind="multi", choices=agentlab.FREE_SKILLS,
                          open_ended=True,
                          help="SDK skills. These need no API key; others do."),
                res.Field("post_prompt", kind="textarea",
                          help="Optional summary pass after the call ends."),
                res.Field("port", kind="int", help="Local port to serve on."),
            ),
        )

    def action_lab_agent(self) -> None:
        spec = self._agent_spec
        initial = {"name": spec.name, "prompt": spec.prompt, "greeting": spec.greeting,
                   "voice": spec.voice, "skills": list(spec.skills),
                   "post_prompt": spec.post_prompt, "port": spec.port}

        def done(values: dict[str, Any] | None) -> None:
            if not values:
                return
            skills = values.get("skills") or []
            self._agent_spec = agentlab.AgentSpec(
                name=str(values.get("name") or spec.name),
                prompt=str(values.get("prompt") or spec.prompt),
                greeting=str(values.get("greeting") or ""),
                voice=str(values.get("voice") or ""),
                skills=tuple(skills if isinstance(skills, list) else [skills]),
                post_prompt=str(values.get("post_prompt") or ""),
                port=int(values.get("port") or spec.port),
            )
            self._render_phone()

        self.push_screen(FormScreen(self._agent_form(), "create", initial,
                                    client=self.client, title="AI agent"), done)

    def action_lab_standup(self) -> None:
        """`u`: stand the agent up, or take a running one down."""
        if self.view != "calls":
            return
        if self.lab.state == agentlab.STARTING:
            return
        if self.lab.running:
            self._teardown_agent()
            return
        self._standup_agent()

    @work(group="agentlab", exclusive=True)
    async def _standup_agent(self) -> None:
        """Serve, tunnel and wire the agent. Several requests and an ngrok
        process, so never on the paint loop."""
        try:
            await self.lab.start(self.client, self._agent_spec)
        except agentlab.AgentLabError as exc:
            self.notify(str(exc), severity="error", timeout=10)
        self._lab_changed()

    @work(group="agentlab", exclusive=True)
    async def _teardown_agent(self) -> None:
        await self.lab.stop(client=self.client)
        self._lab_changed()

    @on(Button.Pressed, "#phone-buttons Button")
    def _phone_button(self, event: Button.Pressed) -> None:
        {"phone-device": self.action_lab_device,
         "phone-power": self.action_lab_register,
         "phone-agent": self.action_lab_agent,
         "phone-standup": self.action_lab_standup,
         "phone-agentcall": self.action_lab_call}[str(event.button.id)]()

    @on(Button.Pressed, "#phone-hook")
    def _hook_clicked(self) -> None:
        self.action_hook()

    @on(Input.Submitted, "#phone-target")
    def _target_entered(self) -> None:
        self.action_hook()

    @on(Button.Pressed, "#phone-keypad .key")
    def _keypad_pressed(self, event: Button.Pressed) -> None:
        """A key on the pad means two different things, and that is the point.

        On a call it is DTMF — the tone goes down the line, which is what a
        keypad is for once you are connected. Off a call it types into the
        target box, which is what it is for before you are. A pad that only did
        one of the two would need the other to be a prompt you open, close and
        reopen per digit, which is how `s` used to work.
        """
        digit = str(event.button.label)
        if self.phone.on_call:
            self._send_dtmf(digit)
            return
        target = self._widget("#phone-target", Input)
        if target is not None:
            target.value += digit
            # Typing continues where the pad left off rather than at 0.
            target.cursor_position = len(target.value)

    @work(group="softphone-dtmf")
    async def _send_dtmf(self, digits: str) -> None:
        # Serialised: two tones sent at once are one tone the far end cannot
        # read, and a pad invites pressing faster than a call can carry.
        async with self._dtmf_lock:
            try:
                await self.phone.send_dtmf(digits)
            except softphone.SoftphoneError as exc:
                self.notify(str(exc), severity="warning", timeout=4)

    # ------------------------------------------------------------------ profiles

    def action_profiles(self) -> None:
        """`ctrl+p` or the Profile menu: manage stored profiles, switch project."""
        self.push_screen(ProfileScreen(active=self.profile.name), self._profile_chosen)

    def _profile_chosen(self, name: str | None) -> None:
        if name and name != self.profile.name:
            self.switch_profile(name)

    @work(exclusive=True, group="profile")
    async def switch_profile(self, name: str) -> None:
        """Point the whole cockpit at another stored profile.

        Same effect as `sw profile use NAME` for later CLI runs, plus a rebuild
        of the client, bus, store and pollers so the tables show the other
        project and nothing from the old one lingers.
        """
        try:
            config.set_default(name)
            profile = config.load_profile(name)
        except ConfigError as exc:
            self.notify(str(exc), severity="error", timeout=6)
            return

        await self._stop_pipeline()
        self.profile = profile
        self._build_pipeline()
        self._start_pipeline()

        self._body_cache.clear()
        self.rows = []
        self.rows_capped = False
        self.load_error = None
        # The tiles counted the old project; keep none of it.
        self._metrics.clear()
        self._metrics_note = ""
        self.load_metrics()
        table = self._widget("#calls", DataTable)
        if table is not None:
            table.clear()
        self._log_line(Text(f"switched to profile {name} ({profile.host})", style="grey58"))
        if self.view == "rows" and self.resource is not None:
            self._drill = None
            self._load(self.resource)
        else:
            self._refresh_view()
        self.notify(f"now using {name}: {profile.host}")

    def action_command(self) -> None:
        command = self.query_one("#command", Input)
        command.display = True
        command.value = ""
        command.focus()

    def action_filter(self) -> None:
        """`/` narrows the rows on screen, the way `--match` narrows a listing.

        Over what is already held, not a new request: `_all_rows` has been and
        fetched the collection, and a keystroke should not cost a round trip.
        Submitting nothing clears it, which is the only way out that does not
        require remembering a second key.
        """
        if self.resource is None or self.view != "rows":
            self.notify("nothing to filter here", severity="warning")
            return
        searched = ", ".join(self.resource.search_fields[:4]) or "every column"

        def apply(value: str | None) -> None:
            self.row_filter = (value or "").strip() or None
            self._refresh_view()

        self.push_screen(PromptScreen(f"filter on {searched}",
                                      placeholder=self.row_filter or ""), apply)

    def action_help(self) -> None:
        """`?` shows the keys. It used to open the resource list, which is the
        one thing in the app that was already reachable another way (`:`)."""
        self.push_screen(HelpScreen(self))

    def action_jump(self) -> None:
        """Drops down every resource that has a screen, anchored at the left."""
        self.push_screen(
            DropdownMenu([r for r in res.RESOURCES if r.standalone],
                         anchor_x=0, title="resources"),
            self._menu_result)

    @on(Input.Submitted, "#command")
    def command_submitted(self, event: Input.Submitted) -> None:
        command = self.query_one("#command", Input)
        command.display = False
        value = event.value.strip()
        if value:
            self.switch_to(value)
        else:
            self._table().focus()

    def action_cursor_down(self) -> None:
        table = self._table()
        if table is not None:
            table.action_cursor_down()

    def action_cursor_up(self) -> None:
        table = self._table()
        if table is not None:
            table.action_cursor_up()

    def action_toggle_ended(self) -> None:
        self.show_ended = not self.show_ended
        self._refresh_view()

    def action_clear_feed(self) -> None:
        self.query_one("#feed", RichLog).clear()

    def action_select_text(self) -> None:
        """`m`: hand the mouse back to the terminal so text can be selected.

        This is the answer to "I cannot copy anything off this screen", and
        the clipboard is not it. A full-screen app turns on mouse reporting
        (`\x1b[?1000h` and friends), and while that is on, the terminal gives
        every click and drag to us instead of using it to select text. OSC 52
        does not save it either: `copy_to_clipboard` is ignored by macOS
        Terminal, which is where this came up.

        So the fix is to stop reporting. With it off the terminal behaves like
        it does over `cat`: drag to select, copy with the usual keystroke. The
        app keeps painting and the keyboard keeps working — only the mouse is
        surrendered, which is why this has to be a mode you leave rather than
        something permanent.
        """
        driver = self._driver
        if driver is None:
            self.notify("no terminal driver; nothing to hand back",
                        severity="warning", timeout=4)
            return
        disable = getattr(driver, "_disable_mouse_support", None)
        enable = getattr(driver, "_enable_mouse_support", None)
        if disable is None or enable is None:
            # A driver without them is a driver we are not running under a
            # terminal with; say so rather than pretending the mode toggled.
            self.notify("this terminal driver cannot release the mouse",
                        severity="warning", timeout=5)
            return
        self.selecting = not self.selecting
        if self.selecting:
            disable()
            self.notify("mouse released - drag to select, copy as usual, "
                        "then press m to take it back", timeout=8)
        else:
            enable()
            self.notify("mouse back in the app", timeout=3)
        self._render_status()

    def action_copy_diagnostics(self) -> None:
        """`y`: put the lab's diagnostics where they can be pasted.

        A full-screen app owns the mouse, so nothing on this screen can be
        selected or quoted. Two destinations rather than one, because neither
        is reliable alone: the clipboard is OSC 52, which macOS Terminal
        ignores, and a file is useless if nothing says where it is. So the
        text goes to both and the notification names the path.
        """
        text = lab_view.diagnostics(self.phone, self.profile, self.lab)
        self.copy_to_clipboard(text)
        path = softphone.diagnostics_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf8")
        except OSError as exc:
            self.notify(f"copied to the clipboard; could not write the file: {exc}",
                        severity="warning", timeout=8)
            return
        self.notify(f"copied to the clipboard and written to {path}", timeout=8)

    def action_refresh(self) -> None:
        if self.view == "home":
            self.load_metrics()
            return
        if self.view == "rows" and self.resource is not None:
            # Refreshing a drill returns to the parent list; refreshing a list
            # reloads it in place.
            self._drill = None
            self._load(self.resource)
        else:
            self._refresh_view()

    def action_inspect(self) -> None:
        self._render_detail()

    # ------------------------------------------------------------------- actions

    def action_hangup(self) -> None:
        """`h`: hang up the selected leg in the table.

        Not the phone's own call, even though both are now on this view. `h`
        belongs to the table's vocabulary and acts on the row under the cursor,
        the way `e` and `d` do; the phone's call is ended by its own button and
        by `H`. A key that meant one call or the other depending on whether a
        softphone happened to be registered would be a key you have to think
        about before pressing.
        """
        if self.view != "calls":
            return
        call = self._selected_call()
        if call is None:
            self.notify("no call selected", severity="warning", timeout=2)
            return
        self._control("hangup", self.client.hangup(call.ref))

    def action_transfer(self) -> None:
        self._prompt_then("transfer to", "sip:agent@example.com or +1555...",
                          lambda call, value: self.client.transfer(call.ref, value))

    def action_play(self) -> None:
        self._prompt_then("say into the call", "text to speak",
                          lambda call, value: self.client.play_tts(call.ref, value))

    def action_digits(self) -> None:
        self._prompt_then("send DTMF", "1234#",
                          lambda call, value: self.client.send_digits(call.ref, value))

    def action_record(self) -> None:
        if self.view != "calls":
            return
        call = self._selected_call()
        if call is None:
            self.notify("no call selected", severity="warning", timeout=2)
            return
        self._control("record", self.client.start_recording(call.ref))

    # ---------------------------------------------------------------- resource CRUD

    def action_new(self) -> None:
        """Create a row in the current resource; on the live view, a new call."""
        if self.view == "calls":
            self.action_dial()
            return
        resource = self._crud_target("create")
        if resource is None:
            return

        # A phone number cannot be typed from memory: you have to see what the
        # platform is offering before you can buy one. Search inventory first.
        if resource.key == "numbers":
            self._buy_number(resource)
            return

        def then(body: dict[str, Any] | None) -> None:
            if body:
                self._write(resource, "create", None, body, "created")

        self.push_screen(FormScreen(resource, "create", client=self.client), then)

    def _buy_number(self, resource: res.Resource) -> None:
        """Search available numbers, then confirm before billing the account."""
        def chosen(number: str | None) -> None:
            if not number:
                return

            def confirmed(yes: bool) -> None:
                if yes:
                    self._write(resource, "create", None,
                                {"number": number}, "bought")

            self.push_screen(
                ConfirmScreen(f"buy {number}? This charges the project."), confirmed
            )

        self.push_screen(NumberSearchScreen(self.client), chosen)

    def action_edit(self) -> None:
        """Edit the selected row, prefilled with its current values."""
        resource = self._crud_target("update")
        if resource is None:
            return
        row = self._selected_row()
        identifier = self._selected_key()
        if row is None or identifier is None:
            self.notify("no row selected", severity="warning", timeout=2)
            return

        def then(body: dict[str, Any] | None) -> None:
            if body:
                self._write(resource, "update", identifier, body, "updated")

        self.push_screen(
            FormScreen(resource, "update", initial=row, client=self.client), then
        )

    def action_delete(self) -> None:
        """Delete the selected row, behind a confirmation."""
        resource = self._crud_target("delete")
        if resource is None:
            return
        identifier = self._selected_key()
        if identifier is None:
            self.notify("no row selected", severity="warning", timeout=2)
            return

        def then(confirmed: bool) -> None:
            if confirmed:
                self._write(resource, "delete", identifier, None, "deleted")

        self.push_screen(
            ConfirmScreen(f"delete {_singular(resource.title)} {identifier}?"), then
        )

    def _crud_target(self, op: str) -> res.Resource | None:
        """The current resource, if it supports ``op``.

        Capability comes from SDK introspection, so a refusal here reflects what
        the API actually offers rather than a gap in swsh.
        """
        if self.view != "rows" or self.resource is None:
            return None
        letter = {"create": res.CREATE, "update": res.UPDATE, "delete": res.DELETE}[op]
        if not self.resource.can(letter):
            self.notify(f"{self.resource.title} does not support {op}",
                        severity="warning", timeout=3)
            return None
        return self.resource

    @work(group="control")
    async def _write(self, resource: res.Resource, op: str, identifier: str | None,
                     body: dict[str, Any] | None, verb: str) -> None:
        """Run a create, update or delete via the transport, then reload."""
        try:
            result = await self.client.invoke(
                resource, op, resource_id=identifier, body=body
            )
        except SwshError as exc:
            self._fail(verb, exc, f"{resource.key}.{op}")
            return
        except Exception as exc:
            self._fail(verb, exc, f"{resource.key}.{op}")
            return

        name = identifier or (result or {}).get(resource.id_field, "")
        self.notify(f"{verb} {name}".strip(), timeout=3)
        self._log_line(Text(f"  {verb} {resource.title}: {name}", style=ui.TURQUOISE))
        if resource.can_list:
            self._load(resource)

    def _fail(self, verb: str, exc: Exception, where: str) -> None:
        """Report a failed write. The message names the action, not a mangled
        past participle."""
        action = {"created": "create", "updated": "update",
                  "deleted": "delete", "bought": "purchase"}.get(verb, verb)
        self.notify(f"{action} failed: {exc}", severity="error", timeout=10)
        self._log_line(Text(f"  {where}: {exc}", style="red"))

    def _available_extras(self) -> list[res.Extra]:
        """The extras that apply to what is on screen right now.

        In the parent list that is every extra not tied to a drill; inside a
        drill it is the extras declared for that drill (a membership's
        "remove member", a token's "reset"), because those act on the drill's
        rows and would hit the wrong id from the parent.
        """
        if self.view != "rows" or self.resource is None:
            return []
        current = self._drill or ""
        extras = [e for e in self.resource.extras if e.on_drill == current]
        if not self._rows_possible():
            # Nothing can be highlighted here, so an extra that acts on the
            # selected row has no id to act with. Only the ones that collect
            # everything they need on their own form can run: send an MFA code,
            # mint a guest token, look up a number.
            extras = [e for e in extras if self.resource.serves_itself(e)]
        return extras

    def _row_key(self, row: dict[str, Any]) -> str:
        return str(row.get("id") or row.get("sid") or "")

    def action_detail_mode(self) -> None:
        """`v`: cycle the detail pane between fields, json and raw.

        The same three things `sw` prints — the field table, `--json` and
        `--raw` — on the row under the cursor, because the answer to "what does
        the API really hold for this?" should not require leaving the cockpit
        and retyping the id.

        It clears the routing tree, which is the fourth way of reading a row and
        is a toggle of its own; showing a JSON document under a heading that
        says routing would be two answers at once.
        """
        if self.view not in ("rows", "calls"):
            return
        index = (DETAIL_MODES.index(self.detail_mode) + 1) % len(DETAIL_MODES)
        self.detail_mode = DETAIL_MODES[index]
        self._routing = None
        self._routing_loading = None
        self._render_detail()
        self.refresh_bindings()

    def action_routing(self) -> None:
        """`F`: follow the selected row's routing to what it points at.

        The same expansion `sw numbers get <n> --full` prints. It is a toggle on
        the detail pane rather than a modal, because it *is* the detail of that
        row — the version that answers "what happens when this rings?" instead
        of listing forty fields of which most are dead.
        """
        if self.view != "rows" or self.resource is None:
            return
        if not self.resource.routing:
            self.notify(f"{self.resource.title} declare no routing to follow",
                        severity="warning", timeout=3)
            return
        row = self._selected_row()
        if row is None:
            self.notify("no row selected", severity="warning", timeout=2)
            return

        key = self._row_key(row)
        self.detail_mode = DETAIL_MODES[0]  # routing replaces the format, not adds to it
        if self._routing is not None and self._routing[0] == key:
            self._routing = None  # pressed again: back to the field table
            self._render_detail()
            return
        self._routing = None
        self._routing_loading = key
        self._render_detail()
        self._expand_routing(key, row, self.resource)

    @work(group="routing", exclusive=True)
    async def _expand_routing(self, key: str, row: dict[str, Any],
                              resource: res.Resource) -> None:
        """Resolve one row's routing off the paint loop.

        This is several requests and can include fetching a webhook on somebody
        else's server, which may sit there until it times out. Doing it inline
        would freeze the 1 Hz repaint for as long as that takes.
        """
        try:
            result = await routing.expand(self.client, resource, row)
        except Exception as exc:
            self._routing_loading = None
            self.notify(f"could not follow the routing: {exc}",
                        severity="error", timeout=6)
            self._render_detail()
            return
        self._routing_loading = None
        # The cursor may have moved on while this was in flight; only show it
        # if it is still the row being looked at.
        current = self._selected_row()
        if current is not None and self._row_key(current) == key:
            self._routing = (key, result)
        self._render_detail()

    def action_extra(self) -> None:
        """Open the resource's extra operations: drills and actions.

        A single extra runs directly; more than one opens a clickable menu, so
        the available operations are shown and picked with the mouse — never a
        set of hotkeys the user has to already know.
        """
        extras = self._available_extras()
        if not extras:
            return
        identifier = self._selected_key()

        if len(extras) == 1:
            self._start_extra(extras[0], identifier)
            return

        by_key = {e.key: e for e in extras}

        def chosen(key: str | None) -> None:
            if key and key in by_key:
                self._start_extra(by_key[key], identifier)

        self.push_screen(
            ContextMenu([(e.key, e.label) for e in extras]), chosen
        )

    def _start_extra(self, extra: res.Extra, identifier: str | None) -> None:
        """Collect what the extra needs, then run it.

        A drill just runs. An action that takes input gets a form (the same one
        create and edit use), prefilled from the highlighted row where a field
        reads from it. One marked ``confirm`` asks first, since it changes
        something that is not undone by pressing escape.
        """
        if extra.needs_id and identifier is None:
            self.notify("no row selected", severity="warning", timeout=2)
            return

        def run(body: dict[str, Any] | None = None) -> None:
            self._run_extra(extra, identifier, body)

        if extra.takes_input:
            def submitted(body: dict[str, Any] | None) -> None:
                if body is not None:
                    run(body)

            self.push_screen(
                FormScreen(extra, "create", initial=self._selected_row(),
                           client=self.client, title=extra.label),
                submitted,
            )
        elif extra.confirm:
            target = f" {identifier}" if extra.needs_id else ""
            self.push_screen(ConfirmScreen(f"{extra.label}{target}?"),
                             lambda yes: run() if yes else None)
        else:
            run()

    @work(group="control")
    async def _run_extra(self, extra: res.Extra, identifier: str | None,
                         body: dict[str, Any] | None = None) -> None:
        resource = self.resource
        if resource is None:
            return
        try:
            payload = await self.client.invoke(
                resource, extra.method,
                resource_id=identifier if extra.needs_id else None,
                body=body or None,
            )
        except Exception as exc:
            self.notify(f"{extra.label} failed: {exc}", severity="error", timeout=6)
            self._log_line(Text(f"  {resource.key} {extra.label}: {exc}", style="red"))
            return

        rows = res.unwrap(payload)
        if _is_read(resource, extra) or rows:
            # Show the result in place as a labelled drill-down, keeping the
            # parent resource so escape/refresh can step back to it. A write
            # that returns an object (a minted token, an MFA request id) is
            # shown the same way, because that object is the point.
            self.rows = rows
            self.rows_capped = False
            self.load_error = None
            self._drill = extra.label
            if not extra.on_drill:
                self._drill_parent = identifier if extra.needs_id else None
            self._refresh_view()
            self.notify(f"{extra.label}: {len(self.rows)} — esc to go back", timeout=3)
            return

        # A write with nothing to show: say so, and reload what it changed.
        name = identifier or ""
        self.notify(f"{extra.label} {name}".strip(), timeout=3)
        self._log_line(Text(f"  {extra.label} {resource.title}: {name}".rstrip(),
                            style=ui.TURQUOISE))
        self._reload_current()

    def _reload_current(self) -> None:
        """Refresh whatever list is showing: the drill if one is open, else the
        resource itself."""
        resource = self.resource
        if resource is None:
            return
        if self._drill:
            drill = next((e for e in resource.extras
                          if e.label == self._drill and e.on_drill == ""), None)
            parent_id = self._drill_parent
            if drill is not None and (parent_id or not drill.needs_id):
                self._run_extra(drill, parent_id)
                return
        self._drill = None
        if resource.can_list:
            self._load(resource)

    # ------------------------------------------------------------------ dialling

    def action_dial(self) -> None:
        """Place a call from the live view. It appears in the table on the next
        poll, so the form is the only extra UI."""
        def submitted(body: dict[str, Any] | None) -> None:
            if not body:
                return
            if not body.get("url") and not body.get("say"):
                self.notify("give a URL to run, or something to say",
                            severity="warning", timeout=4)
                return
            self._control(
                f"dial {body['to']}",
                self.client.dial(to=body["to"], from_=body["from_"],
                                 url=body.get("url"), say=body.get("say")),
            )

        self.push_screen(
            FormScreen(res.DIAL, "create", client=self.client, title="new call"),
            submitted,
        )

    def _prompt_then(self, prompt: str, placeholder: str, action) -> None:
        if self.view != "calls":
            return
        call = self._selected_call()
        if call is None:
            self.notify("no call selected", severity="warning", timeout=2)
            return

        def then(value: str | None) -> None:
            if value:
                self._control(prompt, action(call, value))

        self.push_screen(PromptScreen(prompt, placeholder), then)

    @work(group="control")
    async def _control(self, label: str, awaitable) -> None:
        try:
            await awaitable
        except SwshError as exc:
            self.notify(f"{label} failed: {exc}", severity="error", timeout=6)
            self._log_line(Text(f"  {label} failed: {exc}", style="red"))
        except Exception as exc:
            self.notify(f"{label} failed: {exc}", severity="error", timeout=6)
        else:
            self.notify(f"{label} sent", timeout=2)

    @on(DataTable.RowHighlighted)
    def row_changed(self) -> None:
        self._render_detail()

    @on(DataTable.RowSelected)
    def row_clicked(self) -> None:
        """Clicking or pressing enter on a row opens it in the detail pane."""
        self._render_detail()
        detail = self._widget("#detail-scroll", VerticalScroll)
        if detail is not None:
            detail.scroll_home(animate=False)

    async def on_unmount(self) -> None:
        await self._stop_pipeline()


def _row_detail(row: dict[str, Any]):
    """A two-column field table for a resource row, like the dashboard's panel.

    Nested objects are flattened into dotted keys (``ai_agent.prompt.text``)
    so every field of the object is on screen, however deep the API nests it.
    Nothing is truncated: long values fold onto following lines, and lists of
    objects are printed as indented JSON in full. The pane scrolls.
    """
    from rich.table import Table

    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="grey50", no_wrap=True)
    table.add_column(overflow="fold")
    shown = 0
    for key, value in _flatten(row):
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            rendered = "yes" if value else "no"
        elif isinstance(value, list):
            if all(not isinstance(v, (dict, list)) for v in value):
                rendered = ", ".join(str(v) for v in value) or "[]"
            else:
                rendered = json.dumps(value, indent=2, default=str)
        elif isinstance(value, dict):  # only an empty dict survives flattening
            rendered = "{}"
        else:
            rendered = str(value)
        style = ui.TURQUOISE if key in ("id", "sid") else ""
        table.add_row(key, Text(rendered, style=style))
        shown += 1
    if shown == 0:
        return Text("(empty)", style="grey42")
    return table


def _flatten(row: dict[str, Any], prefix: str = ""):
    """Yield ``(dotted_key, value)`` pairs, descending into nested dicts."""
    for key, value in row.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict) and value:
            yield from _flatten(value, f"{dotted}.")
        else:
            yield dotted, value


def _mode_line(mode: str, note: str = "") -> Text:
    """Name the format on screen, so a JSON document is never mistaken for the
    row sw would act on."""
    text = Text(mode, style=ui.PURPLE)
    if note:
        text.append(f"  {note}", style="grey42")
    text.append("\n")
    return text


def _row_heading(row: dict[str, Any]) -> Text:
    """Name the thing being inspected, before the raw payload.

    Rows label themselves inconsistently across the API surfaces, so this takes
    the first human-readable field that is present.
    """
    name = next(
        (row[k] for k in ("display_name", "name", "number", "username", "email", "e164")
         if row.get(k)),
        None,
    )
    identifier = row.get("id") or row.get("sid") or ""
    heading = Text()
    heading.append(f"{name}\n", style=f"bold {ui.TURQUOISE}") if name else None
    if identifier:
        heading.append(f"{identifier}\n", style="grey50")
    heading.append("\n")
    return heading


def _is_read(resource: res.Resource, extra: res.Extra) -> bool:
    """Whether an extra only fetches, judged by the catalog's method for it.

    A GET is shown as a drill; anything else is an action whose result, if
    any, is shown, and whose absence of a result means "done, reload". An
    extra the catalog does not know (the two SDK-only resources) is treated as
    a drill, which is what every such extra has always been.
    """
    from .. import spec

    op_id = resource.rest_ops.get(extra.method) or extra.spec_op
    operation = spec.get(op_id, api=resource.api) if op_id and resource.api else None
    return operation is None or operation.method.upper() == "GET"


def _singular(title: str) -> str:
    """Rough singular for confirmation prompts. Good enough for a yes/no line."""
    return title[:-1] if title.endswith("s") and not title.endswith("ss") else title


def _cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)[:48]
    text = str(value)
    return text if len(text) <= 46 else f"{text[:45]}…"
