# FULL-501 实现交付：交易录入/导入/修订与持仓计算

日期：2026-08-06
状态：实现完成（固定账本与解析测试全绿），等待系列统一审查
角色：`impl_trading` 实现

## 范围与边界

实现交易录入（含多笔费用）、修订（父记录标记 REVISED）、撤销、JSON Lines 账本导入（去重）和平均成本持仓计算。未改动行情导入与展示。

## 修改文件

- `android/app/src/main/java/com/marketmonitor/app/trading/PositionCalculator.kt`（新增）：日级快照、平均成本、费用入成本/卖出实现盈亏、拆股换股调整、禁止卖空。
- `android/app/src/main/java/com/marketmonitor/app/trading/LedgerImport.kt`（新增）：JSONL 解析（header/strategy/trade/cash）、行号错误、SHA-256 去重摘要。
- `android/app/src/main/java/com/marketmonitor/app/trading/TradingRepository.kt`（新增）：录入/修订/撤销/导入的事务编排与导入批次去重。
- `android/app/src/main/java/com/marketmonitor/app/trading/TradingEntities.kt`（新增 DAO 查询）：按标的/时间/导入批次/单笔查询、批次登记。
- `tests/fixtures/ledger/sample-import.jsonl`（新增）：固定账本夹具（部分成交、多费用、出入金）。
- `android/app/src/test/java/com/marketmonitor/app/trading/PositionCalculatorTest.kt`、`LedgerImportTest.kt`（新增）。

## 验收要点对应证据

| 验收标准 | 证据 |
|---|---|
| 部分成交 | 300@10 + 200@12 → 500 股、成本 5400、均价 10.8（固定样本） |
| 多费用 | 买入佣金入成本、卖出印花税抵扣净收入：100@10 + 费 5 → 卖 100@12 费 3，已实现盈亏 192（手算一致） |
| 出入金 | 入金 10000、买 100@10、出金 -2000 → 现金 7000（固定样本） |
| 拆分 | 1000 股@10 成本 10000，10:1 换股 → 10000 股、均价 1、成本不变，且换股当日先调整后成交 |
| 撤销/修订 | CANCELLED 与 REVISED 记录不计入持仓，修订子记录生效（固定样本） |
| 重复导入 | 同一内容 SHA-256 相同 → `LedgerImportResult.Duplicate`，事务内二次校验防并发重复；重复时不做任何写入 |
| 非法录入 | 卖超持仓抛 `PositionException`；解析错误带行号（固定样本） |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| Android JVM 全量测试 | `gradlew.bat -p android testDebugUnitTest --no-daemon` | PASS，54 项，0 失败（含持仓计算 7 项、导入 3 项） |
| Android lint | `gradlew.bat -p android lintDebug --no-daemon` | PASS |

## 风险与未完成项

- 持仓计算规则（平均成本、费用入成本）已在本交付记录固化，供审查核对；真实券商对账差异需用户在验收阶段用真实账单复核。
- `TradingRepository` 的 Room 事务路径（DAO 执行）未在 JVM 覆盖（需设备/仪器化测试），SQL 层幂等与回滚由 `TradingSchemaMigrationTest` 覆盖；真实验收列入设备流程。

## 状态建议

实现完成，等待系列统一审查。

## 统一审查修复（2026-08-06）

按 `docs/reviews/review-android-chain.md` P1/P2：`importLedger` 先插 `ledger_imports` 父行再插 trades/fees/cash（外键顺序修复，真实 SQLite `PRAGMA foreign_keys=ON` 复现通过）；`reviseTrade` 校验父交易为 EXECUTED；`PositionCalculator.finalSnapshot` 空账本返回零值快照（positions/stats 不再抛 NoSuchElementException）；新增 `EmptyLedgerTest`。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTED`。本机重跑验收命令均通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`。Room DAO 事务路径的设备/仪器化缺口如实记录，不视为已实测；不阻塞本次结论。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `LedgerImportTest`、`PositionCalculatorTest`、`EmptyLedgerTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

验收角色未修改实现代码。
