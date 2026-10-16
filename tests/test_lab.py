"""The lab: a SIP device and a local AI agent.

Two subsystems that exist to test each other, so the tests are about the seams
between them and the platform: what the device dials, what the agent serves,
what gets created in Call Fabric and — the part that matters most — what gets
deleted again.

Nothing here opens a socket to the internet. The agent is genuinely served and
genuinely fetched over 127.0.0.1, because "does it answer with SWML" is not a
question worth mocking. The SIP call itself is the one thing that cannot be
done in-process (the stack allows one runtime per process), and
`scripts/verify_softphone.py` is the probe that covers it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx
import pytest
from textual.widgets import Button, Input

from swsh import agentlab, softphone
from swsh.config import Profile
from swsh.tui.app import SwshApp

FAKE = Profile(name="test", project="proj-1", token="tok", space="example.signalwire.com")


class FakeClient:
    """Records every registry call and hands back plausible rows."""

    def __init__(self, fail_on: str = "") -> None:
        self.calls: list[tuple[str, str, str | None, dict | None]] = []
        self.fail_on = fail_on

    async def invoke(self, resource: Any, op: str, *, resource_id: str | None = None,
                     body: dict | None = None, **params: Any) -> Any:
        self.calls.append((resource.key, op, resource_id, body))
        if self.fail_on and resource.key == self.fail_on and op == "create":
            raise RuntimeError("the platform said no")
        if op == "create":
            return {"id": f"{resource.key}-1"}
        return {}

    def ops(self) -> list[tuple[str, str]]:
        return [(key, op) for key, op, _, _ in self.calls]


class TestTheDeviceKnowsWhereToRegisterAndWhatToDial:
    async def test_the_sip_domain_is_read_not_derived(self):
        """The domain carries a per-space SIP identifier.

            space   example.signalwire.com
            SIP     example-0123456789ab.sip.signalwire.com

        `0123456789ab` is configurable per space and appears nowhere in the
        host, so `<space>.sip.signalwire.com` is a domain that does not resolve
        and a registration that cannot succeed. It lives on the SIP profile.
        """
        class Profiled:
            async def invoke(self, resource, op, **kw):
                assert resource.key == "sipprofile" and op == "read"
                return {"domain": "example-0123456789ab.sip.signalwire.com"}

        assert await softphone.domain_of(Profiled()) \
            == "example-0123456789ab.sip.signalwire.com"
        # and there is no function left that could build one from the config
        assert not hasattr(softphone, "sip_domain")

    async def test_an_unreadable_profile_is_an_empty_string_not_a_crash(self):
        class Broken:
            async def invoke(self, resource, op, **kw):
                raise RuntimeError("network down")

        assert await softphone.domain_of(Broken()) == ""

    def test_nothing_builds_a_domain_out_of_the_configured_space(self):
        """The config must not be able to reach a SIP domain at all.

        A domain derived from the space is missing that space's SIP identifier,
        so it does not resolve — a plausible wrong value that sends calls
        nowhere. The derivation is gone rather than merely unused.
        """
        import inspect

        source = inspect.getsource(softphone) + inspect.getsource(agentlab)
        assert ".sip.signalwire.com" not in source
        assert "sip_domain" not in source

    def test_a_phone_number_is_normalised_to_e164(self):
        """E.164 in the user part is what sends a call to the PSTN.

        Everything is a URI — `UserAgent.dial` takes one and the stack refuses
        anything else. What decides where the call goes is the user part:
        SignalWire routes an E.164 number out to the PSTN and looks anything
        else up *inside* the space, which is why
        `2095550183` rang nothing while `+12095550183` connects.
        """
        domain = "example-0123456789ab.sip.signalwire.com"
        wanted = f"sip:+15551234567@{domain}"
        assert softphone.dial_uri("+15551234567", domain) == wanted
        assert softphone.dial_uri("15551234567", domain) == wanted   # NANP CC
        assert softphone.dial_uri("5551234567", domain) == wanted    # assumed NANP
        assert softphone.dial_uri("+1 (555) 123-4567", domain) == wanted

    def test_every_target_carries_the_sip_scheme(self):
        """The stack refuses a target without one, and this was got wrong.

        `ua_connect` does not complete the scheme. A scheme-less target fails
        locally, before an INVITE exists — with ENOENT or ENOSYS depending on
        the host, so the message is not worth matching on. That was read off
        the stack by `scripts/probe_dial_uri.py`, which is how to settle this
        rather than reasoning about the string.

        So the scheme is not a routing decision. The *user part* is: see
        `test_a_number_is_dialled_as_e164_so_it_reaches_the_pstn`.
        """
        domain = "example-0123456789ab.sip.signalwire.com"
        for typed in ("+15551234567", "5551234567", "1001", "support",
                      "tel:+15551234567", "a@b.com", "sip:x@y.com"):
            assert softphone.dial_uri(typed, domain).startswith("sip:")

    def test_a_sips_target_is_refused_not_quietly_downgraded(self):
        """The stack cannot dial one. Asking for TLS and silently getting
        cleartext is worse than being told no."""
        with pytest.raises(softphone.SoftphoneError, match="sips:"):
            softphone.dial_uri("sips:bob@example.net",
                               "example-0123456789ab.sip.signalwire.com")

    def test_a_tel_uri_is_rewritten_onto_the_domain(self):
        """`tel:` is ENOSYS in this build, so it cannot be passed through."""
        domain = "example-0123456789ab.sip.signalwire.com"
        assert softphone.dial_uri("tel:+15551234567", domain) \
            == f"sip:+15551234567@{domain}"

    def test_an_extension_is_left_alone(self):
        """A short number is an extension or a short code, not a PSTN number."""
        domain = "example-0123456789ab.sip.signalwire.com"
        assert softphone.dial_uri("1001", domain) == f"sip:1001@{domain}"
        assert softphone.dial_uri("911", domain) == f"sip:911@{domain}"

    def test_a_typed_plus_always_wins(self):
        """The NANP assumption only applies to a bare 10-digit number."""
        domain = "example-0123456789ab.sip.signalwire.com"
        assert softphone.dial_uri("+442071234567", domain) \
            == f"sip:+442071234567@{domain}"

    def test_the_dial_log_cannot_crash_the_call(self):
        """`dial` reported what the target became, by index.

        `uri.split(":", 1)[1]` assumed a `sip:` prefix. Removing that prefix
        made every target scheme-less, so placing a call raised
        `IndexError: list index out of range` from inside a worker — the call
        never went out and the app dumped a traceback.
        """
        domain = "example-0123456789ab.sip.signalwire.com"
        for typed in ("+15551234567", "5551234567", "1001", "911", "support",
                      "sip:x@y.com", "a@b.com", "tel:+15551234567",
                      "x@host:5060", "sip:x@host:5060"):
            uri = softphone.dial_uri(typed, domain)
            softphone.user_part(uri)  # must not raise, whatever the shape

    def test_a_port_is_not_mistaken_for_the_user(self):
        """Reading the user part from the right (`rpartition`) turns
        `x@host:5060` into `5060`."""
        assert softphone.user_part("x@y.com:5060") == "x"
        assert softphone.user_part("sips:bob@example.net:5061") == "bob"
        assert softphone.user_part("tel:+15551234567") == "+15551234567"
        assert softphone.user_part("+15551234567@acme.test") == "+15551234567"

    def test_no_domain_is_an_error_not_a_call_to_nowhere(self):
        with pytest.raises(softphone.SoftphoneError, match="no SIP domain"):
            softphone.dial_uri("+15551234567", "")

    def test_a_name_still_belongs_to_the_spaces_own_domain(self):
        domain = "example-0123456789ab.sip.signalwire.com"
        assert softphone.dial_uri("support", domain) == f"sip:support@{domain}"
        # anything already addressed keeps its own host
        assert softphone.dial_uri("sip:x@other.test", domain) == "sip:x@other.test"
        assert softphone.dial_uri("x@other.test", domain) == "sip:x@other.test"

    def test_nothing_to_dial_is_an_error_not_a_call_to_nowhere(self):
        with pytest.raises(softphone.SoftphoneError):
            softphone.dial_uri("  ", "example-0123456789ab.sip.signalwire.com")

    async def test_dialling_without_a_device_says_so(self):
        phone = softphone.Softphone()
        with pytest.raises(softphone.SoftphoneError, match="not registered"):
            await phone.dial("support")

    async def test_a_missing_stack_names_the_install_line(self, monkeypatch):
        """An optional dependency that is not there is a setup step, not a
        traceback."""
        def missing() -> Any:
            raise softphone.SoftphoneError(
                f"the SIP stack did not load: {softphone.INSTALL_HINT}")

        monkeypatch.setattr(softphone, "_stack", missing)
        phone = softphone.Softphone()
        with pytest.raises(softphone.SoftphoneError, match="pip install"):
            await phone.start(softphone.Device("u", "p", "d"))

    def test_the_install_line_names_the_distribution_not_the_console_script(self):
        """`sw` is the command; `swsh` is the package.

        The hint said `pip install --pre 'sw[sip]'`, and `sw` on PyPI is an
        unrelated 1.2kB project by someone else. pip installed *that*, warned
        "sw 0.0.1 does not provide the extra 'sip'" in the middle of its own
        output, exited 0, and the phone then correctly reported a SIP stack
        that had never been asked for. The name in the hint has to be the one
        in `[project] name`, whatever else about the install changes.
        """
        import tomllib

        pyproject = tomllib.loads(
            (Path(__file__).resolve().parents[1] / "pyproject.toml").read_bytes().decode())
        dist = pyproject["project"]["name"]
        assert dist == "swsh"
        assert dist in softphone.INSTALL_HINT
        # never the console script as though it were a package
        assert not re.search(r"(?<![\w-])sw(?![\w-])", softphone.INSTALL_HINT)

    def test_the_sip_stack_ships_with_sw(self):
        """It was an extra, which meant the cockpit's phone was a second install
        step nobody took, and `sw sh` opened on a panel saying so. It is a
        dependency now: `pip install swsh` gets a working phone on every
        platform the stack publishes wheels for.

        The specifier names a pre-release on purpose. pip refuses pre-release
        versions unless the specifier itself mentions one, so `>=0.5.1a1` is
        what makes this resolve with no `--pre` at the call site.
        """
        import tomllib

        pyproject = tomllib.loads(
            (Path(__file__).resolve().parents[1] / "pyproject.toml").read_bytes().decode())
        deps = pyproject["project"]["dependencies"]
        sip = next((d for d in deps if d.startswith("baresip-python")), None)
        assert sip is not None, deps
        assert re.search(r"\d+\.\d+\.\d+(a|b|rc)\d+", sip), sip
        assert "sip" not in pyproject["project"].get("optional-dependencies", {})

    @pytest.mark.parametrize(("sys_platform", "release", "machine", "expected"), [
        ("darwin", "25.0.0", "arm64", True),            # macOS 26
        ("darwin", "24.6.0", "x86_64", True),           # macOS 15, Intel
        ("darwin", "23.6.0", "arm64", False),           # macOS 14: no wheel
        ("linux", "6.8.0-1015-aws", "x86_64", True),
        ("linux", "6.8.0", "aarch64", True),
        ("linux", "6.1.0", "armv7l", False),
        ("win32", "11", "AMD64", False),
    ])
    def test_the_dependency_marker_and_the_runtime_check_agree(
        self, monkeypatch, sys_platform, release, machine, expected
    ):
        """pyproject.toml decides where the stack is installed, and
        `platform_supported()` decides what the panel says when it is missing.
        If they disagreed, a platform would be told to reinstall a phone it can
        never get, or get no hint where reinstalling would fix it."""
        import platform
        import sys
        import tomllib

        from packaging.requirements import Requirement

        pyproject = tomllib.loads(
            (Path(__file__).resolve().parents[1] / "pyproject.toml").read_bytes().decode())
        dep = next(d for d in pyproject["project"]["dependencies"]
                   if d.startswith("baresip-python"))
        marker = Requirement(dep).marker
        assert marker is not None, "the stack must not be required where it has no wheel"
        assert marker.evaluate({"sys_platform": sys_platform, "platform_release": release,
                                "platform_machine": machine}) is expected

        monkeypatch.setattr(sys, "platform", sys_platform)
        monkeypatch.setattr(platform, "release", lambda: release)
        monkeypatch.setattr(platform, "machine", lambda: machine)
        assert softphone.platform_supported() is expected

    def test_an_unsupported_platform_is_told_so_not_told_to_reinstall(self, monkeypatch):
        monkeypatch.setattr(softphone, "platform_supported", lambda: False)
        assert "not available on this platform" in softphone.unavailable_reason()
        assert "pip install" not in softphone.unavailable_reason()
        assert "pip install" not in softphone.unavailable_hint()

    def test_a_supported_platform_without_the_stack_gets_the_reinstall_line(self, monkeypatch):
        monkeypatch.setattr(softphone, "platform_supported", lambda: True)
        assert softphone.INSTALL_HINT in softphone.unavailable_reason()
        assert softphone.unavailable_hint() == softphone.INSTALL_HINT


class TestTheStacksEventsBecomeStateAPanelCanRender:
    """The translation is the whole of the phone's UI contract."""

    def event(self, name: str, **kw: Any) -> Any:
        return type("E", (), {"event": type("N", (), {"name": name}),
                              "peer": kw.get("peer", ""), "text": kw.get("text", "")})

    def test_registration_moves_the_state(self):
        phone = softphone.Softphone()
        phone._on_stack_event(self.event("REGISTER_OK"))
        assert phone.state == softphone.REGISTERED
        phone._on_stack_event(self.event("REGISTER_FAIL", text="403 forbidden"))
        assert phone.state == softphone.FAILED and "403" in phone.error

    def test_a_call_runs_ringing_up_and_ended(self):
        phone = softphone.Softphone()
        phone._on_stack_event(self.event("CALL_RINGING", peer="sip:a@b"))
        assert phone.line.state == "ringing"
        phone._on_stack_event(self.event("CALL_ESTABLISHED", peer="sip:a@b"))
        assert phone.line.state == "up" and phone.line.peer == "sip:a@b"
        phone._on_stack_event(self.event("CALL_CLOSED", peer="sip:a@b", text="bye"))
        assert phone.line.state == "ended" and phone.line.reason == "bye"
        assert phone.on_call is False

    def test_the_feed_keeps_what_happened_but_not_the_packet_noise(self):
        phone = softphone.Softphone()
        phone._on_stack_event(self.event("CALL_RTCP"))
        phone._on_stack_event(self.event("CALL_ESTABLISHED"))
        lines = [text for _, text in phone.log]
        assert "call_established" in lines
        assert not any("rtcp" in line for line in lines)

    def test_a_repaint_that_raises_cannot_take_the_phone_down(self):
        def boom() -> None:
            raise RuntimeError("the screen is gone")

        phone = softphone.Softphone(on_change=boom)
        phone.note("still here")  # must not raise
        assert phone.log


class TestTheAgentIsBuiltFromValues:
    def test_a_name_becomes_a_slug_a_route_and_a_user(self):
        spec = agentlab.AgentSpec(name="Front Desk!!")
        assert agentlab.slug(spec.name) == "front-desk"
        assert spec.route == "/front-desk"

    def test_the_webhook_url_carries_the_credentials_and_the_trailing_slash(self):
        """Both of these are silent failures when wrong: no auth is a 401 the
        platform never reports, and no slash is a 200 whose body is `null`."""
        url = agentlab.webhook_url("https://x.ngrok.app", "/front-desk", ("u", "p"))
        assert url == "https://u:p@x.ngrok.app/front-desk/"

    def test_a_dial_target_prefers_what_the_address_said(self):
        known, ok = agentlab.dial_target(
            {"sip_uri": "sip:real@example-0123456789ab.sip.signalwire.com"},
            user="front-desk")
        assert known == "sip:real@example-0123456789ab.sip.signalwire.com" and ok is True

        # The project's real domain is a fact off the SIP profile.
        real, ok = agentlab.dial_target(
            {}, user="front-desk", domain="example-0123456789ab.sip.signalwire.com")
        assert real == "sip:front-desk@example-0123456789ab.sip.signalwire.com"
        assert ok is True

        # With no domain to read there is no target — nothing is invented.
        nothing, ok = agentlab.dial_target({}, user="front-desk")
        assert nothing == "" and ok is False

    def test_the_prompt_and_skills_reach_the_agent(self):
        agent = agentlab.build_agent(agentlab.AgentSpec(
            name="probe", prompt="Be brief.", greeting="Hello there.",
            skills=("datetime",)))
        sections = json.dumps(agent.get_prompt())
        assert "Be brief." in sections and "Hello there." in sections
        assert "datetime" in agent.list_skills()

    def test_an_unknown_skill_fails_at_build_time_not_at_call_time(self):
        with pytest.raises(agentlab.AgentLabError, match="no-such-skill"):
            agentlab.build_agent(agentlab.AgentSpec(skills=("no-such-skill",)))


class TestStandingTheAgentUp:
    """The lab really serves, and really cleans up. No network: the tunnel is
    handed a public URL, which is the documented way to skip ngrok."""

    async def start(self, lab: agentlab.AgentLab, client: FakeClient, port: int):
        spec = agentlab.AgentSpec(name="probe agent", port=port, skills=())
        return await lab.start(client, spec,
                               public_url=f"http://127.0.0.1:{port}")

    async def test_it_serves_swml_over_http_and_wires_fabric_to_it(self):
        lab, client = agentlab.AgentLab(), FakeClient()
        live = await self.start(lab, client, 3061)
        try:
            assert lab.running
            # The document, fetched the way the platform fetches it.
            async with httpx.AsyncClient(timeout=10) as http:
                answer = await http.post(live.webhook_url, json={})
                assert answer.status_code == 200
                document = answer.json()
                assert document["sections"]["main"][-1]["ai"]["prompt"]
                # and unauthenticated it is refused, so the credentials in the
                # URL are load-bearing rather than decorative
                bare = await http.get("http://127.0.0.1:3061/probe-agent/")
                assert bare.status_code == 401

            # The profile read is how the dial target gets the project's real
            # SIP domain; it creates nothing.
            assert client.ops() == [("swmlhooks", "create"), ("sipaddr", "create"),
                                    ("sipprofile", "read")]
            hook_body = client.calls[0][3]
            assert hook_body["primary_request_url"] == live.webhook_url
            address_body = client.calls[1][3]
            assert address_body["calling_handler_resource_id"] == "swmlhooks-1"
            # FakeClient's sip_profile read returns nothing, so there is no
            # domain and therefore no dial target — not an invented one.
            assert live.dial == ""
        finally:
            await lab.stop(client=client)

    async def test_stopping_deletes_what_it_made_newest_first(self):
        lab, client = agentlab.AgentLab(), FakeClient()
        await self.start(lab, client, 3062)
        await lab.stop(client=client)
        assert client.ops()[-2:] == [("sipaddr", "delete"), ("swmlhooks", "delete")]
        assert lab.state == agentlab.STOPPED and lab.live is None

    async def test_a_failure_part_way_through_unwinds_what_it_already_made(self):
        """The SIP address is refused. The webhook resource that was created a
        moment earlier must not be left pointing at a tunnel that is closing."""
        lab, client = agentlab.AgentLab(), FakeClient(fail_on="sipaddr")
        with pytest.raises(agentlab.AgentLabError):
            await self.start(lab, client, 3063)
        assert lab.state == agentlab.FAILED
        assert ("swmlhooks", "delete") in client.ops()

    async def test_the_port_is_free_again_afterwards(self):
        """A lab that cannot be restarted is a lab you restart the app to use."""
        for _ in range(2):
            lab, client = agentlab.AgentLab(), FakeClient()
            await self.start(lab, client, 3064)
            await lab.stop(client=client)


class TestThePhoneIsAPanelOnCalls:
    """It was a view of its own called the lab, and that was the problem.

    A softphone exists to make a call happen and the thing worth watching
    while it does is the event feed, which is on the calls view. Two views
    meant dialling on one and watching on the other.
    """

    async def test_it_shows_on_calls_and_nowhere_else(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            await pilot.pause()
            # not on the dashboard
            assert app.query_one("#phone").display is False
            app.action_go_calls()
            await pilot.pause()
            assert app.query_one("#phone").display is True
            # and not over a table of rows, where it would be a dial pad
            # under a list of SIP gateways. `_load` is stubbed because the
            # assertion is about the layout, and letting it fetch leaves a
            # worker running past the end of the test.
            app._load = lambda *a, **kw: None
            app.switch_to("numbers")
            await pilot.pause()
            assert app.view == "rows"
            assert app.query_one("#phone").display is False

    async def test_the_names_people_type_for_it_land_on_calls(self):
        """`:lab` has to keep working or it is an error on a screen that used
        to exist, which is worse than a rename."""
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            await pilot.pause()
            for name in ("lab", "phone", "softphone"):
                app.action_go_home()
                await pilot.pause()
                app.switch_to(name)
                await pilot.pause()
                assert app.view == "calls", name

    async def test_there_is_no_lab_view_left(self):
        """One spelling, the same rule `sw sh` itself follows."""
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            await pilot.pause()
            assert not hasattr(app, "action_go_lab")
            assert not app.query("#menu-lab")
            assert not app.query("#lab")

    async def test_the_footer_offers_the_phone_keys_only_on_calls(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            await pilot.pause()
            for action in ("lab_register", "lab_standup", "lab_call"):
                assert app.check_action(action, ()) is False
            app.action_go_calls()
            await pilot.pause()
            for action in ("lab_register", "lab_standup", "lab_call"):
                assert app.check_action(action, ()) is True

    async def test_the_hook_is_withheld_until_there_is_a_device(self):
        """With no device it has nothing to dial from, and the only answer it
        could give is a toast saying so."""
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            app.action_go_calls()
            await pilot.pause()
            assert app.check_action("hook", ()) is False
            app.phone.device = softphone.Device("alice", "pw", "acme.sip.example")
            assert app.check_action("hook", ()) is True

    async def test_calling_the_agent_before_it_exists_says_what_to_do(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            app.action_go_calls()
            await pilot.pause()
            notes: list[str] = []
            app.notify = lambda message, **kw: notes.append(str(message))
            app.action_lab_call()
            assert any("stand the agent up" in note for note in notes)

    async def test_the_panel_renders_both_halves(self):
        """Guarded on the stack: with none installed the panel is one line —
        the install hint — and neither half has anything to render."""
        pytest.importorskip("baresip", reason="no SIP wheel for this platform")
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            app.action_go_calls()
            app.lab.state = agentlab.RUNNING
            app.lab.live = agentlab.Live(
                spec=agentlab.AgentSpec(name="front desk"),
                public_url="https://x.ngrok.app", resource_id="wh-1",
                dial="sip:front-desk@example-0123456789ab.sip.signalwire.com")
            app.phone.state = softphone.REGISTERED
            app.phone.device = softphone.Device(
                "alice", "pw", "example-0123456789ab.sip.signalwire.com")
            app._render_phone()
            await pilot.pause()

            # who the phone is: the border title, which has the width for it
            title = app.query_one("#phone").border_title
            assert "sip:alice@example-0123456789ab.sip.signalwire.com" in title
            assert "registered" in title

            from io import StringIO

            from rich.console import Console
            console = Console(file=StringIO(), width=160, no_color=True)
            console.print(app.query_one("#phone-state").content)
            text = console.file.getvalue()
            # what it is doing: the column. The agent's address loses the
            # domain, which is the device's own and already in the title.
            assert "agent running" in text
            assert "front-desk" in text
            assert "example-0123456789ab.sip.signalwire.com" not in text


class TestThePanelFitsTheColumnItSharesWithTheTable:
    """It shares the left column with the live calls table, and the table has
    `height: 1fr`. Left to grow, the switcher holding it took the whole column
    and the panel below was laid out past the bottom of the screen: present,
    queryable, and never painted."""

    async def test_every_row_of_it_is_on_screen(self):
        for width in (100, 130, 180, 250):
            app = SwshApp(profile=FAKE)
            async with app.run_test(size=(width, 38)) as pilot:
                await pilot.pause()
                app.action_go_calls()
                await pilot.pause()
                for sel in ("#phone", "#phone-buttons", "#actionbar"):
                    region = app.query_one(sel).region
                    assert region.y >= 0, (width, sel)
                    assert region.y + region.height <= 38, (width, sel, region)

    async def test_the_pad_is_never_squeezed(self):
        """A key narrower than its label is unreadable and unclickable, so the
        pad is the one column with a floor; the box and the state column flex
        around it."""
        for width in (100, 130, 180, 250):
            app = SwshApp(profile=FAKE)
            async with app.run_test(size=(width, 38)) as pilot:
                await pilot.pause()
                app.action_go_calls()
                await pilot.pause()
                pad = app.query_one("#phone-keypad")
                # A floor, not an exact width: the gutter between keys is a
                # legibility choice that may change, but three keys across
                # never may.
                assert pad.region.width >= 17, (width, pad.region)
                assert pad.region.height >= 4, (width, pad.region)
                for key in app.query("#phone-keypad .key"):
                    assert key.content_size.width >= 1
                    assert key.content_size.height >= 1
                # and nothing else collapses to nothing
                for sel in ("#phone-target", "#phone-hook", "#phone-state"):
                    size = app.query_one(sel).content_size
                    assert size.width >= 1 and size.height >= 1, (width, sel)


class TestThePeerIsShortEnoughToRead:
    """A dialled URI is `sip:+1...@` plus a domain carrying the space's own SIP
    identifier: fifty-odd characters for eleven digits of information."""

    DOMAIN = "example-0123456789ab.sip.signalwire.com"

    def _column(self, peer: str) -> str:
        from io import StringIO

        from rich.console import Console

        from swsh.tui import lab

        phone = softphone.Softphone()
        phone.device = softphone.Device("alice", "pw", self.DOMAIN)
        phone.state = softphone.REGISTERED
        phone.line = softphone.Line(state="up", peer=peer, direction="out")
        console = Console(file=StringIO(), width=120, no_color=True)
        console.print(lab.state(phone, None, available=True))
        return console.file.getvalue()

    def test_our_own_domain_is_dropped(self):
        """It is already in the border title, and folding it across two rows
        pushed the agent's line off the bottom of a four-row column."""
        text = self._column(f"sip:+14405550166@{self.DOMAIN}")
        assert "+14405550166" in text
        assert self.DOMAIN not in text

    def test_another_domain_is_kept(self):
        """That is the case where the domain is the point."""
        text = self._column("sip:bob@elsewhere.example.com")
        assert "bob@elsewhere.example.com" in text

    def test_a_bare_number_survives(self):
        assert "+14405550166" in self._column("+14405550166")


class TestTheHookIsOneButton:
    """A phone has one hook: you cannot dial while on a call and cannot hang
    up when idle, so a Dial button beside a Hang up button meant one of them
    was always dead and the live one was never where you looked."""

    async def test_it_is_green_dial_when_idle_and_red_hangup_on_a_call(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            app.action_go_calls()
            await pilot.pause()
            hook = app.query_one("#phone-hook", Button)
            assert str(hook.label) == "Dial"
            assert hook.has_class("-busy") is False

            app.phone._call = object()
            app.phone.line = softphone.Line(state="up", peer="sip:a@b")
            app._render_phone()
            await pilot.pause()
            assert str(hook.label) == "Hang up"
            assert hook.has_class("-busy") is True

    async def test_the_label_and_the_action_cannot_disagree(self):
        """Both are read from `on_call`, so whichever half the button offers is
        the half the key performs."""
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            app.action_go_calls()
            app.phone.device = softphone.Device("alice", "pw", "acme.sip.example")
            await pilot.pause()
            called: list[str] = []
            app._dial_target = lambda target: called.append(f"dial:{target}")
            app._hangup_device = lambda: called.append("hangup")

            app.query_one("#phone-target", Input).value = "1001"
            app.action_hook()
            assert called == ["dial:1001"]

            app.phone._call = object()
            app.phone.line = softphone.Line(state="up", peer="sip:a@b")
            app.action_hook()
            assert called == ["dial:1001", "hangup"]

    async def test_h_still_means_the_selected_leg_not_our_own_call(self):
        """`h` belongs to the table's vocabulary, the way `e` and `d` do. A key
        that meant one call or the other depending on whether a softphone was
        registered would be a key you have to think about before pressing."""
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            app.action_go_calls()
            app.phone._call = object()
            app.phone.line = softphone.Line(state="up", peer="sip:a@b")
            await pilot.pause()
            hung: list[str] = []
            app._hangup_device = lambda: hung.append("device")
            notes: list[str] = []
            app.notify = lambda message, **kw: notes.append(str(message))

            app.action_hangup()
            # no row selected, so it says so rather than reaching for the phone
            assert hung == []
            assert any("no call selected" in note for note in notes)


class TestTheKeypad:
    """Twelve keys that mean two things, which is the point: DTMF once you are
    connected, digits before you are. The old `s` opened a prompt per burst."""

    async def test_a_key_types_into_the_target_when_idle(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            app.action_go_calls()
            await pilot.pause()
            keys = {str(b.label): b for b in app.query("#phone-keypad .key")}
            assert set(keys) == set("123456789*0#")
            for digit in "2093":
                keys[digit].press()
            await pilot.pause()
            assert app.query_one("#phone-target", Input).value == "2093"

    async def test_a_key_sends_dtmf_once_there_is_a_call(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            app.action_go_calls()
            await pilot.pause()
            sent: list[str] = []
            app._send_dtmf = lambda digits: sent.append(digits)
            app.phone._call = object()
            app.phone.line = softphone.Line(state="up", peer="sip:a@b")

            keys = {str(b.label): b for b in app.query("#phone-keypad .key")}
            keys["5"].press()
            keys["#"].press()
            await pilot.pause()
            assert sent == ["5", "#"]
            # and nothing leaked into the box you dial from
            assert app.query_one("#phone-target", Input).value == ""


class TestTextCanBeSelectedOffTheScreen:
    """Text on the cockpit screen can be selected and copied.

    The clipboard was not the answer. A full-screen app turns on mouse
    reporting, and while that is on the terminal hands every click and drag to
    the app instead of using it to select; OSC 52 does not rescue it either,
    since macOS Terminal ignores it. So the mouse gets handed back.
    """

    async def test_m_toggles_the_mode_and_the_bar_says_so(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            await pilot.pause()
            calls: list[str] = []
            driver = app._driver
            driver._disable_mouse_support = lambda: calls.append("off")
            driver._enable_mouse_support = lambda: calls.append("on")

            assert app.selecting is False
            app.action_select_text()
            await pilot.pause()
            assert app.selecting is True
            assert calls == ["off"]
            # a mode you cannot tell you are in is indistinguishable from the
            # app having hung, so it has to be on the status bar
            from io import StringIO

            from rich.console import Console
            console = Console(file=StringIO(), width=200, no_color=True)
            console.print(app.query_one("#statusbar").content)
            assert "SELECT" in console.file.getvalue()

            app.action_select_text()
            await pilot.pause()
            assert app.selecting is False
            assert calls == ["off", "on"]

    async def test_a_driver_that_cannot_do_it_says_so_rather_than_lying(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            await pilot.pause()
            # The headless driver genuinely has no mouse to release, which
            # is the case this guards: it must refuse rather than flip a mode
            # it cannot honour.
            assert not hasattr(app._driver, "_disable_mouse_support")
            notes: list[str] = []
            app.notify = lambda message, **kw: notes.append(str(message))

            app.action_select_text()
            assert app.selecting is False, "the mode must not flip if it cannot"
            assert any("cannot release the mouse" in note for note in notes)


class TestTheEdgeReportChecksTheNetworkPath:
    """A registration that stops working where it used to is often not a bug.

    When the network path is the cause, the result is indistinguishable from
    "the stack cannot register" until something asks the edges directly.
    """

    async def test_a_domain_that_does_not_resolve_says_so(self):
        lines = await softphone.edge_report("no-such-host.invalid", timeout=0.2)
        assert len(lines) == 1
        assert "did not resolve" in lines[0]

    async def test_it_sends_exactly_one_probe_per_edge_and_transport(self, monkeypatch):
        """A diagnostic sends one probe per edge and transport, and never
        retries."""
        sent: list[tuple[str, str]] = []

        class FakeUDP:
            def settimeout(self, _): pass
            def sendto(self, _data, addr): sent.append(("udp", addr[0]))
            def recvfrom(self, _n): raise TimeoutError
            def close(self): pass

        class FakeTCP:
            def settimeout(self, _): pass
            def sendall(self, _data): pass
            def recv(self, _n): return b"SIP/2.0 200 Keepalive\r\n"
            def close(self): pass

        import socket as socket_module

        monkeypatch.setattr(socket_module, "socket",
                            lambda *a, **kw: FakeUDP())

        def fake_connect(addr, timeout=None):
            sent.append(("tcp", addr[0]))
            return FakeTCP()

        monkeypatch.setattr(socket_module, "create_connection", fake_connect)

        async def fake_getaddrinfo(self, *a, **kw):
            return [(0, 0, 0, "", ("10.0.0.1", 5060)),
                    (0, 0, 0, "", ("10.0.0.2", 5060))]

        import asyncio
        monkeypatch.setattr(asyncio.base_events.BaseEventLoop, "getaddrinfo",
                            fake_getaddrinfo)

        lines = await softphone.edge_report("acme.sip.example", timeout=0.1)

        # one datagram and one connect per edge, and not one more
        assert sorted(sent) == [
            ("tcp", "10.0.0.1"), ("tcp", "10.0.0.2"),
            ("udp", "10.0.0.1"), ("udp", "10.0.0.2")]
        # and it names the network path when UDP is dead everywhere but TCP answers
        assert any("path is dropping UDP" in line for line in lines)

    async def test_it_never_authenticates(self, monkeypatch):
        """An OPTIONS needs no credentials, so a diagnostic never sends any.
        Asserted on the bytes, because that is what the edge sees."""
        payloads: list[bytes] = []

        class FakeUDP:
            def settimeout(self, _): pass
            def sendto(self, data, _addr): payloads.append(data)
            def recvfrom(self, _n): raise TimeoutError
            def close(self): pass

        class FakeTCP:
            def settimeout(self, _): pass
            def sendall(self, data): payloads.append(data)
            def recv(self, _n): return b""
            def close(self): pass

        import asyncio
        import socket as socket_module

        monkeypatch.setattr(socket_module, "socket", lambda *a, **kw: FakeUDP())
        monkeypatch.setattr(socket_module, "create_connection",
                            lambda addr, timeout=None: FakeTCP())

        async def fake_getaddrinfo(self, *a, **kw):
            return [(0, 0, 0, "", ("10.0.0.1", 5060))]

        monkeypatch.setattr(asyncio.base_events.BaseEventLoop, "getaddrinfo",
                            fake_getaddrinfo)

        await softphone.edge_report("acme.sip.example", timeout=0.1)

        assert payloads, "nothing was sent"
        for payload in payloads:
            text = payload.decode()
            assert text.startswith("OPTIONS sip:acme.sip.example")
            lowered = text.lower()
            for forbidden in ("authorization", "proxy-authorization",
                              "auth_pass", "password"):
                assert forbidden not in lowered, forbidden


class TestWhatThePhoneSaysReachesTheFeed:
    """The phone's notes and the platform's call events are one story.

    `registering`, `dialing sip:+1...` and the voice log's `answered` for the
    same call belong in one place, and reading them in two is what made the
    phone worth moving onto this view.
    """

    async def test_notes_are_written_to_the_event_feed(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            app.action_go_calls()
            await pilot.pause()
            written: list[str] = []
            app._log_line = lambda text: written.append(text.plain)

            app.phone.note("registering sip:alice@acme.sip.example over udp")
            app.phone.note("dialing sip:+15551234567@acme.sip.example")
            await pilot.pause()

            assert len(written) == 2
            assert "registering" in written[0]
            assert "phone" in written[0]
            assert "+15551234567" in written[1]

    async def test_each_note_reaches_it_once(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            app.action_go_calls()
            await pilot.pause()
            written: list[str] = []
            app._log_line = lambda text: written.append(text.plain)

            app.phone.note("one")
            app._lab_changed()
            app._lab_changed()
            await pilot.pause()
            assert len([line for line in written if "one" in line]) == 1

    async def test_a_capped_log_catches_up_from_the_tail(self):
        """`Softphone.log` drops from the front, so an index into it stops
        being valid once it is full. Replaying or skipping are both wrong."""
        app = SwshApp(profile=FAKE)
        async with app.run_test(size=(150, 45)) as pilot:
            app.action_go_calls()
            await pilot.pause()
            app._log_line = lambda text: None
            for n in range(softphone.Softphone.LOG_LINES + 20):
                app.phone.note(f"line {n}")
            # the mark never runs past what the log actually holds
            assert app._phone_logged == len(app.phone.log)


class TestTheInteropKnobs:
    """The settings a call that does not work gets fixed with.

    Each is a real baresip setting, and the vocabularies are checked against
    the stack's own signature rather than copied into a list that can drift.
    """

    def _device_form_fields(self):
        app = SwshApp(profile=FAKE)
        return {f.name: f for f in app._device_form().fields}

    def test_the_vocabularies_are_the_stacks_own(self):
        """`transport` and `dtmf_mode` are Literals on `baresip.Account`.

        A value outside them is a TypeError at registration, so offering one in
        a picker would be a keystroke that raises.
        """
        pytest.importorskip("baresip", reason="no SIP wheel for this platform")
        import inspect
        import typing

        import baresip

        params = inspect.signature(baresip.Account).parameters
        assert set(softphone.TRANSPORTS) == set(typing.get_args(params["transport"].annotation))
        assert set(softphone.DTMF_MODES) == set(typing.get_args(params["dtmf_mode"].annotation))

    def test_every_knob_is_a_field_and_a_device_attribute(self):
        fields = self._device_form_fields()
        blank = softphone.Device("", "", "")
        for name in ("transport", "codecs", "dtmf_mode", "registrar", "auth_user",
                     "reg_interval", "rtp_timeout", "sip_trace", "net_interface",
                     "extra_config"):
            assert name in fields, f"{name} is not on the form"
            assert hasattr(blank, name), f"{name} is not on Device"

    def test_the_knobs_hide_until_asked_for(self):
        """Twelve fields on open would bury the five that are always the answer."""
        fields = self._device_form_fields()
        assert fields["advanced"].kind == "bool"
        for name in ("transport", "dtmf_mode", "registrar", "sip_trace"):
            assert fields[name].show_if == ("advanced", ("True",))
        # the five that are always needed are never hidden
        for name in ("username", "password", "domain", "audio", "auto_answer"):
            assert fields[name].show_if is None

    def test_reopening_a_tweaked_device_shows_its_knobs(self):
        """A device set up with a registrar has to show it, not hide it behind
        a tickbox nobody knows to tick."""
        app = SwshApp(profile=FAKE)
        plain = softphone.Device("1001", "pw", "example-0123456789ab.sip.signalwire.com")
        assert app._device_is_tweaked(plain) is False

        tweaked = softphone.Device("1001", "pw", "example-0123456789ab.sip.signalwire.com",
                                   registrar="sip:proxy.example.net", dtmf_mode="info")
        assert app._device_is_tweaked(tweaked) is True


class TestTheTransportIsVisible:
    """Naming one changes the request URI, and it used to show nowhere.

    `Account.aor()` stamps `;transport=X` onto the request URI *and* the `To`
    header of every INVITE, so naming a transport is not a local preference —
    it is a parameter the far end reads. A device sat on TCP through three
    rounds of debugging the URI because no surface said so.
    """

    @staticmethod
    def _rendered(device) -> str:
        from swsh.tui import lab

        class _Phone:
            state, error, log, line = "registered", "", [], softphone.Line()

            def __init__(self, dev):
                self.device = dev

        # The border title, which is where the identity and the transport
        # live: they are the longest strings on the panel and the border is
        # the only full-width strip it has.
        return lab.title(_Phone(device), available=True)

    def test_the_border_title_names_the_transport(self):
        for transport in ("udp", "tcp", "tls"):
            device = softphone.Device(username="alice", password="x",
                                      domain="example-0123456789ab.sip.signalwire.com",
                                      transport=transport)
            assert transport in self._rendered(device)

    def test_the_registration_note_names_it_too(self):
        """The panel is the moment; the log is what is still there after."""
        phone = softphone.Softphone()
        device = softphone.Device(username="alice", password="x",
                                  domain="example-0123456789ab.sip.signalwire.com",
                                  transport="tcp")
        phone.note(f"registering {device.aor} over {device.transport_label}")
        assert "over tcp" in phone.log[-1][1]

    def test_naming_none_is_the_default(self):
        """Because naming one puts it in the request URI. See `aor_of`."""
        assert softphone.Device(username="a", password="b", domain="c").transport == ""

    def test_an_unnamed_transport_still_says_which_one_is_in_force(self):
        """A blank cell would make the setting that decides the URI look unset.

        It is a decision — send no parameter — so the panel says both: what
        travels (`udp`, by RFC 3263) and that nothing names it.
        """
        device = softphone.Device(username="alice", password="x",
                                  domain="example-0123456789ab.sip.signalwire.com")
        rendered = self._rendered(device)
        assert "udp" in rendered and "unnamed" in rendered


class TestTheInviteNamesNoTransportUnlessAsked:
    """The request URI a working trunk sends, and the one this used to send.

    Two INVITEs to the same E.164 number against the same space: a FreeSWITCH
    trunk that reached the PSTN sent

        INVITE sip:+1440...@example-0123456789ab.sip.signalwire.com SIP/2.0
        To: <sip:+1440...@example-0123456789ab.sip.signalwire.com>

    and this module sent

        INVITE sip:+1440...@example-0123456789ab.sip.signalwire.com;transport=tcp SIP/2.0
        To: <sip:+1440...@example-0123456789ab.sip.signalwire.com;transport=tcp>

    which rang nothing. A third trace, from a softphone that also reaches the
    PSTN, carries `;transport=UDP` in the request URI and a *clean* `To` — so
    the request-URI parameter is harmless and only `To` is suspect. `To`
    always mirrors the request line here and cannot be separated from it, so
    naming no transport is the only shape this stack can send that matches a
    call known to route.

    The parameter is not ours to omit through `Account`, whose `aor()` always
    renders one — `UserAgent.create` taking a raw AOR string is the only
    lever, and `aor_of` is where it is pulled.

    Captured with `scripts/probe_invite_uri.py`, which reads the bytes off a
    socket rather than reasoning about the string.
    """

    DOMAIN = "example-0123456789ab.sip.signalwire.com"

    def _uri(self, aor: str) -> str:
        """Just the URI: everything up to the bracket that closes it."""
        return aor.partition(">")[0]

    def test_the_uri_names_no_transport_by_default(self):
        pytest.importorskip("baresip", reason="no SIP wheel for this platform")
        device = softphone.Device(username="alice", password="pw", domain=self.DOMAIN)
        assert ";transport=" not in self._uri(softphone.aor_of(device))

    def test_naming_one_puts_it_back(self):
        """Because that is the only place baresip reads the transport from, so
        `tcp` and `tls` cannot be had without the parameter."""
        pytest.importorskip("baresip", reason="no SIP wheel for this platform")
        for transport in ("udp", "tcp", "tls"):
            device = softphone.Device(username="alice", password="pw",
                                      domain=self.DOMAIN, transport=transport)
            assert f";transport={transport}" in self._uri(softphone.aor_of(device))

    def test_everything_after_the_uri_is_left_as_the_library_wrote_it(self):
        """Re-rendering the line here is how it would drift from the library."""
        pytest.importorskip("baresip", reason="no SIP wheel for this platform")
        device = softphone.Device(username="alice", password="pw", domain=self.DOMAIN,
                                  registrar="proxy.example.net", codecs=("opus",),
                                  dtmf_mode="info", reg_interval=120)
        params = softphone.aor_of(device).partition(">")[2]
        for expected in ('auth_pass="pw"', "regint=120", "answermode=manual",
                         "audio_codecs=opus", "dtmfmode=info",
                         'outbound="sip:proxy.example.net"'):
            assert expected in params

    def test_a_device_that_does_not_register_still_says_so(self):
        """`regint=0` is how baresip is told not to register, and with a raw
        AOR the library finds that by text — so stripping must not disturb it,
        or `register()` would sit there timing out instead of refusing."""
        pytest.importorskip("baresip", reason="no SIP wheel for this platform")
        import re

        from baresip.ua import _REGINT_ZERO

        aor = softphone.aor_of(softphone.Device(
            username="alice", password="", domain=self.DOMAIN, register=False))
        assert _REGINT_ZERO.search(aor), f"the library cannot read {aor!r}"
        assert re.search(r";transport=", self._uri(aor)) is None

    def test_an_aor_that_is_already_clean_is_left_alone(self):
        """The library dropping the parameter itself is the outcome this wants,
        not a failure to report."""
        clean = '<sip:a@b>;auth_pass="p";regint=600'
        assert softphone.without_transport(clean) == clean

    def test_an_unreadable_aor_is_refused_rather_than_guessed(self):
        """Sending the shape that does not route would be worse than saying so."""
        with pytest.raises(softphone.SoftphoneError):
            softphone.without_transport("sip:a@b;transport=udp")


class TestWhatIsOnScreenCanBeQuoted:
    """A full-screen app owns the mouse, so nothing on it can be selected.

    That made the one string worth quoting in a ticket — the account line,
    which says whether a transport parameter is on the URI — the hardest thing
    to get out of the cockpit, and a call was debugged across screenshots
    instead. `y` copies it.
    """

    DOMAIN = "example-0123456789ab.sip.signalwire.com"

    def _phone(self, **kw):
        phone = softphone.Softphone()
        phone.device = softphone.Device(
            username="alice", password="hunter2", domain=self.DOMAIN, **kw)
        phone.state = softphone.REGISTERED
        return phone

    def test_the_account_line_is_in_it(self):
        """The whole reason the block exists: it shows what goes on the wire."""
        pytest.importorskip("baresip", reason="no SIP wheel for this platform")
        from swsh.tui import lab

        text = lab.diagnostics(self._phone(), FAKE)
        assert "account" in text
        assert f"<sip:alice@{self.DOMAIN}>" in text

    def test_naming_a_transport_shows_up_in_it(self):
        pytest.importorskip("baresip", reason="no SIP wheel for this platform")
        from swsh.tui import lab

        text = lab.diagnostics(self._phone(transport="tcp"), FAKE)
        assert f"<sip:alice@{self.DOMAIN};transport=tcp>" in text

    def test_the_password_never_leaves_the_device(self):
        """It is pasted into tickets, so a credential in it would be a leak."""
        pytest.importorskip("baresip", reason="no SIP wheel for this platform")
        from swsh.tui import lab

        text = lab.diagnostics(self._phone(), FAKE)
        assert "hunter2" not in text
        assert 'auth_pass="***"' in text

    def test_it_says_where_the_trace_is_or_that_it_is_off(self):
        from swsh.tui import lab

        off = lab.diagnostics(self._phone(), FAKE)
        assert "off" in off and "log SIP signalling" in off
        on = lab.diagnostics(self._phone(sip_trace=True), FAKE)
        assert str(softphone.trace_path()) in on

    def test_it_reports_the_target_the_stack_was_handed(self):
        """A request line is built from it, so it is the first thing to check."""
        from swsh.tui import lab

        phone = self._phone()
        phone.last_dial = f"sip:+15551234567@{self.DOMAIN}"
        assert f"sip:+15551234567@{self.DOMAIN}" in lab.diagnostics(phone, FAKE)

    def test_it_survives_a_device_that_was_never_configured(self):
        """`y` before anything is registered must not raise."""
        from swsh.tui import lab

        assert "no device configured" in lab.diagnostics(softphone.Softphone(), FAKE)

    async def test_y_writes_the_file_and_says_where(self, tmp_path, monkeypatch):
        """Two destinations, because neither is reliable alone: the clipboard
        is OSC 52, which macOS Terminal ignores, and a file nobody can find is
        no better than no file."""
        target = tmp_path / "diagnostics.txt"
        monkeypatch.setattr(softphone, "diagnostics_path", lambda: target)

        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            app.phone.device = softphone.Device(
                username="alice", password="hunter2", domain=self.DOMAIN)
            await pilot.press("y")
            await pilot.pause()

        assert target.exists(), "y did not write the file"
        written = target.read_text()
        assert "sw phone diagnostics" in written
        assert "hunter2" not in written
        # and the clipboard got the same text
        assert app._clipboard == written


class TestTheSipTraceActuallyTraces:
    """`sip_trace=True` alone produced no output anywhere.

    The stack logs every SIP message to `baresip.native.sip` at **DEBUG**, and
    the library attaches only a `NullHandler` — output is the application's
    decision. Two things were missing and neither is sufficient alone: the
    native level sat at `"error"`, so the message never reached Python, and
    nothing was listening if it had. The one diagnostic knob this module ships
    was recommended for days while emitting nothing.
    """

    def test_a_record_reaches_the_file(self, tmp_path, monkeypatch):
        import logging

        monkeypatch.setattr(softphone, "trace_path",
                            lambda: tmp_path / "sip-trace.log")
        tracer = softphone._Tracer()
        path = tracer.start()
        assert path is not None
        try:
            logging.getLogger(softphone._Tracer.LOGGER).debug(
                "TX UDP 192.0.2.10:5060 -> 198.51.100.20:5060")
        finally:
            tracer.stop()
        assert "TX UDP 192.0.2.10:5060" in path.read_text()

    def test_stopping_detaches_the_handler(self, tmp_path, monkeypatch):
        import logging

        monkeypatch.setattr(softphone, "trace_path",
                            lambda: tmp_path / "sip-trace.log")
        logger = logging.getLogger(softphone._Tracer.LOGGER)
        before = len(logger.handlers)
        tracer = softphone._Tracer()
        tracer.start()
        assert len(logger.handlers) == before + 1
        tracer.stop()
        assert len(logger.handlers) == before
        tracer.stop()      # idempotent

    def test_tracing_raises_the_native_level(self):
        """A trace the native stack filters out never reaches the logger."""
        pytest.importorskip("baresip", reason="no SIP wheel for this platform")
        import inspect

        source = inspect.getsource(softphone.Softphone.start)
        assert 'native_log_level="debug" if traced else "error"' in source

    def test_the_trace_is_a_file_not_the_feed_or_stderr(self):
        """Twenty lines per message into an eight-line feed is not a trace,
        and Textual owns stderr."""
        assert softphone.trace_path().name.endswith(".log")
