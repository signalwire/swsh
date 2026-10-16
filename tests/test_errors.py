"""Failures reach the user as a sentence, not a traceback.

A CLI that answers a mistyped space with 200 lines of Rich-formatted stack is
telling the user about its own call graph instead of about their mistake. Every
command body runs inside `cli.coro`, so that wrapper is the one place this has to
be right.
"""

from __future__ import annotations

import click
import httpx
import pytest
import typer

from swsh import cli, client
from swsh.config import Profile

FAKE = Profile(name="t", project="proj-1", token="tok", space="example.signalwire.com")


async def _no_sleep(_seconds):
    """Retries are the behaviour under test; the waiting is not."""


@pytest.fixture(autouse=True)
def creds(monkeypatch):
    monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "proj-1")
    monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "tok")
    monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
    for var in ("PROJECT_ID", "REST_API_TOKEN", "SWSH_PROFILE", "SW_TRACEBACK"):
        monkeypatch.delenv(var, raising=False)


def failing(exc: Exception):
    """A command that raises, wrapped exactly as a real one is."""

    @cli.coro
    async def command(client):
        raise exc

    return command


def run(exc: Exception) -> int:
    with pytest.raises(typer.Exit) as caught:
        failing(exc)()
    return caught.value.exit_code


class TestNothingEscapesAsATraceback:
    def test_a_dns_failure_is_one_line_naming_the_space(self, capsys):
        assert run(httpx.ConnectError("[Errno 8] nodename nor servname provided")) == 1
        err = capsys.readouterr().err
        assert "cannot reach example.signalwire.com" in err
        assert "SIGNALWIRE_SPACE" in err
        assert "Traceback" not in err

    def test_a_timeout_says_so(self, capsys):
        assert run(httpx.ConnectTimeout("timed out")) == 1
        assert "timed out talking to example.signalwire.com" in capsys.readouterr().err

    def test_any_other_transport_error_is_still_handled(self, capsys):
        assert run(httpx.RemoteProtocolError("bad chunk")) == 1
        err = capsys.readouterr().err
        assert "RemoteProtocolError" in err
        assert "Traceback" not in err

    def test_an_os_error_is_handled(self, capsys):
        assert run(OSError("socket is closed")) == 1
        assert "socket is closed" in capsys.readouterr().err

    def test_an_unexpected_exception_gets_one_line_and_a_way_in(self, capsys):
        # The catch-all. A bug in sw should still not print a stack at someone
        # who was only trying to list their phone numbers.
        assert run(ValueError("synthetic")) == 1
        err = capsys.readouterr().err
        assert "ValueError: synthetic" in err
        assert "SW_TRACEBACK=1" in err
        assert "Traceback" not in err

    def test_sw_traceback_opts_back_in(self, monkeypatch):
        # Debuggability is not removed, only moved behind a flag.
        monkeypatch.setenv("SW_TRACEBACK", "1")
        with pytest.raises(ValueError, match="synthetic"):
            failing(ValueError("synthetic"))()

    def test_an_interrupt_uses_the_conventional_code(self):
        assert run(KeyboardInterrupt()) == 130

    def test_a_swsh_error_keeps_its_own_message(self, capsys):
        from swsh.client import SwshError

        assert run(SwshError("no spec operation for 'nope'")) == 1
        assert "no spec operation for 'nope'" in capsys.readouterr().err


class TestControlFlowIsNotSwallowed:
    """The catch-all must not eat Click's control-flow exceptions.

    When it did, every `raise typer.Exit(2)` inside a command body — the usage
    errors that `sw api` and the CRUD verbs raise after printing their own
    message — came out as exit 1, and the message was printed twice.
    """

    def test_an_explicit_exit_code_survives(self):
        assert run(typer.Exit(2)) == 2
        assert run(typer.Exit(130)) == 130

    def test_a_clean_exit_survives(self):
        assert run(typer.Exit()) == 0

    def test_a_click_exception_is_left_for_click_to_render(self):
        with pytest.raises(click.UsageError):
            failing(click.UsageError("expected key=value"))()

    def test_the_message_is_not_printed_twice(self, capsys):
        # A body that reported its own problem then exited must not be described
        # again by the wrapper.
        assert run(typer.Exit(2)) == 2
        assert capsys.readouterr().err == ""


class TestTheReporterIsItselfSafe:
    def test_describing_an_error_never_raises(self, monkeypatch):
        # _describe_network_error resolves the profile to name the space. If that
        # resolution is what is broken, reporting must not fail on top of it.
        def explode(*_args, **_kwargs):
            raise RuntimeError("profile is unreadable")

        monkeypatch.setattr(cli, "_profile", explode)
        message = cli._describe_network_error(httpx.ConnectError("boom"))
        assert "the configured space" in message


class TestWhatTheUserIsToldWentWrong:
    """A validation failure is a list of objects, one per offending field.
    `f"{body[key]}"` rendered that as a Python repr — everything a person needs
    was in there and none of it was readable."""

    def test_a_validation_failure_reads_as_field_lines(self):
        body = {"errors": [
            {"type": "validation_error", "code": "missing_required_parameter",
             "message": "Encryption is required", "attribute": "encryption",
             "url": "https://developer.signalwire.com/x"},
            {"type": "validation_error", "code": "missing_sip_configuration",
             "message": "The SIP configuration requires at least one cipher",
             "attribute": "ciphers"},
        ]}
        text = client._describe(422, body)
        assert "Encryption is required" in text
        assert "ciphers: The SIP configuration requires at least one cipher" in text
        assert "{" not in text and "'" not in text, "no dict repr"

    def test_the_field_name_leads_when_the_message_omits_it(self):
        """`uri` maps straight back to the `--set` key that caused it."""
        body = {"errors": [{"code": "not_unique_within_project",
                            "message": "must be unique within project",
                            "attribute": "uri"}]}
        assert client._describe(422, body).startswith("uri: must be unique")

    def test_it_is_not_repeated_when_the_message_already_says_it(self):
        body = {"errors": [{"message": "Encryption is required",
                            "attribute": "encryption"}]}
        assert client._describe(422, body).count("ncryption") == 1

    def test_doc_links_are_collected_for_a_hint_not_inlined(self):
        body = {"errors": [{"message": "x", "url": "https://developer.signalwire.com/a"},
                           {"message": "y", "url": "https://developer.signalwire.com/b"}]}
        assert "https://" not in client._describe(422, body)
        assert client.error_doc_urls(body) == ["https://developer.signalwire.com/a",
                                               "https://developer.signalwire.com/b"]

    def test_statuses_that_used_to_collapse_to_request_failed_now_say_something(self):
        for status, expected in ((403, "forbidden"), (409, "conflict"),
                                 (429, "rate limited")):
            assert expected in client._describe(status, {})

    def test_a_body_with_no_known_key_is_shown_rather_than_discarded(self):
        """Three words that name nothing are worse than the server's own text."""
        text = client._describe(500, {"raw": "<html>Internal Server Error</html>"})
        assert "Internal Server Error" in text

    def test_a_bare_5xx_says_it_is_the_platform(self):
        assert "server error" in client._describe(503, {})


class TestRetryingWhatIsWorthRetrying:
    async def test_a_429_is_retried_and_then_succeeds(self, monkeypatch):
        seen: list[int] = []

        async def flaky(self, method, path, **kw):
            seen.append(1)
            code = 429 if len(seen) == 1 else 200
            return httpx.Response(code, json={"ok": True},
                                  request=httpx.Request(method, "https://x" + path))

        monkeypatch.setattr(client.httpx.AsyncClient, "request", flaky)
        monkeypatch.setattr(client.asyncio, "sleep", _no_sleep)
        c = client.SwshClient(FAKE)
        assert await c.rest_call("GET", "/x") == {"ok": True}
        assert len(seen) == 2

    async def test_it_gives_up_rather_than_retrying_forever(self, monkeypatch):
        seen: list[int] = []

        async def always_429(self, method, path, **kw):
            seen.append(1)
            return httpx.Response(429, json={}, request=httpx.Request(method, "https://x"))

        monkeypatch.setattr(client.httpx.AsyncClient, "request", always_429)
        monkeypatch.setattr(client.asyncio, "sleep", _no_sleep)
        c = client.SwshClient(FAKE)
        with pytest.raises(client.SwshError):
            await c.rest_call("GET", "/x")
        assert len(seen) == client.SwshClient.ATTEMPTS

    async def test_a_5xx_on_a_create_is_not_replayed(self, monkeypatch):
        """It may have been processed before it failed; two of a thing is worse
        than one error."""
        seen: list[str] = []

        async def boom(self, method, path, **kw):
            seen.append(method)
            return httpx.Response(503, json={}, request=httpx.Request(method, "https://x"))

        monkeypatch.setattr(client.httpx.AsyncClient, "request", boom)
        monkeypatch.setattr(client.asyncio, "sleep", _no_sleep)
        c = client.SwshClient(FAKE)
        with pytest.raises(client.SwshError):
            await c.rest_call("POST", "/x")
        assert seen == ["POST"]

    async def test_a_5xx_on_a_read_is_replayed(self, monkeypatch):
        seen: list[str] = []

        async def boom(self, method, path, **kw):
            seen.append(method)
            return httpx.Response(502, json={}, request=httpx.Request(method, "https://x"))

        monkeypatch.setattr(client.httpx.AsyncClient, "request", boom)
        monkeypatch.setattr(client.asyncio, "sleep", _no_sleep)
        c = client.SwshClient(FAKE)
        with pytest.raises(client.SwshError):
            await c.rest_call("GET", "/x")
        assert len(seen) == client.SwshClient.ATTEMPTS

    def test_retry_after_is_honoured_when_it_is_a_sane_number(self):
        def resp(value):
            return httpx.Response(429, headers={"retry-after": value},
                                  request=httpx.Request("GET", "https://x"))

        assert client._retry_after(resp("2")) == 2.0
        assert client._retry_after(resp("Wed, 21 Oct 2026 07:28:00 GMT")) is None
        assert client._retry_after(resp("3600")) is None, "not something to sit through"
        assert client._retry_after(httpx.Response(
            429, request=httpx.Request("GET", "https://x"))) is None


class TestTheSdkGetsATimeoutToo:
    """It shipped with none, so an SDK-backed call waited as long as the far end
    kept the socket open: no output, no error, nothing to interrupt."""

    def test_the_session_request_is_wrapped_once(self):
        class Session:
            def request(self, method, url, **kw):
                return kw

        class Rest:
            def __init__(self):
                self._http = type("H", (), {"_session": Session()})()

        rest = Rest()
        client._give_it_a_timeout(rest, 12.0)
        client._give_it_a_timeout(rest, 99.0)  # idempotent
        assert rest._http._session.request("GET", "/x")["timeout"] == 12.0

    def test_an_explicit_timeout_still_wins(self):
        class Session:
            def request(self, method, url, **kw):
                return kw

        rest = type("R", (), {"_http": type("H", (), {"_session": Session()})()})()
        client._give_it_a_timeout(rest, 12.0)
        assert rest._http._session.request("GET", "/x", timeout=1.0)["timeout"] == 1.0

    def test_an_unfamiliar_sdk_shape_is_left_alone(self):
        """Reaching into another package's privates degrades, never raises."""
        client._give_it_a_timeout(object(), 5.0)

    def test_the_default_comes_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("SWSH_TIMEOUT", "7.5")
        assert client.default_timeout() == 7.5
        monkeypatch.setenv("SWSH_TIMEOUT", "nonsense")
        assert client.default_timeout() == 30.0
        monkeypatch.setenv("SWSH_TIMEOUT", "-1")
        assert client.default_timeout() == 30.0
