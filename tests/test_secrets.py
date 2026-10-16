"""Nothing in the repository may be somebody's credentials or environment.

`scripts/audit_secrets.py` is the scanner; this is the gate. It runs over the
files git actually tracks, because those are the ones that become public the
moment the repo does. The script itself also reports what is merely on disk —
a `.env` that is only gitignored is one `git add -f` away — and that part is
for a person to act on, not for CI to fail on.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _audit():
    spec = importlib.util.spec_from_file_location(
        "audit_secrets", ROOT / "scripts" / "audit_secrets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tracked() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    return [ROOT / line for line in out.stdout.splitlines() if (ROOT / line).is_file()]


class TestNothingTrackedCarriesACredential:
    def test_no_tracked_file_matches_a_secret_rule(self):
        audit = _audit()
        offences = []
        for path in _tracked():
            if path.suffix.lower() in audit.SKIP_SUFFIXES or path.name in audit.SKIP_FILES:
                continue
            text = path.read_text(errors="ignore")
            for lineno, line in enumerate(text.splitlines(), 1):
                for label, rx in audit.SECRETS:
                    if rx.search(line):
                        offences.append(f"{path.relative_to(ROOT)}:{lineno} {label}")
        assert not offences, "credentials in tracked files:\n" + "\n".join(offences)

    def test_no_tracked_file_carries_an_absolute_home_path(self):
        """A path under somebody's home directory does not survive a clone."""
        audit = _audit()
        offences = []
        for path in _tracked():
            if path.suffix.lower() in audit.SKIP_SUFFIXES or path.name in audit.SKIP_FILES:
                continue
            text = path.read_text(errors="ignore")
            for lineno, line in enumerate(text.splitlines(), 1):
                for label, rx in audit.CONFIG:
                    for match in rx.finditer(line):
                        if not audit.ALLOWED.search(match.group(0)):
                            offences.append(f"{path.relative_to(ROOT)}:{lineno} {label}")
        assert not offences, "environment-specific paths:\n" + "\n".join(offences)

    def test_every_spelling_of_an_env_file_is_ignored(self):
        """`.env.bak` was untracked but not ignored — one `git add -A` from public."""
        for name in (".env", ".env.bak", ".env.local", "swsh/.env", "a/b/.env"):
            done = subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT)
            assert done.returncode == 0, f"{name} is not git-ignored"
