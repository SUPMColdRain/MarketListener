# FULL-302 实现交付：市场概览、指标、筛选、异常和质量提示

日期：2026-08-06
状态：实现完成（逻辑层与 JVM 测试通过；UI 接线已编译验证；真机状态显示待设备验收）
角色：root 实现

## 结果

- `MarketOverview`：包/截止时间/陈旧（24h 阈值可注入）/每标的周期、K 线数与 PASS/WARNING/FAILED 计数/异常标的数；缺失数据显式“无已导入行情数据（不显示为零或正常）”。
- 行情页 `OverviewCard`：概览摘要（标的数、K 线数、异常数、陈旧提示）。
- 测试：`MarketOverviewTest`（无数据显式陈旧、异常聚合、陈旧截止时间）。

## 状态建议

实现完成，真机缺失/失败/陈旧状态显示待设备验收。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTANCE`（维持）。本机可执行部分重跑通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`；真机状态显示未验收，如实不标 `ACCEPTED`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `MarketOverviewTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

**设备解除条件**：Android 13+ 设备在缺失/失败/陈旧数据场景确认 UI 显示“无已导入行情数据/异常/陈旧”，不显示为零或正常。已知 P3（未知 `quality_status` 不计异常、无 Compose 层测试）保留。
