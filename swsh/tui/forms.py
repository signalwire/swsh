"""Create and edit forms for any registered resource.

One modal serves every namespace, driven by the field list in
``swsh.resources``. Each field declares a kind and gets the matching control:

* ``bool`` a checkbox
* ``choice`` a select
* ``multi`` a checkbox per option, plus a free-text box when the option list may
  be incomplete
* ``list`` a comma-separated box
* ``int`` an input validated as a whole number
* ``textarea`` a plain multi-line box, for prose such as an agent prompt
* ``code`` a validating editor, used only where the value really is a document

Every text box grows to fit what is in it (``widgets.GrowingArea``): the values
here are webhook URLs and script URLs, and a single-line control that scrolls
sideways hides the half of a pasted URL that tells you it is wrong.

Nobody is asked to type a JSON object to set a flag or pick a codec. The one
editor in the whole form system is for SWML script contents, and even that is
parsed and reported on before anything is sent, so a syntax error surfaces here
with a line number rather than as an opaque error from the API.
"""

from __future__ import annotations

import json
from typing import Any

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Select,
    Static,
    TextArea,
)

from .. import resources as res
from .widgets import GrowingArea

# Textual renamed the "nothing selected" sentinel: it is Select.NULL in current
# versions, while the older Select.BLANK alias now evaluates to plain False and
# is rejected by the value validator. Prefer NULL, fall back for older Textual.
SELECT_NULL = getattr(Select, "NULL", getattr(Select, "BLANK", None))


class FormScreen(ModalScreen[dict[str, Any] | None]):
    """Collects a request body for a create or an update."""

    BINDINGS = [
        Binding("escape", "cancel", "cancel"),
        Binding("ctrl+s", "submit", "save"),
    ]

    def __init__(self, resource: res.Resource | res.Extra, mode: str,
                 initial: dict[str, Any] | None = None, client: Any = None,
                 title: str | None = None):
        super().__init__()
        # Anything with `form_fields(mode)` and `title`: a Resource for create
        # and edit, an Extra for an action that needs input (assign an E911
        # address, mint a token, place a call).
        self.resource = resource
        self.mode = mode  # "create" or "update"
        self.title_text = title or f"{mode} {resource.title}"
        # Needed only by fields whose options come from live data.
        self.client = client
        # Rows behind the loaded options, per field, for `prefill`.
        self._option_rows: dict[str, dict[str, dict]] = {}
        # Follow nested paths so an edit shows the value that is really there.
        self.initial = (
            res.unflatten(resource, initial, mode) if initial else {}
        )

    def compose(self) -> ComposeResult:
        fields = self.resource.form_fields(self.mode)
        with Vertical(id="form-box"):
            with Horizontal(id="form-header"):
                yield Label(self.title_text, id="form-title")
                yield Button("✕", id="form-close", classes="close-x")
            with VerticalScroll(id="form-fields"):
                if not fields:
                    yield Static(
                        "This resource takes no editable fields.",
                        classes="form-help",
                    )
                for field_def in fields:
                    with Vertical(classes="field-wrap", id=f"wrap-{field_def.name}"):
                        yield from self._control(field_def)
            yield Static("", id="form-error")
            with Horizontal(id="form-buttons"):
                yield Button("save", variant="primary", id="save")
                yield Button("cancel", variant="error", id="cancel")

    def on_mount(self) -> None:
        self._apply_visibility()
        self._focus_first_field()
        self._load_dynamic_options()

    def _focus_first_field(self) -> None:
        """Put the cursor in the first field, not on the close button.

        Left to itself Textual focuses the first focusable widget, which here is
        the header's `✕`. The form then looks ready to type into and is not:
        keystrokes go to a button, and reaching the first box takes three tabs
        (close, the scroll container, then the field). Anyone who opened a form
        and started typing lost what they typed.
        """
        for field_def in self.resource.form_fields(self.mode):
            if not field_def.visible_for(self.initial):
                continue
            try:
                self.query_one(f"#field-{field_def.name}").focus()
            except Exception:
                continue
            return

    @work(group="form-options")
    async def _load_dynamic_options(self) -> None:
        """Fill selects whose options come from the project itself.

        Runs after the form is already usable, so a slow lookup never blocks
        typing. A failure leaves the select empty and says why, rather than
        silently offering nothing.
        """
        if self.client is None:
            return
        from ..selectors import Selector

        selector = getattr(self.client, "selector", None) or Selector(self.client)
        for field_def in self.resource.form_fields(self.mode):
            if not field_def.options_from:
                continue
            try:
                opts = await selector.options(field_def.options_from)
            except Exception as exc:
                # The reason goes to the log, not the form. It is useful when
                # something is wrong and meaningless to somebody who just
                # wants to pick an endpoint.
                self.log(f"options for {field_def.name} failed: {exc!r}")
                self._note(field_def, "none available")
                continue

            options = [(o.display, o.value) for o in opts]
            # Keep the rows: a field with `prefill` reads its siblings' values
            # out of the row behind the chosen option, and that row is already
            # here. Fetching it again to read one more key would be a second
            # request for something in hand.
            self._option_rows[field_def.name] = {o.value: o.row for o in opts}
            try:
                select = self.query_one(f"#field-{field_def.name}", Select)
            except Exception:
                continue
            current = self.initial.get(field_def.name)
            select.set_options(options)
            if current and any(v == current for _, v in options):
                select.value = current
            if not options:
                self._note(field_def, "none available")

    def _note(self, field_def: res.Field, message: str) -> None:
        """Replace a field's help line with a live status.

        Un-hides the slot: a field that declares no help has its help node
        collapsed, and a status nobody can see is not a status.

        Keep whatever goes through here short and about the *field*. Nobody
        using a picker needs to know which call failed or what the platform
        does and does not return — that is the application talking about
        itself, and it belongs in the log, not on the form.
        """
        for node in self.query(f"#wrap-{field_def.name} .form-help"):
            node.remove_class("empty")
            node.update(message)
            return

    @on(Select.Changed)
    def _select_changed(self, event: Select.Changed) -> None:
        self._prefill_from(event.select, event.value)
        self._apply_visibility()

    def _prefill_from(self, select: Select, value: Any) -> None:
        """Fill the fields a chosen option can answer for.

        Picking a SIP endpoint already says what its domain is; making somebody
        read it off the dashboard and retype it is a step the form can do
        itself. Only values the row actually carries are written, so a key the
        API withholds (an endpoint's password is the live case) leaves its box
        alone rather than blanking it — silently. An empty box somebody can
        type into needs no explanation of which API returned what.
        """
        name = str(getattr(select, "id", "") or "").removeprefix("field-")
        field_def = next((f for f in self.resource.form_fields(self.mode)
                          if f.name == name and f.prefill), None)
        if field_def is None:
            return
        row = self._option_rows.get(name, {}).get(value) or {}
        for target, source in field_def.prefill:
            found = res.cell(row, source)
            if found in (None, ""):
                # Nothing to fill and nothing to say about it. What the API
                # does or does not return is not the user's problem; an empty
                # box they can type into already says everything they need.
                continue
            try:
                self.query_one(f"#field-{target}").value = _as_text(found)
            except Exception:
                continue

    @on(Checkbox.Changed)
    def _checkbox_changed(self) -> None:
        self._apply_visibility()

    @on(Input.Changed)
    def _input_changed(self) -> None:
        self._apply_visibility()

    @on(TextArea.Changed)
    def _text_changed(self) -> None:
        # The growing text boxes are TextAreas, so `show_if` on a text field
        # would stop reacting without this.
        self._apply_visibility()

    def _apply_visibility(self) -> None:
        """Show only the fields that make sense for the current choices.

        A phone number routed to `laml_webhooks` needs a cXML URL; the same
        number routed to `ai_agent` needs a resource id and no URL at all.
        Showing every companion field at once invites sending the wrong one.
        """
        current = self._raw_values()
        for field_def in self.resource.form_fields(self.mode):
            try:
                wrap = self.query_one(f"#wrap-{field_def.name}")
            except Exception:
                continue
            wrap.display = field_def.visible_for(current)

    def _raw_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field_def in self.resource.form_fields(self.mode):
            try:
                values[field_def.name] = self._read(field_def)
            except Exception:
                values[field_def.name] = ""
        return values

    # ------------------------------------------------------------------ controls

    def _control(self, field_def: res.Field) -> ComposeResult:
        current = self.initial.get(field_def.name)
        widget_id = f"field-{field_def.name}"
        required = field_def.required and self.mode == "create"

        if field_def.kind == "bool":
            # The checkbox carries its own label, so no separate caption.
            yield Checkbox(field_def.title, value=bool(current), id=widget_id)
            yield from self._help(field_def)
            return

        yield Label(f"{field_def.title}{' *' if required else ''}", classes="form-label")

        if field_def.kind == "choice":
            if field_def.options_from:
                # Filled in by _load_dynamic_options once the project answers.
                # The prompt is the field's own name, not "loading...": the load
                # finishes in a moment but the prompt is what shows whenever
                # nothing is selected, so "loading..." sat there for good.
                yield Select([], id=widget_id, allow_blank=True,
                             prompt=field_def.title)
            else:
                options = [(choice, choice) for choice in field_def.choices]
                chosen = current if current in field_def.choices else SELECT_NULL
                yield Select(options, value=chosen, id=widget_id, allow_blank=True)

        elif field_def.kind == "multi":
            selected = {str(v) for v in current} if isinstance(current, (list, tuple)) else set()
            with Vertical(id=widget_id, classes="checkbox-group"):
                for choice in field_def.choices:
                    yield Checkbox(
                        choice,
                        value=choice in selected,
                        id=f"{widget_id}--{_slug(choice)}",
                        classes="group-item",
                    )
            if field_def.open_ended:
                # Anything not in the known set can still be entered, so an
                # incomplete option list never blocks a valid request.
                extra = sorted(selected - set(field_def.choices))
                yield GrowingArea(
                    ", ".join(extra),
                    placeholder="other values, comma separated",
                    id=f"{widget_id}--other",
                    classes="group-other",
                )

        elif field_def.kind == "list":
            value = ", ".join(str(v) for v in current) if isinstance(current, (list, tuple)) \
                else _as_text(current)
            yield GrowingArea(value, placeholder="comma separated", id=widget_id)

        elif field_def.kind in ("textarea", "code"):
            text = _as_text(current)
            if field_def.kind == "code":
                yield TextArea(text or "{}", language=field_def.language, id=widget_id,
                               classes="code-area")
            else:
                yield TextArea(text, id=widget_id, classes="text-area")

        elif field_def.secret:
            yield Input(value=_as_text(current), password=True, id=widget_id)

        elif field_def.kind == "int":
            yield Input(value=_as_text(current), placeholder="whole number",
                        type="integer", id=widget_id)

        else:
            yield GrowingArea(_as_text(current), id=widget_id)

        yield from self._help(field_def)

    def _help(self, field_def: res.Field) -> ComposeResult:
        """The help line, and the slot a live status is written into.

        A field with no help text still gets the node — `_note` writes load
        failures into it — but it is hidden, so it costs no row. Declaring no
        help has to mean nothing under the box, not a blank line under it.
        """
        classes = "form-help" if field_def.help else "form-help empty"
        yield Static(field_def.help, classes=classes)

    # -------------------------------------------------------------------- submit

    def action_submit(self) -> None:
        try:
            body = self._collect()
        except ValueError as exc:
            self._show_error(str(exc))
            return
        if not body:
            self._show_error("nothing to send")
            return
        self.dismiss(body)

    def _collect(self) -> dict[str, Any]:
        raw = self._raw_values()
        # Drop anything currently hidden, so switching handler mid-edit cannot
        # smuggle a stale URL into the request.
        visible = {
            f.name: raw[f.name]
            for f in self.resource.form_fields(self.mode)
            if f.visible_for(raw) and f.name in raw
        }
        return res.build_body(self.resource, self.mode, visible)

    def _read(self, field_def: res.Field) -> Any:
        """Pull one field's value back out of its control."""
        widget_id = f"field-{field_def.name}"

        if field_def.kind == "multi":
            chosen = [
                str(box.label)
                for box in self.query(f"#{widget_id} .group-item").results(Checkbox)
                if box.value
            ]
            if field_def.open_ended:
                others = self.query(f"#{widget_id}--other")
                for box in others.results(GrowingArea):
                    chosen.extend(
                        part.strip() for part in box.value.split(",") if part.strip()
                    )
            return chosen

        widget = self.query_one(f"#{widget_id}")
        if isinstance(widget, Checkbox):
            return widget.value
        if isinstance(widget, Select):
            return "" if widget.value is SELECT_NULL else str(widget.value)
        if isinstance(widget, TextArea):
            return widget.text
        return getattr(widget, "value", "")

    def _show_error(self, message: str) -> None:
        self.query_one("#form-error", Static).update(message)

    @on(Button.Pressed, "#save")
    def save_pressed(self) -> None:
        self.action_submit()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#form-close")
    def close_pressed(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


def _slug(value: str) -> str:
    """Widget-id-safe form of an option value."""
    return "".join(c if c.isalnum() else "-" for c in value)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    if isinstance(value, bool):
        return "true" if value else ""
    return str(value)
