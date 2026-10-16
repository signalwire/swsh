"""A real SIP phone, inside sw.

Everything else in this tool *describes* calls: it lists them, follows their
routing, watches them arrive. None of it can place one from a SIP endpoint, so
testing an endpoint or an agent meant leaving for a softphone, typing the
credentials in again, and losing the context you had. This module is the
missing half: a registered device that dials, answers, sends DTMF and carries
real audio, driven from the cockpit.

It is `baresip-python` underneath — the baresip SIP stack with an asyncio API
and no system dependencies, since the wheels bundle libre and libbaresip. It is
installed with `sw` wherever those wheels exist (`SUPPORTED_PLATFORMS`), and
not at all anywhere else, Windows included.

Nothing here imports it at module import time, and `available()` still answers
whether the stack loaded. Being a dependency is not the same as being present,
and an environment without it should say so in one line on the panel rather
than take the whole cockpit down with an ImportError at startup. So every entry
point raises `SoftphoneError` with `unavailable_reason()` instead: the reinstall
line where a wheel exists, and plainly "not on this platform" where none does.

Two things about the design are deliberate:

- **One device, one call.** A test phone that can hold three calls invites a UI
  that has to explain which one a key acts on. `max_concurrent_calls=1` makes
  the stack enforce what the screen assumes.
- **Registration failure is a state, not an exception that unwinds the app.**
  A wrong password is the single most likely thing to happen here, and the
  answer to it is one red line on the panel that says so, with the device still
  there to fix and retry.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Names the distribution, never the console script: `sw` on PyPI is an
# unrelated project by someone else, and a hint that said `sw` had people
# installing it, seeing "does not provide the extra", and exiting 0.
INSTALL_HINT = "pip install --force-reinstall swsh"

# Where `baresip-python` publishes wheels, and so where pyproject.toml asks for
# it. `platform_supported()` is the same condition as that dependency's marker,
# and `tests/test_lab.py` checks the two agree.
SUPPORTED_PLATFORMS = "macOS 15 or newer, or Linux on x86_64 or aarch64"

# What a device can do with audio. `coreaudio` is the mic and speakers (macOS);
# `aumem` is silence with the PCM readable from code, which is what a headless
# check wants; `ausine` sends a tone, which proves audio flows without a mic.
AUDIO_DRIVERS = ("coreaudio", "aumem", "ausine", "aufile")

# Taken from the stack's own signatures rather than guessed: `baresip.Account`
# types `transport` and `dtmf_mode` as Literals, so anything else is a
# TypeError at registration time rather than a call that merely sounds wrong.
#
# **Naming a transport is not the default, because naming one changes the
# request URI.** baresip carries the account's transport as a URI parameter,
# and the stack copies it onto the request URI and the `To` header of every
# INVITE. A device that names `udp` therefore sends
# `INVITE sip:+1...@space;transport=udp`, where a FreeSWITCH trunk that routes
# to the PSTN sends `INVITE sip:+1...@space` and names its transport in
# `Contact` only — which is where RFC 3261 puts it. An empty transport is the
# absence of the parameter, which is the shape that routes; see `aor_of`.
TRANSPORTS = ("udp", "tcp", "tls")
# The transport the stack uses when the URI names none — RFC 3263's default,
# and what the empty string in `Device.transport` resolves to on the wire.
TRANSPORT_DEFAULT = "udp"
DTMF_MODES = ("rtpevent", "info", "auto")
# baresip's own default pair, offered first because they always interop.
CODECS = ("pcmu", "pcma", "opus", "g722", "g726", "l16")

# Registration states, in the order they happen.
OFFLINE, REGISTERING, REGISTERED, FAILED = "offline", "registering", "registered", "failed"


class SoftphoneError(RuntimeError):
    """Anything the phone cannot do, said in one line."""


def available() -> bool:
    """Whether the SIP stack loaded.

    It ships with `sw`, so this is normally true. It is still asked, because a
    platform with no wheel is a one-line panel message and not a crash.
    """
    try:
        import baresip  # noqa: F401
    except Exception:
        return False
    return True


def platform_supported() -> bool:
    """Whether this platform gets the SIP stack at all.

    The same condition as the dependency's marker in pyproject.toml: macOS 15+
    (Darwin 24+), or Linux on x86_64 or aarch64.
    """
    import platform
    import sys

    if sys.platform == "darwin":
        major = platform.release().split(".")[0]
        return major.isdigit() and int(major) >= 24
    if sys.platform.startswith("linux"):
        return platform.machine() in ("x86_64", "aarch64")
    return False


def unavailable_reason() -> str:
    """Why there is no phone, in one line: fixable here, or not on this platform.

    A reinstall line on a platform with no wheel sends someone round in circles,
    so it is only offered where reinstalling can work.
    """
    if platform_supported():
        return f"the SIP stack did not load: {INSTALL_HINT}"
    return f"the SIP phone is not available on this platform; it needs {SUPPORTED_PLATFORMS}"


def unavailable_hint() -> str:
    """The short form, for the phone panel's narrow column."""
    return INSTALL_HINT if platform_supported() else "no SIP phone on this platform"


def _stack() -> Any:
    try:
        import baresip
    except Exception as exc:  # one line, not a traceback
        raise SoftphoneError(unavailable_reason()) from exc
    return baresip


async def domain_of(client: Any) -> str:
    """The project's real SIP domain, read from its SIP profile.

    One call, no id: the profile is a singleton. This is the only place a SIP
    domain comes from. It is never derived from the configured space: the real
    domain carries a per-space SIP identifier that appears nowhere in the host,
    so anything built out of the config is a domain that does not resolve. An
    empty string means the read failed, and the caller leaves the box empty
    rather than filling it with a guess.
    """
    from . import resources as res

    try:
        row = await client.invoke(res.get("sipprofile"), "read")
    except Exception:
        return ""
    if not isinstance(row, dict):
        return ""
    return str(res.cell(row, "domain") or "").strip()


def digits_of(target: str) -> str:
    """The target stripped of the punctuation people actually type."""
    return re.sub(r"[\s().-]", "", (target or "").strip())


def is_phone_number(target: str) -> bool:
    """Whether what was typed is a phone number rather than a SIP name.

    Digits, optionally `+`-prefixed. A SIP username can be all digits too,
    which is why length decides what happens next rather than this: `1001` is
    an extension, `2095550183` is a number.
    """
    bare = digits_of(target)
    if not bare:
        return False
    return bare.lstrip("+").isdigit() and ("+" not in bare[1:])


def e164(target: str) -> str:
    """A phone number in the form the platform routes to the PSTN.

    **This is what decides whether a call leaves the space.** SignalWire routes
    a SIP INVITE to the PSTN when the user part is an E.164 number; anything
    else it looks for as a resource *inside* the space, which is why dialling
    `2095550183` rang nothing while `+12095550183` connects.

    Only unambiguous cases are converted, and a `+` the caller typed always
    wins:

        +12095550183  ->  +12095550183   already E.164
        12095550183   ->  +12095550183   11 digits, NANP country code
        2095550183    ->  +12095550183   10 digits, assumed NANP
        1001, 911     ->  unchanged      an extension or a short code

    The 10-digit case assumes NANP, because a bare 10-digit number has no
    country code to read. Type the `+` to dial anywhere else.
    """
    bare = digits_of(target)
    if bare.startswith("+"):
        return bare
    if len(bare) == 11 and bare.startswith("1"):
        return "+" + bare
    if len(bare) == 10:
        return "+1" + bare
    return bare


def user_part(uri: str) -> str:
    """The user part of a dial target, whatever shape it arrived in.

    Tolerates a scheme or no scheme. Everything `dial_uri` builds carries
    `sip:`, but this also reads what somebody typed, and reading by index
    (`split(":", 1)[1]`) threw `IndexError` on anything that did not.

    The host part is taken off first, so a port does not get mistaken for the
    user — `rpartition(":")` reads `x@host:5060` as `5060`.
    """
    head = (uri or "").split("@", 1)[0]
    for scheme in ("sips:", "sip:", "tel:"):
        if head.lower().startswith(scheme):
            return head[len(scheme):]
    return head


def dial_uri(target: str, domain: str) -> str:
    """What someone typed, as a target the stack can dial.

    **Every target carries `sip:`, because the stack refuses one without it.**
    `UserAgent.dial` passes the string to `ua_connect`, which does *not*
    complete the scheme. A scheme-less target fails locally, before an INVITE
    exists, with `dial failed:` and an errno that varies by host — ENOENT
    ("No such file or directory") and ENOSYS ("Function not implemented") were
    both seen, so the message is not worth matching on. That was read off the
    stack rather than its documentation: `scripts/probe_dial_uri.py` is the
    probe, and `test_every_target_carries_the_sip_scheme` pins the rule.

    So the scheme is not a routing decision and cannot be used as one. What
    decides whether a call leaves the space is the **user part**: an E.164
    number routes to the PSTN, anything else is looked up as a resource inside
    the space. `e164` is where that happens.

    A `tel:` URI is rewritten onto the device's domain, since the stack cannot
    dial one. `sips:` is refused rather than quietly downgraded to `sip:` —
    asking for TLS and getting cleartext is worse than being told no; set the
    transport knob to `tls` instead.
    """
    target = (target or "").strip()
    if not target:
        raise SoftphoneError("nothing to dial")
    if target.lower().startswith("sips:"):
        raise SoftphoneError(
            "the stack cannot dial a sips: URI; set transport to tls and dial "
            "it as sip:")
    if target.lower().startswith("sip:"):
        return target
    if target.lower().startswith("tel:"):
        target = user_part(target)
    elif "@" in target:
        return f"sip:{target}"
    if not domain:
        raise SoftphoneError(
            "no SIP domain: the device has none, so there is nowhere to send "
            "the call")
    user = e164(target) if is_phone_number(target) else target
    return f"sip:{user}@{domain}"


def without_transport(aor: str) -> str:
    """An AOR line with no `transport` parameter on its URI.

    `baresip.Account.aor()` renders `<sip:user@domain;transport=X>;...`
    unconditionally, and the stack copies that parameter onto the request URI
    and the `To` header of every INVITE it sends. A FreeSWITCH trunk whose
    calls reach the PSTN sends neither — it names its transport in `Contact`
    only — and an E.164 target dialled from here rang nothing. Taking the
    parameter off is the only way to ask this stack for that request line.

    Only the URI is touched. Every parameter after the closing `>` — the
    password, `regint`, `outbound` — is left exactly as the library wrote it,
    because re-rendering the line here is how it would drift from the library.
    The URI's own user, domain and registrar all reject `<` and `>`, so the
    first `>` is always the bracket that closes it.

    An AOR that already names no transport comes back unchanged: the library
    dropping the parameter itself is the outcome this wants, not a failure.
    """
    uri, bracket, params = aor.partition(">")
    if not bracket:
        raise SoftphoneError(
            "the SIP stack rendered an account this cannot read; set a "
            "transport on the device to send it as the stack wrote it")
    return re.sub(r";transport=[^;>]*", "", uri, count=1) + bracket + params


def aor_of(device: Device) -> str:
    """The account line the stack registers as, built for the device.

    The library renders it — quoting, codecs and the outbound proxy are its
    business — and the transport parameter comes off again unless the device
    named one. Naming one is how a transport gets *chosen*, since the URI
    parameter is the only place baresip takes it from; so `tcp` and `tls`
    necessarily travel in the request URI, and that is what asking for them
    means.
    """
    account = _stack().Account(
        user=device.username,
        domain=device.domain,
        password=device.password,
        registrar=device.registrar or None,
        auth_user=device.auth_user or None,
        transport=device.transport or TRANSPORT_DEFAULT,
        audio_codecs=tuple(device.codecs),
        dtmf_mode=device.dtmf_mode or "rtpevent",
        # Registering with an interval of 0 is how baresip is told not to
        # register at all, which is what the loopback bench needs.
        reg_interval=(int(device.reg_interval or 600) if device.register else 0),
    )
    aor = account.aor()
    return aor if device.transport else without_transport(aor)


def redacted_aor(device: Device) -> str:
    """The account line as the stack will read it, with the password removed.

    This is the one string that answers "what am I actually sending": the
    transport parameter either is or is not on the URI here, and the request
    line and `To` of every INVITE are built from it. It exists so that
    question can be answered without a packet capture.

    The password is replaced rather than omitted, because a line with no
    `auth_pass` at all reads as a device configured without one.
    """
    if not available():
        return unavailable_reason()
    try:
        aor = aor_of(device)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return re.sub(r'auth_pass="[^"]*"', 'auth_pass="***"', aor)


def diagnostics_path() -> Path:
    """Where a copied diagnostics block is also written.

    The clipboard is not always reachable — `copy_to_clipboard` is OSC 52,
    which macOS Terminal ignores — so the block is written to a file as well
    and the path is named. A path always works.
    """
    from platformdirs import user_log_dir

    return Path(user_log_dir("swsh")) / "diagnostics.txt"


async def edge_report(domain: str, *, timeout: float = 4.0) -> list[str]:
    """One SIP OPTIONS per edge per transport, and what came back.

    This exists because a registration that stops working where it used to is
    indistinguishable from a client bug, and the cause is often the network
    path instead. The signature is plain once you look — UDP times out while
    TCP answers `200 Keepalive`, or one edge answers and the other accepts the
    connection and returns nothing.

    Deliberately **one datagram and one connect per edge**, and no retries.
    Nothing here authenticates: no account, no credentials, no project token —
    an OPTIONS needs none.
    """
    import asyncio
    import socket

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(domain, 5060, type=socket.SOCK_STREAM)
    except Exception as exc:
        return [f"{domain} did not resolve: {exc}"]
    edges = sorted({info[4][0] for info in infos})
    if not edges:
        return [f"{domain} resolved to no addresses"]

    def request(transport: str) -> bytes:
        return (
            f"OPTIONS sip:{domain} SIP/2.0\r\n"
            f"Via: SIP/2.0/{transport} 0.0.0.0:5060;branch=z9hG4bKswprobe\r\n"
            f"Max-Forwards: 70\r\n"
            f"To: <sip:{domain}>\r\n"
            f"From: <sip:probe@invalid>;tag=swprobe\r\n"
            f"Call-ID: sw-edge-report\r\n"
            f"CSeq: 1 OPTIONS\r\n"
            f"Content-Length: 0\r\n\r\n"
        ).encode()

    def one_edge(ip: str) -> list[str]:
        lines: list[str] = []
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.settimeout(timeout)
        try:
            udp.sendto(request("UDP"), (ip, 5060))
            answer = udp.recvfrom(2048)[0].split(b"\r\n")[0].decode(errors="replace")
            lines.append(f"  {ip}  UDP  {answer}")
        except TimeoutError:
            lines.append(f"  {ip}  UDP  no answer")
        except OSError as exc:
            lines.append(f"  {ip}  UDP  {type(exc).__name__}: {exc}")
        finally:
            udp.close()

        tcp = None
        try:
            tcp = socket.create_connection((ip, 5060), timeout=timeout)
            tcp.settimeout(timeout)
            tcp.sendall(request("TCP"))
            data = tcp.recv(2048)
            answer = (data.split(b"\r\n")[0].decode(errors="replace") if data
                      else "connected, then nothing")
            lines.append(f"  {ip}  TCP  {answer}")
        except OSError as exc:
            lines.append(f"  {ip}  TCP  {type(exc).__name__}: {exc}")
        finally:
            if tcp is not None:
                tcp.close()
        return lines

    out = [f"{domain} -> {', '.join(edges)}"]
    for ip in edges:
        out.extend(await asyncio.to_thread(one_edge, ip))

    udp_dead = all("UDP  no answer" in line for line in out if "  UDP  " in line)
    tcp_alive = any("SIP/2.0" in line for line in out if "  TCP  " in line)
    if udp_dead and tcp_alive:
        out.append("UDP gets no answer on any edge while TCP does: the network")
        out.append("path is dropping UDP, not a fault in sw.")
    elif udp_dead:
        out.append("no edge answered over UDP - check the network path before")
        out.append("changing anything here.")
    return out


def trace_path() -> Path:
    """Where `sip_trace` writes. One file, replaced each time tracing starts.

    A SIP message is twenty lines and the panel's feed shows eight, so the
    trace cannot go there — and stderr is worse, because Textual owns the
    screen and anything written to it corrupts the display or vanishes. A file
    is also what gets pasted into a ticket.
    """
    from platformdirs import user_log_dir

    return Path(user_log_dir("swsh")) / "sip-trace.log"


class _Tracer:
    """Routes `baresip.native.sip` records to `trace_path()` while tracing.

    The stack logs every SIP message to that logger at **DEBUG**, and the
    library attaches nothing but a `NullHandler` — output is the
    application's decision. So `sip_trace=True` on its own produces no
    output anywhere, which is how the one diagnostic knob this module ships
    came to be recommended for days while emitting nothing.

    Two things are needed together, and neither is enough alone: the native
    log level has to be `debug` or the message never reaches Python, and a
    handler has to exist or it is dropped once it gets there.
    """

    LOGGER = "baresip.native.sip"

    def __init__(self) -> None:
        self._handler: logging.Handler | None = None

    def start(self) -> Path | None:
        self.stop()
        path = trace_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(path, mode="w", encoding="utf8")
        except OSError:
            return None
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        handler.setLevel(logging.DEBUG)
        logger = logging.getLogger(self.LOGGER)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        self._handler = handler
        return path

    def stop(self) -> None:
        if self._handler is None:
            return
        logging.getLogger(self.LOGGER).removeHandler(self._handler)
        try:
            self._handler.close()
        except Exception:
            pass
        self._handler = None


@dataclass(frozen=True)
class Device:
    """One SIP identity: what the dashboard shows on a SIP endpoint.

    `password` is write-only on the platform — Fabric never returns it — so it
    is asked for rather than read back. That is not a gap in this module; it is
    the reason the form has a password box.
    """

    username: str
    password: str
    domain: str
    audio: str = "coreaudio"
    # Empty means "name no transport", which is the shape that routes; see
    # the note on TRANSPORTS. "udp", "tcp" and "tls" all put the parameter in
    # the request URI, because that is the only place baresip reads it from.
    transport: str = ""
    codecs: tuple[str, ...] = ()
    auto_answer: bool = True
    caller_id: str = ""
    # Interop knobs. Every one of these is a real baresip setting and the
    # reason each is here is a call that does not work without it:
    #   registrar   send to a proxy that is not the AOR's domain
    #   auth_user   the auth username differs from the SIP user
    #   dtmf_mode   the far end wants SIP INFO, or in-band, not RFC 2833
    #   reg_interval a registrar that expires faster than the default 600s
    #   rtp_timeout  drop a call whose audio has stopped arriving
    #   sip_trace   put the signalling in the log, which is how any of the
    #               above gets diagnosed in the first place
    registrar: str = ""
    auth_user: str = ""
    dtmf_mode: str = "rtpevent"
    reg_interval: int = 600
    rtp_timeout: int = 0
    sip_trace: bool = False
    # A device that does not register dials directly, peer to peer. SignalWire
    # endpoints always register; a loopback bench (`scripts/verify_softphone.py`)
    # has no registrar to register with, and saying so beats pretending.
    register: bool = True
    # Advanced, and the reason the bench works: which interface the stack binds
    # (discovery deliberately skips loopback) and any baresip directive the
    # fields above do not model, `sip_listen` being the one that matters.
    net_interface: str = ""
    extra_config: str = ""

    @property
    def aor(self) -> str:
        return f"sip:{self.username}@{self.domain}"

    @property
    def transport_label(self) -> str:
        """The transport, said so that "unnamed" is not read as "unknown".

        A blank knob is a decision — send no parameter — and rendering it as an
        empty cell would make the one setting that decides the request URI look
        unset. The transport still in force is named alongside it.
        """
        if not self.transport:
            return f"{TRANSPORT_DEFAULT} (unnamed)"
        return self.transport


@dataclass
class Line:
    """The call the device is on, as the panel needs to render it."""

    state: str = "idle"          # idle | calling | ringing | up | ended
    peer: str = ""
    direction: str = ""          # in | out
    since: float = field(default_factory=time.time)
    reason: str = ""

    @property
    def seconds(self) -> float:
        return max(0.0, time.time() - self.since)

    @property
    def busy(self) -> bool:
        return self.state in ("calling", "ringing", "up")


class Softphone:
    """A registered device and at most one call.

    `on_change` is called (on the event loop) whenever anything a panel renders
    moves: registration, call state, a new log line. The cockpit hands it
    `app.call_from_thread`-free repaints because baresip delivers its events on
    the asyncio loop already.
    """

    LOG_LINES = 200

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self.state: str = OFFLINE
        self.error: str = ""
        self.device: Device | None = None
        self.line = Line()
        self.log: list[tuple[float, str]] = []
        # The URI the stack was last handed, kept because the request line is
        # built from it and it is the first thing to check when a call rings
        # nothing. `diagnostics` reports it.
        self.last_dial: str = ""
        self._on_change = on_change
        self._runtime: Any = None
        self._ua: Any = None
        self._call: Any = None
        self._tracer = _Tracer()

    # ------------------------------------------------------------------ status

    @property
    def registered(self) -> bool:
        return self.state == REGISTERED

    @property
    def on_call(self) -> bool:
        return self._call is not None and self.line.busy

    def note(self, text: str) -> None:
        """Add a line to the device's own feed, newest last."""
        self.log.append((time.time(), text))
        del self.log[: max(0, len(self.log) - self.LOG_LINES)]
        self._changed()

    def _changed(self) -> None:
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:  # a repaint must never take the phone down
                pass

    # ----------------------------------------------------------- registration

    async def start(self, device: Device) -> None:
        """Bring the stack up and register. Replaces any current device."""
        baresip = _stack()
        await self.stop()

        self.device = device
        self.state = REGISTERING
        self.error = ""
        # The transport is named because naming one puts it in the request URI
        # *and* the To header of every INVITE, and a URI parameter there is
        # what stops an E.164 target routing to the PSTN. See `aor_of` and
        # `scripts/probe_invite_uri.py`.
        self.note(f"{'registering' if device.register else 'starting'} "
                  f"{device.aor} over {device.transport_label}")

        # A trace that the native stack filters out never reaches Python, so
        # the level follows the knob rather than sitting at "error".
        traced = bool(device.sip_trace)
        path = self._tracer.start() if traced else None
        config = baresip.Config(
            audio_driver=device.audio,
            native_log_level="debug" if traced else "error",
            max_concurrent_calls=1,
            net_interface=device.net_interface or None,
            rtp_timeout=max(0, int(device.rtp_timeout or 0)),
            sip_trace=traced,
            extra_config_text=device.extra_config,
        )
        if traced:
            self.note(f"tracing SIP to {path}" if path
                      else "could not open the SIP trace file")
        try:
            self._runtime = baresip.Runtime()
            await self._runtime.start(config)
            self._runtime.subscribe(self._on_stack_event)
            # An AOR string rather than the Account object, because that is
            # the only way to register without a transport parameter on the
            # URI — the parameter the far end mistakes for a SIP address.
            self._ua = await baresip.UserAgent.create(
                self._runtime, aor_of(device))
            self._ua.on_incoming(self._on_incoming)
            if device.register:
                await self._ua.register()
        except Exception as exc:
            self.state = FAILED
            self.error = f"{type(exc).__name__}: {exc}"
            self.note(self.error)
            await self._teardown()
            raise SoftphoneError(self.error) from exc
        self.state = REGISTERED
        self.note("registered" if device.register else "ready (no registrar)")

    async def stop(self) -> None:
        """Hang up, unregister and free the stack. Safe to call when offline."""
        if self._runtime is None:
            self.state = OFFLINE
            return
        try:
            if self._call is not None:
                await self._safe(self._call.hangup())
            if self._ua is not None:
                await self._safe(self._ua.unregister())
        finally:
            await self._teardown()
            self.state = OFFLINE
            self.line = Line()
            self.note("offline")

    async def _teardown(self) -> None:
        self._tracer.stop()
        runtime, self._runtime, self._ua, self._call = self._runtime, None, None, None
        if runtime is not None:
            try:
                await runtime.close()
            except Exception:
                pass

    @staticmethod
    async def _safe(awaitable: Any) -> None:
        try:
            await awaitable
        except Exception:
            pass

    # ------------------------------------------------------------------- calls

    async def dial(self, target: str) -> None:
        """Place a call. `target` may be a name, a number or a full URI."""
        if self._ua is None:
            raise SoftphoneError("the device is not registered")
        if self.on_call:
            raise SoftphoneError("already on a call")
        uri = dial_uri(target, self.device.domain if self.device else "")
        self.last_dial = uri
        self.line = Line(state="calling", peer=uri, direction="out")
        # Say what the target became. Whether the user part is E.164 is what
        # decides PSTN vs a lookup inside the space, so it is the first thing
        # to check when a call rings nothing.
        typed = (target or "").strip()
        became = user_part(uri)
        if is_phone_number(typed) and became != typed:
            self.note(f"dialing {uri}  ({typed} -> {became})")
        else:
            self.note(f"dialing {uri}")
        try:
            call = await self._ua.dial(uri)
        except Exception as exc:
            self.line = Line(state="ended", peer=uri, direction="out",
                             reason=f"{type(exc).__name__}: {exc}")
            self.note(self.line.reason)
            raise SoftphoneError(self.line.reason) from exc
        self._attach(call, direction="out")

    async def answer(self) -> None:
        if self._call is None:
            raise SoftphoneError("no call to answer")
        await self._call.answer()
        self.note("answered")

    async def hangup(self) -> None:
        if self._call is None:
            raise SoftphoneError("no call to hang up")
        await self._call.hangup()
        self.note("hung up")

    async def send_dtmf(self, digits: str) -> None:
        if self._call is None:
            raise SoftphoneError("no call to send digits on")
        await self._call.send_dtmf(digits)
        self.note(f"dtmf {digits}")

    def _attach(self, call: Any, *, direction: str) -> None:
        # The runtime subscription already carries this call's events; adding a
        # per-call listener too delivers every one of them twice, which doubles
        # the feed and looks like the stack stuttering.
        self._call = call
        peer = getattr(call, "peer", "") or self.line.peer
        # Outbound is "calling" until the far end rings; inbound is already
        # ringing here, because the INVITE is what woke us.
        self.line = Line(state="calling" if direction == "out" else "ringing",
                         peer=peer, direction=direction)
        self._changed()

    def _on_incoming(self, call: Any) -> None:
        """An inbound INVITE. Answer it or leave it to the screen."""
        self._attach(call, direction="in")
        self.note(f"incoming from {getattr(call, 'peer', '?')}")
        if self.device is not None and self.device.auto_answer:
            # The callback runs on the loop, so a task is the way to answer
            # without blocking the stack's delivery of the next event.
            asyncio.get_running_loop().create_task(self._answer_quietly(call))

    async def _answer_quietly(self, call: Any) -> None:
        try:
            await call.answer()
        except Exception as exc:
            self.note(f"could not answer: {exc}")

    # ------------------------------------------------------------------ events

    def _on_stack_event(self, event: Any) -> None:
        """Translate one stack event into state and a line of feed.

        Only the events that change what the panel says are named; the rest are
        logged by name, which is what makes a surprise visible instead of
        silently dropped.
        """
        name = getattr(getattr(event, "event", None), "name", str(event))
        peer = getattr(event, "peer", None) or self.line.peer
        text = getattr(event, "text", "") or ""

        if name == "REGISTER_OK":
            self.state = REGISTERED
            self.error = ""
        elif name == "REGISTER_FAIL":
            self.state = FAILED
            self.error = text or "registration failed"
        elif name in ("CALL_RINGING", "CALL_PROGRESS"):
            self.line.state = "ringing"
            self.line.peer = peer
        elif name in ("CALL_ESTABLISHED", "CALL_ANSWERED"):
            if self.line.state != "up":
                self.line = Line(state="up", peer=peer, direction=self.line.direction)
        elif name == "CALL_CLOSED":
            self.line = Line(state="ended", peer=peer,
                             direction=self.line.direction, reason=text)
            self._call = None
        elif name == "CALL_INCOMING":
            self.line.peer = peer

        if name not in ("CALL_RTCP", "VU_TX", "VU_RX"):  # per-packet noise
            self.note(f"{name.lower()}{f'  {text}' if text else ''}")
        else:
            self._changed()
