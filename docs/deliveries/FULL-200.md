# FULL-200 实现交付：标的主数据、A股/ETF 范围规则与点即时成员

日期：2026-08-06
状态：实现完成（等待系列统一审查）
角色：root 实现

## 范围与边界

在既有 `InstrumentCatalog`（instrument/source_mapping/universe_rules/universe_members）之上完成 FULL-200 实现层：上市/退市日期、旧库自动迁移、A股/ETF 范围规则校验、按上市日期生成点即时成员。回测查询只使用“当时”成员，禁止未来信息泄漏。

## 修改文件

- `desktop/src/market_monitor/catalog.py`：
  - `Instrument` 增加 `list_date`/`delist_date`（可选）。
  - `upsert_instrument` 持久化上市/退市日期；旧库打开时自动 `ALTER TABLE` 迁移（`_ensure_column`）。
  - `save_universe_rule` 调用 `validate_universe_rule`：只允许 `market`（CN/HK）、`kind`（a_share/etf/index/futures/mixed/core）、`exchanges`、`asset_types`，未知键或非法值拒绝。
  - `add_membership_from_listing_dates`：按每只标的的上市/退市日期插入 `universe_members` 有效期，幂等（重复调用新增 0 行）。
- `desktop/tests/test_catalog.py`：新增点即时成员、未来上市不泄漏、旧库迁移、规则校验测试。

## 验收要点对应证据

| 验收标准 | 证据 |
|---|---|
| 回测使用当时成员，无未来信息泄漏 | `test_listing_date_membership_is_point_in_time_without_future_leakage`：2020-12-31 可见、2021-01-01 不可见；2026-09-01 上市标的在 2026-08-31 不可见 |
| A股/ETF 范围规则 | `validate_universe_rule` 白名单词汇表，未知键/非法 exchanges 拒绝；既有 `{"market":"CN","kind":"core"}` 保持兼容 |
| 迁移与幂等 | `test_catalog_migrates_existing_database_with_listing_columns`（手工构造旧库→打开→迁移→上市日期成员）；`add_membership_from_listing_dates` 二次调用返回 0 |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 主数据专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_catalog.py desktop\tests\test_contracts.py -q` | PASS |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS |

## 风险与未完成项

- 真实 A 股/ETF 上市名单、退市名单来自 Provider 真实数据（FULL-110～113/122），本任务只提供存储与查询语义。
- 指数/期货等其他市场的范围规则词表按需在后续任务扩展（当前 `kind` 已预留）。

## 状态建议

实现完成，等待系列统一审查与验收。
