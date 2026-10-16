"""Declarative registry of every SignalWire resource swsh can browse and edit.

The platform exposes 21 REST namespaces. Hand-writing a screen and a command set
per namespace would be 21 places to fix the same bug, so each one is described
here as data and generic machinery renders and edits any of them, in both the
TUI and the CLI.

Two deliberate choices about uncertainty:

**Capabilities are introspected, not assumed.** The ``caps`` string on each
resource records which of list/create/read/update/delete the installed SDK
actually implements, taken from the namespace objects themselves. So the TUI
never offers an edit key for a read-only log, and never hides a create that
exists. (Introspection also corrected the reference docs: ``cxml_applications``
does support create, and ``project.tokens`` has no list at all.)

**Every field gets a real control.** Nobody should have to hand-write a JSON
object to tick a box, so each field declares a kind and the form renders the
matching widget: checkboxes for booleans, checkbox groups for sets like SIP
codecs, selects for enumerations, comma-separated inputs for simple lists. The
sole exception is a field whose value genuinely is a document, such as an SWML
script, which gets a validating editor.

Where a set of allowed values may be incomplete, the field is marked
``open_ended`` so extra values can be typed alongside the checkboxes. Nested
payloads are handled by ``path``, letting a flat form produce a nested body.
``columns_for`` likewise falls back to discovered keys, so a wrong guess about
field names degrades to a useful table rather than a wall of dashes.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from . import spec

# Capability letters, in the order they appear in `caps`.
LIST, CREATE, READ, UPDATE, DELETE = "L", "C", "R", "U", "D"

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


# Columns that name a row to a person. A resource that declares one of these
# can be addressed by it, with no per-resource declaration.
_NAME_LIKE = frozenset({
    "name", "display_name", "friendly_name", "title", "label",
    "number", "short_code", "username", "domain", "uri", "topic", "email",
})


def route_placeholders(operation_id: str, api: str = "") -> tuple[str, ...]:
    """The ids an operation's route needs, from the catalog.

    This is what separates a resource with a screen of its own from one that
    only exists under a parent, and it is read rather than declared: the route
    already knows that a campaign needs a brand and a chunk needs a document.
    ``{AccountSid}`` does not count — the client fills that from the profile.
    """
    if not operation_id:
        return ()
    operation = spec.get(operation_id, api=api or None) or spec.get(operation_id)
    if operation is None:
        return ()
    return tuple(p for p in _PLACEHOLDER.findall(operation.path) if p != "AccountSid")


# Field kinds and the control each one gets.
#
#   text      single-line Input
#   textarea  multi-line TextArea, for prose such as a prompt
#   int       Input, validated as a whole number
#   bool      Checkbox
#   choice    Select, one of `choices`
#   multi     a Checkbox per entry in `choices`, producing a list
#   list      Input of comma-separated values, producing a list of strings
#   code      TextArea holding a document, validated against `language`
#
# `code` is the only kind that asks anyone to type structured markup, and it is
# reserved for fields whose value genuinely is a document: an SWML script, or a
# cXML body. Everything else gets a real control.
KINDS = ("text", "textarea", "int", "bool", "choice", "multi", "list", "code")


@dataclass(frozen=True, slots=True)
class Field:
    """One editable field on a create or update form."""

    name: str
    label: str = ""
    required: bool = False
    kind: str = "text"
    choices: tuple[str, ...] = ()
    help: str = ""
    on_create: bool = True
    on_update: bool = True
    # Dotted destination in the request body, when the API nests this value.
    # `Field("prompt_text", path="prompt.text")` sends {"prompt": {"text": ...}},
    # so the form can stay flat while the payload is shaped correctly.
    path: str | None = None
    # Dotted source when a row *reads back* differently from how it is written.
    # Subscribers are the live example: create takes a flat `email`, but the
    # list response nests it under `subscriber.email`.
    read_path: str | None = None
    # For `multi`: also offer a free-text box for values not in `choices`, so an
    # incomplete list here never blocks a valid request.
    open_ended: bool = False
    # For `code`: the document language, used for highlighting and validation.
    language: str = "json"
    # Show this field only when another field currently holds one of these
    # values, e.g. a phone number's `call_request_url` is meaningless unless
    # the handler is `laml_webhooks`. The form re-evaluates on every change,
    # and a hidden field is never sent.
    show_if: tuple[str, tuple[str, ...]] | None = None
    # Populate a `choice` from live data instead of a fixed list, as
    # (list_path, value_key, label_key). A SIP endpoint's `send_as` has to be
    # one of the numbers you actually own, so typing it freehand is only a way
    # to get it wrong.
    options_from: tuple[str, str, str] | None = None
    # When this `choice` is picked, fill sibling fields from the row behind it,
    # as {field name: dotted row path}. The rows are already in hand from
    # `options_from`, so this costs no extra request. Only a field the row
    # actually carries a value for is filled — a blank never overwrites what
    # somebody typed, and a key the API does not return simply leaves that box
    # to be filled in by hand.
    prefill: tuple[tuple[str, str], ...] = ()
    # Obscure this value as it is typed. The control becomes a masked `Input`
    # rather than a text box, so a password is not left legible on a screen
    # somebody may be sharing — while still showing one mark per keystroke,
    # because a box that shows nothing at all reads as a box that is broken.
    secret: bool = False

    def visible_for(self, values: dict[str, Any]) -> bool:
        if self.show_if is None:
            return True
        other, allowed = self.show_if
        return str(values.get(other, "")) in allowed

    @property
    def title(self) -> str:
        return self.label or self.name.replace("_", " ")

    @property
    def target(self) -> str:
        """Where the value is written in the request body."""
        return self.path or self.name

    @property
    def source(self) -> str:
        """Where the value is read from in a response row."""
        return self.read_path or self.path or self.name


@dataclass(frozen=True, slots=True)
class Route:
    """One channel of a resource's routing: who handles it, and what it points at.

    A phone number answers on two channels, and each names a handler
    (``call_handler``) plus a Fabric resource that handler hands off to
    (``calling_handler_resource_id``). Which *other* fields a handler reads is
    not declared here — the fields already say so with ``show_if``, and saying
    it twice is how the two drift apart.
    """

    channel: str  # what a person calls it: "voice", "messaging"
    handler: str  # the field naming the handler
    pointer: str = ""  # the field holding the Fabric resource id it hands off to


@dataclass(frozen=True, slots=True)
class Extra:
    """A namespace operation beyond plain CRUD, exposed as a keystroke.

    Two shapes share this class. A *drill* is a GET that lists something under
    the selected row (a call flow's versions, a group's memberships) and shows
    the result in place. An *action* is a write: it may need input (``fields``,
    collected on the same form the create/edit paths use), may want a
    confirmation, and reloads the view when it succeeds. Which one an extra is
    follows from the catalog's method for ``spec_op``, so nothing here has to
    say.

    Every non-CRUD operation a resource offers is an ``Extra``. ``rest_ops`` is
    for the five CRUD verbs only; the coverage gate enforces that, because an
    op named in ``rest_ops`` under any other key has no keystroke or verb that
    reaches it and was counted as covered anyway.
    """

    key: str
    label: str
    method: str  # method name on the namespace
    needs_id: bool = True
    confirm: bool = False
    spec_op: str = ""  # spec operation_id this extra implements, for coverage
    # Input the action needs, shown as a form before it runs. A value whose name
    # is a placeholder in the route fills the route (``mfa_request_id``, a
    # room's ``name``); everything else is sent as the request body.
    fields: tuple[Field, ...] = ()
    # Acts on the rows of this drill (named by its label) instead of the parent
    # list: "remove member" makes sense on a membership row, which is what the
    # "memberships" drill shows, not on the group row above it.
    on_drill: str = ""
    # The CLI subcommand name, when the slug of ``label`` is not it. `sw logs
    # events` reads better than `sw logs event-timeline`; and a hand-written
    # command of the same name (the numbers search with its flags) replaces
    # the generated one.
    cli: str = ""

    def form_fields(self, mode: str = "create") -> list[Field]:
        """The same protocol as ``Resource``, so one form serves both."""
        return list(self.fields)

    @property
    def command(self) -> str:
        """The `sw <resource> <command>` name for this extra."""
        return self.cli or re.sub(r"[^a-z0-9]+", "-", self.label.lower()).strip("-")

    @property
    def title(self) -> str:
        return self.label

    @property
    def takes_input(self) -> bool:
        return bool(self.fields)


@dataclass(frozen=True, slots=True)
class Resource:
    """How to list, display, edit and act on one namespace."""

    key: str  # what the user types: `:agents`
    title: str
    namespace: str  # dotted SDK namespace (sdk transport), e.g. "fabric.ai_agents"
    caps: str  # subset of "LCRUD"
    columns: tuple[str, ...] = ()
    group: str = "other"
    id_field: str = "id"
    data_key: str = "data"
    fields: tuple[Field, ...] = field(default_factory=tuple)
    extras: tuple[Extra, ...] = field(default_factory=tuple)
    help: str = ""

    # Which backend serves this resource. "sdk" calls a dotted SDK method;
    # "rest" resolves the route from the spec catalog and issues it directly,
    # for surfaces the SDK cannot call (e911, WhatsApp, …). See client.invoke.
    transport: str = "sdk"
    # Spec API this resource belongs to (e.g. "fabric-api", "relay-rest").
    # Required for rest transport and for the coverage gate.
    api: str = ""
    # rest transport: op-name -> spec operation_id, e.g.
    # {"list": "list_addresses", "assign": "assign_e911_address"}.
    rest_ops: dict[str, str] = field(default_factory=dict)
    # Override the SDK method name for a CRUD op when it is not the default
    # (list/create/get/update/delete), for sdk transport.
    sdk_ops: dict[str, str] = field(default_factory=dict)
    # What the CLI calls a CRUD verb when the generic word would mislead:
    # buying a number is not "creating" it and releasing one is not "deleting"
    # it. {"create": "buy", "delete": "release"}. Unlisted verbs keep the
    # generic name. The TUI keeps its keys; only the command word changes.
    verbs: dict[str, str] = field(default_factory=dict)
    # Handles other than the id that `get` accepts, tried in this order:
    # `sw numbers get +12095550183` and `sw numbers get "Fax Number"` resolve
    # to the same row as the uuid does. Each name is a row field, dotted paths
    # included. Empty means the id is the only way in.
    lookup: tuple[str, ...] = field(default_factory=tuple)
    # Where the list endpoint can do the matching itself: lookup field -> query
    # parameter. Declare one only when it has been verified against a live
    # space, because a filter the API ignores silently returns everything. A
    # field with no entry is matched client-side over the listed page instead.
    list_filters: dict[str, str] = field(default_factory=dict)
    # Channels whose configuration can be followed to what it points at, for
    # `get --full`. Empty means the resource has no routing to expand and the
    # flag is not offered.
    routing: tuple[Route, ...] = field(default_factory=tuple)
    # The resource this one is only ever reached through. A campaign lives
    # under a brand, a SIP credential under a subscriber: every route they have
    # needs a parent id, so their own screen could never fill a table. Naming
    # the parent lets the browser send someone to the drill that does have the
    # rows instead of opening an empty one. It is checked against the routes,
    # not trusted: ``standalone`` derives the same fact from the catalog and
    # ``test_resources`` fails if the two disagree.
    drill_from: str = ""

    @property
    def search_fields(self) -> tuple[str, ...]:
        """What ``list --match`` looks in: the lookup handles, else the columns.

        ``lookup_fields`` is deliberately narrower than this — resolving an
        identifier must not succeed on a ``created_at`` that happens to contain
        the text, while filtering a listing on one is perfectly reasonable.
        """
        return self.lookup_fields or self.columns

    @property
    def lookup_fields(self) -> tuple[str, ...]:
        """Row fields a person may type instead of an id.

        ``lookup`` is the explicit declaration and wins where it exists. Where
        it does not, the name-like columns the resource already declares serve
        instead — because "what is this row called" is not a question that needs
        declaring per resource, and requiring it meant `numbers` was the only
        resource in the registry you could address by name. Everywhere else
        `get`, `update` and `delete` took a uuid and nothing else, and finding
        one meant a `list -m` and a copy-paste.

        Only names, never a date or a status: resolving an identifier has to
        fail rather than match the wrong row, and `created_at` contains "2026"
        for almost everything.
        """
        if self.lookup:
            return self.lookup
        return tuple(c for c in self.columns if c.rsplit(".", 1)[-1] in _NAME_LIKE)

    def verb(self, op: str) -> str:
        """The CLI command name for a CRUD op-name."""
        return self.verbs.get(op, {"read": "get"}.get(op, op))

    # ------------------------------------------------------------ capabilities

    def can(self, op: str) -> bool:
        return op in self.caps

    def sdk_method(self, op: str) -> str:
        """SDK method name for a CRUD op-name (sdk transport)."""
        return self.sdk_ops.get(op, {
            "list": "list", "create": "create", "read": "get",
            "update": "update", "delete": "delete",
        }.get(op, op))

    @property
    def can_list(self) -> bool:
        return LIST in self.caps

    @property
    def can_create(self) -> bool:
        return CREATE in self.caps

    @property
    def can_read(self) -> bool:
        return READ in self.caps

    @property
    def can_update(self) -> bool:
        return UPDATE in self.caps

    @property
    def can_delete(self) -> bool:
        return DELETE in self.caps

    @property
    def is_singleton(self) -> bool:
        """One record rather than a collection.

        `GET /api/relay/rest/sip_profile` carries no `{id}`: the project has
        exactly one, and reading it needs no identifier. A browser that treats
        it as a collection shows an empty table and an edit key that can never
        find a row, when what the API offers is a record sitting right there.
        """
        if self.can_list or not self.can_read:
            return False
        return not route_placeholders(self.rest_ops.get("read", ""), self.api)

    @property
    def standalone(self) -> bool:
        """Whether this resource's own screen can do anything at all.

        True when something can be reached without an id the screen has no way
        to supply: a listing, a singleton's record, a create whose route is a
        bare collection, or an action that collects everything its route needs
        on its own form (an MFA code, a number lookup).

        False for the handful that exist only under a parent. They are not
        broken and they are not hidden — they are drills, reached from the row
        that owns them, and `sw campaigns get <id>` still works from a shell
        where the id can be typed. What they cannot be is a menu entry, because
        that opens a door onto a wall.
        """
        if self.lists_standalone or self.is_singleton:
            return True
        if self.can_create and not route_placeholders(
                self.rest_ops.get("create", ""), self.api):
            return True
        return any(self.serves_itself(e) for e in self.extras)

    @property
    def lists_standalone(self) -> bool:
        """Whether ``list`` can run without an id the screen cannot supply.

        ``can_list`` was enough here once, and it is not: a capability letter
        says the operation exists, not that its route is reachable. `orders`
        lists at ``/registry/beta/campaigns/{id}/orders`` — a real list, on a
        route that needs a campaign nobody has selected — so it claimed a screen
        of its own, got one in the menus and a `sw orders list` in the shell,
        and every invocation of either answered `orders.list needs a resource
        id`. The route already knows; ask it.
        """
        if not self.can_list:
            return False
        return not route_placeholders(self.rest_ops.get("list", ""), self.api)

    def serves_itself(self, extra: Extra) -> bool:
        """Whether an extra can run from the list screen with nothing selected.

        It must not act on a drill's rows, must not need the highlighted row's
        id, and its form must collect every placeholder its route carries —
        which is how `verify code` works while `assigned numbers` does not.
        """
        if extra.on_drill or extra.needs_id:
            return False
        supplied = {f.name for f in extra.fields}
        return all(p in supplied for p in route_placeholders(extra.spec_op, self.api))

    # ------------------------------------------------------------------- paths

    @property
    def list_path(self) -> str:
        return f"{self.namespace}.list"

    @property
    def create_path(self) -> str:
        return f"{self.namespace}.create"

    @property
    def get_path(self) -> str:
        return f"{self.namespace}.get"

    @property
    def update_path(self) -> str:
        return f"{self.namespace}.update"

    @property
    def delete_path(self) -> str:
        return f"{self.namespace}.delete"

    def form_fields(self, mode: str) -> list[Field]:
        """Fields relevant to 'create' or 'update'."""
        if mode == "create":
            return [f for f in self.fields if f.on_create]
        return [f for f in self.fields if f.on_update]


def _f(name: str, **kw: Any) -> Field:
    return Field(name=name, **kw)


# Handler values a phone number can route to, from the SDK's PhoneCallHandler.
# The spec's enum for `call_handler` has 11 values; the dashboard sets two more
# it does not declare (`ai_agent`, `call_flow`), and both have been seen on live
# numbers. The union is what the API actually accepts, so it is what sw offers —
# a short list here is a valid handler that `--set call_handler=` refuses.
# `scripts/audit_fields.py` compares this against the spec.
CALL_HANDLERS = (
    "relay_script", "relay_topic", "relay_context", "relay_application",
    "relay_connector", "relay_sip_endpoint", "relay_verto_endpoint",
    "laml_webhooks", "laml_application", "ai_agent", "call_flow",
    "video_room", "dialogflow",
)

# SIP negotiation values, read from the live dashboard forms rather than
# guessed. The OPUS variants carry rate and packetisation in the value itself,
# and there is no VP9 option despite VP8 and H264 being offered.
CODECS = (
    "OPUS", "OPUS@48000H@20I", "OPUS@24000H@20I", "OPUS@16000H@20I", "OPUS@8000H@20I",
    "G722", "PCMU", "PCMA", "G729", "VP8", "H264",
)
CIPHERS = (
    "AEAD_AES_256_GCM_8",
    "AES_256_CM_HMAC_SHA1_80",
    "AES_CM_128_HMAC_SHA1_80",
    "AES_256_CM_HMAC_SHA1_32",
    "AES_CM_128_HMAC_SHA1_32",
)

# The two SIP resources do not share an encryption vocabulary: an endpoint can
# defer to the project default, a gateway can forbid encryption outright.
SIP_ENDPOINT_ENCRYPTION = ("default", "required", "optional")
SIP_GATEWAY_ENCRYPTION = ("required", "optional", "forbidden")

# Probed live against the conferences route: `xlarge` and `huge` are refused
# with `Size is not included in the list`.
VIDEO_CONFERENCE_SIZES = ("small", "medium", "large")

# E911 sub-unit kinds, from the create-address request schema.
E911_ADDRESS_TYPES = (
    "Apartment", "Basement", "Building", "Department", "Floor", "Office",
    "Penthouse", "Suite", "Trailer", "Unit",
)

# Project auth token scopes, from the live token form.
TOKEN_SCOPES = (
    "calling", "messaging", "video", "fax", "chat", "pubsub", "numbers",
    "storage", "tasking", "datasphere", "management", "fsa",
)

# How a script resource is used, and where its document comes from.
SCRIPT_USED_FOR = ("calling", "messaging")
CXML_CALL_TYPE = ("calling", "messaging", "faxing")
HANDLE_USING = ("script", "external_url")
HTTP_METHODS = ("POST", "GET")

# Sending a one-time code by call and by SMS take the same request.
_MFA_FIELDS = (
    Field("to", required=True, help="E.164 destination."),
    Field("from_", label="from", path="from", kind="choice",
          options_from=("numbers.list", "number", "name"),
          help="Optional; SignalWire uses a verified number if empty."),
    Field("message", help="Spoken or sent before the code. One SMS segment."),
    Field("token_length", label="code length", kind="int", help="4 to 20; default 6."),
    Field("valid_for", label="valid for (seconds)", kind="int", help="Default 3600."),
    Field("max_attempts", kind="int", help="1 to 20; default 3."),
    Field("allow_alphas", label="letters in code", kind="bool"),
)

# The TUI's "new call" form. Not a resource: a call is placed through the
# compat surface (``client.dial``) and then shows up in the live view from the
# voice log, so the only registry involvement is reusing the form machinery.
DIAL = Extra(
    "D", "new call", "dial", needs_id=False,
    fields=(
        Field("from_", label="from", required=True, kind="choice",
              options_from=("numbers.list", "number", "name"),
              help="A voice-capable number you own."),
        Field("to", required=True, help="E.164 number or sip: address."),
        Field("url", label="SWML or cXML URL",
              help="Fetched when the call is answered. Leave empty to use 'say'."),
        Field("say", kind="textarea",
              help="Spoken to whoever answers, then hangs up. Used when no URL is given."),
    ),
)


RESOURCES: tuple[Resource, ...] = (
    # ------------------------------------------------------------------ voice
    Resource(
        key="calls", title="calls", namespace="", caps="", group="voice",
        help="Live calls merged from RELAY, status callbacks and polling.",
    ),
    Resource(
        key="logs", title="voice logs", namespace="logs.voice", caps="LR", group="logs",
        columns=("id", "from", "to", "direction", "status", "duration", "created_at"),
        extras=(Extra("v", "event timeline", "list_events", spec_op="list_voice_log_events",
                      cli="events"),),
        help="Completed calls. Read-only; each has an event timeline.",
    ),
    Resource(
        key="recordings", title="recordings", namespace="recordings", caps="LRD", group="voice",
        columns=("id", "status", "duration_in_seconds", "relay_pstn_leg_id", "created_at"),
    ),
    Resource(
        key="queues", title="queues", namespace="queues", caps="LCRUD", group="voice",
        # The API reads back `friendly_name`/`date_created` for the `name` you send.
        columns=("id", "friendly_name", "current_size", "max_size", "date_created"),
        fields=(
            _f("name", required=True),
            _f("max_size", kind="int", help="Maximum callers held in the queue."),
        ),
        api="relay-rest",
        extras=(
            Extra("m", "members", "list_members", spec_op="list_queue_members"),
            Extra("M", "member", "get_member", spec_op="retrieve_queue_member"),
            Extra("N", "next member", "get_next_member", needs_id=True,
                  spec_op="retrieve_next_queue_member"),
        ),
    ),
    Resource(
        key="conflogs", title="conference logs", namespace="logs.conferences", caps="L",
        group="logs", columns=("id", "name", "status", "duration", "created_at"),
    ),
    # --------------------------------------------------------------- messaging
    Resource(
        key="messages", title="message logs", namespace="logs.messages", caps="LR",
        group="logs",
        columns=("id", "from", "to", "direction", "status", "segments", "created_at"),
    ),
    Resource(
        key="fax", title="fax logs", namespace="logs.fax", caps="LR", group="logs",
        columns=("id", "from", "to", "direction", "status", "created_at"),
    ),
    Resource(
        key="shortcodes", title="short codes", namespace="short_codes", caps="LRU",
        group="messaging", columns=("id", "short_code", "country", "capabilities"),
        fields=(_f("name"),),
    ),
    Resource(
        key="brands", title="10DLC brands", namespace="registry.brands", caps="LCR",
        group="messaging",
        columns=("id", "name", "state", "legal_entity_type", "created_at"),
        fields=(
            _f("name", required=True),
            _f("company_name"),
            _f("legal_entity_type", kind="choice",
               choices=("PRIVATE_PROFIT", "PUBLIC_PROFIT", "NON_PROFIT", "GOVERNMENT")),
            _f("contact_email"), _f("contact_phone"),
            _f("ein"), _f("ein_issuing_country"),
            _f("company_vertical"), _f("company_address"),
            _f("status_callback_url"),
        ),
        extras=(
            Extra("c", "campaigns", "list_campaigns", spec_op="list_campaigns"),
            # Orders hang off a campaign, which hangs off a brand. Reached from
            # the rows of the campaigns drill, which is the only place a
            # campaign id is in hand — the same shape as `remove member` on a
            # number group's memberships.
            Extra("o", "orders", "list_orders", on_drill="campaigns",
                  spec_op="list_orders"),
        ),
        help="Brand registrations; each brand lists its campaigns, and each "
             "campaign its number orders.",
    ),
    # ----------------------------------------------------------------- numbers
    Resource(
        key="numbers", title="phone numbers", namespace="phone_numbers", caps="LCRUD",
        group="numbers", verbs={"create": "buy", "delete": "release"},
        # `call_status_callback_url` was here and is null on almost every
        # number — a per-number status webhook is the exception, not the
        # rule — while being the widest column in the table, which is what
        # squeezed the uuid out. `created_at` earns the space instead.
        columns=("number", "name", "call_handler", "id", "created_at"),
        # Nobody remembers a number's uuid; they remember the number, and they
        # named it. Both filters do a substring match server-side, verified
        # against a live space — see TestVerifiedAgainstLiveProject.
        lookup=("number", "name"),
        list_filters={"number": "filter_number", "name": "filter_name"},
        fields=(
            _f("number", required=True, on_update=False,
               help="E.164. Creating purchases the number."),
            _f("name", on_create=False),
            _f("call_handler", kind="choice", choices=CALL_HANDLERS, on_create=False,
               help="Pick a handler; the field it needs appears below."),
            _f("call_request_url", label="cXML webhook URL", on_create=False,
               show_if=("call_handler", ("laml_webhooks",))),
            _f("call_status_callback_url", on_create=False,
               show_if=("call_handler", ("laml_webhooks",))),
            _f("call_laml_application_id", on_create=False,
               show_if=("call_handler", ("laml_application",))),
            _f("call_relay_script_url", label="SWML webhook URL", on_create=False,
               show_if=("call_handler", ("relay_script",))),
            _f("call_relay_topic", on_create=False,
               show_if=("call_handler", ("relay_topic",))),
            _f("call_relay_topic_status_callback_url", on_create=False,
               show_if=("call_handler", ("relay_topic",))),
            _f("call_relay_application", on_create=False,
               show_if=("call_handler", ("relay_application",))),
            _f("call_relay_context", on_create=False,
               show_if=("call_handler", ("relay_context",))),
            _f("call_relay_context_status_callback_url", on_create=False,
               show_if=("call_handler", ("relay_context",))),
            _f("call_relay_connector_id", on_create=False,
               show_if=("call_handler", ("relay_connector",))),
            _f("call_sip_endpoint_id", on_create=False,
               show_if=("call_handler", ("relay_sip_endpoint",))),
            _f("call_verto_resource", on_create=False,
               show_if=("call_handler", ("relay_verto_endpoint",))),
            _f("call_video_room_id", on_create=False,
               show_if=("call_handler", ("video_room",))),
            _f("call_fallback_url", on_create=False,
               show_if=("call_handler", ("laml_webhooks",))),
            _f("calling_handler_resource_id", label="target resource id",
               on_create=False,
               show_if=("call_handler", ("ai_agent", "call_flow", "video_room")),
               help="The AI agent, call flow or video room to route to."),
            _f("call_dialogflow_agent_id", on_create=False,
               show_if=("call_handler", ("dialogflow",))),
            _f("message_handler", kind="choice", choices=CALL_HANDLERS, on_create=False),
            _f("message_request_url", on_create=False,
               show_if=("message_handler", ("laml_webhooks",))),
            _f("message_fallback_url", on_create=False,
               show_if=("message_handler", ("laml_webhooks",))),
            _f("message_laml_application_id", on_create=False,
               show_if=("message_handler", ("laml_application",))),
            _f("message_relay_context", on_create=False,
               show_if=("message_handler", ("relay_context", "relay_application"))),
            _f("message_relay_topic", on_create=False,
               show_if=("message_handler", ("relay_topic",))),
        ),
        # Two channels, each naming its handler and the Fabric resource that
        # handler hands off to. `get --full` follows these.
        routing=(
            Route("voice", "call_handler", "calling_handler_resource_id"),
            Route("messaging", "message_handler", "messaging_handler_resource_id"),
        ),
        extras=(
            Extra("S", "search available", "search", needs_id=False,
                  spec_op="search_available_phone_numbers", cli="search"),
            # E911 lives on the number it protects; the address CRUD itself is
            # the `addresses` resource.
            Extra("E", "assign E911 address", "assign_e911_address",
                  spec_op="assign_e911_address",
                  fields=(_f("e911_address_id", label="E911 address", required=True,
                             kind="choice", options_from=("addresses.list", "id", "name"),
                             help="A validated E911 address in this project."),)),
            Extra("X", "remove E911 address", "remove_e911_address", confirm=True,
                  spec_op="remove_e911_address"),
        ),
        help="Owned numbers and how each routes. Creating one purchases it.",
    ),
    Resource(
        key="groups", title="number groups", namespace="number_groups", caps="LCRUD",
        group="numbers", columns=("id", "name", "created_at"),
        fields=(_f("name", required=True),),
        api="relay-rest",
        extras=(
            Extra("m", "memberships", "list_memberships",
                  spec_op="list_number_group_memberships"),
            Extra("a", "add member", "add_member",
                  spec_op="create_number_group_membership",
                  fields=(_f("phone_number_id", label="phone number", required=True,
                             kind="choice", options_from=("numbers.list", "id", "number")),)),
            # Membership rows carry their own id, so these act inside the drill.
            Extra("g", "show member", "get_member", on_drill="memberships",
                  spec_op="retrieve_number_group_membership"),
            Extra("r", "remove member", "remove_member", on_drill="memberships",
                  confirm=True, spec_op="delete_number_group_membership"),
        ),
    ),
    Resource(
        key="imported", title="imported numbers", namespace="imported_numbers", caps="C",
        group="numbers", columns=("id", "number", "carrier", "created_at"),
        fields=(_f("number", required=True), _f("carrier")),
        help="Create-only: numbers can be imported but the API offers no list of them.",
    ),
    Resource(
        key="verified", title="verified callers", namespace="verified_callers", caps="LCRUD",
        group="numbers", columns=("id", "number", "verified", "created_at"),
        fields=(_f("number", required=True),),
        extras=(
            Extra("V", "submit verification", "submit_verification",
                  spec_op="validate_verification_code"),
            Extra("A", "redial verification", "redial_verification",
                  spec_op="redial_verification_call"),
        ),
    ),
    Resource(
        key="addresses", title="E911 addresses", namespace="addresses", caps="LCRUD",
        group="numbers",
        columns=("id", "label", "street_number", "street_name", "city", "state",
                 "postal_code", "emergency_enabled"),
        # These were `name` and `display_name`, neither of which exists on the
        # endpoint, so create could not succeed. An emergency address is a
        # postal address and the API requires all nine parts of it.
        fields=(
            _f("label", required=True, help="What to call this address."),
            _f("country", required=True, help="ISO 3166 alpha-2, e.g. US."),
            _f("first_name", required=True),
            _f("last_name", required=True),
            _f("street_number", required=True),
            _f("street_name", required=True),
            _f("city", required=True),
            _f("state", required=True),
            _f("postal_code", required=True),
            _f("address_type", kind="choice", choices=E911_ADDRESS_TYPES,
               help="Sub-unit kind, when the address has one."),
            _f("address_number", help="Sub-unit number, e.g. the suite number."),
            _f("emergency_enabled", kind="bool",
               help="Carrier-validates the address. Regulated and billable."),
            _f("auto_correct_address", kind="bool",
               help="Let the carrier correct the address. Defaults to true."),
        ),
        api="relay-rest",
        rest_ops={"update": "update_address"},  # SDK addresses has no update
        help="Emergency (E911) addresses. Assign one to a number with "
             "`sw numbers assign-e911-address`.",
    ),
    # ------------------------------------------------------------------ fabric
    Resource(
        key="agents", title="AI agents", namespace="fabric.ai_agents", caps="LCRUD",
        group="ai", columns=("id", "name", "display_name", "created_at"),
        fields=(
            _f("name", required=True),
            _f("display_name"),
            _f("prompt_text", label="prompt", kind="textarea", path="prompt.text",
               help="What the agent should do. Sent as prompt.text."),
            _f("post_prompt_text", label="post prompt", kind="textarea",
               path="post_prompt.text",
               help="Optional summary pass after the call ends."),
        ),
        extras=(Extra("a", "addresses", "list_addresses", spec_op="list_ai_agent_addresses"),),
    ),
    Resource(
        key="swml", title="SWML scripts", namespace="fabric.swml_scripts", caps="LCRUD",
        group="fabric", columns=("id", "name", "display_name", "created_at"),
        fields=(
            _f("name", required=True),
            _f("contents", label="SWML document", kind="code", language="json",
               required=True,
               help="SignalWire hosts this and generates the request URL for you."),
            _f("script_type", kind="choice", choices=SCRIPT_USED_FOR),
            _f("status_callback_url", label="webhook URL"),
            _f("status_callback_method", kind="choice", choices=HTTP_METHODS),
        ),
        help="A hosted SWML document. There is no URL field: SignalWire serves "
             "the script and mints the URL. To point at your own endpoint, use "
             "swmlhooks instead.",
        extras=(Extra("a", "addresses", "list_addresses", spec_op="list_swml_script_addresses"),),
    ),
    Resource(
        key="swmlhooks", title="SWML webhooks", namespace="fabric.swml_webhooks", caps="LCRUD",
        group="fabric",
        columns=("id", "display_name", "swml_webhook.primary_request_url", "created_at"),
        fields=(
            _f("name"),
            _f("primary_request_url", label="primary request URL", required=True,
               help="Your endpoint. Must be http or https."),
        ),
        help="Points at an SWML endpoint you host. For a document SignalWire "
             "hosts for you, use swml instead.",
    ),
    Resource(
        key="cxml", title="cXML scripts", namespace="fabric.cxml_scripts", caps="LCRUD",
        group="fabric", columns=("id", "name", "display_name", "created_at"),
        fields=(
            _f("name", required=True),
            _f("contents", label="cXML document", kind="textarea", required=True,
               help="e.g. <Response><Say>Hello</Say></Response>"),
            _f("script_type", kind="choice", choices=CXML_CALL_TYPE),
            _f("status_callback_url", label="webhook URL"),
            _f("status_callback_method", kind="choice", choices=HTTP_METHODS),
        ),
        help="A hosted cXML document; for your own endpoint use cxmlhooks.",
    ),
    Resource(
        key="cxmlhooks", title="cXML webhooks", namespace="fabric.cxml_webhooks", caps="LCRUD",
        group="fabric",
        columns=("id", "display_name", "cxml_webhook.primary_request_url", "created_at"),
        fields=(_f("name", required=True), _f("primary_request_url", required=True)),
    ),
    Resource(
        key="cxmlapps", title="cXML applications", namespace="fabric.cxml_applications",
        caps="LCRUD", group="fabric",
        # A fabric row names the application in `display_name`; `name` is
        # not a key it carries, so the column resolved to nothing and the
        # listing fell back to a bare id and a date.
        columns=("id", "display_name", "created_at"),
        fields=(_f("name", required=True),),
        # The one hybrid resource. `create` exists in the SDK but is not declared
        # in the spec, so the resource stays on the SDK transport for that one op
        # while every other op takes the exact REST route. `client.invoke` routes
        # an op named in rest_ops over REST regardless of transport, which is
        # precisely what that escape valve is for.
        api="fabric-api",
        rest_ops={
            "list": "list_cxml_applications",
            "read": "get_cxml_application",
            "update": "update_cxml_application",
            "delete": "delete_cxml_application",
        },
    ),
    Resource(
        key="flows", title="call flows", namespace="fabric.call_flows", caps="LCRUD",
        group="fabric", columns=("id", "name", "display_name", "created_at"),
        # Probed live: `{"title": "..."}` alone creates a flow. `name` was
        # rejected with `Title is required`, and the audit's other three
        # "required" fields (flow_data, relayml, document_version) are not.
        fields=(_f("title", required=True,
                   help="What the flow is called; also its display name."),),
        extras=(
            Extra("V", "versions", "list_versions", spec_op="list_call_flow_versions"),
            Extra("D", "deploy version", "deploy_version", confirm=True,
                  spec_op="deploy_call_flow_version"),
        ),
    ),
    Resource(
        key="confrooms", title="conference rooms", namespace="fabric.conference_rooms",
        caps="LCRUD", group="fabric",
        columns=("id", "name", "display_name", "created_at"),
        fields=(
            _f("name", required=True), _f("display_name"),
            _f("max_members", kind="int"), _f("record", kind="bool"),
        ),
    ),
    Resource(
        key="subscribers", title="subscribers", namespace="fabric.subscribers", caps="LCRUD",
        group="fabric",
        columns=("id", "display_name", "type", "created_at"),
        fields=(
            _f("email", required=True, read_path="subscriber.email"),
            _f("password", on_update=False),
            _f("first_name", read_path="subscriber.first_name"),
            _f("last_name", read_path="subscriber.last_name"),
            _f("display_name", read_path="subscriber.display_name"),
            _f("job_title", read_path="subscriber.job_title"),
            _f("company_name", read_path="subscriber.company_name"),
            _f("time_zone", read_path="subscriber.time_zone"),
            _f("country", read_path="subscriber.country"),
        ),
        help="List rows nest the person under `subscriber`; create takes them flat.",
        extras=(
            Extra("e", "SIP credentials", "list_sip_endpoints",
                  spec_op="list_subscriber_sip_credentials"),
        ),
    ),
    Resource(
        key="sip", title="SIP endpoints", namespace="fabric.sip_endpoints", caps="LCRUD",
        group="fabric",
        # Fabric nests the endpoint's own fields under `sip_endpoint`.
        columns=("id", "display_name", "sip_endpoint.username", "sip_endpoint.send_as",
                 "created_at"),
        fields=(
            _f("username", label="URI", required=True,
               help="The SIP username, shown as URI in the dashboard."),
            _f("password", required=True, on_update=False),
            _f("send_as", kind="choice",
               options_from=("numbers.list", "number", "name"),
               help="Outbound caller ID on calls to the PSTN. Must be a number "
                    "you own, so the list is your purchased numbers."),
            _f("caller_id",
               help="Caller ID shown on SIP-to-SIP calls. Free text, not a "
                    "purchased number."),
            _f("hold_music_url"),
            _f("encryption", kind="choice", choices=SIP_ENDPOINT_ENCRYPTION),
            _f("codecs", kind="multi", choices=CODECS, open_ended=True),
            _f("ciphers", kind="multi", choices=CIPHERS, open_ended=True),
        ),
    ),
    Resource(
        key="gateways", title="SIP gateways", namespace="fabric.sip_gateways", caps="LCRUD",
        group="fabric", columns=("id", "display_name", "sip_gateway.uri", "created_at"),
        fields=(
            _f("name", required=True),
            _f("uri", label="external URI", required=True),
            # All three are required by the API, verified live: a create with
            # only name and uri comes back 422 `missing_required_parameter` on
            # encryption, and then `missing_sip_configuration` on ciphers and
            # on codecs in turn. Declared optional, the form and the CLI both
            # collected two values and sent a request that could not succeed.
            _f("encryption", kind="choice", choices=SIP_GATEWAY_ENCRYPTION,
               required=True),
            _f("codecs", kind="multi", choices=CODECS, open_ended=True,
               required=True),
            _f("ciphers", kind="multi", choices=CIPHERS, open_ended=True,
               required=True),
        ),
    ),
    Resource(
        key="relayapps", title="RELAY applications", namespace="fabric.relay_applications",
        caps="LCRUD", group="fabric",
        columns=("id", "display_name", "relay_application.topic", "created_at"),
        fields=(
            # Probed live: a create without a name is 422
            # `missing_required_parameter`. It was declared optional.
            _f("name", required=True),
            _f("topic", required=True,
               help="The RELAY topic this application subscribes to."),
            _f("call_status_callback_url", label="webhook URL"),
        ),
    ),
    Resource(
        key="connectors", title="FreeSWITCH connectors",
        namespace="fabric.freeswitch_connectors", caps="LCRUD", group="fabric",
        columns=("id", "display_name", "freeswitch_connector.name", "created_at"),
        fields=(
            _f("name", required=True),
            # Probed live: `Token is required`. Undeclared, so a create from the
            # form or the CLI could not succeed at all.
            _f("token", required=True, secret=True,
               help="Shared secret the FreeSWITCH instance authenticates with."),
        ),
    ),
    Resource(
        key="fabricaddresses", title="fabric addresses", namespace="fabric.addresses", caps="LR",
        group="fabric", columns=("id", "name", "display_name", "type", "channels"),
    ),
    # ------------------------------------------------------------------- video
    Resource(
        key="videorooms", title="video rooms", namespace="video.rooms", caps="LCRUD",
        group="video",
        columns=("id", "name", "display_name", "max_members", "created_at"),
        fields=(
            _f("name", required=True), _f("display_name"),
            # Probed live: a create with `max_participants=7` came back with
            # `max_members: 20` — the default. The value was accepted, ignored
            # and never mentioned again, which is the worst way for a setting
            # to fail.
            _f("max_members", kind="int", label="max participants"),
            _f("quality", kind="choice", choices=("720p", "1080p")),
            _f("record_on_start", kind="bool"),
            _f("join_from"), _f("join_until"), _f("remove_at"),
        ),
        api="video-api",
        extras=(
            Extra("s", "streams", "list_streams", spec_op="list_room_streams"),
            Extra("S", "start stream", "create_stream", spec_op="create_room_stream",
                  fields=(_f("url", label="RTMP(S) URL", required=True,
                             help="A server accepting incoming RTMP/RTMPS."),)),
            Extra("t", "mint room token", "create_token", needs_id=False,
                  spec_op="create_room_token",
                  fields=(
                      # Prefilled from the highlighted room's name.
                      _f("room_name", required=True, read_path="name"),
                      _f("user_name", help="Display name; random if empty."),
                      _f("join_as", kind="choice", choices=("member", "audience")),
                      _f("auto_create_room", kind="bool"),
                  )),
            Extra("n", "find by name", "by_name", needs_id=False,
                  spec_op="get_room_by_name",
                  fields=(_f("name", required=True),)),
        ),
    ),
    Resource(
        key="vsessions", title="room sessions", namespace="video.room_sessions", caps="LR",
        group="video", columns=("id", "room_id", "name", "status", "created_at"),
        extras=(
            Extra("m", "members", "list_members",
                  spec_op="list_room_session_members"),
            Extra("v", "recordings", "list_recordings",
                  spec_op="list_room_session_recordings"),
            Extra("e", "events", "list_events", spec_op="list_room_session_events"),
        ),
        api="video-api",
    ),
    Resource(
        key="vrecordings", title="room recordings", namespace="video.room_recordings",
        caps="LRD", group="video",
        columns=("id", "room_session_id", "status", "duration", "created_at"),
        api="video-api",
        extras=(
            Extra("e", "events", "list_events", spec_op="list_room_recording_events"),
        ),
    ),
    Resource(
        key="vconf", title="video conferences", namespace="video.conferences", caps="LCRUD",
        group="video", columns=("id", "name", "display_name", "size", "created_at"),
        fields=(
            _f("name", required=True),
            # Probed live: `Display Name is required`; it was optional.
            _f("display_name", required=True),
            # `max_participants` was accepted and dropped — a conference row
            # carries no such key at all. Capacity here is a size band.
            _f("size", kind="choice", choices=VIDEO_CONFERENCE_SIZES,
               help="Capacity band. A conference has no numeric participant cap."),
        ),
        api="video-api",
        extras=(
            Extra("s", "streams", "list_streams", spec_op="list_conference_streams"),
            Extra("S", "start stream", "create_stream",
                  spec_op="create_conference_stream",
                  fields=(_f("url", label="RTMP(S) URL", required=True),)),
            Extra("t", "tokens", "list_tokens", spec_op="list_conference_tokens"),
            Extra("g", "show token", "get_token", on_drill="tokens",
                  spec_op="get_conference_token"),
            Extra("r", "reset token", "reset_token", on_drill="tokens", confirm=True,
                  spec_op="reset_conference_token"),
        ),
    ),
    # ------------------------------------------------------------------- other
    Resource(
        key="datasphere", title="Datasphere", namespace="datasphere.documents",
        caps="LCRUD", group="ai",
        columns=("id", "name", "status", "chunks", "created_at"),
        fields=(
            # Probed live: `Url is required`, and it must be http(s).
            _f("url", required=True, help="Source URL to ingest. http(s) only."),
            _f("name"),
            _f("tags", kind="list", help="Comma separated."),
        ),
        extras=(
            Extra("k", "chunks", "list_chunks", spec_op="list_document_chunks"),
        ),
    ),
    Resource(
        key="tokens", title="API tokens", namespace="project.tokens", caps="CUD",
        group="other", columns=("id", "name", "permissions"),
        fields=(
            _f("name", required=True),
            _f("permissions", kind="multi", choices=TOKEN_SCOPES, open_ended=True),
        ),
        help="Create, update and revoke: the API offers no list of project tokens.",
    ),
    Resource(
        key="sipprofile", title="SIP profile", namespace="sip_profile", caps="RU",
        group="other",
        columns=("domain", "domain_identifier", "default_encryption",
                 "default_send_as", "default_outbound_policy"),
        # Read off the live record: the profile carries exactly these seven
        # keys. `username` and `default_caller_id` were declared here and are
        # not among them — neither name exists on this route, so editing either
        # sent a value nowhere and reported success. The real caller id is
        # `default_send_as`.
        #
        # The write side is unverified on purpose: this is one project-wide
        # record, and probing it means changing the SIP defaults of whatever
        # space the probe runs against. Naming the fields correctly already
        # removes the silent drop.
        fields=(
            _f("domain_identifier",
               help="The per-space SIP identifier; `domain` is built from it."),
            _f("default_encryption", kind="choice", choices=SIP_ENDPOINT_ENCRYPTION),
            _f("default_codecs", kind="multi", choices=CODECS, open_ended=True),
            _f("default_ciphers", kind="multi", choices=CIPHERS, open_ended=True),
            _f("default_send_as", label="default caller id"),
            _f("default_outbound_policy"),
        ),
        help="A single project-wide record rather than a collection.",
    ),

    # ------------------------------------------------------------------------
    # Spec-backed resources (transport="rest"): real product surfaces the SDK
    # cannot call. Each closes backlog operations; the coverage gate credits
    # every operation id named in rest_ops. See swsh.client.invoke.
    # ------------------------------------------------------------------------

    # E911 assign/remove are extras on `numbers`: they act on a phone number row,
    # and a standalone resource with nothing to list was a dead menu entry.

    # Native messaging (message-api), distinct from the compat surface.
    Resource(
        key="send", title="send message", namespace="", caps="C", group="messaging",
        transport="rest", api="message-api",
        rest_ops={"create": "create_message", "update": "update_message"},
        fields=(
            # `from` is a keyword, so the form field is `from_`; the body key
            # the API reads is `from`.
            _f("from_", label="from", path="from", required=True, kind="choice",
               options_from=("numbers.list", "number", "name")),
            _f("to", required=True),
            _f("body", kind="textarea"),
            _f("media", kind="list", help="Media URLs, comma separated (MMS)."),
        ),
        help="Send SMS/MMS/WhatsApp via the native message API.",
    ),

    # WhatsApp (message-api).
    Resource(
        key="wanumbers", title="WhatsApp numbers", namespace="", caps="LR",
        group="messaging", transport="rest", api="message-api",
        rest_ops={"list": "list_whatsapp_numbers", "read": "retrieve_whatsapp_number"},
        columns=("id", "phone_number", "display_name"),
        help="WhatsApp senders on this project. Read-only.",
    ),
    Resource(
        key="watemplates", title="WhatsApp templates", namespace="", caps="LCRUD",
        group="messaging", transport="rest", api="message-api",
        rest_ops={
            "list": "list_whatsapp_templates", "create": "create_whatsapp_template",
            "read": "retrieve_whatsapp_template", "update": "update_whatsapp_template",
            "delete": "delete_whatsapp_template",
        },
        columns=("id", "name", "language", "category", "status"),
        fields=(
            _f("name", required=True), _f("language"), _f("category"),
            _f("body_text", kind="textarea", label="body"),
        ),
    ),
    Resource(
        key="wabiz", title="WhatsApp businesses", namespace="", caps="L",
        group="messaging", transport="rest", api="message-api",
        rest_ops={"list": "list_whatsapp_businesses"},
        columns=("id", "name"),
    ),

    # 10DLC campaigns + orders (relay-rest), under Messaging Campaigns.
    Resource(
        key="campaigns", title="10DLC campaigns", namespace="", caps="RU",
        group="messaging", transport="rest", api="relay-rest",
        drill_from="brands",
        columns=("id", "description", "status"),
        # caps is RU: creating a campaign is a 10DLC vetting flow with 29
        # parameters, which belongs in its own command rather than this form.
        fields=(_f("name", required=True),),
        rest_ops={
            "list": "list_campaigns", "create": "create_campaign",
            "read": "retrieve_campaign", "update": "update_campaign",
        },
        extras=(
            Extra("n", "assigned numbers", "list_number_assignments",
                  spec_op="list_number_assignments"),
            Extra("u", "unassign number", "unassign", on_drill="assigned numbers",
                  confirm=True, spec_op="delete_number_assignment"),
        ),
    ),
    Resource(
        key="orders", title="number orders", namespace="", caps="LCR",
        group="messaging", transport="rest", api="relay-rest",
        # Both the listing and the create hang off a campaign
        # (`/registry/beta/campaigns/{id}/orders`), so this is a drill like
        # `campaigns` itself, not a collection with a screen. `sw orders get
        # <order-id>` still works from a shell, where the id can be typed.
        drill_from="campaigns",
        rest_ops={
            "list": "list_orders", "create": "create_order", "read": "retrieve_order",
        },
        columns=("id", "status", "created_at"),
        fields=(
            _f("phone_numbers", kind="list",
               help="E.164 numbers to assign to the campaign."),
            _f("status_callback_url", help="Where order status changes are posted."),
        ),
    ),

    # SIP domain applications (relay-rest).
    Resource(
        key="domains", title="SIP domain apps", namespace="", caps="LCRUD",
        group="numbers", transport="rest", api="relay-rest",
        rest_ops={
            "list": "list_domain_applications", "create": "create_domain_application",
            "read": "retrieve_domain_application", "update": "update_domain_application",
            "delete": "delete_domain_application",
        },
        columns=("id", "name", "domain", "created_at"),
        fields=(
            _f("name", required=True),
            # Probed live: `Identifier is required`. It is the label the SIP
            # domain is built from, and it was not declared at all.
            _f("identifier", required=True,
               help="Subdomain label, e.g. `support` for support.<space>."),
            _f("domain"),
        ),
    ),

    # Phone number lookup + MFA (relay-rest number tools).
    Resource(
        key="lookup", title="number lookup", namespace="", caps="", group="numbers",
        transport="rest", api="relay-rest",
        rest_ops={"read": "lookup_phone_number"},
        # A lookup is a question, not a collection: the number *is* the route
        # (`/lookup/phone_number/{e164_number}`), so the only way to ask it is
        # to type one. `sw lookup get <number>` was the whole surface, which
        # left the browser with a screen that could do nothing at all. The
        # extra puts the same operation behind a form; the CLI skips generating
        # a second command for it because `read` already reaches it.
        extras=(
            Extra("l", "look up a number", "lookup", needs_id=False,
                  spec_op="lookup_phone_number",
                  fields=(_f("e164_number", required=True,
                             help="the number to look up, e.g. +15551234567"),)),
        ),
        help="Carrier/CNAM lookup for an E.164 number.",
    ),
    Resource(
        key="mfa", title="MFA", namespace="", caps="", group="other",
        transport="rest", api="relay-rest",
        extras=(
            Extra("c", "send code by call", "call", needs_id=False,
                  spec_op="request_mfa_call", fields=_MFA_FIELDS),
            Extra("s", "send code by SMS", "sms", needs_id=False,
                  spec_op="request_mfa_sms", fields=_MFA_FIELDS),
            Extra("v", "verify code", "verify", needs_id=False, spec_op="verify_mfa_token",
                  fields=(
                      _f("mfa_request_id", label="request id", required=True,
                         help="The id returned when the code was sent."),
                      _f("token", label="code", required=True),
                  )),
        ),
        help="Send and verify multi-factor codes over call or SMS. "
             "Actions only; nothing to list.",
    ),

    # Fabric SIP addresses + subscriber SIP credentials (fabric).
    Resource(
        key="sipaddr", title="SIP addresses", namespace="", caps="LCRUD",
        group="fabric", transport="rest", api="fabric-api",
        rest_ops={
            "list": "list_sip_addresses", "create": "create_sip_address",
            "read": "get_sip_address", "update": "update_sip_address",
            "delete": "delete_sip_address",
        },
        columns=("id", "name", "user", "created_at"),
        fields=(
            _f("name", required=True,
               help="URL-safe: lowercase letters, numbers and hyphens. Builds the URI."),
            _f("user", help="SIP username callers dial. Defaults to * (any username)."),
            _f("calling_handler_resource_id", label="handles calls with", required=True,
               kind="choice", options_from=("resources.list", "id", "display_name"),
               help="The Fabric resource inbound calls to this address are handed to."),
            _f("context_id", label="domain",
               help="Domain (context) to group the address under. Defaults to the "
                    "project's own."),
            _f("password", on_update=False, help="Write-only. Never returned."),
            _f("encryption", kind="choice", choices=SIP_GATEWAY_ENCRYPTION),
            _f("codecs", kind="multi", choices=CODECS, open_ended=True),
            _f("ciphers", kind="multi", choices=CIPHERS, open_ended=True),
            _f("ip_auth_enabled", kind="bool"),
            _f("ip_auth", label="allowed IPs", kind="list",
               help="IP or CIDR entries, comma separated. Required when IP auth "
                    "is enabled."),
        ),
        help="A SIP URI that rings a Fabric resource: the hop that makes an "
             "agent, a SWML webhook or a room callable from a SIP phone.",
    ),
    Resource(
        key="subcreds", title="subscriber SIP credentials", namespace="", caps="CRUD",
        group="fabric", transport="rest", api="fabric-api",
        drill_from="subscribers",
        rest_ops={
            "create": "create_subscriber_sip_credential",
            "read": "get_subscriber_sip_credential",
            "update": "update_subscriber_sip_credential",
            "delete": "delete_subscriber_sip_credential",
        },
        # Matches the SIP arguments swsh 2.0 exercised against live spaces, and
        # the documented request body agrees.
        fields=(
            _f("username", required=True),
            _f("password", required=True, on_update=False),
            _f("caller_id", help="Friendly caller ID name."),
            _f("send_as", help="Default caller ID number."),
            _f("encryption", kind="choice", choices=SIP_ENDPOINT_ENCRYPTION),
            _f("codecs", kind="multi", choices=CODECS, open_ended=True),
            _f("ciphers", kind="multi", choices=CIPHERS, open_ended=True),
        ),
        help="SIP credentials under a subscriber (drill from Subscribers).",
    ),

    # Datasphere document chunks (datasphere).
    Resource(
        key="chunks", title="Datasphere chunks", namespace="", caps="RD",
        group="ai", transport="rest", api="datasphere-api",
        drill_from="datasphere",
        rest_ops={
            "read": "get_document_chunk", "delete": "delete_document_chunk",
        },
        help="Chunks within a Datasphere document (drill from Datasphere).",
    ),

    # Subprojects (projects-api), under Other. The API calls them
    # projects, but from inside a project the rows are its children.
    Resource(
        key="projects", title="subprojects", namespace="", caps="LCRUD", group="other",
        transport="rest", api="projects-api",
        rest_ops={
            "list": "list_projects", "create": "create_subproject",
            "read": "get_project", "update": "update_project",
            "delete": "delete_subproject",
        },
        columns=("id", "name", "created_at"),
        fields=(_f("name", required=True),),
        extras=(Extra("k", "rotate signing key", "rotate_signing_key",
                      confirm=True, spec_op="rotate_signing_key"),),
    ),

    # Chat & PubSub tokens (chat-api / pubsub-api).
    Resource(
        key="chattoken", title="chat token", namespace="", caps="C", group="other",
        transport="rest", api="chat-api",
        fields=(
            _f("ttl", kind="int", required=True,
               help="Validity in MINUTES, 1 to 43200. Not seconds."),
            _f("channels", kind="code", required=True,
               help='Per-channel permissions, e.g. {"support": {"read": true}}.'),
            _f("member_id", help="Identifies the member this token acts as."),
            _f("state", kind="code", help="Arbitrary state carried on the member."),
        ),
        rest_ops={"create": "create_chat_token"},
    ),
    Resource(
        key="pubsubtoken", title="pubsub token", namespace="", caps="C", group="other",
        transport="rest", api="pubsub-api",
        # Same shape as the chat token; the two services share the token model.
        fields=(
            _f("ttl", kind="int", required=True,
               help="Validity in MINUTES, 1 to 43200. Not seconds."),
            _f("channels", kind="code", required=True,
               help='Per-channel permissions, e.g. {"alerts": {"read": true}}.'),
            _f("member_id", help="Identifies the member this token acts as."),
            _f("state", kind="code", help="Arbitrary state carried on the member."),
        ),
        rest_ops={"create": "create_token"},
    ),

    # Generic fabric resource operations + routing assignment (fabric-api).
    Resource(
        key="resources", title="fabric resources", namespace="", caps="LRD",
        group="fabric", transport="rest", api="fabric-api",
        rest_ops={
            "list": "list_resources", "read": "get_resource", "delete": "delete_resource",
        },
        columns=("id", "type", "display_name", "created_at"),
        extras=(
            Extra("a", "addresses", "addresses", spec_op="list_resource_addresses"),
            Extra("d", "assign to SIP domain app", "assign_domain",
                  spec_op="assign_resource_domain_application",
                  fields=(_f("domain_application_id", label="SIP domain app", required=True,
                             kind="choice", options_from=("domains.list", "id", "name")),)),
            Extra("p", "assign to phone route", "assign_route",
                  spec_op="assign_resource_phone_route",
                  fields=(
                      _f("phone_route_id", label="phone route id", required=True,
                         help="The fabric phone route (a number's fabric id)."),
                      _f("handler", required=True, kind="choice",
                         choices=("calling", "messaging")),
                  )),
            Extra("s", "assign to SIP endpoint", "assign_sip",
                  spec_op="assign_resource_to_sip_credential",
                  fields=(_f("sip_endpoint_id", label="SIP endpoint", required=True,
                             kind="choice",
                             options_from=("sip.list", "id", "sip_endpoint.username")),)),
        ),
        help="Every fabric resource, and the routing-assignment actions.",
    ),

    # Subscriber & guest/embed tokens (fabric-api).
    Resource(
        key="subtokens", title="subscriber tokens", namespace="", caps="C",
        group="fabric", transport="rest", api="fabric-api",
        # `create` mints a plain subscriber token, which is what `sw subtokens
        # create` and the TUI's `n` reach. The other token kinds take
        # different input, so each is an action with its own form.
        rest_ops={"create": "create_subscriber_token"},
        extras=(
            Extra("g", "mint guest token", "guest", needs_id=False,
                  spec_op="create_subscriber_guest_token",
                  fields=(
                      _f("allowed_addresses", required=True, kind="list",
                         help="Up to 10 fabric address ids, comma separated."),
                      _f("expire_at", kind="int", help="Unix timestamp; default two hours."),
                  )),
            Extra("i", "mint invite token", "invite", needs_id=False,
                  spec_op="create_subscriber_invite_token",
                  fields=(
                      _f("address_id", label="subscriber address id", required=True),
                      _f("expires_at", kind="int", help="Unix timestamp; default two hours."),
                  )),
            Extra("r", "refresh token", "refresh", needs_id=False,
                  spec_op="refresh_subscriber_token",
                  fields=(_f("refresh_token", required=True),)),
            Extra("e", "mint embed token", "embed", needs_id=False,
                  spec_op="create_guest_embed_token",
                  fields=(_f("token", label="click-to-call token", required=True),)),
        ),
        fields=(
            _f("reference", required=True,
               help="Identifies the subscriber this token is for."),
            _f("expire_at", kind="int", help="Unix timestamp the token expires at."),
            _f("application_id"),
            _f("password"),
            _f("fingerprint", help="Binds the token to one device."),
            _f("scope", kind="choice", choices=("sat:refresh",),
               help="Only a refresh-capable token needs a scope."),
            _f("first_name"),
            _f("last_name"),
            _f("display_name"),
            _f("job_title"),
            _f("time_zone"),
            _f("country"),
            _f("region", kind="choice", choices=("us-central",)),
            _f("company_name"),
        ),
        help="Mint subscriber, guest, invite, refresh and embed tokens.",
    ),

    # Video streams + logs (video-api) — surfaces the SDK does not fully wire.
    Resource(
        key="vstreams", title="video streams", namespace="", caps="RUD",
        group="video", transport="rest", api="video-api",
        drill_from="videorooms",
        rest_ops={
            "read": "get_stream", "update": "update_stream", "delete": "delete_stream",
        },
        columns=("id", "status", "url"),
        fields=(_f("url", required=True, help="RTMP destination for the stream."),),
    ),
    Resource(
        key="vlogs", title="video logs", namespace="", caps="LR", group="logs",
        transport="rest", api="video-api",
        rest_ops={"list": "list_logs", "read": "get_log"},
        columns=("id", "type", "created_at"),
    ),
)

def _with_extra(resource: Resource, extra: Extra) -> Resource:
    import dataclasses
    if any(e.key == extra.key for e in resource.extras):
        return resource
    return dataclasses.replace(resource, extras=(*resource.extras, extra))


# Uniformly attach the per-type "addresses" drill (GET .../{id}/addresses) to the
# fabric resources that have one, so those list-addresses operations are covered
# without hand-editing each resource. The SDK exposes them as `list_addresses`.
_ADDRESS_DRILLS = {
    "flows": "list_call_flow_addresses",
    "confrooms": "list_conference_room_addresses",
    "cxmlapps": "list_cxml_application_addresses",
    "cxml": "list_cxml_script_addresses",
    "cxmlhooks": "list_cxml_webhook_addresses",
    "connectors": "list_freeswitch_connector_addresses",
    "relayapps": "list_relay_application_addresses",
    "gateways": "list_sip_gateway_addresses",
    "subscribers": "list_subscriber_addresses",
    "swmlhooks": "list_swml_webhook_addresses",
    "sip": "list_sip_credential_addresses",
}

# Detail/action drills that map an extra to a specific spec operation.
_DETAIL_DRILLS = {
    "messages": Extra("g", "log detail", "get", spec_op="get_message_log"),
    "logs": Extra("g", "log detail", "get", spec_op="get_voice_log"),
    "datasphere": Extra("f", "search", "search", needs_id=False, spec_op="search_documents"),
}

RESOURCES = tuple(
    (lambda r: (
        _with_extra(r, Extra("a", "addresses", "list_addresses",
                             spec_op=_ADDRESS_DRILLS[r.key]))
        if r.key in _ADDRESS_DRILLS else r
    ))(r)
    for r in RESOURCES
)
RESOURCES = tuple(
    _with_extra(r, _DETAIL_DRILLS[r.key]) if r.key in _DETAIL_DRILLS else r
    for r in RESOURCES
)

# ------------------------------------------------------- transport migration
#
# Every resource below moves from the SDK to the spec-driven REST transport.
# The reasons, in order of weight:
#
# * One code path. A resource's routes come from `spec_catalog.json` whether it
#   is a plain CRUD namespace or a surface the SDK never wrapped, so there is a
#   single thing to reason about and a single thing to test.
# * No SDK version coupling. `signalwire-sdk` 3.3.0.dev drops the `compat.*`
#   namespace and ships *fewer* callable methods than 3.0.2. Pinning resource
#   coverage to SDK method presence means a stable 3.1 can silently remove
#   commands. After this, the SDK is reachable only from the RELAY tap in
#   `events/relay_source.py`, which already degrades gracefully on its own.
# * Capabilities become derivable. `caps` can be checked against the spec rather
#   than against whatever happens to be installed.
#
# `caps` letters are deliberately left as they are: they were introspected off a
# live SDK and match what the spec offers. `test_resources.py` now checks them
# against the spec instead of the SDK.
#
# Not migrated, with reasons:
#   cxmlapps  create — the SDK implements it, the spec does not declare it.
#                      Introspection caught this originally (see the module
#                      docstring). Left on the SDK so the capability survives;
#                      revisit when the spec catches up.
#   calls     a live view, not a namespace. No transport.
#   lookup / mfa / resources / and the other already-rest resources are
#                      untouched; they were spec-driven from the start.
_REST_MIGRATION: dict[str, tuple[str, dict[str, str]]] = {
    "addresses": ("relay-rest", {"list": "list_addresses", "create": "create_address",
                                 "read": "get_address", "update": "update_address",
                                 "delete": "delete_address"}),
    "agents": ("fabric-api", {"list": "list_ai_agents", "create": "create_ai_agent",
                              "read": "get_ai_agent", "update": "update_ai_agent",
                              "delete": "delete_ai_agent"}),
    "brands": ("relay-rest", {"list": "list_brands", "create": "create_brand",
                              "read": "retrieve_brand"}),
    "conflogs": ("logs-api", {"list": "list_conferences"}),
    "connectors": ("fabric-api", {"list": "list_freeswitch_connectors",
                                  "create": "create_freeswitch_connector",
                                  "read": "get_freeswitch_connector",
                                  "update": "update_freeswitch_connector",
                                  "delete": "delete_freeswitch_connector"}),
    "cxml": ("fabric-api", {"list": "list_cxml_scripts", "create": "create_cxml_script",
                            "read": "get_cxml_script", "update": "update_cxml_script",
                            "delete": "delete_cxml_script"}),
    "cxmlhooks": ("fabric-api", {"list": "list_cxml_webhooks",
                                 "create": "create_cxml_webhook",
                                 "read": "get_cxml_webhook",
                                 "update": "update_cxml_webhook",
                                 "delete": "delete_cxml_webhook"}),
    "datasphere": ("datasphere-api", {"list": "list_documents", "create": "create_document",
                                "read": "get_document", "update": "update_document",
                                "delete": "delete_document"}),
    # The `fax` resource is fax *logs*. Sending a fax is a compatibility-api
    # operation and is currently excluded; `sw api send_fax` reaches it.
    "fax": ("fax-api", {"list": "list_fax_logs", "read": "get_fax_log"}),
    "flows": ("fabric-api", {"list": "list_call_flows", "create": "create_call_flow",
                             "read": "get_call_flow", "update": "update_call_flow",
                             "delete": "delete_call_flow"}),
    # `/api/fabric/addresses` is the project-wide address list; the per-resource
    # drills live on each resource as the "addresses" extra.
    "fabricaddresses": ("fabric-api", {"list": "list_resource_addresses_client",
                               "read": "get_resource_address_client"}),
    "gateways": ("fabric-api", {"list": "list_sip_gateways", "create": "create_sip_gateway",
                                "read": "get_sip_gateway", "update": "update_sip_gateway",
                                "delete": "delete_sip_gateway"}),
    "groups": ("relay-rest", {"list": "list_number_groups", "create": "create_number_group",
                              "read": "retrieve_number_group",
                              "update": "update_number_group",
                              "delete": "delete_number_group"}),
    # The spec spells this collection imported_phone_numbers, not imported_numbers.
    "imported": ("relay-rest", {"create": "create_imported_phone_number"}),
    "logs": ("voice-api", {"list": "list_voice_logs", "read": "get_voice_log"}),
    "messages": ("message-api", {"list": "list_message_logs", "read": "get_message_log"}),
    # Purchase and release, not create and delete.
    "numbers": ("relay-rest", {"list": "list_phone_numbers", "create": "purchase_phone_number",
                               "read": "retrieve_phone_number",
                               "update": "update_phone_number",
                               "delete": "release_phone_number"}),
    "queues": ("relay-rest", {"list": "list_queues", "create": "create_queue",
                              "read": "get_queue", "update": "update_queue",
                              "delete": "delete_queue"}),
    "recordings": ("relay-rest", {"list": "list_call_recordings",
                                  "read": "get_call_recording",
                                  "delete": "delete_call_recording"}),
    "relayapps": ("fabric-api", {"list": "list_relay_applications",
                                 "create": "create_relay_application",
                                 "read": "get_relay_application",
                                 "update": "update_relay_application",
                                 "delete": "delete_relay_application"}),
    "confrooms": ("fabric-api", {"list": "list_conference_rooms",
                             "create": "create_conference_room",
                             "read": "get_conference_room",
                             "update": "update_conference_room",
                             "delete": "delete_conference_room"}),
    "shortcodes": ("relay-rest", {"list": "list_short_codes",
                                  "read": "retrieve_short_code",
                                  "update": "update_short_code"}),
    # Fabric SIP endpoints. The relay-rest /endpoints/sip surface is excluded as
    # superseded; the sub-resource variant lives on `subcreds`.
    "sip": ("fabric-api", {"list": "list_sip_credentials", "create": "create_sip_credential",
                           "read": "get_sip_credential", "update": "update_sip_credential",
                           "delete": "delete_sip_credential"}),
    "sipprofile": ("relay-rest", {"read": "retrieve_sip_profile",
                                  "update": "update_sip_profile"}),
    "subscribers": ("fabric-api", {"list": "list_subscribers", "create": "create_subscriber",
                                   "read": "get_subscriber", "update": "update_subscriber",
                                   "delete": "delete_subscriber"}),
    "swml": ("fabric-api", {"list": "list_swml_scripts", "create": "create_swml_script",
                            "read": "get_swml_script", "update": "update_swml_script",
                            "delete": "delete_swml_script"}),
    "swmlhooks": ("fabric-api", {"list": "list_swml_webhooks",
                                 "create": "create_swml_webhook",
                                 "read": "get_swml_webhook",
                                 "update": "update_swml_webhook",
                                 "delete": "delete_swml_webhook"}),
    "tokens": ("project-api", {"create": "create_token", "update": "update_token",
                               "delete": "delete_token"}),
    "vconf": ("video-api", {"list": "list_video_conferences",
                            "create": "create_video_conference",
                            "read": "get_video_conference",
                            "update": "update_video_conference",
                            "delete": "delete_video_conference"}),
    "verified": ("relay-rest", {"list": "list_verified_caller_ids",
                                "create": "create_verified_caller_id",
                                "read": "retrieve_verified_caller_id",
                                "update": "update_verified_caller_id",
                                "delete": "delete_verified_caller_id"}),
    "vrecordings": ("video-api", {"list": "list_room_recordings",
                                  "read": "get_room_recording",
                                  "delete": "delete_room_recording"}),
    "videorooms": ("video-api", {"list": "list_rooms", "create": "create_room",
                             "read": "get_room", "update": "update_room",
                             "delete": "delete_room"}),
    "vsessions": ("video-api", {"list": "list_room_sessions", "read": "get_room_session"}),
}


def _to_rest(resource: Resource) -> Resource:
    """Move one resource onto the spec-driven REST transport."""
    import dataclasses

    api, ops = _REST_MIGRATION[resource.key]
    # Merge rather than replace, so a route a resource names itself survives
    # the migration table's defaults. Non-CRUD operations are not routes here
    # at all: they are ``Extra``s, resolved through ``spec_op``.
    merged = {**ops, **resource.rest_ops}
    return dataclasses.replace(resource, transport="rest", api=api, rest_ops=merged)


RESOURCES = tuple(
    _to_rest(r) if r.key in _REST_MIGRATION else r for r in RESOURCES
)


BY_KEY: dict[str, Resource] = {r.key: r for r in RESOURCES}

# Menu-bar order. Keys stay stable (they appear in ``sw docs --list`` and in
# every ``group=`` above); the labels people see come from GROUP_TITLES.
#
# Numbers leads because a phone number is what a project starts with and what
# most visits are about; Voice, Messaging and AI Agents are the channels it
# routes to. The rest follow in decreasing frequency. The live-calls view is not
# a group and sits at the far end of the bar (``tui/app.py``), beside the meter
# that counts them.
GROUPS: tuple[str, ...] = (
    "numbers", "voice", "messaging", "ai", "fabric", "video", "logs", "other",
)

GROUP_TITLES: dict[str, str] = {
    "voice": "Voice",
    "messaging": "Messaging",
    "numbers": "Numbers",
    "ai": "AI Agents",
    # "fabric" is the platform's name for the resource tree; in the dashboard,
    # and to the people using it, these are simply Resources.
    "fabric": "Resources",
    "video": "Video",
    "logs": "Logs",
    "other": "Other",
}

# Where the registry's order is not the order a menu should read in. SWML is
# the current scripting surface and leads; cXML is the compatibility surface
# and sits at the bottom. Keys not listed follow, in registry order.
MENU_ORDER: dict[str, tuple[str, ...]] = {
    "fabric": (
        "swml", "swmlhooks", "flows", "sip", "gateways", "sipaddr", "subscribers",
        "subcreds", "subtokens", "confrooms", "relayapps", "connectors", "resources",
        "fabricaddresses", "cxml", "cxmlhooks", "cxmlapps",
    ),
    "logs": ("logs", "conflogs", "messages", "fax", "vlogs"),
    "ai": ("agents", "datasphere", "chunks"),
}


def group_title(group: str) -> str:
    return GROUP_TITLES.get(group, group.title())


# Keys that were renamed after people had typed them. The old spelling keeps
# resolving so scripts and muscle memory survive.
# From the 2026-09-09 test-plan pass: "docs" read as `sw docs`, "vrooms" and
# "rooms" read as the same thing, and nobody would guess "fabres"/"fabaddr".
KEY_ALIASES: dict[str, str] = {
    "docs": "datasphere",
    "vrooms": "videorooms",
    "rooms": "confrooms",
    "fabres": "resources",
    "fabaddr": "fabricaddresses",
}


def get(key: str) -> Resource | None:
    """Look up by exact key, then an old name, then unique prefix, the way k9s
    resolves names."""
    key = key.strip()
    if key in BY_KEY:
        return BY_KEY[key]
    if key in KEY_ALIASES:
        return BY_KEY[KEY_ALIASES[key]]
    hits = [r for r in RESOURCES if r.key.startswith(key)]
    if len(hits) == 1:
        return hits[0]
    titled = [r for r in RESOURCES if r.title.startswith(key)]
    return titled[0] if len(titled) == 1 else None


def in_group(group: str) -> list[Resource]:
    """Resources of a group, in the order a menu should list them."""
    order = MENU_ORDER.get(group, ())
    rank = {key: i for i, key in enumerate(order)}
    members = [r for r in RESOURCES if r.group == group]
    return sorted(members, key=lambda r: (rank.get(r.key, len(order)), members.index(r)))


def unwrap(payload: Any, data_key: str = "data") -> list[dict[str, Any]]:
    """Pull the row list out of whatever envelope the namespace uses.

    The surfaces disagree: Fabric wraps in ``data``, some RELAY-REST endpoints
    return a bare list, and LaML uses a plural resource name. Each is tried in
    turn rather than assumed.
    """
    if payload is None:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []

    for candidate in (data_key, "data", "items", "results"):
        value = payload.get(candidate)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]

    lists = [v for v in payload.values() if isinstance(v, list)]
    if len(lists) == 1:
        return [row for row in lists[0] if isinstance(row, dict)]

    return [payload] if payload else []


def cell(row: dict[str, Any], key: str) -> Any:
    """Read one column from a row, following dots into nested objects.

    Fabric list rows carry the type-specific fields one level down
    (``{"display_name": ..., "sip_endpoint": {"username": ...}}``), so a column
    named ``sip_endpoint.username`` reaches them. A missing segment yields
    None, which renders as ``-`` like any other absent value.
    """
    if "." not in key:
        return row.get(key)
    cursor: Any = row
    for part in key.split("."):
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(part)
    return cursor


def has_key(row: dict[str, Any], key: str) -> bool:
    """Whether ``key`` (dotted paths included) exists in ``row`` at all.

    Distinct from ``cell(row, key) is not None``: a key that is present with a
    null value is a real column with an empty cell, while a key the API never
    sends is a wrong guess. Column choice needs the former to survive.
    """
    cursor: Any = row
    parts = key.split(".")
    for part in parts[:-1]:
        if not isinstance(cursor, dict):
            return False
        cursor = cursor.get(part)
    return isinstance(cursor, dict) and parts[-1] in cursor


# An identifier is an id when it has an id's shape: a uuid, or a compatibility
# SID (two letters then 32 hex). Anything else typed in an id's place is a
# handle — a phone number, a name — and gets resolved through `lookup`. Shape is
# checked rather than tried-and-404'd because the handle is the *common* case
# for a number, and paying a round trip to learn that is a tax on every call.
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
                      r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_SID_RE = re.compile(r"^[A-Za-z]{2}[0-9a-fA-F]{32}$")


def looks_like_id(value: str) -> bool:
    """Whether a typed identifier is an id rather than a human handle."""
    return bool(_UUID_RE.match(value) or _SID_RE.match(value))


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def row_matches(row: dict[str, Any], query: str, fields: Sequence[str]) -> bool:
    """Whether ``query`` appears in any of ``fields`` on ``row``.

    Substring, case-insensitive, and digit-insensitive as well: a number typed
    as ``(209) 555-0183`` or ``209-555-0183`` has to find the ``+12095550183``
    the API stores, and nobody types the ``+1``.
    """
    needle = query.casefold()
    digits = _digits(query)
    for name in fields:
        value = cell(row, name)
        if value is None:
            continue
        text = str(value)
        if needle in text.casefold():
            return True
        # Two digits is not a phone number, it is a substring of every id.
        if len(digits) >= 3 and digits in _digits(text):
            return True
    return False


def row_matches_exactly(row: dict[str, Any], query: str, fields: Sequence[str]) -> bool:
    """Whether ``query`` *is* one of ``fields`` on ``row``, by the same laxity.

    An exact hit beats every substring hit, so ``get`` on a name that is also a
    prefix of another name resolves instead of reporting an ambiguity.
    """
    needle = query.casefold()
    digits = _digits(query)
    for name in fields:
        value = cell(row, name)
        if value is None:
            continue
        text = str(value)
        if needle == text.casefold():
            return True
        # `2095550183` is exactly the number `+12095550183`, to the person who
        # typed it. Seven digits is a local number and a safe floor for
        # treating a suffix as the same number rather than a coincidence.
        other = _digits(text)
        if len(digits) >= 7 and other and (digits == other or other.endswith(digits)):
            return True
    return False


_IDENTIFIERS = ("id", "sid")


def columns_for(resource: Resource, rows: Sequence[dict[str, Any]],
                limit: int = 7) -> list[str]:
    """Choose columns: preferred fields that exist, otherwise discovered ones.

    A declared column counts as present when any row carries the key, dotted
    paths included, whatever its value. Presence is judged on the key rather
    than on a non-null value so that the column set does not depend on which
    rows happen to be on the page: ``sw numbers list -n 1`` must draw the same
    columns as ``sw numbers list``, even when that one row has no name yet. If
    the only declared columns that matched are identifiers, the discovered
    scalar fields are appended: a table of bare ids is what the test-plan pass
    called "useless", and it is what a stale guess produced.
    """
    if not rows:
        return list(resource.columns[:limit]) or ["id"]

    chosen = [c for c in resource.columns if any(has_key(row, c) for row in rows)]

    scalar = [k for k, v in rows[0].items() if isinstance(v, (str, int, float, bool, type(None)))]
    discovered = sorted(scalar, key=lambda k: (k not in ("id", "sid", "name"), k))

    if chosen and any(c not in _IDENTIFIERS for c in chosen):
        return chosen[:limit]
    if chosen:
        extra = [k for k in discovered if k not in chosen]
        return (chosen + extra)[:limit]
    return discovered[:limit] or list(rows[0])[:limit]


def coerce(field_def: Field, raw: Any) -> Any:
    """Turn a control's value into the type the API expects.

    Empty means "leave unset" rather than "send empty string", so a partial edit
    never blanks a field the user did not touch.
    """
    if field_def.kind in ("multi", "list"):
        return _coerce_list(field_def, raw)

    if field_def.kind == "bool":
        # A checkbox is always definite: unticked means False, not unset.
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "y", "on")

    text = ("" if raw is None else str(raw)).strip()
    if text == "":
        return None

    if field_def.kind == "int":
        try:
            return int(text)
        except ValueError as exc:
            raise ValueError(f"{field_def.title} must be a whole number") from exc

    if field_def.kind == "code":
        return _coerce_code(field_def, text)

    # A closed choice is checked here, not by the API: `--set call_handler=bogus`
    # should fail before a request is made, the way the TUI's select never
    # offers the value at all. `options_from` lists come from live data and
    # `open_ended` ones are deliberately incomplete, so neither is checked.
    if (field_def.kind == "choice" and field_def.choices and not field_def.open_ended
            and not field_def.options_from and text not in field_def.choices):
        raise ValueError(
            f"{field_def.title} must be one of: {', '.join(field_def.choices)}"
        )

    return text


def _coerce_list(field_def: Field, raw: Any) -> list[str] | None:
    """Normalise a checkbox group or comma-separated input to a list."""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple, set)):
        items = [str(v).strip() for v in raw if str(v).strip()]
    else:
        items = [part.strip() for part in str(raw).replace("\n", ",").split(",")]
        items = [part for part in items if part]
    # An empty selection is "unset" so an untouched edit does not clear the
    # field. Clearing is done deliberately through the API, not by omission.
    return items or None


def _coerce_code(field_def: Field, text: str) -> Any:
    """Validate a document field and return it in the shape the API wants.

    JSON documents are parsed so the request carries a real object rather than a
    string, and so a syntax error is caught here with a line number instead of
    coming back as an opaque 4xx.
    """
    if field_def.language != "json":
        return text  # cXML and friends travel as text
    import json

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{field_def.title} is not valid JSON: {exc.msg} on line {exc.lineno}"
        ) from exc


def _assign(body: dict[str, Any], dotted: str, value: Any) -> None:
    """Set a possibly nested key, creating intermediate objects."""
    parts = dotted.split(".")
    target = body
    for part in parts[:-1]:
        existing = target.get(part)
        if not isinstance(existing, dict):
            existing = {}
            target[part] = existing
        target = existing
    target[parts[-1]] = value


def build_body(resource: Resource | Extra, mode: str,
               values: dict[str, Any]) -> dict[str, Any]:
    """Assemble a request body from form values, validating as it goes."""
    body: dict[str, Any] = {}
    missing: list[str] = []
    problems: list[str] = []

    for field_def in resource.form_fields(mode):
        if field_def.name not in values:
            continue
        try:
            value = coerce(field_def, values[field_def.name])
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if value is None:
            if field_def.required and mode == "create":
                missing.append(field_def.title)
            continue
        _assign(body, field_def.target, value)

    if problems:
        raise ValueError("; ".join(problems))
    if missing:
        raise ValueError(f"required: {', '.join(missing)}")
    return body


def unflatten(resource: Resource | Extra, row: dict[str, Any], mode: str) -> dict[str, Any]:
    """Read a row back into flat form values, following nested field paths.

    The inverse of ``build_body``, so editing an AI agent shows the existing
    prompt text in the prompt box rather than an empty field.

    Fabric list rows wrap the type's own fields one level down
    (``{"display_name": ..., "swml_script": {"contents": ...}}``) while the
    form declares them at the top level, because that is where the request
    body wants them. When the declared path finds nothing, the value is taken
    from the single nested object that carries it, so the edit form opens
    with what the detail panel already shows.
    """
    flat: dict[str, Any] = {}
    nested = [v for v in row.values() if isinstance(v, dict)]
    for field_def in resource.form_fields(mode):
        value = cell(row, field_def.source)
        if value is None:
            found = [cell(sub, field_def.source) for sub in nested]
            found = [v for v in found if v is not None]
            if len(found) == 1:
                value = found[0]
        if value is not None:
            flat[field_def.name] = value
    return flat
