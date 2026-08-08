# FULL-601 实现交付：期货、商品指数、主力与连续合约语义

日期：2026-08-06
状态：实现完成（领域逻辑与固定样本通过；真实代表合约部分 PASS）
角色：root 实现

## 结果

- `market_expansion.py`：`FuturesContract`（symbol/exchange/expiry/open_interest/volume）、`select_main_contract`（主力=最高持仓→成交量→最近到期）、`build_continuous_series`（逐日选主力拼接；换月日显式标记 `is_roll_day` 与 `roll_gap`，不做静默价格调整，策略必须消费换月标记避免虚假收益）。
- 夜盘交易日归属复用 `aggregation.SESSION_RULES["CN_FUTURE"]`（21:00-23:00 归当日 trading_day）与既有固定样本。
- 测试：`test_main_contract_selection_uses_open_interest_then_volume_then_expiry`、`test_continuous_series_marks_roll_day_and_reports_gap`。

## 真实探测（2026-08-06，NO_PROXY=*）

| 能力 | 结果 | 证据 |
|---|---|---|
| 股指期货主力 IF0（新浪 `futures_main_sina`） | PASS，2317 行 | 真实行数 2317；日期范围未在探针中另存（交付记录保留运行输出） |

## 自动化证据

`test_market_expansion.py` PASS（5 项）；Ruff PASS。

## 风险与未完成项

- 连续合约真实价格拼接依赖多合约日线数据源（当前仅主力端点到手）；商品/夜盘代表合约的完整真实闭环待网络条件恢复后验收。

## 状态建议

实现完成，等待系列统一审查与验收。
