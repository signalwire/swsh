"""Field definitions versus what the API documents.

The catalog carries each operation's request parameters, so a resource's declared
`Field` set can be checked against the real thing without a live space. This is
the gate that keeps them from drifting apart again.

It is a ratchet, not a pass/fail on the whole registry: 29 of 38 writable resources
still differ, and fixing them all at once was never the plan. What these tests
forbid is going backwards — a resource that matches the documentation must keep
matching, and no writable resource may go back to having no fields at all.

Matching the documentation is *not* the goal, and this file must not be read as
one. The audit compares against a shared schema that over-reports required
fields: it says `sip` is missing three of them, when a SIP endpoint
creates fine without any. `scripts/probe_fields.py` asks the platform instead,
and where the two disagree the platform wins — see
`test_resources.py::TestVerifiedAgainstLiveProject`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from swsh import resources as res

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_fields.py"


def load_audit():
    spec_ = importlib.util.spec_from_file_location("audit_fields", SCRIPT)
    module = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit():
    return load_audit()


# Resources whose fields match the documented request body exactly. This set may
# grow and must never shrink.
CLEAN = {
    "addresses",    # E911: was `name`/`display_name`, neither of which exists
    "chattoken",
    "orders",
    "relayapps",    # probed live: `name` is required, and was declared optional
    "pubsubtoken",
    "sipaddr",      # filled out for the lab: it is how a resource gets a URI
    "subcreds",     # matches the SIP arguments swsh 2.0 verified live
    "subtokens",
    "vstreams",
}


class TestRatchet:
    def test_the_clean_resources_stay_clean(self, audit):
        audited, _ = audit.collect()
        clean = {a["resource"] for a in audited if not a["problems"]}
        regressed = CLEAN - clean
        assert regressed == set(), (
            f"these matched the documentation and no longer do: {sorted(regressed)}"
        )

    def test_newly_clean_resources_are_recorded(self, audit):
        # Keeps CLEAN honest: fixing a resource without listing it here means the
        # ratchet silently stops protecting it.
        audited, _ = audit.collect()
        clean = {a["resource"] for a in audited if not a["problems"]}
        unrecorded = clean - CLEAN
        assert unrecorded == set(), (
            f"now matching the docs but missing from CLEAN: {sorted(unrecorded)}"
        )


class TestEveryWritableResourceHasFields:
    def test_no_writable_resource_is_fieldless(self):
        # A create or update path with no declared fields accepts only untyped
        # --set, offers no pickers and no validation, and its --help lists
        # nothing. Seven resources were in that state.
        fieldless = [
            r.key for r in res.RESOURCES
            if any(c in r.caps for c in (res.CREATE, res.UPDATE)) and not r.fields
        ]
        assert fieldless == [], f"writable but no fields: {fieldless}"


class TestTheAuditItself:
    """The audit had three false-positive classes while it was being written.
    Each is pinned so a future change cannot quietly reintroduce one."""

    def test_nested_paths_are_not_reported_as_missing_and_extra(self, audit):
        # `agents` writes prompt_text -> prompt.text. Comparing names rather than
        # write targets reported `prompt` missing and `prompt_text` invented.
        result = audit.audit(res.BY_KEY["agents"])
        problems = result["problems"]
        # exact names, not substrings: post_prompt_url contains "prompt"
        missing_names = {item.split(":")[0] for item in problems.get("missing", [])}
        assert "prompt" not in missing_names
        assert "prompt_text" not in problems.get("extra", [])
        assert "post_prompt_text" not in problems.get("extra", [])

    def test_a_resource_is_judged_only_on_operations_it_claims(self, audit):
        # `campaigns` is RU. Its create documents 29 parameters that its form has
        # no business offering, so create must not be part of the comparison.
        campaigns = res.BY_KEY["campaigns"]
        ops = audit.form_operations(campaigns)
        assert [o.operation_id for o in ops] == ["update_campaign"]

    def test_create_and_update_bodies_are_unioned(self, audit):
        # One form serves both verbs and the two parameter sets differ, so a
        # field only valid on update must not look invented.
        subcreds = res.BY_KEY["subcreds"]
        ops = audit.form_operations(subcreds)
        assert {o.operation_id for o in ops} == {
            "create_subscriber_sip_credential", "update_subscriber_sip_credential",
        }
