"""Ask the platform which fields a create really needs, then delete what it made.

`scripts/audit_fields.py` compares the registry against the *documented* request
body and reports the drift. That is a report, not a verdict: the spec's required
list is drawn from a shared schema and over-reports. It says `sip` is
missing three required fields, yet a SIP endpoint creates fine from a name, a
username and a password. Believing it would mark five fields required that are
not, and every form in the tool would start demanding them.

So this asks the only authority there is. For each resource it sends a create
carrying nothing but the fields the registry already marks required, reads the
422, and reports what the platform named. Anything that succeeds is deleted
again immediately — the point is the error, not the object.

    .venv/bin/python scripts/probe_fields.py
    .venv/bin/python scripts/probe_fields.py --only sip,flows
    .venv/bin/python scripts/probe_fields.py --json

This is the companion to `verify_registry.py`: that one proves the routes exist,
this one proves what they will accept. It is the script that turned
`gateways`' three optional fields into three required ones.
"""

from __future__ import annotations

import asyncio
import json
import sys

from swsh import resources as res
from swsh.client import SwshClient, SwshError
from swsh.config import resolve

# Resources whose create is free, reversible and affects nobody outside the
# project. Everything else is left out **by name**, so adding a resource to the
# registry does not quietly add it to a script that creates things:
#
#   numbers, imported        cost money
#   brands, campaigns, orders 10DLC registration reaches the carriers
#   verified                 places a call to the number being verified
#   send, mfa                send a message to a real handset
#   tokens, *token           mint credentials, several with no delete route
#   projects                 creates a subproject, which is not a scratch object
#   wa*                      needs a WhatsApp business, and is not ours to make
#   addresses                E911 validation is a real-world address lookup
#   shortcodes               provisioned by the carrier, not by us
SAFE = (
    "queues", "swml", "swmlhooks", "cxml", "cxmlhooks", "cxmlapps", "flows",
    "confrooms", "sip", "gateways", "relayapps", "connectors", "sipaddr",
    "subscribers", "agents", "datasphere", "videorooms", "vconf", "domains",
    "groups",
)

# A plausible value per field kind, so the probe fails on *absence* rather than
# on a type the API would have rejected anyway.
STAMP = "sw-probe"


def sample(field: res.Field, name: str) -> object:
    # Kind before choices: a `multi` field with an enum still wants a *list*.
    # Sending `"OPUS"` where `["OPUS"]` belongs is rejected for its type, which
    # would read like a missing required field and is not.
    if field.kind in ("multi", "list"):
        return [field.choices[0]] if field.choices else [name]
    if field.choices:
        return field.choices[0]
    if field.kind == "int":
        return 1
    if field.kind == "bool":
        return False
    if field.kind == "code":
        return {"sections": {"main": []}} if field.language == "json" else "{}"
    if "url" in field.name:
        return "https://example.com/hook"
    if "email" in field.name:
        return f"{name}@example.com"
    if "uri" in field.name:
        return f"sip:{name}.example.com"
    if field.name in ("username", "user", "identifier", "domain", "topic"):
        return name
    return name


def minimal_body(resource: res.Resource, name: str) -> dict:
    """Only what the registry already claims is required.

    Keyed by the field's own name, which is what `--set` and the forms produce;
    `client._invoke_rest` is what turns a dotted `path` into a nested body and
    lifts a route placeholder out of it.
    """
    return {f.name: sample(f, name)
            for f in resource.form_fields("create") if f.required}


async def probe(client: SwshClient, resource: res.Resource) -> dict:
    name = f"{STAMP}-{resource.key}"
    out: dict = {"key": resource.key, "declared_required":
                 [f.name for f in resource.form_fields("create") if f.required]}

    if "create" not in resource.rest_ops or not resource.can_create:
        out["status"] = "skipped"
        out["note"] = "no create route"
        return out

    try:
        created = await client.invoke(resource, "create", body=minimal_body(resource, name))
    except SwshError as exc:
        named = sorted(_named_fields(exc.body))
        declared = set(out["declared_required"])
        out["http"] = exc.status
        out["note"] = str(exc).split(" (HTTP")[0]
        out["fields"] = named
        # Two very different rejections wear the same status code:
        #
        #   "Token is required"                    -> the registry is wrong
        #   "token is incorrect or not ready"      -> the registry is right and
        #                                             this script cannot invent
        #                                             a real FreeSWITCH token
        #
        # Only the first is a defect. Told apart by whether the platform is
        # complaining about a field we did not send, and by the code it used.
        absent = _missing_codes(exc.body) or not named or bool(set(named) - declared)
        out["status"] = "rejected" if absent else "value"
        return out

    identifier = created.get("id") if isinstance(created, dict) else None
    out["status"] = "accepted"
    out["note"] = "the declared required set is enough"
    if identifier and "delete" in resource.rest_ops:
        try:
            await client.invoke(resource, "delete", resource_id=str(identifier))
            out["cleaned"] = True
        except SwshError as exc:
            out["cleaned"] = False
            out["note"] = f"COULD NOT DELETE {identifier}: {exc}"
    else:
        out["cleaned"] = False
        out["note"] = f"left behind {identifier}: no delete route"
    return out


# The codes the platform uses for "you did not send this", as opposed to
# "what you sent is wrong".
_MISSING = ("missing_required_parameter", "missing_sip_configuration")


def _missing_codes(body: object) -> bool:
    items = body.get("errors") if isinstance(body, dict) else None
    if isinstance(items, dict):
        items = [items]
    for item in items or []:
        if isinstance(item, dict) and str(item.get("code", "")) in _MISSING:
            return True
        # `domains` answers with a bare string and no code at all.
        if isinstance(item, dict) and "is required" in str(item.get("message", "")):
            return True
    return False


def _named_fields(body: object) -> set[str]:
    """Which fields the platform complained about, from its error body."""
    found: set[str] = set()
    items = body.get("errors") if isinstance(body, dict) else None
    if isinstance(items, dict):
        items = [items]
    for item in items or []:
        if isinstance(item, dict):
            name = item.get("attribute") or item.get("field") or item.get("parameter")
            if name:
                found.add(str(name))
    return found


# A create can make a linked record under another resource: a video room also
# appears as a Fabric conference room. Anything this script creates is this
# script's to remove, so it goes looking for its own name afterwards rather
# than trusting the delete it already issued.
SHADOWS = {"videorooms": "confrooms"}


async def residue(probed: tuple[str, ...]) -> list[str]:
    """Rows named after this script that survived the cleanup."""
    lines: list[str] = []
    async with SwshClient(resolve()) as client:
        for key in {SHADOWS[k] for k in probed if k in SHADOWS}:
            resource = res.get(key)
            if resource is None:
                continue
            try:
                payload = await client.invoke(resource, "list")
            except SwshError:
                continue
            stale = [row for row in res.unwrap(payload, resource.data_key)
                     if STAMP in str(row)]
            for row in stale:
                lines.append(f"  RESIDUE  {key:14} {row.get('id')}  "
                             f"{row.get('display_name') or row.get('name')}")
    if lines:
        lines.append("  delete these with `sw <resource> delete <id> --yes`; a "
                     "create can leave a record the matching delete does not.")
    return lines


async def main() -> None:
    as_json = "--json" in sys.argv
    only: tuple[str, ...] = SAFE
    for arg in sys.argv[1:]:
        if arg.startswith("--only"):
            value = arg.split("=", 1)[1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1]
            only = tuple(k.strip() for k in value.split(","))

    unsafe = [k for k in only if k not in SAFE]
    if unsafe:
        print(f"refusing: not on the safe list: {', '.join(unsafe)}")
        print("Creating one of these costs money, reaches a carrier, or cannot be undone.")
        raise SystemExit(2)

    results = []
    async with SwshClient(resolve()) as client:
        for key in only:
            resource = res.get(key)
            if resource is None:
                continue
            results.append(await probe(client, resource))

    if as_json:
        print(json.dumps(results, indent=2))
        return

    for r in results:
        if r["status"] == "skipped":
            print(f"  --       {r['key']:14} {r['note']}")
        elif r["status"] == "accepted":
            mark = "ok" if r.get("cleaned") else "OK*"
            print(f"  {mark:8} {r['key']:14} {r['note']}")
        elif r["status"] == "value":
            # The declaration is right; the probe cannot invent a real
            # FreeSWITCH token or a URL that resolves.
            print(f"  ok       {r['key']:14} declared set accepted; "
                  f"rejected on a value: {r['note'][:80]}")
        else:
            print(f"  NEEDS    {r['key']:14} HTTP {r.get('http')}")
            print(f"           declared required: {r['declared_required']}")
            if r["fields"]:
                print(f"           platform named:    {r['fields']}")
            print(f"           {r['note'][:150]}")

    left = [r["key"] for r in results if r["status"] == "accepted" and not r.get("cleaned")]
    if left:
        print(f"\nnot cleaned up, delete by hand: {', '.join(left)}")
    for line in await residue(only):
        print(line)
    short = [r["key"] for r in results if r["status"] == "rejected"]
    print(f"\n{len(results)} probed, {len(short)} declare too few required fields"
          f"{': ' + ', '.join(short) if short else ''}")


if __name__ == "__main__":
    asyncio.run(main())
