"""Credential resolution, profile management, and logout.

The load-bearing property: a stored profile must beat a stray ``.env`` file, so
creating, deleting and switching profiles always takes effect. A leftover
``.env`` silently overriding everything is exactly the bug this guards against.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from swsh import config


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Point config + .env at a temp dir and clear real env vars."""
    cfg = tmp_path / "config.toml"
    monkeypatch.setattr(config, "config_path", lambda: cfg)
    legacy = [a for aliases in config.ENV_ALIASES.values() for a in aliases]
    for var in (config.ENV_PROJECT, config.ENV_TOKEN, config.ENV_SPACE,
                "SWSH_PROFILE", *legacy):
        # The legacy aliases matter here: a developer machine that still exports
        # PROJECT_ID would otherwise leak a real credential into these tests.
        monkeypatch.delenv(var, raising=False)
    # keep keyring out of the test
    monkeypatch.setattr(config, "_keyring_set", lambda *a, **k: False)
    monkeypatch.setattr(config, "_keyring_get", lambda *a, **k: None)
    # resolve .env from the temp dir, not the real cwd
    dotenv = tmp_path / ".env"
    real_load = config.load_dotenv
    monkeypatch.setattr(config, "load_dotenv", lambda path=None: real_load(dotenv))
    return tmp_path


def write_env(tmp_path, **vals):
    (tmp_path / ".env").write_text("\n".join(f"{k}={v}" for k, v in vals.items()))


class TestPrecedence:
    def test_stored_profile_beats_a_stray_dotenv(self, isolated):
        # The reported bug: a .env made profile switching a no-op.
        write_env(isolated, SIGNALWIRE_PROJECT_ID="proj-ENV",
                  SIGNALWIRE_API_TOKEN="tok-ENV", SIGNALWIRE_SPACE="example.signalwire.com")
        config.save_profile("work", "proj-WORK", "tok-WORK", "example.signalwire.com")

        profile, sources = config.resolve_with_sources()
        assert profile.project == "proj-WORK"
        assert sources["project"] == "profile"

    def test_dotenv_is_the_fallback_when_no_profile(self, isolated):
        write_env(isolated, SIGNALWIRE_PROJECT_ID="proj-ENV",
                  SIGNALWIRE_API_TOKEN="tok-ENV", SIGNALWIRE_SPACE="example.signalwire.com")
        profile, sources = config.resolve_with_sources()
        assert profile.project == "proj-ENV"
        assert sources["project"] == ".env"

    def test_real_env_beats_profile(self, isolated, monkeypatch):
        config.save_profile("work", "proj-WORK", "tok-WORK", "example.signalwire.com")
        monkeypatch.setenv(config.ENV_PROJECT, "proj-REALENV")
        monkeypatch.setenv(config.ENV_TOKEN, "tok-REALENV")
        monkeypatch.setenv(config.ENV_SPACE, "example.signalwire.com")
        profile, sources = config.resolve_with_sources()
        assert profile.project == "proj-REALENV"
        assert sources["project"] == "env"

    def test_a_named_profile_beats_the_environment(self, isolated, monkeypatch):
        # From the test-plan pass: `sw get numbers --profile alice` kept using
        # the exported project. Naming a profile is the clearest thing a person
        # can say, so it outranks whatever the shell happens to export.
        config.save_profile("work", "proj-WORK", "tok-WORK", "example.signalwire.com")
        config.save_profile("scratch", "proj-SCRATCH", "tok-SCRATCH", "example.signalwire.com")
        config.set_default("work")
        monkeypatch.setenv(config.ENV_PROJECT, "proj-REALENV")
        monkeypatch.setenv(config.ENV_TOKEN, "tok-REALENV")
        monkeypatch.setenv(config.ENV_SPACE, "example.signalwire.com")

        profile, sources = config.resolve_with_sources("scratch")
        assert profile.project == "proj-SCRATCH"
        assert profile.token == "tok-SCRATCH"
        assert sources == {"project": "profile", "token": "profile", "space": "profile"}
        # The default, not named, still loses: scripts that export stay predictable.
        assert config.resolve_with_sources()[0].project == "proj-REALENV"

    def test_swsh_profile_counts_as_naming_one(self, isolated, monkeypatch):
        config.save_profile("scratch", "proj-SCRATCH", "tok-SCRATCH", "example.signalwire.com")
        monkeypatch.setenv(config.ENV_PROJECT, "proj-REALENV")
        monkeypatch.setenv("SWSH_PROFILE", "scratch")
        assert config.resolve().project == "proj-SCRATCH"

    def test_a_named_profile_still_falls_back_to_env_for_what_it_lacks(
            self, isolated, monkeypatch):
        # A partial profile fills its gaps from the environment; naming it is
        # not a vow of silence about everything else.
        config.save_profile("partial", "proj-PART", "", "example.signalwire.com")
        monkeypatch.setenv(config.ENV_TOKEN, "tok-REALENV")
        profile, sources = config.resolve_with_sources("partial")
        assert profile.project == "proj-PART" and profile.token == "tok-REALENV"
        assert sources["token"] == "env"

    def test_source_summary_follows_the_named_profile(self, isolated, monkeypatch):
        config.save_profile("scratch", "proj-SCRATCH", "tok-SCRATCH", "example.signalwire.com")
        monkeypatch.setenv(config.ENV_PROJECT, "proj-REALENV")
        monkeypatch.setenv(config.ENV_TOKEN, "tok-REALENV")
        monkeypatch.setenv(config.ENV_SPACE, "example.signalwire.com")
        assert set(config.active_source_summary().values()) == {"env"}
        assert set(config.active_source_summary("scratch").values()) == {"profile"}

    def test_shadowing_sources_counts_the_legacy_alias_form(self):
        summary = {"project": "env (PROJECT_ID)", "token": "profile", "space": ".env"}
        assert config.shadowing_sources(summary) == {"env (PROJECT_ID)", ".env"}
        assert config.shadowing_sources({"project": "profile"}) == set()

    def test_explicit_flag_wins_over_all(self, isolated):
        config.save_profile("work", "proj-WORK", "tok-WORK", "example.signalwire.com")
        profile, sources = config.resolve_with_sources(project="proj-FLAG",
                                                       token="t", space="s")
        assert profile.project == "proj-FLAG"
        assert sources["project"] == "flag"


class TestProfileManagement:
    def test_create_then_switch_takes_effect(self, isolated):
        config.save_profile("a", "proj-A", "tok-A", "example.signalwire.com")
        config.save_profile("b", "proj-B", "tok-B", "example.signalwire.com")
        config.set_default("a")
        assert config.resolve().project == "proj-A"
        config.set_default("b")
        assert config.resolve().project == "proj-B"

    def test_delete_removes_the_profile(self, isolated):
        config.save_profile("a", "proj-A", "tok-A", "example.signalwire.com")
        assert "a" in config.list_profiles()
        assert config.delete_profile("a") is True
        assert "a" not in config.list_profiles()


class TestLogout:
    """Logging out deselects; it does not delete.

    These two used to be the same operation: `logout` called `delete_profile`
    and destroyed the API token, so logging out of one of two profiles left you
    silently logged in as the other. Removal is `sw profile delete`.
    """

    def test_logout_keeps_every_profile(self, isolated):
        config.save_profile("work", "p1", "t1", "example.signalwire.com")
        config.save_profile("home", "p2", "t2", "example.signalwire.com")

        report = config.logout()

        assert sorted(report["kept"]) == ["home", "work"]
        assert sorted(config.list_profiles()) == ["home", "work"]
        assert report["still_provided_by"] == {}

    def test_logout_reports_which_profile_was_active(self, isolated):
        config.save_profile("work", "p1", "t1", "example.signalwire.com")
        assert config.logout()["profile"] == "work"

    def test_after_logout_no_profile_is_selected(self, isolated):
        config.save_profile("work", "p1", "t1", "example.signalwire.com")
        config.save_profile("home", "p2", "t2", "example.signalwire.com")
        config.logout()

        # The bug this guards: an empty default used to fall back to the first
        # profile, so logging out logged you in as someone else.
        assert config.is_logged_out()
        assert config.default_profile_name() == ""

    def test_logged_out_resolution_says_to_pick_one(self, isolated):
        config.save_profile("work", "p1", "t1", "example.signalwire.com")
        config.logout()
        with pytest.raises(config.ConfigError) as caught:
            config.resolve()
        message = str(caught.value)
        assert "not logged in" in message
        assert "sw profile use" in message
        assert "work" in message  # names what is available

    def test_logging_back_in_needs_nothing_re_entered(self, isolated):
        config.save_profile("work", "p1", "t1", "example.signalwire.com")
        config.logout()
        config.set_default("work")

        assert not config.is_logged_out()
        profile = config.resolve()
        assert profile.name == "work"
        assert profile.token == "t1"  # never left the file

    def test_an_absent_default_still_falls_back_to_the_only_profile(self, isolated):
        # A never-chosen default is different from an explicitly cleared one, so
        # a single-profile setup needs no ceremony.
        config.save_profile("solo", "p", "t", "example.signalwire.com")
        doc = config._read_doc()
        doc.pop("default", None)
        config._write_doc(doc)

        assert not config.is_logged_out()
        assert config.default_profile_name() == "solo"

    def test_logout_warns_when_dotenv_still_shadows(self, isolated):
        config.save_profile("default", "proj", "tok", "example.signalwire.com")
        write_env(isolated, SIGNALWIRE_PROJECT_ID="p", SIGNALWIRE_API_TOKEN="t",
                  SIGNALWIRE_SPACE="s")
        report = config.logout()
        # logout must reveal that .env keeps you effectively logged in
        assert set(report["still_provided_by"].values()) == {".env"}

    def test_logout_warns_when_real_env_still_shadows(self, isolated, monkeypatch):
        config.save_profile("default", "proj", "tok", "example.signalwire.com")
        monkeypatch.setenv(config.ENV_PROJECT, "p")
        report = config.logout()
        assert report["still_provided_by"].get("project") == "env"

    def test_logout_with_no_profiles_at_all_is_harmless(self, isolated):
        report = config.logout()
        assert report["kept"] == []


class TestDurableStorage:
    """Credentials must survive a missing/locked keyring — the reported
    "I keep getting logged out" bug."""

    def test_token_persists_in_the_file_not_only_the_keyring(self, isolated, monkeypatch):
        # keyring writes succeed, but the file must STILL hold the token so a
        # later keyring failure cannot log the user out.
        monkeypatch.setenv("SWSH_USE_KEYRING", "1")
        monkeypatch.setattr(config, "_keyring_set", lambda *a, **k: True)
        config.save_profile("default", "proj", "tok-DURABLE", "example.signalwire.com")
        doc = config._read_doc()
        assert doc["profiles"]["default"]["token"] == "tok-DURABLE"

    def test_resolves_even_when_keyring_is_dead(self, isolated, monkeypatch):
        config.save_profile("default", "proj", "tok-DURABLE", "example.signalwire.com")
        # keyring now returns nothing (locked/denied) — file must carry the day.
        monkeypatch.setattr(config, "_keyring_get", lambda *a, **k: None)
        assert config.resolve().token == "tok-DURABLE"

    def test_legacy_keyring_only_profile_is_migrated_into_the_file(
        self, isolated, monkeypatch
    ):
        # Simulate an old profile: token lives only in the keyring.
        config.save_profile("default", "proj", "IGNORED", "example.signalwire.com")
        doc = config._read_doc()
        del doc["profiles"]["default"]["token"]
        doc["profiles"]["default"]["token_in_keyring"] = True
        config._write_doc(doc)
        monkeypatch.setattr(config, "_keyring_get", lambda *a, **k: "tok-LEGACY")

        profile = config.resolve()
        assert profile.token == "tok-LEGACY"
        # and it is now durably in the file, so the next keyring failure is moot
        migrated = config._read_doc()
        assert migrated["profiles"]["default"]["token"] == "tok-LEGACY"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
    def test_a_new_config_file_is_private_from_the_start(self, isolated, monkeypatch):
        # Created 0600, not written under the umask and chmodded afterwards:
        # the token must never sit in a file someone else can read.
        modes: list[int] = []
        real_open = config.os.open

        def recording_open(path, flags, mode=0o777):
            modes.append(mode)
            return real_open(path, flags, mode)

        monkeypatch.setattr(config.os, "open", recording_open)
        config.save_profile("default", "proj", "tok", "example.signalwire.com")
        assert modes and all(m == 0o600 for m in modes)
        assert (isolated / "config.toml").stat().st_mode & 0o777 == 0o600

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
    def test_an_existing_loose_config_file_is_tightened(self, isolated):
        cfg = isolated / "config.toml"
        cfg.write_text("")
        cfg.chmod(0o644)
        config.save_profile("default", "proj", "tok", "example.signalwire.com")
        assert cfg.stat().st_mode & 0o777 == 0o600


class TestRelayHost:
    def test_prod_relay_host(self):
        p = config.Profile("x", "p", "t", "example.signalwire.com")
        assert p.relay_host == "relay.signalwire.com"

    def test_staging_relay_host(self):
        p = config.Profile("x", "p", "t", "example.swire.io")
        assert p.relay_host == "relay.swire.io"

    def test_relay_host_ignores_url_scheme(self):
        p = config.Profile("x", "p", "t", "https://example.signalwire.com/")
        assert p.relay_host == "relay.signalwire.com"


class TestLegacyEnvAliases:
    """swsh 1.x/2.0 exported PROJECT_ID and REST_API_TOKEN.

    Upgrading to `sw` must not look like a silent logout for anyone whose shell,
    .env or CI job still sets those names.
    """

    def test_legacy_names_resolve(self, isolated, monkeypatch):
        monkeypatch.setenv("PROJECT_ID", "proj-legacy")
        monkeypatch.setenv("REST_API_TOKEN", "tok-legacy")
        monkeypatch.setenv(config.ENV_SPACE, "example.signalwire.com")

        profile, sources = config.resolve_with_sources()

        assert profile.project == "proj-legacy"
        assert profile.token == "tok-legacy"
        # the source names the alias, so `whoami` stays honest about the origin
        assert sources["project"] == "env (PROJECT_ID)"
        assert sources["token"] == "env (REST_API_TOKEN)"
        assert sources["space"] == "env"

    def test_canonical_name_wins_over_the_alias(self, isolated, monkeypatch):
        monkeypatch.setenv("PROJECT_ID", "proj-legacy")
        monkeypatch.setenv(config.ENV_PROJECT, "proj-canonical")
        monkeypatch.setenv("REST_API_TOKEN", "tok-legacy")
        monkeypatch.setenv(config.ENV_SPACE, "example.signalwire.com")

        profile, sources = config.resolve_with_sources()

        assert profile.project == "proj-canonical"
        assert sources["project"] == "env"

    def test_a_stored_profile_still_beats_a_legacy_dotenv(self, isolated):
        # Same load-bearing property as TestPrecedence, via the alias path.
        write_env(isolated, PROJECT_ID="proj-ENV", REST_API_TOKEN="tok-ENV",
                  SIGNALWIRE_SPACE="example.signalwire.com")
        config.save_profile("work", project="proj-WORK", token="tok-WORK",
                            space="example.signalwire.com")

        profile, sources = config.resolve_with_sources("work")

        assert profile.project == "proj-WORK"
        assert sources["project"] == "profile"

    def test_logout_reports_a_shadowing_legacy_var(self, isolated, monkeypatch):
        config.save_profile("work", project="p", token="t", space="example.signalwire.com")
        monkeypatch.setenv("PROJECT_ID", "proj-legacy")

        report = config.logout()

        assert report["kept"] == ["work"]  # deselected, not deleted
        assert report["still_provided_by"]["project"] == "env (PROJECT_ID)"


class TestSpaceNormalisation:
    """A space may be written as a bare name, a hostname, or a URL.

    The dashboard and the docs both call it "your space name", so the bare form
    is what people type. Left alone it produced `https://example` and a
    DNS failure whose message said nothing about the space.
    """

    def _host(self, space: str) -> str:
        return config.Profile(name="t", project="p", token="k", space=space).host

    def test_a_bare_name_gets_the_default_domain(self):
        assert self._host("example") == "example.signalwire.com"

    def test_a_full_hostname_is_left_alone(self):
        assert self._host("example.signalwire.com") == "example.signalwire.com"

    def test_a_url_is_reduced_to_its_host(self):
        assert self._host("https://example.signalwire.com/") == (
            "example.signalwire.com"
        )

    def test_a_bare_name_in_a_url_still_gets_the_domain(self):
        assert self._host("https://example") == "example.signalwire.com"

    def test_whitespace_is_tolerated(self):
        assert self._host("  example  ") == "example.signalwire.com"

    def test_a_staging_hostname_is_never_rewritten(self):
        # Staging spaces live on swire.io; appending would break them.
        assert self._host("example.swire.io") == "example.swire.io"
        assert self._host("https://example.swire.io/") == "example.swire.io"

    def test_staging_base_url(self):
        profile = config.Profile(name="t", project="p", token="k", space="example.swire.io")
        assert profile.base_url == "https://example.swire.io"

    def test_known_domains_are_accepted(self):
        assert config.check_space("example") == "example.signalwire.com"
        assert config.check_space("https://Example.SignalWire.com/") == "Example.SignalWire.com"
        assert config.check_space("dev.swire.io") == "dev.swire.io"
        assert config.space_domain("dev.swire.io") == "swire.io"

    @pytest.mark.parametrize("space", ["example.example.com", "swire.io", "signalwire.com",
                                       "example.notswire.io", "localhost:8080", ""])
    def test_unknown_domains_are_refused(self, space):
        with pytest.raises(config.ConfigError, match="invalid space domain"):
            config.check_space(space)

    def test_a_host_with_a_port_is_never_rewritten(self):
        assert self._host("localhost:8080") == "localhost:8080"

    def test_relay_host_follows_the_normalised_domain(self):
        profile = config.Profile(name="t", project="p", token="k", space="example")
        assert profile.relay_host == "relay.signalwire.com"

    def test_base_url_is_a_reachable_url(self):
        profile = config.Profile(name="t", project="p", token="k", space="example")
        assert profile.base_url == "https://example.signalwire.com"


class TestLegacyDotenvLocation:
    """swsh 1.x and 2.0 read `~/.swsh/.env` as a fallback.

    Dropping it silently logged out anyone who kept credentials there, with no
    message pointing at the cause.
    """

    def test_both_locations_are_searched_in_order(self):
        paths = config.dotenv_paths()
        assert paths[0].name == ".env"
        assert paths[0].parent == Path.cwd()
        assert paths[1] == Path.home() / ".swsh" / ".env"

    def test_the_legacy_file_is_read_when_there_is_no_local_one(self, tmp_path, monkeypatch):
        legacy = tmp_path / "legacy" / ".env"
        legacy.parent.mkdir()
        legacy.write_text("SIGNALWIRE_PROJECT_ID=from-legacy\n")
        monkeypatch.setattr(config, "dotenv_paths",
                            lambda: [tmp_path / "absent" / ".env", legacy])
        assert config.load_dotenv()["SIGNALWIRE_PROJECT_ID"] == "from-legacy"

    def test_a_project_local_file_wins_over_the_legacy_one(self, tmp_path, monkeypatch):
        local = tmp_path / "local.env"
        local.write_text("SIGNALWIRE_PROJECT_ID=from-local\n")
        legacy = tmp_path / "legacy.env"
        legacy.write_text("SIGNALWIRE_PROJECT_ID=from-legacy\n")
        monkeypatch.setattr(config, "dotenv_paths", lambda: [local, legacy])
        assert config.load_dotenv()["SIGNALWIRE_PROJECT_ID"] == "from-local"

    def test_neither_present_is_not_an_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "dotenv_paths",
                            lambda: [tmp_path / "a.env", tmp_path / "b.env"])
        assert config.load_dotenv() == {}


class TestLoadProfile:
    def test_stored_values_win_over_the_environment(self, isolated, monkeypatch):
        # `resolve` would hand back the env var; a person who named a profile
        # wants that profile.
        config.save_profile("scratch", "proj-s", "tok-s", "example.signalwire.com")
        monkeypatch.setenv(config.ENV_PROJECT, "proj-from-env")
        profile = config.load_profile("scratch")
        assert profile.project == "proj-s"
        assert profile.host == "example.signalwire.com"

    def test_unknown_name_is_a_config_error(self, isolated):
        with pytest.raises(config.ConfigError):
            config.load_profile("nope")
