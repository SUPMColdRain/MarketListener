---
status: accepted
date: 2026-08-12
---

# ADR-0009：Canonical 周期与派生 K 线的存储边界

## 背景

R1 需要逐步扩展多周期行情，但按每个周期重复落库会造成存储放大、更新不一致和跨端包体膨胀。现有 `MarketStore` 已按 `market/asset_type/period/year` 分区，Silver 写入以 `(instrument_id, period, bar_open_time)` 去重覆盖；`IncrementalCollector` 保存 per-source/instrument/period 游标并有锁。`aggregation.py` 已支持交易时段桶与日线到周/月的可重复聚合。

实际 Silver parquet 同时保存规范列 `instrument_id`、`bar_period`、`bar_open_time` 和 Hive 分区列 `market`、`asset_type`、`period`、`year`；原始业务字段保留在 `bar_json`。2026-08-12 对实际分区和全量测试的检查确认此布局可被当前 API 读取。

## 决定

1. 将上游真实可稳定取得的最细、完整且具交易时段语义的周期作为一个数据类别的 canonical 输入周期；不因 UI 下拉框而预写所有派生周期。
2. `1h/2h/4h` 仅能通过会话规则聚合，禁止自然小时 resample。CN 股票、HK 股票和 CN 期货必须使用已有 `SessionRule`；期货夜盘需交易日历确认归属。
3. `1w/1mo` 从 canonical 日线按标的聚合，保留 `source_period`、`aggregated_from`、规则版本和 `is_partial`。派生查询/缓存层上线前不得写为新的长期 Silver 真相来源。
4. 主备 Provider 的选择单位是完整分区/能力，不允许按行混源；这是 ADR-0007 的延续。
5. `NULL` 表示上游未提供或能力不支持。尤其 `amount`、`open_interest` 和沉淀资金不得写零；沉淀资金在明确可复核的定义、单位和输入字段前不进入 canonical schema。

## 后果

- R1 当前不进行全量 parquet 迁移或重复回填，保持 Android 包和已有读取接口兼容。
- 新 Provider 必须先登记输入周期、交易日语义、字段能力和增量游标，再实施派生读取；对应全覆盖工作继续由 `R1-T007` 阻塞跟踪。
- 已通过 `/api/market/instruments/{instrument_id}/bars` 实现只读派生查询：实际存在的 30m/更细粒度 K 线可按会话规则投影为 `1h/2h/4h`，`1d` 可投影为 `1w/1mo`，且响应显式提供 `availablePeriods`。派生结果不回写 Silver。
- 聚合遇到任一输入 bar 的 `volume`、`amount`、`high` 或 `low` 缺失/非数值时，对应派生字段为 `NULL`，而不是回退为零或忽略缺失输入。
- 后续仍需在真实新增分钟数据后，增加缺口、节假日、午休、夜盘、周/月边界、重复写入和 NULL 语义的跨市场集成证据。
