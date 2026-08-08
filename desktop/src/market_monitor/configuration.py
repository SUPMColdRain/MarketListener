"""Local-only configuration for credential-gated provider probes."""

from __future__ import annotations

import os
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class ConfigurationError(ValueError):
    """An explicitly requested local configuration file is unsafe or invalid."""


@dataclass(frozen=True)
class LocalConfiguration:
    """Configuration values loaded without writing them to reports or logs."""

    values: Mapping[str, str]

    def get(self, name: str) -> str | None:
        value = self.values.get(name)
        return value if value else None

    @property
    def secret_values(self) -> tuple[str, ...]:
        return tuple(value for name, value in self.values.items() if value and _is_sensitive_configuration_name(name))


def load_local_configuration(
    *, config_file: Path | None = None, environment: Mapping[str, str] | None = None, repo_root: Path | None = None
) -> LocalConfiguration:
    """Load environment values plus one explicitly named, repository-external file.

    Both the caller's lexical path and its final link-resolved target must be
    outside ``repo_root``.  Checking both positions rejects a repository
    junction pointing outward and an outward symlink pointing back into the
    repository.  Values are kept only in memory.
    """

    values = dict(environment if environment is not None else os.environ)
    if config_file is None:
        return LocalConfiguration(values)

    lexical = _lexical_absolute(config_file)
    resolved = _regular_readable_file(lexical)
    if repo_root is not None:
        lexical_root = _lexical_absolute(repo_root)
        resolved_root = _resolved_directory(repo_root)
        if _is_within(lexical, lexical_root) or _is_within(resolved, resolved_root):
            raise ConfigurationError("the explicit local configuration file must be outside the repository")
    values.update(_parse_env_file(resolved))
    return LocalConfiguration(values)


def _lexical_absolute(path: Path) -> Path:
    """Normalize ``.``/``..`` and case without resolving links or junctions."""

    return Path(os.path.normpath(os.path.abspath(os.fspath(path.expanduser()))))


def _resolved_directory(path: Path) -> Path:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as error:
        raise ConfigurationError("the repository path cannot be resolved safely") from error
    if not resolved.is_dir():
        raise ConfigurationError("the repository path is not a directory")
    return resolved


def _regular_readable_file(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ConfigurationError("the explicit local configuration file is not a regular file")
        with resolved.open("r", encoding="utf-8-sig"):
            pass
    except ConfigurationError:
        raise
    except (OSError, UnicodeError) as error:
        raise ConfigurationError("the explicit local configuration file is not a readable regular file") from error
    return resolved


def _is_within(candidate: Path, root: Path) -> bool:
    """Case-insensitive, drive-safe containment for Windows and portable tests."""

    try:
        common = os.path.commonpath((os.path.normcase(os.fspath(candidate)), os.path.normcase(os.fspath(root))))
    except ValueError:  # Different Windows drives / UNC roots are necessarily separate.
        return False
    return os.path.normcase(common) == os.path.normcase(os.fspath(root))


def _is_sensitive_configuration_name(name: str) -> bool:
    normalized = "".join(character for character in unicodedata.normalize("NFKC", name) if character.isalnum()).casefold()
    without_digits = normalized.rstrip("0123456789")
    parts = {
        "token",
        "accesstoken",
        "refreshtoken",
        "apikey",
        "secret",
        "clientsecret",
        "password",
        "passphrase",
        "privatekey",
        "authorization",
        "credential",
        "credentials",
        "cookie",
        "account",
        "username",
        "key",
        "passwd",
        "pwd",
        "secretkey",
        "accesskey",
        "awssecretaccesskey",
        "awsaccesskeyid",
        "bearer",
    }
    suffixes = (
        "token",
        "apikey",
        "secret",
        "password",
        "privatekey",
        "credential",
        "username",
        "account",
        "passwd",
        "pwd",
        "secretkey",
        "accesskey",
        "authorization",
        "cookie",
    )
    return (
        normalized in parts
        or without_digits in parts
        or normalized.endswith(suffixes)
        or without_digits.endswith(suffixes)
    )


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as error:
        raise ConfigurationError("the explicit local configuration file is not readable") from error
    for line_number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigurationError(f"local configuration has an invalid entry at line {line_number}")
        name, value = line.split("=", 1)
        name = name.strip()
        if not name or not name.replace("_", "").isalnum():
            raise ConfigurationError(f"local configuration has an invalid variable name at line {line_number}")
        canonical_name = name.upper()
        if canonical_name.casefold() in seen:
            raise ConfigurationError(f"local configuration has a duplicate variable at line {line_number}")
        seen.add(canonical_name.casefold())
        value = value.strip()
        if len(value) >= 2 and value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        parsed[canonical_name] = value
    return parsed
