#!/usr/bin/env python3
"""Build sw's operation catalog from SignalWire's compiled OpenAPI.

The specs (github.com/signalwire/docs, `specs/`) are the authoritative API
surface, written in TypeSpec. An earlier version of this script read the `.tsp`
sources directly with regular expressions. That was a mistake and it cost real
correctness: TypeSpec puts `@operationId` and the HTTP verb decorator in either
order, and declares an interface's route relative to its parent, so a regex
cannot reliably tell which decorator belongs to which operation or reassemble a
nested route. The result was 41 wrong paths and 2 wrong methods, twelve of which
had to be repaired by hand in `swsh/spec.py`.

So this reads the *compiled* OpenAPI instead, where every operation carries its
exact method, its fully-resolved path, and its request schema. Nothing is
inferred.

    cd <docs>/specs/signalwire-rest   && tsp compile .
    cd <docs>/specs/compatibility-api && tsp compile .
    python scripts/build_catalog.py <docs>/fern/apis/*/openapi.yaml

Compiling needs the specs' own emitters built first:

    cd <docs>/specs && npm install
    for e in emitters/*; do (cd $e && npm install && npm run build); done

What lands in the catalog, per operation: the API it belongs to, its operation
id, method, exact path, summary, and its request parameters with types, required
flags, defaults and enumerated values. The parameters are what let the field
audit check that each command offers what the API actually accepts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

OUT = Path(__file__).resolve().parent.parent / "swsh" / "spec_catalog.json"

# Path prefix -> the API name sw uses. Longest prefix wins, so /api/projects is
# not swallowed by /api/project.
API_BY_PREFIX: dict[str, str] = {
    "/api/ai": "ai-api",
    "/api/calling": "calling-api",
    "/api/chat": "chat-api",
    "/api/datasphere": "datasphere-api",
    "/api/fabric": "fabric-api",
    "/api/fax": "fax-api",
    "/api/laml/2010-04-01": "compatibility-api",
    "/api/logs": "logs-api",
    "/api/messaging": "message-api",
    "/api/project": "project-api",
    "/api/projects": "projects-api",
    "/api/pubsub": "pubsub-api",
    "/api/relay/rest": "relay-rest",
    "/api/video": "video-api",
    "/api/voice": "voice-api",
}

METHODS = ("get", "post", "put", "patch", "delete")


def api_for(path: str) -> tuple[str, str]:
    """(api name, base route) for a full path, by longest matching prefix."""
    best = ""
    for prefix in API_BY_PREFIX:
        if path == prefix or path.startswith(prefix + "/"):
            if len(prefix) > len(best):
                best = prefix
    if not best:
        return "", ""
    return API_BY_PREFIX[best], best


def server_prefix(doc: dict) -> str:
    """The path portion of the server URL, which compat folds into its server."""
    for server in doc.get("servers") or []:
        url = str(server.get("url", ""))
        marker = ".signalwire.com"
        if marker in url:
            tail = url.split(marker, 1)[1].rstrip("/")
            if tail:
                return tail
    return ""


def resolve(schema: Any, doc: dict, depth: int = 0) -> dict:
    """Follow a local $ref. Depth-capped: a self-referencing schema is possible."""
    if not isinstance(schema, dict) or depth > 8:
        return schema if isinstance(schema, dict) else {}
    ref = schema.get("$ref")
    if not ref or not ref.startswith("#/"):
        return schema
    node: Any = doc
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            return {}
        node = node[part]
    return resolve(node, doc, depth + 1)


def enum_values(prop: dict, doc: dict) -> list[str]:
    """Enumerated values, whether inline, behind a $ref, or inside anyOf."""
    prop = resolve(prop, doc)
    if prop.get("enum"):
        return [str(v) for v in prop["enum"]]
    for key in ("anyOf", "oneOf", "allOf"):
        for branch in prop.get(key) or []:
            found = enum_values(branch, doc)
            if found:
                return found
    return []


def type_of(prop: dict, doc: dict) -> str:
    prop = resolve(prop, doc)
    declared = prop.get("type")
    if isinstance(declared, str):
        return declared
    for key in ("anyOf", "oneOf", "allOf"):
        for branch in prop.get(key) or []:
            found = type_of(branch, doc)
            if found:
                return found
    return ""


def params_for(op: dict, doc: dict) -> list[dict]:
    """Request-body properties, flattened, with everything a form needs."""
    body = op.get("requestBody") or {}
    content = body.get("content") or {}
    # JSON first; the compat surface also documents a urlencoded variant that
    # carries the same properties.
    schema = None
    for kind in ("application/json", "application/x-www-form-urlencoded"):
        if kind in content:
            schema = content[kind].get("schema")
            break
    if schema is None and content:
        schema = next(iter(content.values())).get("schema")
    schema = resolve(schema, doc)
    if not schema:
        return []

    # Schemas compose three ways and all three appear in these specs:
    #
    #   allOf          intersection. Merge properties, union the required lists.
    #   oneOf / anyOf  variants. A SWML script is a calling script OR a
    #                  messaging one; a brand is managed OR CSP. One form has to
    #                  offer the union of their properties, but a property is
    #                  only genuinely required if *every* variant requires it —
    #                  otherwise picking the other variant makes it optional.
    #
    # Without the variant handling these schemas yielded zero parameters, which
    # silently read as "this endpoint takes no body".
    def collect(node: Any, depth: int = 0) -> tuple[dict[str, Any], set[str]]:
        node = resolve(node, doc)
        if not isinstance(node, dict) or depth > 8:
            return {}, set()
        props: dict[str, Any] = dict(node.get("properties") or {})
        required: set[str] = set(node.get("required") or [])

        for branch in node.get("allOf") or []:
            branch_props, branch_required = collect(branch, depth + 1)
            props.update(branch_props)
            required |= branch_required

        variants = (node.get("oneOf") or []) + (node.get("anyOf") or [])
        if variants:
            variant_required: list[set[str]] = []
            for branch in variants:
                branch_props, branch_required = collect(branch, depth + 1)
                props.update(branch_props)
                variant_required.append(branch_required)
            # Only what every variant demands is genuinely required.
            required |= set.intersection(*variant_required)

        return props, required

    properties, required = collect(schema)

    out = []
    for name, prop in properties.items():
        resolved = resolve(prop, doc)
        out.append({
            "name": name,
            "type": type_of(prop, doc),
            "required": name in required,
            "enum": enum_values(prop, doc),
            "default": resolved.get("default"),
            "description": (resolved.get("description") or "").strip()[:200],
        })
    return out


def build(paths: list[Path]) -> dict:
    catalog: dict = {"apis": {}, "operations": []}
    seen: set[tuple[str, str]] = set()

    for spec_path in paths:
        doc = yaml.safe_load(spec_path.read_text())
        prefix = server_prefix(doc)
        for route, item in (doc.get("paths") or {}).items():
            full = prefix + route
            api, base = api_for(full)
            if not api:
                print(f"  skipping unmapped path {full}", file=sys.stderr)
                continue
            for method, op in item.items():
                if method not in METHODS or not isinstance(op, dict):
                    continue
                operation_id = op.get("operationId")
                if not operation_id:
                    continue
                key = (api, operation_id)
                if key in seen:
                    continue
                seen.add(key)
                catalog["operations"].append({
                    "api": api,
                    "operation_id": operation_id,
                    "method": method.upper(),
                    "path": full,
                    "base_route": base,
                    "summary": (op.get("summary") or "").strip(),
                    "params": params_for(op, doc),
                })

    for op in catalog["operations"]:
        meta = catalog["apis"].setdefault(
            op["api"], {"base_route": op["base_route"], "operations": 0}
        )
        meta["operations"] += 1

    catalog["operations"].sort(key=lambda o: (o["api"], o["operation_id"]))
    catalog["apis"] = dict(sorted(catalog["apis"].items()))
    catalog["total"] = len(catalog["operations"])
    return catalog


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: build_catalog.py <openapi.yaml> [<openapi.yaml> ...]",
              file=sys.stderr)
        return 2
    paths = [Path(a).expanduser().resolve() for a in sys.argv[1:]]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        for p in missing:
            print(f"not a file: {p}", file=sys.stderr)
        return 2

    catalog = build(paths)
    OUT.write_text(json.dumps(catalog, indent=2) + "\n")
    with_params = sum(1 for o in catalog["operations"] if o["params"])
    print(f"wrote {OUT.name}: {catalog['total']} operations across "
          f"{len(catalog['apis'])} APIs ({with_params} with request parameters)")
    for api, meta in catalog["apis"].items():
        print(f"  {api:20} {meta['operations']:>3}  {meta['base_route']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
