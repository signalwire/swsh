"""Profile storage for swsh.

Resolution order for every credential field, highest priority first:

1. an explicit argument (``--project``, ``--token``, ``--space``)
2. environment variables (``SIGNALWIRE_PROJECT_ID`` and friends, and the names
   swsh 1.x used)
3. the selected stored profile, in ``config.toml`` under the platform's user
   config directory (``sw profile path`` prints it)
4. a ``.env`` in the current directory, then ``~/.swsh/.env``

Naming a profile (``--profile`` or ``SWSH_PROFILE``) moves it above the
environment; ``resolve`` has the details.

Tokens are stored durably in the config file, which is written with 0600
permissions from the start, so a profile survives reboots, new terminals and a
flaky or locked OS keyring. Set ``SWSH_USE_KEYRING=1`` to additionally push the
token into the OS keyring; even then the file keeps a copy so retrieval never
depends on the keyring being reachable. Legacy keyring-only profiles are
migrated into the file the first time they resolve successfully.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit
from platformdirs import user_config_dir

APP_NAME = "swsh"
KEYRING_SERVICE = "swsh"

ENV_PROJECT = "SIGNALWIRE_PROJECT_ID"
ENV_TOKEN = "SIGNALWIRE_API_TOKEN"
ENV_SPACE = "SIGNALWIRE_SPACE"

# swsh 1.x/2.0 read these names, and they are what existing shells, .env files
# and CI jobs still export. Accepted as fallbacks so upgrading to `sw` does not
# look like a silent logout. Canonical names win when both are set.
ENV_ALIASES: dict[str, tuple[str, ...]] = {
    ENV_PROJECT: ("PROJECT_ID",),
    ENV_TOKEN: ("REST_API_TOKEN",),
    ENV_SPACE: (),
}


# Appended when a space is given as a bare name, which is how the dashboard and
# the docs refer to it ("your space name").
DEFAULT_SPACE_DOMAIN = ".signalwire.com"


def config_path() -> Path:
    return Path(user_config_dir(APP_NAME)) / "config.toml"


def dotenv_paths() -> list[Path]:
    """Where a ``.env`` is looked for, in priority order.

    ``~/.swsh/.env`` is where swsh 1.x and 2.0 kept credentials, and dropping it
    silently logged out anyone who had been using it. Kept as the lower-priority
    of the two so a project-local ``.env`` still wins.
    """
    return [Path.cwd() / ".env", Path.home() / ".swsh" / ".env"]


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    """Read a ``.env`` and return its values, without touching ``os.environ``.

    Deliberately does not mutate the environment: a leftover ``.env`` is a
    convenience, and it must not silently override a profile the user is
    actively managing. ``resolve`` consults it as the lowest-priority source.

    With no explicit path, the first file that exists from ``dotenv_paths``
    wins — the project-local one, then the legacy ``~/.swsh/.env``.
    """
    if path is None:
        path = next((p for p in dotenv_paths() if p.is_file()), dotenv_paths()[0])
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


class ConfigError(RuntimeError):
    pass


@dataclass(slots=True)
class Profile:
    """One set of SignalWire credentials."""

    name: str
    project: str
    token: str
    space: str

    @property
    def host(self) -> str:
        """Bare hostname, however the space was written.

        All of these resolve to ``example.signalwire.com``::

            example
            example.signalwire.com
            https://example.signalwire.com
            https://example.signalwire.com/

        The bare form is the one people actually type, because the dashboard and
        the docs both call it "your space name". Left alone it produced
        ``https://example`` and a DNS failure with nothing pointing at the cause.

        A value that already carries a domain is never touched, so a full
        hostname and anything with a port keep working.
        """
        space = self.space.strip()
        for prefix in ("https://", "http://"):
            if space.startswith(prefix):
                space = space[len(prefix) :]
        space = space.rstrip("/")
        if space and "." not in space and ":" not in space:
            return f"{space}{DEFAULT_SPACE_DOMAIN}"
        return space

    @property
    def base_url(self) -> str:
        return f"https://{self.host}"

    @property
    def relay_host(self) -> str:
        """The RELAY endpoint for this space.

        RELAY connects to ``relay.<domain>`` (``relay.signalwire.com``), derived
        from the space's domain, not its full ``<space>.<domain>`` hostname.
        """
        labels = self.host.split(".")
        domain = ".".join(labels[-2:]) if len(labels) >= 2 else self.host
        return f"relay.{domain}"

    def redacted(self) -> dict[str, str]:
        tail = self.token[-4:] if len(self.token) > 4 else "?"
        return {
            "profile": self.name,
            "project": self.project,
            "space": self.host,
            "token": f"...{tail}",
        }


def _read_doc() -> tomlkit.TOMLDocument:
    path = config_path()
    if not path.is_file():
        return tomlkit.document()
    return tomlkit.parse(path.read_text(encoding="utf-8"))


def _write_doc(doc: tomlkit.TOMLDocument) -> None:
    # The file holds API tokens, so it is never readable by anyone else, not
    # even for the moment between writing it and a chmod: a new file is created
    # 0600, and an existing one is tightened before the token is written into it.
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    if hasattr(os, "fchmod"):
        os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(tomlkit.dumps(doc))
    path.chmod(0o600)


def _use_keyring() -> bool:
    """Whether to mirror tokens into the OS keyring.

    Off by default: the keyring is the very thing that makes profiles look like
    they log themselves out (a locked or denied Keychain returns nothing). The
    durable store is always the 0600 config file; the keyring is opt-in mirror.
    """
    return os.environ.get("SWSH_USE_KEYRING", "").strip().lower() in {"1", "true", "yes"}


def _keyring_get(profile: str) -> str | None:
    try:
        import keyring
    except Exception:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, profile)
    except Exception:
        return None


def _keyring_set(profile: str, token: str) -> bool:
    try:
        import keyring
    except Exception:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, profile, token)
        return True
    except Exception:
        return False


def list_profiles() -> list[str]:
    doc = _read_doc()
    profiles = doc.get("profiles", {})
    return sorted(profiles.keys())


def default_profile_name() -> str:
    """The active profile's name, or ``""`` when logged out.

    An *empty* ``default`` key is the logged-out state: profiles are still
    stored, none is selected. An *absent* key means nothing has ever chosen one,
    which falls back to the only (or first) profile so a single-profile setup
    needs no ceremony.

    The distinction matters. Without it, clearing the default silently promoted
    another profile, so logging out kept you logged in as someone else.
    """
    doc = _read_doc()
    if "default" in doc:
        return str(doc["default"])
    names = list_profiles()
    return names[0] if names else "default"


def is_logged_out() -> bool:
    """True when profiles exist but none is selected."""
    doc = _read_doc()
    return "default" in doc and not str(doc["default"])


def save_profile(
    name: str, project: str, token: str, space: str, make_default: bool = True
) -> Profile:
    doc = _read_doc()
    profiles = doc.setdefault("profiles", tomlkit.table())

    entry = tomlkit.table()
    entry["project"] = project
    entry["space"] = space
    # The file is the durable store — always keep the token here so resolution
    # never depends on the keyring being reachable. Optionally mirror it into
    # the keyring for users who want it, but the file copy still governs.
    entry["token"] = token
    if _use_keyring() and _keyring_set(name, token):
        entry["token_in_keyring"] = True
    profiles[name] = entry

    if make_default or "default" not in doc:
        doc["default"] = name
    _write_doc(doc)
    return Profile(name=name, project=project, token=token, space=space)


def delete_profile(name: str) -> bool:
    doc = _read_doc()
    profiles = doc.get("profiles", {})
    if name not in profiles:
        return False
    del profiles[name]
    if doc.get("default") == name:
        remaining = sorted(profiles.keys())
        if remaining:
            doc["default"] = remaining[0]
        else:
            doc.pop("default", None)
    _write_doc(doc)
    try:
        import keyring

        keyring.delete_password(KEYRING_SERVICE, name)
    except Exception:
        pass
    return True


def load_profile(name: str) -> Profile:
    """The stored profile exactly as saved, ignoring the environment and .env.

    ``resolve`` lets an exported variable outrank a stored profile, which is
    right for a script but wrong when a person has just pointed at a profile by
    name. This is what the TUI's profile switcher uses.
    """
    doc = _read_doc()
    profiles = doc.get("profiles", {})
    if name not in profiles:
        raise ConfigError(f"no such profile: {name}")
    stored = dict(profiles[name])
    token = stored.get("token")
    if not token and stored.get("token_in_keyring"):
        token = _keyring_get(name)
    missing = [label for label, value in (("project id", stored.get("project")),
                                          ("api token", token),
                                          ("space", stored.get("space"))) if not value]
    if missing:
        raise ConfigError(f"profile {name} is missing {', '.join(missing)}")
    return Profile(name=name, project=str(stored["project"]), token=str(token),
                   space=str(stored["space"]))


def set_default(name: str) -> None:
    doc = _read_doc()
    if name not in doc.get("profiles", {}):
        raise ConfigError(f"no such profile: {name}")
    doc["default"] = name
    _write_doc(doc)


def resolve(
    name: str | None = None,
    project: str | None = None,
    token: str | None = None,
    space: str | None = None,
    use_dotenv: bool = True,
) -> Profile:
    """Resolve one usable profile, or raise ConfigError explaining what is missing.

    Precedence, highest first: explicit argument, then a real environment
    variable, then the selected stored profile, then a ``.env`` file. The stored
    profile deliberately beats ``.env`` so that creating, deleting or switching
    profiles takes effect even when a ``.env`` is lying around.

    Naming a profile (``--profile X`` on a command, or ``SWSH_PROFILE``) moves
    that profile above the environment: a person who just pointed at a profile
    by name means it, whatever their shell happens to export. The stored
    *default* keeps the ordinary order, so a script that exports credentials
    still wins over a saved profile it never mentioned.
    """
    profile, _ = resolve_with_sources(name, project, token, space, use_dotenv)
    return profile


# Where each resolved value came from, for `whoami`/`logout` transparency.
def resolve_with_sources(
    name: str | None = None,
    project: str | None = None,
    token: str | None = None,
    space: str | None = None,
    use_dotenv: bool = True,
) -> tuple[Profile, dict[str, str]]:
    dotenv = load_dotenv() if use_dotenv else {}

    named = name or os.environ.get("SWSH_PROFILE")
    profile_name = named or default_profile_name()
    # An explicitly named profile outranks the environment (see `resolve`).
    profile_first = bool(named)

    stored: dict[str, object] = {}
    doc = _read_doc()
    if profile_name in doc.get("profiles", {}):
        stored = dict(doc["profiles"][profile_name])

    stored_token = stored.get("token")
    if not stored_token and stored.get("token_in_keyring"):
        # Legacy profile whose token lives only in the keyring. Read it once and
        # migrate it into the 0600 file, so the next resolve does not depend on
        # the keyring — the recurring "logged myself out" cause.
        stored_token = _keyring_get(profile_name)
        if stored_token and profile_name in doc.get("profiles", {}):
            doc["profiles"][profile_name]["token"] = stored_token
            try:
                _write_doc(doc)
            except OSError:
                pass  # migration is best-effort; resolution still succeeds

    def pick(explicit, env_key, stored_value):
        """Return (value, source) honouring flag > env > profile > .env, or
        flag > profile > env > .env when the profile was named explicitly.

        Each tier checks the canonical name first, then the swsh 1.x/2.0 alias,
        so an existing ``PROJECT_ID``/``REST_API_TOKEN`` environment keeps
        working. The source string names the alias when one is used, so
        ``whoami`` still tells the truth about where a value came from.
        """
        keys = (env_key, *ENV_ALIASES.get(env_key, ()))
        if explicit:
            return explicit, "flag"

        def from_env():
            for key in keys:
                if os.environ.get(key):
                    return os.environ[key], "env" if key == env_key else f"env ({key})"
            return None

        def from_profile():
            return (stored_value, "profile") if stored_value else None

        tiers = (from_profile, from_env) if profile_first else (from_env, from_profile)
        for tier in tiers:
            hit = tier()
            if hit:
                return hit
        for key in keys:
            if dotenv.get(key):
                return dotenv[key], ".env" if key == env_key else f".env ({key})"
        return None, "missing"

    resolved_project, src_project = pick(project, ENV_PROJECT, stored.get("project"))
    resolved_token, src_token = pick(token, ENV_TOKEN, stored_token)
    resolved_space, src_space = pick(space, ENV_SPACE, stored.get("space"))

    missing = [
        label
        for label, value in (
            ("project id", resolved_project),
            ("api token", resolved_token),
            ("space", resolved_space),
        )
        if not value
    ]
    if missing:
        raise ConfigError(
            _missing_message(missing, profile_name)
        )

    sources = {"project": src_project, "token": src_token, "space": src_space}
    profile = Profile(
        name=profile_name,
        project=str(resolved_project),
        token=str(resolved_token),
        space=str(resolved_space),
    )
    return profile, sources


def active_source_summary(name: str | None = None) -> dict[str, str]:
    """Best-effort {field: source} for the current resolution, for display.

    Pass the profile a command was given with ``--profile`` so the summary
    describes the resolution that command actually used. Returns an empty dict
    if nothing resolves (not logged in).
    """
    try:
        _, sources = resolve_with_sources(name)
    except ConfigError:
        return {}
    return sources


def shadowing_sources(sources: dict[str, str]) -> set[str]:
    """The sources in a summary that outrank the stored default profile.

    Both the canonical form (``env``) and the alias form (``env (PROJECT_ID)``)
    count; a legacy variable shadows a profile just as thoroughly.
    """
    return {v for v in sources.values() if v.startswith("env") or v.startswith(".env")}


def _missing_message(missing: list[str], profile_name: str) -> str:
    """Why credentials could not be resolved, and what to do about it.

    Logged out with profiles still stored is a different situation from having
    none, and the fix is different too: pick one rather than re-enter it.
    """
    stored = list_profiles()
    if not profile_name and stored:
        return (
            f"not logged in (missing {', '.join(missing)}). "
            f"Run `sw profile use NAME` to pick one of: {', '.join(stored)}."
        )
    where = f" for profile '{profile_name}'" if profile_name else ""
    return (
        f"missing {', '.join(missing)}{where}. "
        f"Run `sw login`, set {ENV_PROJECT}/{ENV_TOKEN}/{ENV_SPACE}, "
        f"or drop them in a .env file."
    )


def logout() -> dict[str, Any]:
    """Log out: deselect the active profile, keeping every profile stored.

    Logging out and deleting are different things, and this used to conflate
    them: it called ``delete_profile`` and destroyed the API token. Now it only
    clears the selection, so logging back in is ``sw profile use NAME`` and
    nothing has to be re-entered. Removal is ``delete_profile``.

    Returns a report noting whether ambient env vars or a ``.env`` will still
    provide credentials afterwards, so the user is never left thinking they are
    logged out while a shadow source keeps them in.
    """
    was = default_profile_name()
    doc = _read_doc()
    # Empty rather than absent: absent means "never chosen", which falls back to
    # the first profile. Empty is the explicit logged-out state.
    doc["default"] = ""
    _write_doc(doc)

    shadow = {}
    dotenv = load_dotenv()
    for label, env_key in (("project", ENV_PROJECT), ("token", ENV_TOKEN),
                           ("space", ENV_SPACE)):
        # Legacy aliases shadow just as effectively as the canonical names, so a
        # lingering PROJECT_ID has to be reported too or logout lies.
        for key in (env_key, *ENV_ALIASES.get(env_key, ())):
            if os.environ.get(key):
                shadow[label] = "env" if key == env_key else f"env ({key})"
                break
            if dotenv.get(key):
                shadow[label] = ".env" if key == env_key else f".env ({key})"
                break
    return {"profile": was, "kept": list_profiles(), "still_provided_by": shadow}
