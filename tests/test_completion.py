"""Shell tab completion: install, inspect, remove.

Typer ships `--install-completion` and no way to undo it, and it never says what
it wrote. Since the installer edits a real shell startup file, every test here
runs against a sandboxed `HOME` — a test that appends to the developer's own
`~/.zshrc` would be worse than no test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from swsh import cli

runner = CliRunner()


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A throwaway HOME with an existing startup file to protect."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".zshrc").write_text("# existing config\nalias ll='ls -la'\n")
    (tmp_path / ".bashrc").write_text("# existing bash config\n")
    # The layout table is built at import time from Path.home(), so rebuild it
    # against the sandbox.
    monkeypatch.setattr(cli, "_COMPLETION_LAYOUT", {
        "zsh": {
            "script": lambda prog: tmp_path / ".zfunc" / f"_{prog}",
            "rc": tmp_path / ".zshrc",
            "rc_line": "fpath+=~/.zfunc; autoload -Uz compinit; compinit",
            "rc_line_shared": True,
        },
        "bash": {
            "script": lambda prog: tmp_path / ".bash_completions" / f"{prog}.sh",
            "rc": tmp_path / ".bashrc",
            "rc_line": None,
            "rc_line_shared": False,
        },
    })
    return tmp_path


def install_zsh_for(home_dir: Path, prog: str = "sw") -> Path:
    """Write a completion script the way typer's installer would."""
    script = home_dir / ".zfunc" / f"_{prog}"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(f"#compdef {prog}\n")
    rc = home_dir / ".zshrc"
    rc.write_text(rc.read_text()
                  + "\nfpath+=~/.zfunc; autoload -Uz compinit; compinit\n")
    return script


class TestStatus:
    def test_reports_not_installed(self, home):
        result = runner.invoke(cli.app, ["completion", "status", "--shell", "zsh"])
        assert result.exit_code == 0
        assert "not installed" in result.output

    def test_reports_installed_and_names_the_file(self, home):
        install_zsh_for(home)
        out = runner.invoke(cli.app, ["completion", "status", "--shell", "zsh"]).output
        assert "installed" in out
        assert "_sw" in out

    def test_the_shared_zsh_line_is_not_evidence_of_installation(self, home):
        """The bug this caught: the `~/.zfunc` startup line is shared by every
        tool that puts completions there, so treating it as evidence reported
        `swsh` as installed whenever `sw` was."""
        install_zsh_for(home, "sw")  # only sw
        out = runner.invoke(cli.app, ["completion", "status", "--shell", "zsh"]).output
        assert "sw for zsh" in out
        assert "swsh for zsh" not in out

    def test_json_carries_the_paths(self, home):
        import json

        install_zsh_for(home)
        result = runner.invoke(
            cli.app, ["completion", "status", "--shell", "zsh", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        entry = next(e for e in payload["entries"] if e["program"] == "sw")
        assert entry["installed"] is True
        assert entry["script"].endswith("_sw")

    def test_an_unknown_shell_lists_the_known_ones(self, home):
        result = runner.invoke(cli.app, ["completion", "status", "--shell", "tcsh"])
        assert result.exit_code == 2
        assert "zsh" in result.output


class TestUninstall:
    def test_it_removes_the_script(self, home):
        script = install_zsh_for(home)
        result = runner.invoke(
            cli.app, ["completion", "uninstall", "--shell", "zsh", "--yes"])
        assert result.exit_code == 0
        assert not script.exists()

    def test_it_keeps_the_rest_of_the_startup_file(self, home):
        # The whole risk of this command: it edits a file full of someone's
        # unrelated configuration.
        install_zsh_for(home)
        runner.invoke(cli.app, ["completion", "uninstall", "--shell", "zsh", "-y"])
        rc = (home / ".zshrc").read_text()
        assert "# existing config" in rc
        assert "alias ll='ls -la'" in rc

    def test_it_removes_the_zsh_line_when_nothing_else_uses_zfunc(self, home):
        install_zsh_for(home)
        runner.invoke(cli.app, ["completion", "uninstall", "--shell", "zsh", "-y"])
        assert "fpath+=~/.zfunc" not in (home / ".zshrc").read_text()

    def test_it_leaves_the_zsh_line_when_another_tool_uses_zfunc(self, home):
        install_zsh_for(home)
        (home / ".zfunc" / "_someothertool").write_text("#compdef someothertool\n")

        result = runner.invoke(
            cli.app, ["completion", "uninstall", "--shell", "zsh", "-y"])

        assert "fpath+=~/.zfunc" in (home / ".zshrc").read_text()
        assert "still use" in result.output
        assert (home / ".zfunc" / "_someothertool").exists()

    def test_bash_loses_its_source_line(self, home):
        # Unlike zsh's, the bash line names our script, so it is ours to remove.
        script = home / ".bash_completions" / "sw.sh"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# completion\n")
        rc = home / ".bashrc"
        rc.write_text(rc.read_text() + f"\nsource '{script}'\n")

        result = runner.invoke(
            cli.app, ["completion", "uninstall", "--shell", "bash", "-y"])

        assert result.exit_code == 0
        assert not script.exists()
        assert "source" not in rc.read_text()
        assert "# existing bash config" in rc.read_text()

    def test_nothing_installed_is_not_an_error(self, home):
        result = runner.invoke(
            cli.app, ["completion", "uninstall", "--shell", "zsh", "-y"])
        assert result.exit_code == 0
        assert "no zsh completion installed" in result.output

    def test_it_refuses_without_yes_when_non_interactive(self, home, monkeypatch):
        monkeypatch.setattr(cli.prompts, "interactive", lambda: False)
        script = install_zsh_for(home)
        result = runner.invoke(cli.app, ["completion", "uninstall", "--shell", "zsh"])
        assert result.exit_code == 2
        assert script.exists()

    def test_declining_removes_nothing(self, home, monkeypatch):
        monkeypatch.setattr(cli.prompts, "interactive", lambda: True)
        monkeypatch.setattr(cli.typer, "confirm", lambda *a, **k: False)
        script = install_zsh_for(home)
        result = runner.invoke(cli.app, ["completion", "uninstall", "--shell", "zsh"])
        assert result.exit_code == 0
        assert script.exists()

    def test_all_also_removes_the_alias_completion(self, home):
        install_zsh_for(home, "sw")
        install_zsh_for(home, "swsh")
        runner.invoke(
            cli.app, ["completion", "uninstall", "--shell", "zsh", "--all", "-y"])
        assert not (home / ".zfunc" / "_sw").exists()
        assert not (home / ".zfunc" / "_swsh").exists()

    def test_without_all_the_alias_is_left_alone(self, home):
        install_zsh_for(home, "sw")
        install_zsh_for(home, "swsh")
        runner.invoke(cli.app, ["completion", "uninstall", "--shell", "zsh", "-y"])
        assert not (home / ".zfunc" / "_sw").exists()
        assert (home / ".zfunc" / "_swsh").exists()

    def test_an_undetectable_shell_says_what_to_pass(self, home, monkeypatch):
        monkeypatch.setattr(cli, "_current_shell", lambda: None)
        result = runner.invoke(cli.app, ["completion", "uninstall", "-y"])
        assert result.exit_code == 2
        assert "--shell" in result.output


class TestShow:
    def test_it_prints_a_script_without_installing(self, home):
        result = runner.invoke(cli.app, ["completion", "show", "--shell", "zsh"])
        assert result.exit_code == 0
        assert "compdef sw" in result.output
        assert not (home / ".zfunc").exists()  # nothing written

    def test_an_unsupported_shell_fails_cleanly(self, home):
        result = runner.invoke(cli.app, ["completion", "show", "--shell", "tcsh"])
        assert result.exit_code == 2


class TestShellDetection:
    def test_it_falls_back_to_the_shell_variable(self, monkeypatch):
        # shellingham reads the process tree and fails under a pipe, which is
        # exactly how this runs in CI.
        monkeypatch.setitem(__import__("sys").modules, "shellingham", None)
        monkeypatch.setenv("SHELL", "/usr/local/bin/fish")
        assert cli._current_shell() == "fish"

    def test_no_shell_at_all_is_none_not_a_crash(self, monkeypatch):
        monkeypatch.setitem(__import__("sys").modules, "shellingham", None)
        monkeypatch.setenv("SHELL", "")
        assert cli._current_shell() is None


class TestRuntimeCompletionStaysRegistered:
    """`add_completion=False` removes typer's two root flags — and, as a side
    effect nobody would guess, stops it registering the per-shell completion
    classes. An installed script then fails with "Shell zsh not supported".

    `cli` calls `completion_init()` itself to compensate. These pin that.
    """

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish", "powershell", "pwsh"])
    def test_every_shell_class_is_registered(self, shell):
        from typer._click.shell_completion import get_completion_class

        assert get_completion_class(shell) is not None, shell

    def test_the_root_flags_are_gone(self):
        out = runner.invoke(cli.app, ["--help"]).output
        options = out.split("Options")[1].split("Commands")[0]
        assert "--install-completion" not in options
        assert "--show-completion" not in options

    def test_the_completion_subcommand_replaces_them(self):
        out = runner.invoke(cli.app, ["--help"]).output
        assert "completion" in out

    def test_completion_actually_resolves_resource_keys(self, monkeypatch):
        # End to end: this is what the installed shell script invokes. If the
        # classes were unregistered it prints an error instead of candidates.
        monkeypatch.setenv("_SW_COMPLETE", "complete_zsh")
        monkeypatch.setenv("_TYPER_COMPLETE_ARGS", "sw numbers ")
        result = runner.invoke(cli.app, [])
        assert "not supported" not in result.output
        assert "list" in result.output and "buy" in result.output


class TestPathWarning:
    """Completion invokes `sw` by name, so it needs `sw` on PATH.

    Installed with `pip install -e .` in a virtualenv, `sw` exists only while
    that environment is active. A new terminal cannot find it and the completion
    script then does nothing — silently, with no error to follow. Installing
    completion without saying so sets up a confusing failure.
    """

    def test_it_warns_when_sw_is_only_inside_the_venv(self, home, monkeypatch):
        import sysconfig

        venv_bin = sysconfig.get_path("scripts")
        monkeypatch.setattr(
            "shutil.which", lambda name: f"{venv_bin}/sw" if name == "sw" else None)
        monkeypatch.setattr(
            "typer._completion_shared.install",
            lambda **kw: ("zsh", home / ".zfunc" / "_sw"))

        out = runner.invoke(cli.app, ["completion", "install", "--shell", "zsh"]).output
        assert "only on PATH inside this virtualenv" in out
        assert "uv tool install" in out

    def test_it_stays_quiet_when_sw_is_globally_available(self, home, monkeypatch):
        monkeypatch.setattr(
            "shutil.which", lambda name: "/usr/local/bin/sw" if name == "sw" else None)
        monkeypatch.setattr(
            "typer._completion_shared.install",
            lambda **kw: ("zsh", home / ".zfunc" / "_sw"))

        out = runner.invoke(cli.app, ["completion", "install", "--shell", "zsh"]).output
        assert "virtualenv" not in out

    def test_it_warns_when_sw_is_not_found_at_all(self, home, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _name: None)
        monkeypatch.setattr(
            "typer._completion_shared.install",
            lambda **kw: ("zsh", home / ".zfunc" / "_sw"))

        out = runner.invoke(cli.app, ["completion", "install", "--shell", "zsh"]).output
        assert "silently do nothing" in out


class TestItIsSetUpWithoutBeingAskedFor:
    """`--install-completion` is a thing you have to already know exists, and
    typing `sw numb<TAB>` and getting nothing is how people conclude a CLI has
    none. pip cannot do it — installing a wheel runs no code — so the first
    interactive run is the earliest honest moment.
    """

    @pytest.fixture
    def first_run(self, home, monkeypatch):
        """A terminal, a known shell, and nothing installed yet."""
        marker = home / "config" / "completion-attempted"
        monkeypatch.setattr(cli, "_completion_marker", lambda: marker)
        monkeypatch.setattr(cli, "_on_a_terminal", lambda: True)
        monkeypatch.setattr(cli, "_current_shell", lambda: "zsh")
        monkeypatch.delenv(cli.AUTO_COMPLETION_ENV, raising=False)
        installed: list[tuple] = []

        def fake_install(shell=None, prog_name=None):
            (home / ".zfunc").mkdir(exist_ok=True)
            path = home / ".zfunc" / f"_{prog_name}"
            path.write_text("# completion\n")
            installed.append((shell, prog_name))
            return shell, path

        monkeypatch.setattr("typer._completion_shared.install", fake_install)
        return installed, marker

    def test_the_first_run_in_a_terminal_installs_it(self, first_run):
        installed, marker = first_run
        cli._autoinstall_completion()
        assert installed == [("zsh", "sw")]
        assert marker.exists()

    def test_it_says_what_it_wrote_and_how_to_undo_it(self, first_run, capsys):
        """Editing someone's shell configuration in silence is worse than not
        offering completion at all."""
        cli._autoinstall_completion()
        out = capsys.readouterr().out
        assert "completion" in out
        assert "sw completion uninstall" in out

    def test_it_happens_once_however_it_turned_out(self, first_run):
        installed, _ = first_run
        cli._autoinstall_completion()
        cli._autoinstall_completion()
        assert len(installed) == 1

    def test_an_uninstall_is_final(self, first_run, monkeypatch):
        """Reinstalling on the next command would make `uninstall` a no-op."""
        installed, marker = first_run
        marker.parent.mkdir(parents=True, exist_ok=True)
        runner.invoke(cli.app, ["completion", "uninstall", "--shell", "zsh", "--yes"])
        assert marker.exists()
        cli._autoinstall_completion()
        assert installed == []

    def test_a_pipe_or_a_ci_job_is_never_touched(self, first_run, monkeypatch):
        """The same guard is what keeps the suite out of a developer's ~/.zshrc."""
        installed, marker = first_run
        monkeypatch.setattr(cli, "_on_a_terminal", lambda: False)
        cli._autoinstall_completion()
        assert installed == [] and not marker.exists()

    def test_pretending_a_prompt_is_possible_does_not_open_the_door(
            self, first_run, monkeypatch):
        """`prompts.interactive()` is patched to True by tests exercising a
        confirmation. One of them appended to the developer's real ~/.zshrc,
        because this guard used to read that instead of the streams."""
        installed, marker = first_run
        monkeypatch.setattr(cli, "_on_a_terminal", lambda: False)
        monkeypatch.setattr(cli.prompts, "interactive", lambda: True)
        cli._autoinstall_completion()
        assert installed == [] and not marker.exists()

    def test_it_can_be_switched_off(self, first_run, monkeypatch):
        installed, marker = first_run
        monkeypatch.setenv(cli.AUTO_COMPLETION_ENV, "1")
        cli._autoinstall_completion()
        assert installed == [] and not marker.exists()

    def test_a_shell_it_cannot_place_is_not_probed_again(self, first_run, monkeypatch):
        installed, marker = first_run
        monkeypatch.setattr(cli, "_current_shell", lambda: None)
        cli._autoinstall_completion()
        assert installed == []
        assert marker.exists(), "an unknown shell must not be re-detected every command"

    def test_an_existing_installation_is_left_alone(self, first_run, home):
        installed, marker = first_run
        (home / ".zfunc").mkdir()
        (home / ".zfunc" / "_sw").write_text("# already here\n")
        cli._autoinstall_completion()
        assert installed == []
        assert marker.exists()

    def test_a_failed_install_is_silent_and_not_retried(self, first_run, monkeypatch, capsys):
        """It runs in front of the command someone actually typed."""
        _, marker = first_run

        def boom(shell=None, prog_name=None):
            raise RuntimeError("no")

        monkeypatch.setattr("typer._completion_shared.install", boom)
        cli._autoinstall_completion()
        assert capsys.readouterr().out == ""
        assert marker.exists()
