"""Stand a SignalWire AI agent up from here, and make it callable.

The registry already models the platform's *hosted* AI agents (`sw agents`),
which are a row you edit. This is the other kind: an agent written with the
Agents SDK, running in this process, reached by the platform over a tunnel. It
is what the SDK exists for — the model talks, your code decides — and until now
trying one meant a scratch script, a second terminal, an ngrok window and three
dashboard tabs to make it dialable.

`AgentLab.start()` is those four steps, in order, with the undo recorded as it
goes:

1. **Build** an `AgentBase` from a declarative `AgentSpec`. Prompt, voice,
   language and skills are values, not code, so the cockpit can collect them on
   the same kind of form every other create uses.
2. **Serve** it on a local port, as a uvicorn task on the running loop. Never a
   thread and never `agent.run()`, which owns the process and would take the
   cockpit with it.
3. **Tunnel** the port with the same ngrok helper `sw listen` uses, and lock
   the agent's public base to it with `SWML_PROXY_URL_BASE` — the one input the
   SDK treats as authoritative for the URLs it writes into its own SWML.
4. **Wire** it into Call Fabric: a SWML webhook resource pointing at the tunnel,
   and a SIP address pointing at that resource. The second is what lets a SIP
   phone dial it, which is the whole point of the pairing with `softphone.py`.

Three things worth knowing before changing this:

- **The SDK logs to stderr at construction.** In a full-screen app that is a
  corrupted display, so `SIGNALWIRE_LOG_MODE=off` is set before the agent is
  built, not after, and uvicorn is started with its logging configuration
  disabled outright.
- **Everything created is deleted on `stop()`, newest first**, and a failure
  part-way through start unwinds what it already made. A lab that leaves a
  dangling SIP address behind is worse than one that refuses to start.
- **The dial target is read, never derived.** The address record is the source
  when it carries a URI; otherwise it is the SIP address's user at the domain
  on the project's SIP profile. Nothing is built from the configured space:
  that domain is missing the space's SIP identifier, so it does not resolve.
  With no profile to read there is no dial target, and the panel says so.
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from . import resources as res
from . import softphone

# The lab's states, in the order they happen.
STOPPED, STARTING, RUNNING, FAILED = "stopped", "starting", "running", "failed"

# Skills that need no API key, so they are safe to offer in a form. The SDK
# ships more (`skill_registry.list_skills()`); the rest want credentials and
# would fail at call time rather than at build time.
FREE_SKILLS = ("datetime", "math", "joke", "wikipedia_search")

DEFAULT_PROMPT = (
    "You are a friendly test agent answering a call placed from the sw command "
    "line. Greet the caller, say which space and project you are running in if "
    "asked, answer questions briefly, and let the caller end the call."
)


class AgentLabError(RuntimeError):
    """Anything that stops the lab, said in one line."""


def slug(text: str) -> str:
    """A URL-safe name: what a Fabric SIP address requires of its `name`."""
    cleaned = re.sub(r"[^a-z0-9-]+", "-", (text or "").strip().lower()).strip("-")
    return cleaned or "sw-agent"


@dataclass(frozen=True)
class AgentSpec:
    """An agent as values. The form collects exactly this."""

    name: str = "sw-agent"
    prompt: str = DEFAULT_PROMPT
    greeting: str = "Thanks for calling. What can I do for you?"
    voice: str = ""
    language: str = "English"
    language_code: str = "en-US"
    skills: tuple[str, ...] = ("datetime",)
    post_prompt: str = ""
    port: int = 3010

    @property
    def route(self) -> str:
        return f"/{slug(self.name)}"


@dataclass
class Live:
    """What a running lab holds, including everything it has to undo."""

    spec: AgentSpec
    public_url: str = ""
    webhook_url: str = ""
    resource_id: str = ""
    address_id: str = ""
    dial: str = ""
    dial_is_derived: bool = True
    address_row: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)


def build_agent(spec: AgentSpec) -> Any:
    """An `AgentBase` from a spec, with the SDK's logging silenced first.

    Basic auth is generated here rather than left to the SDK so the credentials
    can be written into the URL Fabric is given: the platform has to
    authenticate to fetch the SWML, and nothing else in this flow has a place
    to carry a header.
    """
    os.environ.setdefault("SIGNALWIRE_LOG_MODE", "off")
    try:
        from signalwire import AgentBase
    except Exception as exc:  # pragma: no cover - the SDK is a hard dependency
        raise AgentLabError(f"the Agents SDK is not importable: {exc}") from exc

    auth = (f"sw-{secrets.token_hex(3)}", secrets.token_urlsafe(24))
    agent = AgentBase(name=slug(spec.name), route=spec.route, basic_auth=auth,
                      suppress_logs=True)
    agent.prompt_add_section("Role", body=spec.prompt)
    if spec.greeting:
        agent.prompt_add_section(
            "Greeting", body=f"Open the call with: {spec.greeting}")
    if spec.post_prompt:
        agent.set_post_prompt(spec.post_prompt)
    if spec.voice:
        agent.add_language(spec.language, spec.language_code, spec.voice)
    for name in spec.skills:
        try:
            agent.add_skill(name)
        except Exception as exc:
            raise AgentLabError(f"skill {name!r}: {exc}") from exc
    return agent


def webhook_url(public_url: str, route: str, auth: tuple[str, str]) -> str:
    """The URL Fabric fetches the SWML from, credentials included.

    Two details, both of which produce a call that silently does nothing when
    they are wrong:

    - **The trailing slash is required.** The SWML lives at ``<route>/``. A
      request to ``<route>`` lands on the app's catch-all, which answers ``200``
      with a body of ``null`` — so the platform gets a well-formed empty answer
      and the caller hears nothing. Verified against a served agent.
    - **The credentials go in the URL.** The platform authenticates with HTTP
      basic to fetch the document, and a resource's request URL is the only
      field in this flow that can carry the pair. Anything already carrying
      credentials is left as it is.
    """
    base = public_url.rstrip("/")
    route = "/" + route.strip("/") + "/"
    if "@" in base.split("//", 1)[-1].split("/", 1)[0]:
        return f"{base}{route}"
    scheme, _, host = base.partition("://")
    user, password = auth
    return f"{scheme}://{user}:{password}@{host}{route}"


def dial_target(address_row: dict[str, Any], *, user: str,
                domain: str = "") -> tuple[str, bool]:
    """What to dial to reach the address, and whether it is known.

    A record that names its own URI is believed. Otherwise the address's SIP
    user is joined to the project's SIP domain, read off the SIP profile —
    the only place that domain exists, since it carries a per-space identifier
    no amount of string work on the configured space will produce.

    With no domain to read there is no target. Nothing is derived from the
    config: a plausible wrong domain sends the call somewhere that does not
    answer, which is worse than saying there is nowhere to dial.
    """
    for key in ("sip_uri", "uri", "address", "sip_address", "dial_uri"):
        value = address_row.get(key) if isinstance(address_row, dict) else None
        if isinstance(value, str) and value.startswith(("sip:", "sips:")):
            return value, True
    if domain:
        return f"sip:{user}@{domain}", True
    return "", False


class AgentLab:
    """One local agent, served, tunnelled and wired into Call Fabric."""

    def __init__(self, on_change: Any = None) -> None:
        self.state: str = STOPPED
        self.error: str = ""
        self.live: Live | None = None
        self.log: list[tuple[float, str]] = []
        self.agent: Any = None
        self._on_change = on_change
        self._server: Any = None
        self._serving: asyncio.Task | None = None
        self._tunnel: Any = None
        self._proxy_before: str | None = None

    # ------------------------------------------------------------------ status

    @property
    def running(self) -> bool:
        return self.state == RUNNING

    def note(self, text: str) -> None:
        self.log.append((time.time(), text))
        del self.log[: max(0, len(self.log) - 200)]
        self._changed()

    def _changed(self) -> None:
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                pass

    # ----------------------------------------------------------------- startup

    async def start(self, client: Any, spec: AgentSpec, *,
                    public_url: str | None = None) -> Live:
        """Build, serve, tunnel and wire. Unwinds itself if any step fails."""
        if self.state in (STARTING, RUNNING):
            raise AgentLabError("the lab is already running")
        self.state = STARTING
        self.error = ""
        live = Live(spec=spec)
        self.live = live
        self.note(f"building {slug(spec.name)}")
        try:
            self._tunnel = await self._open_tunnel(spec.port, public_url)
            live.public_url = self._tunnel.public_url.rstrip("/")
            self.note(f"public at {live.public_url}")

            # Locked before the agent exists: the SDK treats this as the final
            # word on where it is reachable, and the URLs it writes into its own
            # SWML are built from it.
            self._proxy_before = os.environ.get("SWML_PROXY_URL_BASE")
            os.environ["SWML_PROXY_URL_BASE"] = live.public_url

            self.agent = build_agent(spec)
            await self._serve(spec.port)
            self.note(f"serving {spec.route} on port {spec.port}")

            live.webhook_url = webhook_url(
                live.public_url, spec.route, self.agent.get_basic_auth_credentials())
            await self._wire(client, live)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.note(self.error)
            # With the client, so the unwind can delete what was already
            # created: a SIP address refused after the webhook was made leaves
            # a resource pointing at a tunnel that is about to close.
            await self.stop(client=client, quiet=True)
            self.state = FAILED
            self._changed()
            raise AgentLabError(self.error) from exc
        self.state = RUNNING
        self.note("running")
        return live

    async def _open_tunnel(self, port: int, public_url: str | None) -> Any:
        from .events.tunnel import open_tunnel

        return await open_tunnel(port, public_url=public_url)

    async def _serve(self, port: int) -> None:
        """uvicorn as a task on this loop, with its logging turned off.

        `log_config=None` matters as much as the level: uvicorn's default
        configuration installs handlers on the root logger, and in a full-screen
        app every one of them writes over the display.
        """
        import uvicorn

        config = uvicorn.Config(self.agent.get_app(), host="127.0.0.1", port=port,
                                log_config=None, log_level="critical",
                                access_log=False)
        self._server = uvicorn.Server(config)
        self._serving = asyncio.create_task(self._server.serve())
        for _ in range(100):  # ~5s, then say so rather than wire a dead port
            if getattr(self._server, "started", False):
                return
            if self._serving.done():
                self._serving.result()  # re-raise whatever killed it
                raise AgentLabError("the agent server stopped immediately")
            await asyncio.sleep(0.05)
        raise AgentLabError(f"the agent server did not come up on port {port}")

    async def _wire(self, client: Any, live: Live) -> None:
        """Create the Fabric resource and the SIP address that reaches it."""
        hooks = res.get("swmlhooks")
        created = await client.invoke(hooks, "create", body={
            "name": slug(live.spec.name),
            "primary_request_url": live.webhook_url,
            "used_for": "calling",
        })
        live.resource_id = str(_id_of(created))
        if not live.resource_id:
            raise AgentLabError("the SWML webhook came back without an id")
        self.note(f"swml webhook {live.resource_id}")

        addresses = res.get("sipaddr")
        user = slug(live.spec.name)
        row = await client.invoke(addresses, "create", body={
            "name": user,
            "user": user,
            "calling_handler_resource_id": live.resource_id,
        })
        live.address_row = row if isinstance(row, dict) else {}
        live.address_id = str(_id_of(row))
        live.dial, known = dial_target(
            live.address_row, user=user,
            domain=await softphone.domain_of(client))
        live.dial_is_derived = not known
        self.note(f"dial {live.dial}")

    # ---------------------------------------------------------------- teardown

    async def stop(self, *, client: Any = None, quiet: bool = False) -> None:
        """Undo everything, newest first. Safe to call in any state."""
        live, self.live = self.live, None
        if live is not None and client is not None:
            await self._unwire(client, live)
        if self._server is not None:
            self._server.should_exit = True
        if self._serving is not None:
            try:
                await asyncio.wait_for(self._serving, timeout=5)
            except Exception:
                self._serving.cancel()
        self._server = self._serving = None
        if self._tunnel is not None:
            try:
                await self._tunnel.close()
            except Exception:
                pass
            self._tunnel = None
        if self._proxy_before is None:
            os.environ.pop("SWML_PROXY_URL_BASE", None)
        else:
            os.environ["SWML_PROXY_URL_BASE"] = self._proxy_before
        self._proxy_before = None
        self.agent = None
        if not quiet:
            self.state = STOPPED
            self.note("stopped")
        self._changed()

    async def _unwire(self, client: Any, live: Live) -> None:
        """Delete what `_wire` made. A failure is reported, never raised.

        Stopping has to get as far as it can: refusing to free the port because
        an address was already gone by hand leaves the lab unusable.
        """
        for key, identifier in (("sipaddr", live.address_id),
                                ("swmlhooks", live.resource_id)):
            if not identifier:
                continue
            try:
                await client.invoke(res.get(key), "delete", resource_id=identifier)
                self.note(f"deleted {key} {identifier}")
            except Exception as exc:
                self.note(f"could not delete {key} {identifier}: {exc}")


def _id_of(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("id", "resource_id", "sid"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""
