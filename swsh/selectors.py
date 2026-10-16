"""The selector service — one place that turns "a field is a choice from the
project" into concrete options.

The rule: never make someone type an identifier swsh can enumerate.
A *from* number, an e911 address, a SIP destination, a template — all are
presented as a list. That list comes from here, and the same implementation
feeds TUI dropdowns, CLI interactive pickers, and shell-completion candidates.

Options are resolved through ``client.invoke`` (so rest and sdk resources both
work) and cached per session, because a picker or a ``<TAB>`` must be instant
and must not hit the API on every keystroke.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import resources as res


@dataclass(frozen=True, slots=True, eq=False)
class Option:
    """One selectable choice: the value sent, a human label, and its source row.

    The row is kept so callers can filter on fields that are not part of the
    label — e.g. a phone number's ``capabilities``.
    """

    value: str
    label: str
    capabilities: tuple[str, ...] = ()
    # The whole row, so a caller can read a field the label never showed — a
    # number's capabilities, a SIP endpoint's domain. The docstring above
    # promised this row and only `capabilities` was actually kept, so reading
    # anything else meant fetching a row that was already in hand.
    row: dict = field(default_factory=dict)

    @property
    def display(self) -> str:
        return f"{self.value}  {self.label}" if self.label and self.label != self.value \
            else self.value


class Selector:
    """Resolves and caches option lists for enumerable fields."""

    def __init__(self, client):
        self.client = client
        self._cache: dict[str, list[Option]] = {}

    async def options(self, source: tuple[str, str, str], *,
                      refresh: bool = False) -> list[Option]:
        """Options for a field's ``options_from = (list_path, value_key, label_key)``.

        ``list_path`` is ``"<resource-key>.list"`` (e.g. ``"numbers.list"``),
        resolved through the registry and ``client.invoke`` so it works for rest
        resources too.
        """
        list_path, value_key, label_key = source
        cache_key = list_path
        if not refresh and cache_key in self._cache:
            return self._cache[cache_key]

        resource_key = list_path.split(".", 1)[0]
        resource = res.get(resource_key)
        options: list[Option] = []
        if resource is not None:
            try:
                payload = await self.client.invoke(resource, "list")
                rows = res.unwrap(payload, resource.data_key)
                for row in rows:
                    # Dotted keys reach Fabric's nested fields (sip_endpoint.username).
                    value = res.cell(row, value_key)
                    if not value:
                        continue
                    label = res.cell(row, label_key) or ""
                    caps = tuple(row.get("capabilities") or ())
                    options.append(Option(str(value), str(label), caps, dict(row)))
            except Exception:
                # A selector must never take down the form/CLI; an empty list is
                # a survivable "nothing to choose", surfaced by the caller.
                options = []
        self._cache[cache_key] = options
        return options

    def invalidate(self, list_path: str | None = None) -> None:
        if list_path is None:
            self._cache.clear()
        else:
            self._cache.pop(list_path, None)

    @staticmethod
    def capable(options: list[Option], channel: str) -> list[Option]:
        """Keep only numbers capable of a channel (``voice``/``fax``/``sms``/``mms``).

        A message send should not offer a fax-only number. Numbers whose
        capabilities are unknown (empty) are kept, so a sparse API response never
        hides everything.
        """
        wanted = {"message": ("sms", "mms"), "msg": ("sms", "mms"),
                  "fax": ("fax",), "voice": ("voice",), "call": ("voice",)}.get(
            channel, (channel,))
        out = []
        for opt in options:
            if not opt.capabilities or any(c in opt.capabilities for c in wanted):
                out.append(opt)
        return out
