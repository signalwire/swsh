"""Form controls that show what is in them.

One control lives here, for one reason. Nearly every long value in these forms
is a URL — a cXML webhook, a SWML script, a status callback — and a single-line
``Input`` scrolls horizontally, so a pasted 120-character URL shows about thirty
characters with no way to read the rest but arrowing along it. A URL you cannot
read is a URL you cannot check, which is the whole job of pasting it into a form.

So this wraps rather than scrolls, and takes the height it needs.
"""

from __future__ import annotations

from textual import events
from textual.widgets import TextArea


class GrowingArea(TextArea):
    """A single-value text box that grows to fit its content.

    Starts one line tall and grows as the value wraps, up to ``max_lines``,
    after which it scrolls — a form whose every field is ten lines tall is no
    easier to read than one that hides the values.

    The value is still *one* value, so ``enter`` moves to the next field the way
    it would from an ``Input`` rather than inserting a newline: a line break in
    a webhook URL is never what anybody meant, and it would be sent.
    """

    DEFAULT_CSS = """
    GrowingArea {
        height: 1;
        min-height: 1;
        border: solid #044EF4;
        background: #11141d;
        padding: 0 1;
    }
    GrowingArea:focus {
        border: solid #40E0D0;
    }
    """

    def __init__(self, value: str = "", *, placeholder: str = "",
                 max_lines: int = 6, **kwargs) -> None:
        super().__init__(value, soft_wrap=True, placeholder=placeholder,
                         show_line_numbers=False, **kwargs)
        self.max_lines = max_lines

    @property
    def value(self) -> str:
        """Mirrors ``Input.value``, so callers need not know which control this is."""
        return self.text

    @value.setter
    def value(self, new: str) -> None:
        self.text = new

    def on_mount(self) -> None:
        self._fit()

    def _on_resize(self) -> None:
        # The wrap width changed, so the same text may now need a different
        # number of lines. Without this, widening the terminal leaves a box
        # three lines tall around a value that fits on one. Textual dispatches
        # by signature, and TextArea's own handler takes no event — matching it
        # is not optional.
        super()._on_resize()
        self._fit()

    def _on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._fit()

    def _fit(self) -> None:
        """Set the height to the number of wrapped lines, plus the border.

        `height` is the *outer* height — Textual's box-sizing is `border-box` —
        so the solid border's two rows come out of it. Setting it to the line
        count alone left a box one row tall with a two-row gutter and a content
        area of zero rows: every keystroke was accepted and stored, and none of
        it was ever painted. `gutter.height` is that border plus any vertical
        padding, read from the widget rather than hard-coded at 2.
        """
        try:
            lines = self.wrapped_document.height
        except Exception:  # before the document has been laid out
            lines = 1
        visible = max(1, min(lines or 1, self.max_lines))
        try:
            gutter = self.gutter.height
        except Exception:  # before styles are resolved
            gutter = 0
        self.styles.height = visible + gutter

    def _on_focus(self, event: events.Focus) -> None:
        # A prefilled box opens with the cursor at 0, so the first thing typed
        # lands in front of the value instead of after it — typing into a filled
        # domain gave `-xacme-…`. Focus means "carry on from what is
        # here", so the cursor goes to the end.
        try:
            self.move_cursor(self.document.end)
        except Exception:  # before the document exists
            pass

    async def _on_key(self, event: events.Key) -> None:
        # `TextArea._on_key` is a coroutine, so this override has to be one too
        # and has to await it. Declared `def`, the super() call built a
        # coroutine nobody ran: every key but `enter` reached a handler that
        # never executed, and Python reported it only as a RuntimeWarning about
        # a coroutine that was never awaited — on stderr, which a full-screen
        # app has already taken over.
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.screen.focus_next()
            return
        await super()._on_key(event)
