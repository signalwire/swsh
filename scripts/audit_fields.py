#!/usr/bin/env python3
"""Diff every resource's declared fields against what the API documents.

The catalog carries each operation's request parameters, straight from the
compiled OpenAPI, so this needs no network and no docs-slug guessing: it is a
local comparison between `Resource.fields` and `Operation.params`.

What it reports, per resource:

  missing    the API accepts it, the registry does not offer it
  extra      the registry offers it, the API does not accept it (usually a
             wrong name, which is worse than a missing one: the value is
             silently dropped or 422s)
  required   the API requires it and the registry does not mark it required,
             or the reverse
  enum       the API enumerates values the registry does not list
  kind       the declared control type does not match the documented type

Run with no arguments for a report. `--check` exits non-zero when anything
differs; some resources differ on purpose, so it is not a gate. CI regenerates
the Markdown instead and fails if the committed copy is out of date.

    python scripts/audit_fields.py            # human report
    python scripts/audit_fields.py --markdown # docs/field-audit.md
    python scripts/audit_fields.py --check    # non-zero on any difference
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swsh import resources as res
from swsh import spec

# The op whose parameters define a resource's create/update form. Create is the
# fuller of the two, so it is the baseline; update-only resources fall back.
FORM_OPS = ("create", "update")

# OpenAPI type -> the registry field kind that should represent it.
KIND_FOR_TYPE = {
    "string": {"text", "textarea", "choice", "code", "list"},
    "boolean": {"bool"},
    "integer": {"int"},
    "number": {"int"},
    "array": {"multi", "list"},
    "object": {"code", "text"},
}


def form_operations(resource) -> list[spec.Operation]:
    """The operations whose params describe this resource's editable fields.

    Both create and update, because one registry form serves both and the two
    parameter sets differ: a field only valid on update would otherwise look
    like an invented one. `Field.on_create` / `on_update` express which side a
    field belongs to; this audit checks membership, not which half.
    """
    if not resource.api:
        return []
    # Only the operations the resource actually claims. A read/update resource
    # must not be judged against a create body it never sends: `campaigns` is
    # RU, and its create documents 29 parameters that its form has no business
    # offering.
    caps_for = {"create": res.CREATE, "update": res.UPDATE}
    ops = []
    for op_name in FORM_OPS:
        if caps_for[op_name] not in resource.caps:
            continue
        op_id = resource.rest_ops.get(op_name)
        if not op_id:
            continue
        op = spec.get(op_id, api=resource.api)
        if op is not None and op.params:
            ops.append(op)
    return ops


def audit(resource) -> dict | None:
    """Compare one resource. None when there is nothing to compare against."""
    ops = form_operations(resource)
    if not ops:
        return None

    # Union across create and update; when both document a parameter, the
    # stricter (required) declaration wins, so a create-required field is not
    # softened by update treating it as optional.
    documented: dict[str, spec.Param] = {}
    for op in ops:
        for param in op.params:
            existing = documented.get(param.name)
            if existing is None or (param.required and not existing.required):
                documented[param.name] = param
    # Compare on where a field is *written*, not what it is called. A flat form
    # field can target a nested body path — `Field("prompt_text",
    # path="prompt.text")` sends {"prompt": {"text": ...}} — so the documented
    # parameter it satisfies is the root of its target, `prompt`. Comparing names
    # would report that field as both an extra and a missing one.
    declared: dict[str, object] = {}
    for f in resource.fields:
        declared.setdefault(f.target.split(".")[0], f)

    problems: dict[str, list[str]] = {
        "missing": [], "extra": [], "required": [], "enum": [], "kind": [],
    }

    for name, param in documented.items():
        field = declared.get(name)
        if field is None:
            flag = " (required)" if param.required else ""
            problems["missing"].append(f"{name}: {param.type or '?'}{flag}")
            continue
        nested = field.target != name  # this field fills part of an object
        if param.required and not field.required and not nested:
            problems["required"].append(f"{name} is required by the API")
        if field.required and not param.required and not nested:
            problems["required"].append(f"{name} is not required by the API")
        if nested:
            # A field targeting prompt.text cannot be type-checked against the
            # `prompt` object, and its enum lives on the sub-property.
            continue
        if param.enum:
            missing_values = [v for v in param.enum if v not in field.choices]
            if missing_values:
                problems["enum"].append(
                    f"{name} missing {len(missing_values)} of {len(param.enum)} values: "
                    f"{', '.join(missing_values[:6])}"
                )
        allowed = KIND_FOR_TYPE.get(param.type)
        if allowed and field.kind not in allowed:
            problems["kind"].append(
                f"{name} is {param.type}, declared as kind={field.kind}"
            )

    for name in declared:
        if name not in documented:
            problems["extra"].append(name)

    return {
        "resource": resource.key,
        "operation": " + ".join(o.key.split(":")[1] for o in ops),
        "documented": len(documented),
        "declared": len(declared),
        "problems": {k: v for k, v in problems.items() if v},
    }


def collect() -> tuple[list[dict], list[str]]:
    """(audited resources, resources with no comparable operation)."""
    audited, skipped = [], []
    for resource in sorted(res.RESOURCES, key=lambda r: r.key):
        if not any(c in resource.caps for c in "CU"):
            continue  # read-only: no form, nothing to compare
        result = audit(resource)
        if result is None:
            skipped.append(resource.key)
        else:
            audited.append(result)
    return audited, skipped


def render_text(audited: list[dict], skipped: list[str]) -> str:
    lines: list[str] = []
    clean = [a for a in audited if not a["problems"]]
    dirty = [a for a in audited if a["problems"]]
    lines.append(f"{len(audited)} writable resources audited, "
                 f"{len(clean)} clean, {len(dirty)} with differences")
    if skipped:
        lines.append(f"{len(skipped)} could not be audited (no documented request "
                     f"body for their create/update op): {', '.join(skipped)}")
    lines.append("")
    for a in dirty:
        lines.append(f"{a['resource']}  ({a['operation']}: "
                     f"{a['declared']} declared vs {a['documented']} documented)")
        for kind, items in a["problems"].items():
            for item in items:
                lines.append(f"    {kind:9s} {item}")
        lines.append("")
    if clean:
        lines.append(f"clean: {', '.join(a['resource'] for a in clean)}")
    return "\n".join(lines)


def render_markdown(audited: list[dict], skipped: list[str]) -> str:
    clean = [a for a in audited if not a["problems"]]
    dirty = [a for a in audited if a["problems"]]
    out = [
        "# Field audit",
        "",
        "Generated by `scripts/audit_fields.py`. Do not edit by hand.",
        "",
        "Each writable resource's declared `Field` set compared against the "
        "request parameters the API documents, taken from the compiled OpenAPI "
        "in `swsh/spec_catalog.json`.",
        "",
        f"- {len(audited)} writable resources audited",
        f"- {len(clean)} match the documentation",
        f"- {len(dirty)} differ",
        f"- {len(skipped)} have no documented request body to compare against",
        "",
    ]
    if dirty:
        out += ["## Differences", ""]
        for a in dirty:
            out.append(f"### `{a['resource']}`")
            out.append("")
            out.append(f"`{a['operation']}` — {a['declared']} declared, "
                       f"{a['documented']} documented.")
            out.append("")
            for kind, items in a["problems"].items():
                out.append(f"**{kind}**")
                out.append("")
                for item in items:
                    out.append(f"- {item}")
                out.append("")
    if clean:
        out += ["## Matching the documentation", "",
                ", ".join(f"`{a['resource']}`" for a in clean), ""]
    if skipped:
        out += ["## Not comparable", "",
                "No documented request body for the create/update operation, so "
                "there is nothing to diff against:", "",
                ", ".join(f"`{k}`" for k in skipped), ""]
    return "\n".join(out)


def main() -> int:
    audited, skipped = collect()
    if "--markdown" in sys.argv:
        target = Path(__file__).resolve().parent.parent / "docs" / "field-audit.md"
        target.parent.mkdir(exist_ok=True)
        target.write_text(render_markdown(audited, skipped) + "\n")
        print(f"wrote {target.relative_to(target.parent.parent)}")
        return 0

    print(render_text(audited, skipped))
    if "--check" in sys.argv:
        dirty = [a for a in audited if a["problems"]]
        return 1 if dirty else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
