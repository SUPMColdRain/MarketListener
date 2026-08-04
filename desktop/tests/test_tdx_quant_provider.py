"""tdx_quant remains explicitly unsupported until a legal API is verified."""

from market_monitor.providers import CapabilityStatus
from market_monitor.providers.tdx_quant import TdxQuantProvider


def test_missing_tdx_quant_module_is_explicitly_unsupported(monkeypatch) -> None:
    monkeypatch.setattr("importlib.util.find_spec", lambda _: None)

    capabilities = TdxQuantProvider().probe_capabilities()

    assert capabilities
    assert all(capability.status is CapabilityStatus.UNSUPPORTED for capability in capabilities)
    assert "HK stocks" in (capabilities[-1].detail or "")
