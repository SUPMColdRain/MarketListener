import json
import zipfile

from market_monitor.market_package import build_market_package
from market_monitor.quality import QualityReport
from market_monitor.signing import generate_development_key, sign_market_package, verify_market_package


def package(tmp_path):
    bar = {"instrument_key": {"country_or_market": "CN", "exchange": "SSE", "asset_type": "STOCK", "code": "600519"}, "period": "1d", "bar_open_time": "2026-08-03T09:30:00+08:00"}
    return build_market_package(tmp_path, "signed", [bar], QualityReport("p", []), "2026-08-03T15:00:00+08:00", [])


def test_signature_rejects_tampered_old_schema_and_truncated_packages(tmp_path):
    private_key, public_key = tmp_path / "private.pem", tmp_path / "public.pem"
    generate_development_key(private_key, public_key)
    signed = package(tmp_path); sign_market_package(signed, private_key)
    assert verify_market_package(signed, public_key)
    tampered = tmp_path / "tampered.zip"; tampered.write_bytes(signed.read_bytes())
    with zipfile.ZipFile(tampered, "a") as archive: archive.writestr("manifest.json", b"{}")
    assert not verify_market_package(tampered, public_key)
    truncated = tmp_path / "truncated.zip"; truncated.write_bytes(signed.read_bytes()[:20])
    assert not verify_market_package(truncated, public_key)
    old_schema = tmp_path / "old.zip"; old_schema.write_bytes(signed.read_bytes())
    with zipfile.ZipFile(old_schema, "a") as archive:
        manifest = json.loads(archive.read("manifest.json")); manifest["schema_version"] = 0; archive.writestr("manifest.json", json.dumps(manifest))
    assert not verify_market_package(old_schema, public_key)
