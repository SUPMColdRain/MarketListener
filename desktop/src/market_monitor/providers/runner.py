"""Independent Provider probing and machine/human report output."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
from typing import Iterable, Sequence
from uuid import uuid4

from .base import (
    Capability,
    CapabilityRegistration,
    CapabilityStatus,
    ErrorCategory,
    ProviderOperation,
    ProviderRequest,
    Provider,
    ProviderError,
    ProviderRunResult,
    utc_now,
)


_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(token|api[_-]?key|secret|password|account|username)\b\s*([:=])\s*([^\s,;]+)"
)
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


def redact_secrets(message: str) -> str:
    """Prevent credentials embedded by upstream SDK errors from reaching reports."""

    redacted = _SECRET_ASSIGNMENT.sub(r"\1\2***", message)
    return _BEARER_TOKEN.sub("Bearer ***", redacted)


@dataclass(frozen=True)
class ProbeReport:
    generated_at: str
    results: Sequence[ProviderRunResult]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "generated_at": self.generated_at,
            "providers": [result.to_dict() for result in self.results],
        }


class ProbeRunner:
    """Runs each provider independently so one source cannot stop the others."""

    def __init__(self, *, timeout_seconds: float = 45.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds

    def run(self, providers: Iterable[Provider]) -> ProbeReport:
        results = [self._run_one(provider) for provider in providers]
        return ProbeReport(
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            results=results,
        )

    def write_reports(self, report: ProbeReport, report_dir: Path) -> tuple[Path, Path]:
        report_dir.mkdir(parents=True, exist_ok=True)
        machine_path = report_dir / "provider-capabilities.json"
        human_path = report_dir / "provider-capabilities.md"
        machine_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        human_path.write_text(self._human_report(report), encoding="utf-8")
        return machine_path, human_path

    def _run_one(self, provider: Provider) -> ProviderRunResult:
        started_at = utc_now()
        run_id = f"probe-{provider.name}-{uuid4().hex[:12]}"
        completed = Event()
        capabilities: Sequence[Capability] = ()
        raised: Exception | None = None

        def invoke() -> None:
            nonlocal capabilities, raised
            try:
                capabilities = tuple(provider.probe_capabilities())
            except Exception as error:  # External SDKs may use arbitrary exception classes.
                raised = error
            finally:
                completed.set()

        Thread(target=invoke, name=f"provider-probe-{provider.name}", daemon=True).start()
        if not completed.wait(self._timeout_seconds):
            return ProviderRunResult(
                run_id=run_id,
                source=provider.source,
                started_at=started_at,
                completed_at=utc_now(),
                capabilities=(self._run_error_capability(
                    ProviderError(ErrorCategory.NETWORK, f"provider probe exceeded {self._timeout_seconds:g} seconds")
                ),),
            )
        try:
            if raised:
                raise raised
            return ProviderRunResult(
                run_id=run_id,
                source=provider.source,
                started_at=started_at,
                completed_at=utc_now(),
                capabilities=capabilities,
            )
        except ProviderError as error:
            return ProviderRunResult(
                run_id=run_id,
                source=provider.source,
                started_at=started_at,
                completed_at=utc_now(),
                capabilities=(self._run_error_capability(
                    ProviderError(error.category, redact_secrets(error.message))
                ),),
            )
        except Exception as error:
            return ProviderRunResult(
                run_id=run_id,
                source=provider.source,
                started_at=started_at,
                completed_at=utc_now(),
                capabilities=(self._run_error_capability(
                    ProviderError(ErrorCategory.UNKNOWN, redact_secrets(str(error)))
                ),),
            )

    @staticmethod
    def _run_error_capability(error: ProviderError) -> Capability:
        return Capability(
            "provider-run-error",
            CapabilityStatus.FAILED,
            detail="provider probe did not return individual capability results",
            registration=CapabilityRegistration(
                "provider-run-error",
                "Provider run-level error represented as an independent capability",
                ProviderRequest(ProviderOperation.HEALTH_CHECK),
            ),
            error=error,
        )

    @staticmethod
    def _human_report(report: ProbeReport) -> str:
        lines = ["# Provider capability report", "", f"Generated at: {report.generated_at}", ""]
        if not report.results:
            lines.extend(["No providers were registered.", ""])
        for result in report.results:
            lines.extend([f"## {result.source.display_name}", ""])
            for capability in result.capabilities:
                suffix = f" - {capability.detail}" if capability.detail else ""
                lines.append(f"- {capability.name}: {capability.status.value}{suffix}")
                if capability.error:
                    lines.append(f"  - error: {capability.error.category.value} - {capability.error.message}")
            lines.append("")
        return "\n".join(lines)
