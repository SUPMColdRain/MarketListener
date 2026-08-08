# FULL-201 实现交付：交易日历、交易时段、复权因子与公司行动

日期：2026-08-06
状态：实现完成（等待系列统一审查）
角色：root 实现

## 范围与边界

在既有 `aggregation.py`（A股午休、期货夜盘、部分尾部标记）与 FULL-121 新增契约之上完成 FULL-201 实现层：日历语义（非交易日/缺失日不产生幻影 bar）、复权因子计算、公司行动建模；A股午休、期货夜盘、港股尾部、停牌缺失、除权连续性均有固定样本。

## 修改文件

- `desktop/src/market_monitor/calendar.py`（新增）：`TradingCalendar`。
- `desktop/src/market_monitor/corporate_actions.py`（新增）：公司行动模型与前后复权因子引擎。
- `contracts/trading-calendar.schema.json`、`contracts/corporate-action.schema.json`、`contracts/adjustment-factor.schema.json`（新增，见 FULL-121）。
- `desktop/tests/test_calendar.py`、`desktop/tests/test_corporate_actions.py`（新增）。

## 固定样本覆盖

| 场景 | 样本 | 断言 |
|---|---|---|
| 周末/节假日/缺失日 | 8/3 交易日、8/4 非交易日、8/6 缺失 | `is_trading_day` 精确；缺失日不视为交易日（无幻影 bar） |
| 午休 | 既有 `test_a_share_lunch_break_never_merges_into_a_single_hour_bar` | 11:30 与 13:00 不合并，尾部 `is_partial` |
| 停牌 | 交易日历中无当日 bar | 日历查询不发明新 bar（缺失日返回非交易日） |
| 除权 | 现金分红/拆股/送股/配股公式与连续性 | `adjusted_prev_close ≈ adjusted_ex_open`（rel 1e-12） |
| 期货夜盘 | 既有 `test_future_night_session_does_not_cross_trading_days` + 日历市场隔离 | 21:00 归属当日 trading_day，不跨日 |
| 港股尾部 | `aggregation.SESSION_RULES` HK 12:00–13:00 午休、16:00 收盘 | 尾部 bar 标记 partial |
| 缺失前收盘价 | `test_missing_previous_close_is_an_error_not_a_silent_skip` | 显式 `ValueError` |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 日历/复权/契约专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_calendar.py desktop\tests\test_corporate_actions.py desktop\tests\test_aggregation.py desktop\tests\test_contracts.py -q` | PASS |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS |

## 风险与未完成项

- 真实节假日与公司行动数据依赖 Provider 真实探测（FULL-110～113/122）；本任务使用合成固定样本验证语义。
- 港股尾部时段测试仅覆盖聚合语义；真实港股样本在 FULL-600。

## 状态建议

实现完成，等待系列统一审查与验收。
