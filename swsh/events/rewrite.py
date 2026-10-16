"""Temporary rewriting of status-callback URLs, with guaranteed restore.

``sw listen`` points your phone numbers at a throwaway tunnel so callbacks
land in your terminal. That means mutating live project configuration, so the
contract here is strict:

* every original value is written to a journal on disk **before** anything is
  changed, so a crash, a SIGKILL or a closed laptop lid can still be undone
* restore is idempotent and safe to run repeatedly
* ``sw listen --restore`` recovers a journal left behind by a previous run

The field names below come from a live phone-number payload; ``ROUTING_FIELDS``
says which, and why.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from platformdirs import user_state_dir

from ..client import SwshClient

# Every routing field swsh may touch. Captured wholesale so a restore puts the
# number back exactly as found, not just the one field that was overwritten.
# Taken verbatim from a live phone_numbers payload, not from the docs. Notably
# there is no `call_ai_agent_id` or `call_flow_id` in the read model: numbers
# routed to an AI agent, call flow or video room point at
# `calling_handler_resource_id` instead, even though the SDK's typed helpers
# accept the older per-type names on write.
ROUTING_FIELDS = (
    "call_handler",
    "call_receive_mode",
    "calling_handler_resource_id",
    "call_request_url",
    "call_request_method",
    "call_fallback_url",
    "call_fallback_method",
    "call_status_callback_url",
    "call_status_callback_method",
    "call_laml_application_id",
    "call_dialogflow_agent_id",
    "call_relay_context",
    "call_relay_context_status_callback_url",
    "call_relay_topic",
    "call_relay_topic_status_callback_url",
    "call_relay_application",
    "call_relay_connector_id",
    "call_relay_script_url",
    "call_sip_endpoint_id",
    "call_verto_resource",
    "call_video_room_id",
    "message_handler",
    "messaging_handler_resource_id",
    "message_request_url",
    "message_request_method",
    "message_fallback_url",
    "message_fallback_method",
    "message_laml_application_id",
    "message_relay_context",
    "message_relay_topic",
)

# Which field carries the status callback, per handler. Several handlers have
# nowhere to put one, hence the None entries; those numbers are reported as
# skipped rather than silently left unwatched.
#
# `relay_context` gets its own field. The earlier version of this table pointed
# it at the topic field, which would have written the callback to the wrong
# key and then "restored" a value that was never there.
STATUS_FIELD_BY_HANDLER: dict[str, str | None] = {
    "laml_webhooks": "call_status_callback_url",
    "relay_topic": "call_relay_topic_status_callback_url",
    "relay_context": "call_relay_context_status_callback_url",
    "relay_script": None,
    "laml_application": None,
    "ai_agent": None,
    "call_flow": None,
    "relay_application": None,
    "relay_connector": None,
    "video_room": None,
    "dialogflow": None,
}


def journal_path() -> Path:
    return Path(user_state_dir("swsh")) / "rewrite-journal.json"


@dataclass(slots=True)
class NumberSnapshot:
    """Everything needed to put one number back the way it was."""

    id: str
    number: str
    original: dict[str, Any]
    applied_field: str | None = None
    applied_value: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "original": self.original,
            "applied_field": self.applied_field,
            "applied_value": self.applied_value,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> NumberSnapshot:
        return cls(
            id=data["id"],
            number=data.get("number", ""),
            original=data.get("original", {}),
            applied_field=data.get("applied_field"),
            applied_value=data.get("applied_value"),
        )


class RewriteError(RuntimeError):
    pass


@dataclass
class CallbackRewriter:
    """Applies and reverts temporary status-callback URLs across numbers."""

    client: SwshClient
    snapshots: list[NumberSnapshot] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    # ------------------------------------------------------------------ applying

    async def apply(self, numbers: list[dict[str, Any]], callback_url: str) -> list[NumberSnapshot]:
        """Point each number's status callback at ``callback_url``.

        Numbers whose handler has no status-callback field are skipped and
        reported rather than silently ignored, because a user who asked to watch
        a number deserves to know swsh cannot.
        """
        for row in numbers:
            number_id = str(row.get("id") or row.get("sid") or "")
            label = str(row.get("number") or row.get("phone_number") or number_id)
            if not number_id:
                continue

            handler = str(row.get("call_handler") or "")
            field_name = STATUS_FIELD_BY_HANDLER.get(handler, "call_status_callback_url")
            if field_name is None:
                self.skipped.append(
                    (label, f"handler '{handler}' has no status callback field")
                )
                continue

            snapshot = NumberSnapshot(
                id=number_id,
                number=label,
                original={k: row.get(k) for k in ROUTING_FIELDS if k in row},
                applied_field=field_name,
                applied_value=callback_url,
            )

            # Journal before mutating. If the process dies between these two
            # lines the worst case is a restore that writes back what is
            # already there, which is harmless.
            self.snapshots.append(snapshot)
            self._write_journal()

            try:
                await self.client.call_sdk(
                    "phone_numbers.update", number_id, **{field_name: callback_url}
                )
            except Exception as exc:
                self.snapshots.pop()
                self._write_journal()
                self.skipped.append((label, f"update failed: {exc}"))

        return self.snapshots

    # ----------------------------------------------------------------- restoring

    async def restore(self) -> list[tuple[str, str | None]]:
        """Put every rewritten number back. Returns (number, error) per attempt."""
        results: list[tuple[str, str | None]] = []
        remaining: list[NumberSnapshot] = []

        for snapshot in self.snapshots:
            if not snapshot.applied_field:
                continue
            previous = snapshot.original.get(snapshot.applied_field)
            try:
                await self.client.call_sdk(
                    "phone_numbers.update",
                    snapshot.id,
                    **{snapshot.applied_field: previous},
                )
                results.append((snapshot.number, None))
            except Exception as exc:
                results.append((snapshot.number, str(exc)))
                remaining.append(snapshot)

        # Anything that failed stays in the journal so it can be retried with
        # `sw listen --restore` rather than being lost.
        self.snapshots = remaining
        if remaining:
            self._write_journal()
        else:
            self._clear_journal()
        return results

    # ------------------------------------------------------------------- journal

    def _write_journal(self) -> None:
        path = journal_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "written_at": time.time(),
            "space": self.client.profile.host,
            "project": self.client.profile.project,
            "snapshots": [s.to_json() for s in self.snapshots],
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)  # atomic, so a crash mid-write cannot corrupt it

    def _clear_journal(self) -> None:
        path = journal_path()
        if path.is_file():
            path.unlink()

    @classmethod
    def load_journal(cls, client: SwshClient) -> CallbackRewriter | None:
        """Rebuild a rewriter from a journal left by a previous run."""
        path = journal_path()
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

        snapshots = [NumberSnapshot.from_json(s) for s in payload.get("snapshots", [])]
        if not snapshots:
            path.unlink(missing_ok=True)
            return None

        if payload.get("project") and payload["project"] != client.profile.project:
            raise RewriteError(
                f"journal belongs to project {payload['project']}, but the active "
                f"profile is {client.profile.project}. Switch profiles to restore it."
            )

        rewriter = cls(client=client)
        rewriter.snapshots = snapshots
        return rewriter


def has_pending_restore() -> bool:
    return journal_path().is_file()
