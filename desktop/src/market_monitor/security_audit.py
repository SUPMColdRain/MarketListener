"""Credential scans, signing-key rotation and backup drills."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .signing import generate_development_key, verify_market_package


_CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("BEARER_TOKEN", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}")),
    (
        "ENV_SECRET_VALUE",
        re.compile(
            r"^\s*(?:JQDATA_USERNAME|JQDATA_PASSWORD|TUSHARE_TOKEN|API_KEY|CLIENT_SECRET|PRIVATE_KEY)\s*=\s*\S+",
            re.MULTILINE,
        ),
    ),
)

_BINARY_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".parquet", ".sqlite", ".db", ".apk", ".pyc", ".pem"}
)


@dataclass(frozen=True)
class CredentialFinding:
    path: str
    line: int
    pattern: str
    snippet: str

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "line": self.line, "pattern": self.pattern, "snippet": self.snippet}


def scan_for_credentials(root: Path, *, exclude_dirs: Sequence[str] = (".git", ".venv", "__pycache__", ".ruff_cache")) -> list[CredentialFinding]:
    """Scan text files for credential shapes without writing anything."""

    findings: list[CredentialFinding] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in exclude_dirs for part in relative.parts):
            continue
        if path.suffix.lower() in _BINARY_SUFFIXES or path.name == "chat_processes.json":
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, UnicodeError):
            continue
        for line_index, line in enumerate(lines, 1):
            for name, pattern in _CREDENTIAL_PATTERNS:
                match = pattern.search(line)
                if match:
                    findings.append(
                        CredentialFinding(
                            str(relative),
                            line_index,
                            name,
                            _redact_snippet(line[match.start() : match.end()]),
                        )
                    )
    return findings


@dataclass(frozen=True)
class RotationResult:
    new_private_path: Path
    new_public_path: Path
    backup_private_path: Path
    backup_public_path: Path


def rotate_signing_key(private_path: Path, public_path: Path, backup_dir: Path) -> RotationResult:
    """Move the current key pair to a timestamped backup, then generate a new pair."""

    if not private_path.is_file() or not public_path.is_file():
        raise FileNotFoundError("Both current private and public keys are required for rotation")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_private = backup_dir / f"private-{stamp}.pem"
    backup_public = backup_dir / f"public-{stamp}.pem"
    shutil.copy2(private_path, backup_private)
    shutil.copy2(public_path, backup_public)
    private_path.unlink()
    public_path.unlink()
    generate_development_key(private_path, public_path)
    return RotationResult(private_path, public_path, backup_private, backup_public)


@dataclass(frozen=True)
class BackupResult:
    backup_root: Path
    files: tuple[tuple[str, str, int], ...]
    verified: bool

    def to_dict(self) -> dict[str, object]:
        return {"backup_root": str(self.backup_root), "files": [list(item) for item in self.files], "verified": self.verified}


def backup_store(data_root: Path, backup_root: Path) -> BackupResult:
    """Copy the store and verify every copied file by SHA-256."""

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backup_root / stamp
    target.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[str, str, int]] = []
    verified = True
    for path in sorted(data_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(data_root)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        source_digest = _sha256(path)
        copy_digest = _sha256(destination)
        entries.append((relative.as_posix(), source_digest, path.stat().st_size))
        if source_digest != copy_digest:
            verified = False
    return BackupResult(target, tuple(entries), verified)


def dependency_audit(venv_python: Path) -> dict[str, object]:
    """Run ``pip check`` and record the resolved environment (no new installs)."""

    check = subprocess.run(
        [str(venv_python), "-m", "pip", "check"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return {
        "pip_check_exit_code": check.returncode,
        "pip_check_stdout": check.stdout,
        "pip_check_stderr": check.stderr,
    }


def verify_old_package_with_rotated_keys(package_path: Path, backup_public_path: Path, new_public_path: Path) -> dict[str, bool]:
    """Matrix check: old key verifies, new key must reject a package signed by the old key."""

    return {
        "old_key_verifies": verify_market_package(package_path, backup_public_path),
        "new_key_rejects": not verify_market_package(package_path, new_public_path),
    }


def _redact_snippet(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-2:]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
