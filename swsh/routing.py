"""Follow a resource's routing to everything it points at.

`sw numbers get <n> --full` answers "what actually happens when this rings?".
That question is not answerable from the number's own row, for three reasons
this module exists to handle.

**Most of the row is dead.** A number keeps every pointer it has ever had. A
number on ``relay_script`` still carries the ``call_laml_application_id`` from
the cXML application it used last year, and nothing in the payload says which
of them is live except ``call_handler``. So the handler picks the fields, and
the rest are reported as *not in use* rather than quietly shown next to the
ones that matter, which is the exact confusion this is meant to end.

**The configuration is one hop away.** ``calling_handler_resource_id`` names a
Fabric resource, and ``GET /api/fabric/resources/{id}`` returns that resource's
entire configuration inline — a SWML script arrives with its ``contents``, a
call flow with its ``flow_data``, an AI agent with its prompt. One call gets
the whole target whatever type it is, so nothing here branches per handler.

**A webhook is sometimes another hop.** When the dashboard points a number at a
hosted bin it stores a ``cxml_webhook`` whose URL is
``https://<space>/laml-bins/<id>`` — and that ``<id>`` is the script's *inner*
id, not its Fabric resource id, so it has to be matched against the listing
rather than fetched. Anything not hosted on the space is fetched over the wire.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from . import resources as res
from .client import SwshClient, SwshError, next_page

# A hosted bin's URL carries the script's inner id, and which collection to
# look in follows from the path: LaML bins are cXML, relay bins are SWML.
_BIN_URL = re.compile(r"^/(laml|relay)-bins/([0-9a-fA-F-]{36})")
_BIN_KIND = {"laml": "cxml", "relay": "swml"}

# The URL a node hands off to. Only the primary: a fallback is by definition
# not what happens, so it is shown as a field and not followed.
_FOLLOW = ("primary_request_url", "request_url", "url")

# Keys inside a Fabric type object that are the configuration rather than a
# setting: a script's contents, a call flow's graph, an agent's prompt. Any
# non-scalar value is treated this way, so a new type needs no entry here.
_SELF_REFERENTIAL = {"request_url"}  # a script's own bin URL; following it loops


@dataclass(slots=True)
class Document:
    """A configuration document, at full length."""

    label: str
    language: str  # "xml" | "json" | "text"
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {"label": self.label, "language": self.language, "text": self.text}


@dataclass(slots=True)
class Node:
    """One hop: a Fabric resource, a fetched URL, or a failure to reach one."""

    kind: str  # the Fabric type, "external" for a fetched URL
    id: str = ""
    name: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    documents: list[Document] = field(default_factory=list)
    child: Node | None = None
    note: str = ""  # why this is as far as it goes

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind}
        if self.id:
            out["id"] = self.id
        if self.name:
            out["name"] = self.name
        if self.fields:
            out["fields"] = self.fields
        if self.documents:
            out["documents"] = [d.as_dict() for d in self.documents]
        if self.note:
            out["note"] = self.note
        if self.child is not None:
            out["points_to"] = self.child.as_dict()
        return out


@dataclass(slots=True)
class Channel:
    """One routing channel of the row, resolved."""

    name: str
    handler: str
    live: dict[str, Any] = field(default_factory=dict)
    target: Node | None = None
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"channel": self.name, "handler": self.handler,
                               "settings": self.live}
        if self.note:
            out["note"] = self.note
        if self.target is not None:
            out["points_to"] = self.target.as_dict()
        return out


@dataclass(slots=True)
class Routing:
    """The whole picture for one row."""

    row: dict[str, Any]
    channels: list[Channel] = field(default_factory=list)
    unused: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.row.get("id"),
                "channels": [c.as_dict() for c in self.channels],
                "not_in_use": self.unused}


def _scalar(value: Any) -> bool:
    """Whether a value belongs on a field row rather than in a document.

    A list of plain strings — a SIP endpoint's codecs, its ciphers — is a
    setting, and pretty-printing it as a six-line JSON block buries the three
    settings next to it. Only a structure with shape (an object, a list of
    objects) is a document.
    """
    if isinstance(value, (str, int, float, bool, type(None))):
        return True
    return isinstance(value, list) and all(
        isinstance(v, (str, int, float, bool)) for v in value)


def _document(label: str, value: Any) -> Document:
    """Render one non-scalar (or markup) value as a document."""
    if isinstance(value, str):
        text = value.strip()
        language = "xml" if text.startswith("<") else "text"
        return Document(label, language, text)
    return Document(label, "json", json.dumps(value, indent=2, default=str))


class _Expander:
    """Resolves one row. Carries the per-invocation caches."""

    def __init__(self, client: SwshClient):
        self.client = client
        self._bins: dict[str, dict[str, dict[str, Any]]] = {}

    # ------------------------------------------------------------------ fabric

    async def _fabric(self, resource_id: str) -> dict[str, Any] | None:
        fabric = res.get("resources")
        try:
            payload = await self.client.invoke(fabric, "read", resource_id=resource_id)
        except SwshError:
            return None
        return payload if isinstance(payload, dict) else None

    async def _bin_index(self, kind: str) -> dict[str, dict[str, Any]]:
        """Inner script id -> its Fabric resource, for one script collection.

        Built by walking the listing because a bin URL carries the *inner* id
        and no route accepts it; ``GET .../cxml_scripts/{inner}`` is a 404.
        """
        if kind in self._bins:
            return self._bins[kind]
        index: dict[str, dict[str, Any]] = {}
        resource = res.get(kind)
        payload: Any = await self.client.invoke(resource, "list", page_size=100)
        while True:
            for row in res.unwrap(payload, resource.data_key):
                inner = row.get(row.get("type") or "", {})
                if isinstance(inner, dict) and inner.get("id"):
                    index[str(inner["id"])] = row
            link = next_page(payload)
            if not link:
                break
            payload = await self.client.rest_call("GET", link)
        self._bins[kind] = index
        return index

    # ----------------------------------------------------------------- fetching

    async def _fetch(self, url: str) -> Node:
        """Retrieve a URL and present whatever came back as a document.

        The space's own URLs go over the authenticated client. **Everything
        else gets a fresh client with no credentials on it** — sending a
        SignalWire project token to somebody's tunnel because their number
        happens to point there would be handing out the keys to the space.
        """
        node = Node(kind="external", name=url)
        host = urlsplit(url).hostname or ""
        try:
            if host == self.client.profile.host:
                node.kind = "hosted"
                response = await self.client.http.get(url, follow_redirects=True)
            else:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as anon:
                    response = await anon.get(url)
        except httpx.HTTPError as exc:
            node.note = f"could not be fetched: {type(exc).__name__}"
            return node

        content_type = response.headers.get("content-type", "")
        node.fields = {"status": response.status_code,
                       "content_type": content_type or "-"}
        body = response.text.strip()
        if not body:
            node.note = "responded with an empty body"
        elif not response.is_success:
            # An error page is not this number's configuration. The status is
            # the finding; printing somebody's 404 page in full buries it.
            node.note = f"HTTP {response.status_code} — no document returned"
        elif "html" in content_type:
            # Same: a tunnel that is down answers 200 with its own landing page.
            node.note = "answered with HTML, not a call document"
        else:
            node.documents.append(_document("response", body))
        return node

    # -------------------------------------------------------------------- hops

    async def _follow_url(self, url: str) -> Node | None:
        """A hosted bin resolves through the API; anything else is fetched."""
        split = urlsplit(url)
        match = _BIN_URL.match(split.path or "")
        if match and (split.hostname or "") == self.client.profile.host:
            kind = _BIN_KIND[match.group(1)]
            row = (await self._bin_index(kind)).get(match.group(2))
            if row is not None:
                return self._node(row)
            return Node(kind=f"{kind}_script", id=match.group(2),
                        note="hosted bin, but no script in this project has that id")
        return await self._fetch(url)

    def _node(self, payload: dict[str, Any]) -> Node:
        """One Fabric resource as a node: its settings and its documents."""
        kind = str(payload.get("type") or "")
        inner = payload.get(kind)
        inner = inner if isinstance(inner, dict) else {}
        node = Node(kind=kind or "unknown", id=str(payload.get("id") or ""),
                    name=str(payload.get("display_name") or ""))
        for key, value in inner.items():
            # The inner id and name are the header; repeating them as rows just
            # pushes the settings that differ further down the screen.
            if key in ("id", "name"):
                continue
            if _scalar(value):
                node.fields[key] = value
            else:
                node.documents.append(_document(key, value))
        # A script's contents arrive as markup or as a mapping; either way they
        # are the document, not a setting.
        if node.fields.get("contents"):
            node.documents.append(_document("contents", node.fields.pop("contents")))
        if not inner:
            node.note = "the API returns no further configuration for this type"
        return node

    async def _target(self, resource_id: str) -> Node:
        payload = await self._fabric(resource_id)
        if payload is None:
            return Node(kind="unknown", id=resource_id,
                        note="no Fabric resource with this id (it may have been deleted)")
        node = self._node(payload)
        if node.documents:
            return node  # it carries its own configuration; nothing to follow
        for key in _FOLLOW:
            url = node.fields.get(key)
            if key in _SELF_REFERENTIAL or not isinstance(url, str) or not url:
                continue
            node.child = await self._follow_url(url)
            break
        return node

    # ------------------------------------------------------------------- entry

    async def run(self, resource: res.Resource, row: dict[str, Any]) -> Routing:
        routing = Routing(row=row)

        for route in resource.routing:
            handler = row.get(route.handler)
            channel = Channel(name=route.channel, handler=str(handler or "-"))

            for field_def in resource.fields:
                if not field_def.show_if or field_def.show_if[0] != route.handler:
                    continue
                # The pointer is the hop itself, shown as the target below.
                if field_def.name == route.pointer:
                    continue
                value = row.get(field_def.name)
                if handler in field_def.show_if[1]:
                    channel.live[field_def.name] = value
                elif value not in (None, "", [], {}):
                    # Set, and belonging to a handler that is not the one in
                    # effect: sediment from an earlier configuration. This is
                    # the sole reason reading the raw row misleads people.
                    routing.unused[field_def.name] = value

            pointer = row.get(route.pointer) if route.pointer else None
            if pointer:
                channel.target = await self._target(str(pointer))
            elif handler:
                channel.note = "this handler names no target resource"
            routing.channels.append(channel)
        return routing


async def expand(client: SwshClient, resource: res.Resource,
                 row: dict[str, Any]) -> Routing:
    """Resolve every channel of ``row`` to what it actually points at."""
    return await _Expander(client).run(resource, row)
