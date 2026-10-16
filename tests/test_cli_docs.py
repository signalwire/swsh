"""Registry-driven docs and shell-completion candidates.

Both are generated from the registry, which is the whole point: `swsh docs` and
`--from <TAB>` cannot describe operations the CLI does not actually offer,
because they read the same source of truth the commands do.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from swsh import __version__, cli, resources, spec

runner = CliRunner()


@pytest.fixture(autouse=True)
def never_touch_the_real_config(tmp_path, monkeypatch):
    """No test reads the machine's actual credentials.

    Without this, `sw api --list` and friends passed only because the developer
    happened to be logged in. Logging out on the real machine broke the suite,
    which is the wrong way to find out a test was reading ambient state.
    """
    monkeypatch.setattr(cli.config, "config_path", lambda: tmp_path / "config.toml")
    monkeypatch.setattr(cli.config, "load_dotenv", lambda path=None: {})
    monkeypatch.setattr(cli.config, "_keyring_set", lambda *a, **k: False)
    monkeypatch.setattr(cli.config, "_keyring_get", lambda *a, **k: None)
    for var in ("SIGNALWIRE_PROJECT_ID", "SIGNALWIRE_API_TOKEN", "SIGNALWIRE_SPACE",
                "PROJECT_ID", "REST_API_TOKEN", "SWSH_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    # Reset the module-level flag state the root callback would normally set.
    cli.Ctx.as_json = False
    cli.Ctx.profile_name = None


def test_version_flag_prints_and_exits_zero():
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_no_args_shows_help_not_an_error():
    result = runner.invoke(cli.app, [])
    assert result.exit_code == 0
    assert "Usage" in result.stdout


def test_docs_command_runs_end_to_end():
    result = runner.invoke(cli.app, ["docs"])
    assert result.exit_code == 0
    assert "resource reference" in result.stdout


def test_docs_cover_every_registered_resource():
    text = cli._render_docs()
    # every resource key appears as its own heading
    for r in resources.RESOURCES:
        assert f"`{r.key}`" in text
    # and the document is grouped and labelled, not a raw dump
    assert text.startswith("# sw resource reference")
    assert "operations:" in text


def test_docs_list_editable_fields_with_their_kind():
    # pick a resource that has fields and assert they are documented
    withfields = next(r for r in resources.RESOURCES if r.fields)
    text = cli._render_docs()
    section = text.split(f"`{withfields.key}`", 1)[1]
    a_field = withfields.fields[0]
    assert f"`{a_field.name}`" in section


def test_docs_name_the_commands_for_each_resource():
    # The reference is where someone learns that buying a number is
    # `sw numbers buy`, so the command line for each resource is in it.
    text = cli._render_docs()
    assert "`sw numbers buy`" in text
    assert "`sw numbers release`" in text
    assert "`sw numbers assign-e911-address`" in text
    assert "`sw swml delete`" in text


def test_docs_point_at_the_api_escape_hatch():
    # The reference lists only what is modelled, so it has to say how to reach
    # the rest, or a reader concludes the other operations do not exist.
    text = cli._render_docs()
    assert "sw api" in text
    assert "--list" in text


class TestGlobalFlagsBelongToCommands:
    """`--json` and `--profile` follow the command, and only the command.

    They describe what a command does, not what `sw` is. Having them on the root
    callback as well made `sw --help` list them among `sw`'s own options, which
    reads as though `sw --json` were a command in its own right.
    """

    def _resources(self, argv: list[str]):
        result = runner.invoke(cli.app, argv)
        assert result.exit_code == 0, result.output
        return result.output

    def test_json_after_the_command(self):
        assert self._resources(["docs", "--list", "--json"]).lstrip().startswith("[")

    def test_json_before_the_command_is_a_usage_error(self):
        result = runner.invoke(cli.app, ["--json", "docs"])
        assert result.exit_code == 2
        assert "--json" in result.output  # names the offending option

    def test_profile_before_the_command_is_a_usage_error(self):
        result = runner.invoke(cli.app, ["--profile", "scratch", "docs"])
        assert result.exit_code == 2

    def test_the_root_help_does_not_advertise_them(self):
        # The reason for all of the above: they must not look like `sw` options.
        out = runner.invoke(cli.app, ["--help"]).output
        options = out.split("Options")[1].split("Commands")[0]
        assert "--json" not in options
        assert "--profile" not in options

    def test_order_among_a_command_s_own_flags_does_not_matter(self):
        # Both of these must work, which is what Click gives us for free once
        # the options belong to the command.
        for argv in (["api", "--list", "fax-api", "--json"],
                     ["api", "--json", "--list", "fax-api"]):
            result = runner.invoke(cli.app, argv)
            assert result.exit_code == 0, (argv, result.output)
            assert result.output.lstrip().startswith("["), argv

    def test_command_help_advertises_them(self):
        # They are real Typer parameters, not argv munging, so help lists them.
        for argv in (["whoami", "--help"], ["docs", "--help"], ["numbers", "list", "--help"],
                     ["numbers", "assign-e911-address", "--help"]):
            out = runner.invoke(cli.app, argv).output
            assert "--json" in out, argv
            assert "--profile" in out, argv

    def test_the_flags_do_not_leak_into_the_command_body(self):
        # They are popped before the body runs; a stray kwarg would be a
        # TypeError at call time.
        result = runner.invoke(cli.app, ["profile", "list", "--json"])
        assert result.exit_code == 0, result.output

    def test_profile_after_the_command_reaches_ctx(self):
        result = runner.invoke(cli.app, ["docs", "--list", "--profile", "whatever", "--json"])
        assert result.exit_code == 0, result.output


class TestTheCockpitIsFindable:
    """`sw` points at the cockpit; it does not become it.

    A bare `sw` prints help rather than launching the TUI, for two reasons that
    are easy to forget once someone proposes the shortcut again: it runs in
    pipes, CI jobs and Dockerfiles where a full-screen app hangs or dies, and
    that listing is the only place the command tree advertises itself. So
    findability is the listing's job — the first row, and a closing line that
    names the command.
    """

    def test_bare_sw_prints_help_rather_than_launching_the_cockpit(self):
        result = runner.invoke(cli.app, [])
        assert result.exit_code == 0
        assert "Usage" in result.output

    def test_sh_is_the_first_command_registered(self):
        # Typer lists commands in registration order and always prints the
        # default panel before every named one, so the first `@app.command()`
        # in cli.py is the first row a person reads.
        assert cli.app.registered_commands[0].callback is cli.shell

    def test_sh_is_the_first_command_listed(self):
        out = runner.invoke(cli.app, ["--help"]).output
        assert out.index("sh") < out.index("login") < out.index("whoami")

    def test_the_help_closes_by_naming_the_cockpit(self):
        # The epilog: last thing on the screen, after every panel.
        out = runner.invoke(cli.app, ["--help"]).output
        assert "sw sh" in out.rsplit("╯", 1)[-1]


class TestThereIsOneSpellingOfTheCockpit:
    """`sw sh`, and nothing else.

    The cockpit was `sw tui`, and a second console script named `swsh` opened
    it when run bare — the name the interactive shell had through 2.0. Both are
    gone: `sw` + `sh` still spells the old name while keeping the shell where
    every other capability already is, as a subcommand of the one binary. These
    pin that no second spelling creeps back in, because an alias is how a tool
    ends up with two ways to say one thing and documentation for neither.
    """

    def test_the_cockpit_answers_to_sh(self, monkeypatch):
        opened: list[str] = []
        monkeypatch.setattr(cli, "_profile", lambda: object())

        class FakeApp:
            def __init__(self, **kw):
                opened.append("built")

            def run(self):
                opened.append("ran")

        import swsh.tui.app as tui_app

        monkeypatch.setattr(tui_app, "SwshApp", FakeApp)
        assert runner.invoke(cli.app, ["sh"]).exit_code == 0
        assert opened == ["built", "ran"]

    def test_the_old_spellings_are_gone(self):
        root = typer.main.get_command(cli.app)
        assert "tui" not in root.commands
        assert not hasattr(cli, "main_swsh")

    def test_no_second_console_script_ships(self):
        # The entry points are the one place a stray alias would survive a
        # rename, because nothing in the test suite imports them.
        scripts = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
        block = scripts.split("[project.scripts]", 1)[1].split("[", 1)[0]
        assert 'sw = "swsh.cli:main"' in block
        assert "main_swsh" not in block


class TestProfilesAreDiscoverable:
    """Where credentials live, and why a saved profile can look ignored.

    The config file sits at an OS-specific path nobody would guess
    (`~/Library/Application Support/swsh/config.toml` on macOS), and an ambient
    env var silently outranks it. Both have to be visible from the CLI.
    """

    def test_profile_path_prints_the_config_file(self):
        from swsh import config

        result = runner.invoke(cli.app, ["profile", "path"])
        assert result.exit_code == 0
        assert result.output.strip() == str(config.config_path())

    def test_profile_path_is_a_bare_line_for_scripting(self):
        # `$EDITOR "$(sw profile path)"` has to work, so no panel or styling.
        out = runner.invoke(cli.app, ["profile", "path"]).output
        assert out.count("\n") == 1
        assert "╭" not in out

    def test_profile_list_shows_where_the_file_is(self):
        from swsh import config

        out = runner.invoke(cli.app, ["profile", "list"]).output
        # the path is wrapped in a panel, so compare on the filename
        assert config.config_path().name in out

    def test_profile_list_json_carries_path_and_sources(self):
        result = runner.invoke(cli.app, ["profile", "list", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert set(payload) >= {"profiles", "default", "config_path", "sources"}

    def test_profile_list_warns_when_the_environment_outranks_a_profile(self, monkeypatch):
        # The state that makes profile switching look broken.
        monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "env-proj")
        monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "env-tok")
        monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
        out = runner.invoke(cli.app, ["profile", "list"]).output
        assert "outranks" in out

    def test_profile_list_is_quiet_when_nothing_is_shadowing(self, monkeypatch):
        for var in ("SIGNALWIRE_PROJECT_ID", "SIGNALWIRE_API_TOKEN",
                    "SIGNALWIRE_SPACE", "PROJECT_ID", "REST_API_TOKEN"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr(cli.config, "load_dotenv", lambda path=None: {})
        out = runner.invoke(cli.app, ["profile", "list"]).output
        assert "outranks" not in out

    def test_whoami_with_an_explicit_profile_uses_it_despite_the_environment(
            self, monkeypatch):
        # From the test-plan pass: `--profile ALICE` kept reporting the env
        # project. Naming a profile means it, and the summary must agree with
        # the client rather than describing the default profile's resolution.
        cli.config.save_profile("work", "proj-WORK", "tok-WORK", "example.signalwire.com")
        monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "proj-ENV")
        monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "tok-ENV")
        monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
        seen = {}

        async def fake_whoami(self):
            seen["project"] = self.profile.project
            return {"status": "active", "friendly_name": "Work"}

        monkeypatch.setattr(cli.SwshClient, "whoami", fake_whoami)
        result = runner.invoke(cli.app, ["whoami", "--json", "--profile", "work"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert seen["project"] == "proj-WORK"
        assert payload["project"] == "proj-WORK"
        assert payload["credentials_from"] == "profile"

        # Without --profile the environment still wins, and the note says how
        # to get past it.
        result = runner.invoke(cli.app, ["whoami"])
        assert "environment variables" in result.output
        assert "--profile NAME" in result.output
        assert "environment/.env" not in result.output

    def test_profile_use_note_points_at_the_flag(self, monkeypatch):
        cli.config.save_profile("work", "proj-WORK", "tok-WORK", "example.signalwire.com")
        monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "proj-ENV")
        monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "tok-ENV")
        monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
        out = runner.invoke(cli.app, ["profile", "use", "work"]).output
        assert "--profile work" in out

    def test_profile_edit_without_a_config_file_explains_itself(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cli.config, "config_path", lambda: tmp_path / "absent.toml")
        result = runner.invoke(cli.app, ["profile", "edit"])
        assert result.exit_code == 2
        assert "sw login" in result.output


class TestProfileDelete:
    """Removing a profile destroys an API token, so it behaves like a delete.

    It previously took one name and removed it with no confirmation, and silently
    repointed the default when you deleted the active profile.
    """

    @pytest.fixture(autouse=True)
    def profiles(self):
        for name in ("alpha", "beta", "gamma"):
            cli.config.save_profile(name, f"p-{name}", f"t-{name}", "example.signalwire.com")

    def test_an_unknown_name_lists_what_does_exist(self):
        result = runner.invoke(cli.app, ["profile", "delete", "nope"])
        assert result.exit_code == 2
        assert "no such profile: nope" in result.output
        assert "alpha" in result.output  # the hint names the real ones

    def test_it_refuses_without_yes_when_non_interactive(self, monkeypatch):
        monkeypatch.setattr(cli.prompts, "interactive", lambda: False)
        result = runner.invoke(cli.app, ["profile", "delete", "alpha"])
        assert result.exit_code == 2
        assert "--yes" in result.output
        assert "alpha" in cli.config.list_profiles()  # nothing removed

    def test_declining_the_confirmation_removes_nothing(self, monkeypatch):
        monkeypatch.setattr(cli.prompts, "interactive", lambda: True)
        monkeypatch.setattr(cli.typer, "confirm", lambda *a, **k: False)
        result = runner.invoke(cli.app, ["profile", "delete", "alpha"])
        assert result.exit_code == 0
        assert "alpha" in cli.config.list_profiles()

    def test_yes_deletes_without_prompting(self):
        result = runner.invoke(cli.app, ["profile", "delete", "alpha", "--yes"])
        assert result.exit_code == 0
        assert "alpha" not in cli.config.list_profiles()

    def test_several_names_at_once(self):
        result = runner.invoke(cli.app, ["profile", "delete", "alpha", "beta", "-y"])
        assert result.exit_code == 0
        assert cli.config.list_profiles() == ["gamma"]

    def test_deleting_the_active_profile_reports_the_new_default(self):
        cli.config.set_default("beta")
        result = runner.invoke(cli.app, ["profile", "delete", "beta", "-y"])
        assert result.exit_code == 0
        assert "active profile is now" in result.output
        assert cli.config.default_profile_name() in ("alpha", "gamma")

    def test_deleting_the_last_profile_says_what_to_do_next(self):
        result = runner.invoke(
            cli.app, ["profile", "delete", "alpha", "beta", "gamma", "-y"])
        assert result.exit_code == 0
        assert "sw login" in result.output
        assert cli.config.list_profiles() == []

    def test_nothing_is_deleted_when_one_name_is_wrong(self):
        # All-or-nothing: a typo in the second name must not remove the first.
        result = runner.invoke(cli.app, ["profile", "delete", "alpha", "typo", "-y"])
        assert result.exit_code == 2
        assert cli.config.list_profiles() == ["alpha", "beta", "gamma"]

    def test_it_warns_that_the_environment_still_provides_credentials(self, monkeypatch):
        monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "env-proj")
        monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "env-tok")
        monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
        result = runner.invoke(cli.app, ["profile", "delete", "alpha", "-y"])
        assert "not logged out" in result.output

    def test_completion_offers_stored_names(self):
        assert set(cli._complete_profile("")) == {"alpha", "beta", "gamma"}
        assert cli._complete_profile("al") == ["alpha"]


class TestLogoutIsNotDelete:
    """`sw logout` deselects; `sw profile delete` removes.

    They used to be the same call, so logging out of one of two profiles
    destroyed it and silently left you logged in as the other.
    """

    @pytest.fixture(autouse=True)
    def profiles(self):
        cli.config.save_profile("work", "p1", "t1", "example.signalwire.com")
        cli.config.save_profile("home", "p2", "t2", "example.signalwire.com")

    def test_logout_keeps_the_profiles(self):
        result = runner.invoke(cli.app, ["logout"])
        assert result.exit_code == 0
        assert sorted(cli.config.list_profiles()) == ["home", "work"]
        assert "kept" in result.output

    def test_logout_says_how_to_log_back_in(self):
        out = runner.invoke(cli.app, ["logout"]).output
        assert "sw profile use" in out

    def test_logout_deselects_so_nothing_is_active(self):
        runner.invoke(cli.app, ["logout"])
        assert cli.config.is_logged_out()
        assert cli.config.default_profile_name() == ""

    def test_a_command_while_logged_out_says_to_pick_a_profile(self):
        runner.invoke(cli.app, ["logout"])
        result = runner.invoke(cli.app, ["whoami"])
        assert result.exit_code == 2
        assert "not logged in" in result.output
        assert "work" in result.output  # names the choices

    def test_an_explicit_profile_still_works_while_logged_out(self):
        # Keeping the profiles is the point: they remain usable by name.
        runner.invoke(cli.app, ["logout"])
        profile = cli.config.resolve("home")
        assert profile.token == "t2"

    def test_profile_list_shows_the_logged_out_state(self):
        runner.invoke(cli.app, ["logout"])
        out = runner.invoke(cli.app, ["profile", "list"]).output
        assert "logged out" in out
        assert "*" not in out.split("config.toml")[0]  # nothing marked active

    def test_logout_is_idempotent(self):
        runner.invoke(cli.app, ["logout"])
        result = runner.invoke(cli.app, ["logout"])
        assert result.exit_code == 0
        assert "already logged out" in result.output

    def test_a_no_op_logout_says_only_that(self):
        # Nothing changed, so there is nothing to explain. Repeating the kept
        # profiles and how to log back in is noise on a no-op.
        runner.invoke(cli.app, ["logout"])
        out = runner.invoke(cli.app, ["logout"]).output
        assert out.strip() == "already logged out"

    def test_the_first_logout_still_explains_itself(self):
        # The counterpart: the run that actually changed something keeps its
        # report, so trimming the no-op does not trim both.
        out = runner.invoke(cli.app, ["logout"]).output
        assert "kept" in out
        assert "sw profile use" in out

    def test_name_redirects_rather_than_deleting(self):
        # This flag used to delete the named profile.
        result = runner.invoke(cli.app, ["logout", "--name", "home"])
        assert result.exit_code == 2
        assert "sw profile delete home" in result.output
        assert sorted(cli.config.list_profiles()) == ["home", "work"]

    def test_logout_reports_a_shadowing_environment(self, monkeypatch):
        monkeypatch.setenv("SIGNALWIRE_PROJECT_ID", "p")
        monkeypatch.setenv("SIGNALWIRE_API_TOKEN", "t")
        monkeypatch.setenv("SIGNALWIRE_SPACE", "example.signalwire.com")
        out = runner.invoke(cli.app, ["logout"]).output
        assert "still logged in" in out


class TestLogTables:
    """`sw logs` renders the fields the API really returns."""

    @pytest.fixture(autouse=True)
    def logged_in(self):
        cli.config.save_profile("work", "proj-WORK", "tok-WORK", "example.signalwire.com")

    def test_events_table_has_the_real_event_columns(self, monkeypatch):
        # The old guess (type/created_at/description) drew a table of dashes
        # over rows that plainly had content.
        events = [{"event_at": "2026-09-09T20:20:12Z", "level": "info", "name": "initiated",
                   "details": {}, "log_id": "log-1"},
                  {"event_at": "2026-09-09T20:20:25Z", "level": "info", "name": "answered",
                   "details": {}, "log_id": "log-1"}]

        async def fake_events(self, log_id):
            return {"data": events}

        monkeypatch.setattr(cli.SwshClient, "voice_log_events", fake_events)
        result = runner.invoke(cli.app, ["logs", "events", "log-1"])
        assert result.exit_code == 0, result.output
        for column in cli.LOG_EVENT_COLUMNS:
            assert column in result.output
        assert "initiated" in result.output and "answered" in result.output
        assert "type" not in result.output.split("\n")[2]  # header row is the real one

    def test_voice_table_uses_the_registry_columns(self, monkeypatch):
        rows = [{"id": "log-1", "from": "+1", "to": "+2", "direction": "inbound",
                 "status": "ended", "duration": 3, "created_at": "2026-09-09T20:15:26Z"}]

        async def fake_invoke(self, resource, op, **kw):
            assert (resource.key, op) == ("logs", "list")
            return {"data": rows}

        monkeypatch.setattr(cli.SwshClient, "invoke", fake_invoke)
        result = runner.invoke(cli.app, ["logs", "list", "-n", "1"])
        assert result.exit_code == 0, result.output
        for column in cli.resources.get("logs").columns:
            assert column in result.output


class TestCatalogCommandsNeedNoCredentials:
    """Reading the checked-in catalog must not require being logged in.

    `coro` used to resolve a profile before the command body ran, so
    `sw api --list` — which touches nothing but `spec_catalog.json` — failed with
    "not logged in". Found when logging out on a real machine broke the suite.
    """

    def test_api_list_works_logged_out(self):
        result = runner.invoke(cli.app, ["api", "--list", "--json"])
        assert result.exit_code == 0, result.output
        assert len(json.loads(result.output)) == spec.total()

    def test_api_list_scoped_works_logged_out(self):
        result = runner.invoke(cli.app, ["api", "--list", "fax-api"])
        assert result.exit_code == 0, result.output

    def test_resources_table_works_logged_out(self):
        assert runner.invoke(cli.app, ["docs", "--list"]).exit_code == 0

    def test_docs_works_logged_out(self):
        assert runner.invoke(cli.app, ["docs"]).exit_code == 0

    def test_a_request_still_reports_missing_credentials(self):
        # Deferring resolution must not swallow the failure, only move it.
        result = runner.invoke(cli.app, ["whoami"])
        assert result.exit_code == 2
        assert "missing" in result.output or "not logged in" in result.output

    def test_api_dry_run_needs_no_credentials_either(self):
        # A dry run resolves the route and prints it; it sends nothing, so it
        # should not demand a token. The space is still needed to show the URL.
        result = runner.invoke(cli.app, ["api", "list_subscribers", "--dry-run"])
        assert result.exit_code in (0, 2)  # 2 only because the URL needs a space


class TestTheVersionHasOneSourceOfTruth:
    """It was declared in `pyproject.toml` and `swsh/__init__.py` with nothing
    keeping them in step. The first sign of a drift is a wheel whose metadata
    disagrees with what `sw --version` prints, which nobody looks at."""

    def test_the_package_and_the_distribution_agree(self):
        import importlib.metadata

        from swsh import __version__
        assert importlib.metadata.version("swsh") == __version__

    def test_pyproject_does_not_declare_it_a_second_time(self):
        import tomllib

        pyproject = tomllib.loads(
            (Path(__file__).resolve().parents[1] / "pyproject.toml").read_bytes().decode())
        assert "version" not in pyproject["project"]
        assert "version" in pyproject["project"]["dynamic"]

    def test_what_sw_version_prints_is_that_same_string(self):
        from swsh import __version__
        result = runner.invoke(cli.app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
