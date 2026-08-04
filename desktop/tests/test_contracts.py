"""The desktop contract suite consumes the shared checked-in fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_monitor.contracts import ContractValidationError, validate_contract


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "contracts"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_shared_contract_fixtures(case: dict[str, object]) -> None:
    fixture = FIXTURES / str(case["fixture"])
    document = json.loads(fixture.read_text(encoding="utf-8"))
    if case["valid"]:
        validate_contract(str(case["schema"]), document)
    else:
        with pytest.raises(ContractValidationError):
            validate_contract(str(case["schema"]), document)
