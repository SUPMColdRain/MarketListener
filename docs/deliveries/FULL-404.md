# FULL-404 实现交付：策略参数编辑、启停、运行历史和信号解释页面

日期：2026-08-06
状态：实现完成（等待系列统一审查；真机操作待设备验收）
角色：root 实现

## 范围与边界

Android 策略页：内置声明式 DSL v1 示例策略（MA 交叉），参数按 Schema 定义渲染输入控件（数字/整数/布尔，含最小/最大值提示），参数校验与解释器边界一致；运行使用已导入行情包的日线收盘序列；运行历史持久化（SharedPreferences JSON，可插拔 `StrategyHistoryStore`）；每条运行展示状态、信号标签、触发条件、信号位置与风险标签。

## 修改文件

- `android/app/src/main/java/com/marketmonitor/app/strategy/ui/StrategyViewModel.kt`（新增）：`StrategyRunRecord`、`StrategyHistoryStore`（内存与 SharedPreferences 实现）、`StrategyViewModel`（validate 与解释器一致的参数类型/边界/整数校验；run 捕获 DslException 不崩溃并记录 FAILED）。
- `android/app/src/main/java/com/marketmonitor/app/strategy/ui/StrategyTab.kt`（新增）：Compose 策略页（参数表单、运行按钮、信号解释卡片、运行历史）。
- `android/app/src/main/java/com/marketmonitor/app/MainActivity.kt`：新增“策略”页签（index 3）。
- `android/app/src/test/java/com/marketmonitor/app/strategy/ui/StrategyViewModelTest.kt`（新增）：参数越界拒绝、合法运行 PASS 且信号/解释/历史正确、运行时参数错误记录 FAILED 不崩溃。

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon`（JDK 21 + subst） | BUILD SUCCESSFUL，65 tests / 0 failures（含本任务 3 项） |

## 风险与未完成项

- 内置示例策略为演示 DSL；策略包导入与多策略管理留待后续（策略包清单契约已存在）。
- 真机参数编辑→运行→历史与信号解释流程需设备验收。

## 状态建议

实现完成，等待系列统一审查与验收。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTANCE`（维持）。本机可执行部分重跑通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`；真机参数编辑→运行→历史与信号解释流程未验收，如实不标 `ACCEPTED`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `StrategyViewModelTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

**设备解除条件**：Android 13+ 设备完成策略参数编辑→运行→运行历史与信号解释页面流程。已知 P2（主线程同步解释器卡 UI 且无取消/进度；历史 `parameters` 恢复为 `emptyMap`）保留。
