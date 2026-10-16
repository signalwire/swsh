#!/usr/bin/env python3
"""Scan the tree for anything that must not reach a public repository.

Two classes of finding, and the difference matters:

  **secret**  a live credential — a token, a private key, basic auth in a URL.
              Never acceptable, in any file, tracked or not: a file that is
              only gitignored is one `git add -f` or one zip away from public.
  **config**  somebody's environment — a real space, an absolute home path.
              Harmless to them, wrong in a repo other people clone.

Run it as a gate with `--check`; it exits non-zero on any finding. A file that
git ignores is still reported, with its status, because the point is what is
*on disk*, not what git happens to be tracking today.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Hidden directories (.git, .venv, caches, editor settings) are skipped too,
# except .github, which is committed. Hidden *files* such as .env are scanned.
SKIP_DIRS = {"venv", "__pycache__", "node_modules"}
SCANNED_HIDDEN_DIRS = {".github"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pyc", ".whl", ".so", ".gz",
                 ".zip", ".pdf"}
# Checked in on purpose: the bundled API catalog, operation ids and routes, no
# credentials.
SKIP_FILES = {"spec_catalog.json"}

SECRETS = [
    ("SignalWire API token", re.compile(r"\bPT[0-9a-f]{24,}\b", re.I)),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("credentials in a URL", re.compile(r"https?://[^/\s:@]+:[^/\s@]{4,}@")),
    ("assigned secret literal", re.compile(
        r"(?i)\b(api[_-]?key|secret|passwd|password|auth[_-]?token)\b\s*[:=]\s*"
        r"['\"][^'\"\s]{12,}['\"]")),
]

CONFIG = [
    ("absolute home path", re.compile(r"/(?:Users|home)/(?!<)[a-z0-9._-]+/", re.I)),
    # A space's SIP domain carries a per-space identifier, so this shape names
    # one real space and nobody else's, even though it reads like a hash.
    ("real SignalWire space", re.compile(
        r"\b[a-z0-9][a-z0-9-]*-[0-9a-f]{12}\.sip\.signalwire\.com\b", re.I)),
]

# Documentation examples and SignalWire's own product hostnames. A space named
# here is nobody's: that is the whole point of using them in docs and tests.
ALLOWED = re.compile(
    r"(?i)\b(acme|example|demo|test|scratch|localhost|127\.0\.0\.1|"
    r"your-space|my-space|<[^>]+>|relay|pstn|developer)\b")


def ignored_by_git(rel: str) -> bool:
    return subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT).returncode == 0


def scan() -> list[tuple[str, int, str, str, str]]:
    findings: list[tuple[str, int, str, str, str]] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.name in SKIP_FILES:
            continue
        dirs = path.relative_to(ROOT).parts[:-1]
        if any(d in SKIP_DIRS or (d.startswith(".") and d not in SCANNED_HIDDEN_DIRS)
               for d in dirs):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        rel = str(path.relative_to(ROOT))
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for kind, rules in (("secret", SECRETS), ("config", CONFIG)):
                for label, rx in rules:
                    for match in rx.finditer(line):
                        found = match.group(0)
                        if kind == "config" and ALLOWED.search(found):
                            continue
                        findings.append((kind, rel, lineno, label, found[:60]))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero on any finding (the CI gate)")
    args = parser.parse_args()

    findings = scan()
    if not findings:
        print("clean: no credentials or environment-specific config on disk")
        return 0

    secrets = [f for f in findings if f[0] == "secret"]
    config = [f for f in findings if f[0] == "config"]

    for title, group in (("SECRETS", secrets), ("ENVIRONMENT CONFIG", config)):
        if not group:
            continue
        print(f"\n{title}  ({len(group)})")
        for _, rel, lineno, label, found in group:
            status = " [git-ignored]" if ignored_by_git(rel) else " [IN THE REPO]"
            print(f"  {rel}:{lineno}{status}")
            print(f"      {label}: {found}")

    if secrets:
        print("\nA git-ignored credential is still a credential on disk. Move it to"
              "\nthe profile store (`sw login`) and rotate anything that has been"
              "\ncopied, pasted or backed up.")
    return 1 if args.check else 0


if __name__ == "__main__":
    sys.exit(main())
