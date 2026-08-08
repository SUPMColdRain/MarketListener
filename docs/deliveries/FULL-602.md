# FULL-602 实现交付：同花顺指数、ETF 去重和重要市场指标

日期：2026-08-06
状态：实现完成（指标口径/校验与 ETF 去重固定样本通过；同花顺指数真实探测受 akshare 版本限制，如实记录）
角色：root 实现

## 结果

- `market_expansion.py`：`MarketIndicator`（code/name/definition/unit/frequency/source/data_cutoff/value + `validation_errors`），每项指标强制口径、单位、频率、来源与截止时间；`THS_INDEX_SAMPLE`（884116 白酒、884039 半导体、884072 医疗器械，口径=同花顺行业分类成分股指数）；`deduplicate_etfs`（按 underlying+share_class 去重，SH>SZ>HK 优先，确定性）。
- 测试：`test_etf_dedup_keeps_one_share_per_underlying_with_exchange_priority`、`test_indicator_validation_requires_definition_unit_source_and_iso_cutoff`。

## 真实探测（2026-08-06，NO_PROXY=*）

| 能力 | 结果 | 原因/解除条件 |
|---|---|---|
| 同花顺指数（`stock_zh_index_ths`） | FAILED/PROVIDER | akshare 1.18.81 无该函数（API 变更）；`stock_board_industry_index_ths("白酒")` 返回 `'??'` 编码错误；解除条件=升级/替换 akshare 或接入官方 THS 端点后由验收重跑 |

涨跌家数等市场指标的口径/单位/频率/来源/截止时间已由 `MarketIndicator` 模型强制，真实代表值待数据源可用后采集。

## 自动化证据

`test_market_expansion.py` PASS（5 项）；Ruff PASS。

## 状态建议

实现完成，等待系列统一审查与验收。
