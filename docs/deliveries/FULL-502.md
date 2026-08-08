# FULL-502 实现交付：净值/胜率/盈亏比/回撤/暴露/归因统计

日期：2026-08-06
状态：实现完成（固定账本手算对照全绿），等待系列统一审查
角色：`impl_trading` 实现

## 范围与边界

在纯 Kotlin 领域层实现基于持仓快照的统计与归因：净值曲线、总收益率、最大回撤、胜率、盈亏比、平均/最大暴露、按策略与按标的的已实现/未实现归因。未改动任何行情读取逻辑。

## 修改文件

- `android/app/src/main/java/com/marketmonitor/app/trading/TradingStats.kt`（新增）：`TradingStatsCalculator`、`DailyClose`、`NavPoint`、`TradingStatsResult`。
- `android/app/src/main/java/com/marketmonitor/app/trading/TradingRepository.kt`：`stats(closes)` 数据装配入口（从 Room 加载账本 → 计算器）。
- `android/app/src/test/java/com/marketmonitor/app/trading/TradingStatsTest.kt`（新增）：5 项固定样本手算对照。

## 口径（固定，供审查核对）

- 净值 = 现金 + 持仓市值；缺收盘价时回退最近收盘价，再回退成本价并标记 `markedWithFallback`。
- 胜率 = 盈利平仓笔数 / 全部平仓笔数（保本算未胜）；盈亏比 = 毛利 / 毛损，无亏损时为 null。
- 暴露 = 持仓市值 / 净值（仅做多，故非负）；回撤按净值峰值到谷值计算。
- 归因：已实现按交易归属；未实现按每标的最新成交的策略归属，未指定策略归 `UNASSIGNED`。

## 验收要点对应证据

| 验收标准 | 证据 |
|---|---|
| 净值曲线 | 入金 10000 → 买 X@10 → 卖 X@12 → 买 Y@10 → 卖 Y@9 → 买 X@10 → 卖 X@10，逐日净值 10000/10200/10100/10100 手算一致 |
| 胜率/盈亏比 | +200/-100/0 三笔平仓：胜率 1/3、毛利 200、毛损 100、盈亏比 2.0；全盈时盈亏比为 null |
| 最大回撤 | 10000→9000→8000→11000 样本：回撤 20%，总收益 10% |
| 暴露 | 样本逐日暴露 10%/9.80%/9.90%/0%，最大 10% |
| 多维归因 | s1 +200 与 Z 未实现 +200、s2 -100，按策略/按标的分别核对 |
| 无未来数据 | 统计只消费已发生交易与当日及以前收盘价；测试均按日推进 |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| Android JVM 全量测试 | `gradlew.bat -p android testDebugUnitTest --no-daemon` | PASS，54 项，0 失败（含统计 5 项） |
| Android lint | `gradlew.bat -p android lintDebug --no-daemon` | PASS |

## 风险与未完成项

- 统计口径（含费用入成本、保本计数、回退估值）已在本文件固化；真机界面展示和用户对账在 FULL-504/统一验收阶段执行。
- 净值曲线按自然日推进，未按交易日历裁剪；真实交易日历对齐依赖 FULL-201/301 的日历语义，已在状态表注明。

## 状态建议

实现完成，等待系列统一审查。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTED`。本机重跑验收命令均通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`。P3（UTC `epochDay` 自然日划分）保留为已知缺口，不阻塞本次结论。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `TradingStatsTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

验收角色未修改实现代码。
