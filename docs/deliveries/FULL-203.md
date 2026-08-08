# FULL-203 实现交付：完整性、价格、成交量、时区与跨源差异规则

日期：2026-08-06
状态：实现完成（等待系列统一审查）
角色：root 实现

## 范围与边界

在既有 `validate_partition`（重复/OHLC/成交量/时间戳/截止时间/缺口/跳变）之上新增：时区偏移规则、跨源对比（主源 vs 校验源）、隔离区持久化。跨源对比只产出报告，绝不逐行混源。

## 修改文件

- `desktop/src/market_monitor/quality.py`：
  - `validate_partition` 新增 `expected_offset`：bar 的 UTC 偏移与市场期望不一致时产生 `TIMEZONE`/`ERROR`（阻断）。
  - `validate_cross_source`：按 `(instrument, period, bar_open_time)` 对齐主源与参考源；收盘价相对差异超阈值 → `CROSS_SOURCE`/`ERROR`（阻断）；参考行缺失与成交量差异 → WARNING；不产生混合数据。
  - `quarantine_partition`：把被阻断的分区原子写入 `quarantine/<partition_id>/bars.jsonl + quality-report.json`（仓库外数据根目录），重复写入拒绝。
- `desktop/tests/test_quality.py`：新增时区、跨源、隔离区 3 个测试。

## 验收要点对应证据

| 验收标准 | 证据 |
|---|---|
| 缺口/OHLC/成交量/时区固定样本 | 既有 DUPLICATE/OHLC/VOLUME/TIMESTAMP/GAP/SOURCE 测试 + 新增 TIMEZONE 匹配通过/不匹配阻断 |
| 异常跳变/跨源阈值 | 既有 close jump WARNING + `test_cross_source_comparison_never_mixes_rows_and_flags_diffs`（1.1 倍 close 超 0.5% 阈值 → ERROR） |
| 阻断进隔离区 | `test_quarantine_persists_bars_and_report_outside_silver`：阻塞报告 + 隔离区文件 + 二次写入拒绝 |
| 不逐行混源 | `validate_cross_source` 只读对比、不修改任何 bar；隔离区与 Silver 分离 |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 质量专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_quality.py desktop\tests\test_incremental.py -q` | PASS（10 项） |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS |

## 风险与未完成项

- 跨源阈值（收盘 0.5%、成交量 50%）是默认值，可在调用处按市场/周期调整；真实多源样本校准留在 FULL-120/122。

## 状态建议

实现完成，等待系列统一审查与验收。

## 统一审查修复（2026-08-06）

按 `docs/reviews/unified-review-data.md` P1-4/P2-5：OHLC 必填且为正有限数、成交量必填非负（空 bar/负 OHLC/缺 volume 均阻断）；流水线 `quality/run` 支持 `expected_offset` 与 `reference_bars` 接线。
