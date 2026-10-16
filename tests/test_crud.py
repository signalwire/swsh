"""CRUD wiring through the cockpit.

The HTTP call itself is stubbed. What matters here is that sw issues the right
method against the right URL with the right body, respects the capability flags,
and reloads afterwards, none of which needs a live project.

These stub `rest_call`, not `call_sdk`: every CRUD resource resolves its route
from the spec catalog now, so the URL *is* the thing worth asserting. A route
that regresses to the wrong path fails here rather than in production.
"""

from __future__ import annotations

from typing import Any

from swsh.config import Profile
from swsh.tui.app import SwshApp

FAKE = Profile(name="test", project="proj-1", token="tok", space="nowhere.invalid")


class Recorder:
    """Stands in for SwshClient.rest_call and records every request."""

    def __init__(self, result: Any = None, error: Exception | None = None):
        self.calls: list[tuple[str, str, dict, dict]] = []
        self.result = result if result is not None else {"id": "new-1"}
        self.error = error

    async def __call__(self, method: str, path: str, *, params: Any = None,
                       body: Any = None) -> Any:
        self.calls.append((method, path, dict(params or {}), dict(body or {})))
        if self.error is not None:
            raise self.error
        return self.result

    def routes(self) -> list[tuple[str, str]]:
        return [(c[0], c[1]) for c in self.calls]

    def one(self, method: str, path: str) -> tuple[str, str, dict, dict]:
        return next(c for c in self.calls if c[0] == method and c[1] == path)


async def ready(app: SwshApp, pilot, resource: str, rows: list[dict]):
    """Open a resource with stub data already loaded."""
    app.switch_to(resource)
    await pilot.pause(0.3)
    app.rows = rows
    app.load_error = None
    app.loading = False
    app._refresh_view()
    await pilot.pause()


class TestCreate:
    async def test_new_dispatches_create_then_reloads(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await ready(app, pilot, "queues", [])
            recorder = Recorder()
            app.client.rest_call = recorder

            app.action_new()
            await pilot.pause()
            app.screen.query_one("#field-name").value = "support"
            app.screen.action_submit()
            await pilot.pause(0.3)

            create = recorder.one("POST", "/api/relay/rest/queues")
            assert create[3] == {"name": "support"}
            # reloaded after the write
            assert ("GET", "/api/relay/rest/queues") in recorder.routes()

    async def test_create_is_refused_on_a_read_only_resource(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await ready(app, pilot, "logs", [{"id": "l-1"}])
            recorder = Recorder()
            app.client.rest_call = recorder

            app.action_new()
            await pilot.pause()
            assert recorder.calls == []
            assert len(app.screen_stack) == 1  # no form opened


class TestUpdate:
    async def test_edit_dispatches_update_with_the_row_id(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await ready(app, pilot, "queues", [{"id": "q-1", "name": "support", "max_size": 10}])
            recorder = Recorder()
            app.client.rest_call = recorder

            app.action_edit()
            await pilot.pause()
            app.screen.query_one("#field-max_size").value = "99"
            app.screen.query_one("#field-name").value = ""  # leave unchanged
            app.screen.action_submit()
            await pilot.pause(0.3)

            update = recorder.one("PUT", "/api/relay/rest/queues/q-1")
            assert update[3] == {"max_size": 99}  # only what was filled in

    async def test_edit_without_a_selection_does_nothing(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await ready(app, pilot, "queues", [])
            recorder = Recorder()
            app.client.rest_call = recorder
            app.action_edit()
            await pilot.pause()
            assert recorder.calls == []


class TestDelete:
    async def test_delete_asks_first_then_dispatches(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await ready(app, pilot, "queues", [{"id": "q-1", "name": "support"}])
            recorder = Recorder()
            app.client.rest_call = recorder

            app.action_delete()
            await pilot.pause()
            assert len(app.screen_stack) == 2  # confirmation is showing
            assert recorder.calls == []  # nothing sent yet

            await pilot.press("y")
            await pilot.pause(0.3)
            assert ("DELETE", "/api/relay/rest/queues/q-1") in recorder.routes()

    async def test_declining_the_confirmation_sends_nothing(self):
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await ready(app, pilot, "queues", [{"id": "q-1"}])
            recorder = Recorder()
            app.client.rest_call = recorder

            app.action_delete()
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause(0.3)
            assert recorder.calls == []


class TestFailureHandling:
    async def test_a_failed_write_does_not_crash_or_reload(self):
        from swsh.client import SwshError

        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await ready(app, pilot, "queues", [])
            recorder = Recorder(error=SwshError("boom", status=422))
            app.client.rest_call = recorder

            app.action_new()
            await pilot.pause()
            app.screen.query_one("#field-name").value = "support"
            app.screen.action_submit()
            await pilot.pause(0.3)

            assert app.is_running
            # no reload after failure
            assert recorder.routes() == [("POST", "/api/relay/rest/queues")]


class TestExtras:
    async def test_extra_operation_dispatches_its_method(self):
        """`x` on voice logs opens the per-call event timeline."""
        app = SwshApp(profile=FAKE)
        async with app.run_test() as pilot:
            await ready(app, pilot, "logs", [{"id": "log-1"}])
            recorder = Recorder(result={"data": [{"type": "answered"}]})
            app.client.rest_call = recorder

            # logs exposes several extras now, so drive the timeline one directly
            extra = next(e for e in app.resource.extras if e.method == "list_events")
            app._run_extra(extra, "log-1")
            await pilot.pause(0.3)

            assert ("GET", "/api/voice/logs/log-1/events") in recorder.routes()
            assert app.rows == [{"type": "answered"}]
