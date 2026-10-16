"""Check the resource registry against a live SignalWire project.

The registry's namespace paths, column choices and field names were written
from SDK introspection and the reference docs. This script exercises every
listable namespace against a real project and reports three things:

* whether the endpoint exists at all (a 404 means the path is wrong)
* which keys the rows actually carry, so column guesses can be corrected
* which declared columns are absent from real data

Run it with credentials in the environment or a .env:

    .venv/bin/python scripts/verify_registry.py
    .venv/bin/python scripts/verify_registry.py --json
"""

from __future__ import annotations

import asyncio
import json
import sys

from swsh import resources as res
from swsh.client import SwshClient, SwshError
from swsh.config import resolve


async def probe(client: SwshClient, resource: res.Resource) -> dict:
    result: dict = {"key": resource.key, "namespace": resource.namespace}
    if not resource.namespace or not resource.can_list:
        result["status"] = "skipped"
        result["note"] = "no list endpoint"
        return result

    try:
        payload = await client.call_sdk(resource.list_path)
    except SwshError as exc:
        result["status"] = "error"
        result["http"] = exc.status
        result["note"] = str(exc)[:160]
        return result

    rows = res.unwrap(payload, resource.data_key)
    result["status"] = "ok"
    result["rows"] = len(rows)
    if rows:
        keys = sorted({k for row in rows for k in row})
        result["actual_keys"] = keys
        declared = list(resource.columns)
        result["columns_present"] = [c for c in declared if c in keys]
        result["columns_missing"] = [c for c in declared if c not in keys]
        # Compare against where the field is *read* from, following read_path
        # and path, and only check the top-level segment of a nested source.
        result["fields_missing"] = [
            f.name for f in resource.fields
            if f.on_update and f.source.split(".")[0] not in keys
        ]
    else:
        result["envelope"] = (
            sorted(payload)[:8] if isinstance(payload, dict) else type(payload).__name__
        )
    return result


async def main() -> None:
    as_json = "--json" in sys.argv
    async with SwshClient(resolve()) as client:
        results = []
        for resource in res.RESOURCES:
            results.append(await probe(client, resource))

    if as_json:
        print(json.dumps(results, indent=2))
        return

    bad = 0
    for r in results:
        if r["status"] == "skipped":
            print(f"  --   {r['key']:14} {r['note']}")
            continue
        if r["status"] == "error":
            bad += 1
            print(f"  FAIL {r['key']:14} HTTP {r.get('http')}  {r['namespace']}")
            print(f"       {r['note'][:120]}")
            continue

        note = f"{r['rows']} rows"
        print(f"  ok   {r['key']:14} {note}")
        if r.get("columns_missing"):
            print(f"       columns not in data: {r['columns_missing']}")
            print(f"       actual keys:         {r['actual_keys'][:14]}")
        if r.get("fields_missing"):
            print(f"       fields not in data:  {r['fields_missing']}")

    print(f"\n{len(results)} resources, {bad} endpoint failures")


if __name__ == "__main__":
    asyncio.run(main())
