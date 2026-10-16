"""Coverage gate: does swsh cover the whole API surface?

Every spec operation (``swsh.spec``) must fall into exactly one bucket:

* **covered** — a registry resource names it in ``rest_ops`` or an extra's
  ``spec_op``, so coverage is exactly what the CLI will actually call
* **excluded** — we will never build it: the Twilio-compat surface (reachable
  through `sw api` instead), deprecated dialogflow, and the imperative calling-api command
  channel (surfaced as live call control, not a browsable resource)
* **not-yet** — everything else: the honest build backlog, each entry declared
  in ``BACKLOG`` with a reason

The gate test asserts these three partition the surface exactly, and a ratchet
asserts ``covered`` only ever grows. Building a screen moves its operations from
not-yet to covered and the ratchet is raised — that is what makes "complete
dashboard in a terminal" a checked invariant instead of a claim.
"""

from __future__ import annotations

from . import resources as res
from . import spec

# Ratchet note: RESOURCE_SPEC used to live here — a second map from resource key
# to spec interface route, used to grant CRUD coverage by matching an operation's
# interface and verb name. It is gone. Every REST resource now names an explicit
# spec operation id for each capability it claims (enforced by
# test_resources.py::TestRestTransportIsComplete), so the registry is the single
# source of what is covered, and coverage cannot disagree with what the CLI will
# actually call.

# Ratchet: coverage may only grow. Raise this as steps land.
MIN_COVERED = 241


# The verbs a person can reach: `sw <resource> list|get|create|update|delete`
# and the TUI's
# list, n, e and d. A route under any other key in ``rest_ops`` has no way in.
CRUD_OPS = ("list", "create", "read", "update", "delete")


def reachable_ops(resource: res.Resource) -> list[str]:
    """The spec operation ids a resource actually exposes.

    A CRUD verb in ``rest_ops`` is reached by the generic CLI verbs and the TUI
    keys; an ``Extra`` is reached by `x` in the TUI. Nothing else is, so
    nothing else is listed.
    """
    op_ids = [resource.rest_ops[op] for op in CRUD_OPS if op in resource.rest_ops]
    op_ids += [e.spec_op for e in resource.extras if e.spec_op]
    return op_ids


def covered_keys() -> set[str]:
    """Spec keys a registry resource implements *and a person can reach*.

    Derived from ``reachable_ops`` only. "Covered" used to mean "named
    somewhere in ``rest_ops``", which let 28 operations count while no verb
    or keystroke led to them (E911 assign, MFA, group memberships, video
    tokens). Now an operation counts only through a CRUD verb or an ``Extra``;
    ``test_coverage`` also fails on any ``rest_ops`` key outside ``CRUD_OPS`` so
    the loophole cannot reopen.
    """
    covered: set[str] = set()
    for resource in res.RESOURCES:
        api = resource.api
        if not api:
            continue
        for op_id in reachable_ops(resource):
            hit = spec.get(op_id, api=api)
            if hit is not None:
                covered.add(hit.key)
    return covered


def excluded() -> dict[str, str]:
    """Spec keys sw does not model as resources, each with a reason.

    "Excluded" means no registry entry, not unreachable. Everything here can be
    called through `sw api`, which resolves any operation id from this same
    catalog, so the gate measures what is *modelled* rather than what is
    possible.
    """
    out: dict[str, str] = {}
    for op in spec.operations():
        if op.api == "compatibility-api":
            out[op.key] = "compat/LaML surface — reachable via `sw api`, not modelled"
        elif "dialogflow" in op.operation_id:
            out[op.key] = "dialogflow — deprecated"
        elif op.api == "calling-api":
            out[op.key] = "imperative call control — surfaced as live call actions"
        elif op.api == "relay-rest" and op.path.startswith("/api/relay/rest/endpoints/sip"):
            # The relay-rest SIP endpoint surface is superseded by the Fabric
            # SIP endpoints (`sip` resource); the SDK omits it deliberately.
            out[op.key] = "superseded by Fabric SIP endpoints"
    return out


# The build backlog: operations that are real, in scope, and not covered yet.
# Every entry needs a reason, so a newly-discovered endpoint is a tracked
# decision rather than something that quietly appears in a set. Regenerating the
# catalog against newer specs is exactly how entries arrive here.
BACKLOG: dict[str, str] = {
    "ai-api:chat_methods": (
        "New API family, found when the catalog was regenerated from the current "
        "specs. POST /api/ai/chat is JSON-RPC shaped: one endpoint carrying "
        "create_conversation / chat / summarize / end_conversation / delete, the "
        "same shape as calling-api's call-commands. Surface it the same way, as "
        "generated subcommands, rather than as a CRUD resource."
    ),
}

# The backlog may only shrink.
MAX_BACKLOG = len(BACKLOG)


def not_yet() -> set[str]:
    """The build backlog: everything neither covered nor excluded."""
    return spec.keys() - covered_keys() - set(excluded())


def backlog_by_api() -> dict[str, list[str]]:
    """The backlog grouped by API, for reporting and build ordering."""
    grouped: dict[str, list[str]] = {}
    for op in spec.operations():
        if op.key in not_yet():
            grouped.setdefault(op.api, []).append(op.operation_id)
    return {api: sorted(ids) for api, ids in sorted(grouped.items())}
