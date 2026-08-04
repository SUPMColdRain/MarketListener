# Contracts

Version 1 uses JSON Schema Draft 2020-12. These files are the sole public
format definitions used by the desktop producer and Android consumer.

- `canonical-instrument.schema.json`: canonical identity and optional source symbols
- `bar.schema.json`: normalized OHLCV bar and source provenance
- `provider-run-result.schema.json`: a real Provider probe/run outcome
- `quality-issue.schema.json`: quarantine and data-quality evidence
- `market-package-manifest.schema.json`: market package inventory
- `strategy-package-manifest.schema.json`: strategy package metadata
- `strategy-result.schema.json`: observational strategy output and risk tags

Cross-field OHLC bounds and bar timestamp ordering are enforced by matching
desktop and Android validation code because JSON Schema cannot compare sibling
numeric or timestamp values directly. Shared legal and illegal examples live
under `tests/fixtures/contracts`.

Day 0 has stopped without final acceptance. These version 1 contracts remain
the current shared baseline; any future incompatible change requires the ADR
process described in `../ADR.md`, not a rewrite of historical D0 evidence.
