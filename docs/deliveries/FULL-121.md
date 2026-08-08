# FULL-121 实现交付：契约升级（日历/公司行动/复权/来源追踪）

日期：2026-08-06
状态：实现完成（等待系列统一审查；用户指示先完成 5.1–5.9 再审查）
角色：root 实现

## 范围与边界

本交付完成 FULL-121 的契约层：交易日历、公司行动、复权因子三个新公开 Schema 与 Python 模型、共享正反例夹具，并保持既有标的/K线/来源追踪契约兼容。未执行真实数据拉取（属 FULL-110～113/122 范围）；Android 共享夹具由 `ContractValidationTest` 自动消费（新增 cases 会随 `tests/fixtures` 资源进入 Android JVM 测试）。

## 修改文件

- `contracts/trading-calendar.schema.json`（新增）：单日条目（market、calendar_date、is_trading_day、session_kind、sessions、source）。
- `contracts/corporate-action.schema.json`（新增）：现金分红/送股/拆股/配股，按 action_type 用 allOf 条件约束必填数值字段。
- `contracts/adjustment-factor.schema.json`（新增）：前/后复权步进因子序列（effective_date + factor > 0）。
- `desktop/src/market_monitor/calendar.py`（新增）：`TradingCalendar` 数据驱动交易日查询；缺失日期不是交易日（不产生幻影 bar）；重复条目拒绝；映射输入走共享 Schema 校验。
- `desktop/src/market_monitor/corporate_actions.py`（新增）：`CorporateAction`、`single_action_factor`、`build_adjustment_factors`（前/后复权）、`factor_for_day`、`apply_adjustment`；复权公式见模块 docstring。
- `tests/fixtures/contracts/valid|invalid/`：新增 6 个正反例；`cases.json` 新增 7 条，Python 与 Android 共享。
- `desktop/tests/test_calendar.py`、`desktop/tests/test_corporate_actions.py`（新增）。

## 复权定义与不变量

- 单次行动价格因子 `k = (P - cash + rights_price*rights_ratio) / (P * (split_ratio + bonus_ratio + rights_ratio))`，P 为除权日前一交易日收盘。
- 后复权（BACKWARD_ADJUSTED）：除权日后价格乘以累计 `1/k`；前复权（FORWARD_ADJUSTED）：epoch 锚点携带全部 k 的乘积，历史价格按累计 k 缩放，最新价格因子为 1.0。
- 不变量：除权日前收盘价与除权日开盘价经调整后连续（相对误差 1e-12 内）。
- 缺失前收盘价时显式报错，不静默跳过（避免错误复权）。

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 契约/日历/复权/主数据专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_calendar.py desktop\tests\test_corporate_actions.py desktop\tests\test_catalog.py desktop\tests\test_contracts.py -q` | PASS（49 项） |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS |

桌面全量与 Android JVM 共享夹具验证将在 5.2–5.5 实现 Agent 收敛后由 root 统一重跑（当前运行中的 Tushare Agent 尚未收敛，其文件有临时失败属其工作区状态，与本交付无关）。

## 兼容性与安全

- 既有 `canonical-instrument`、`bar`、`provider-run-result`、`strategy-*` Schema 未修改；新增 Schema 均为增量。
- Android `ContractValidationTest` 通过 `tests/fixtures/contracts/cases.json` 自动覆盖新增正反例，无需改 Kotlin 代码。
- 无凭据、私钥或个人数据写入仓库；全部夹具为合成值。

## 风险与未完成项

- 真实日历/公司行动数据来源与质量校验由 FULL-110～113、FULL-201 后续真实数据任务覆盖。
- 复权公式采用本仓库明确声明的口径；与上游 Provider 复权口径的交叉验证留在 FULL-122/201 真实数据闭环。

## 状态建议

实现完成，等待系列统一审查与验收；不自审、不验收。
