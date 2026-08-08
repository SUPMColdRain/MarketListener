# FULL-402 实现交付：Kotlin 离线 DSL 解释器

日期：2026-08-06
状态：实现完成（等待系列统一审查）
角色：impl_strategy_dsl（解释器主体）+ root（编译修复、JVM 测试、交付补齐）

## 范围与边界

Android Kotlin 白名单解释器与校验器：与 Python 端节点语义逐条一致；超时/取消/无数据/数值错误/规模超限不崩溃，返回结构化 DslException 错误；只引用截至当根 bar 收盘的历史数据。

## 修改文件

- `android/app/src/main/java/com/marketmonitor/app/strategy/dsl/DslProgram.kt`（新增）：DSL 文档解析/校验（白名单节点、类型推断、深度/规模、窗口参数约束、信号布尔检查）。
- `android/app/src/main/java/com/marketmonitor/app/strategy/dsl/DslInterpreter.kt`（新增）：拓扑求值、操作预算、超时/取消、数值错误包装。
- `android/app/src/main/java/com/marketmonitor/app/strategy/dsl/DslError.kt`（新增）：错误分类。
- `android/app/src/test/java/com/marketmonitor/app/strategy/dsl/DslInterpreterTest.kt`（新增）：合法求值、未知节点/任意代码/非布尔信号、NO_DATA、空序列、除零、TIMEOUT、CANCELLED、LIMIT。
- `android/app/build.gradle.kts`：jackson-databind 从 testImplementation 提升为 implementation（主源码依赖）；更新 `android/app/gradle.lockfile`。
- 编译修复：inner class 内禁止 companion（BATCH 移至外部 companion）；参数默认值范围检查支持 Int（`as? Number`）。

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon`（JDK 21 + 临时 subst 映射） | BUILD SUCCESSFUL；17 tests，0 failures |

## 状态建议

实现完成，等待系列统一审查与验收。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTED`。本机重跑验收命令均通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`。已知 P3（`windowRef` 上限未对齐 schema 1000、`nodes.maxProperties` 契约与代码上限不一致）保留为已知缺口，不阻塞本次结论。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| DSL/图谱/契约专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_strategy_dsl.py desktop\tests\test_industry_graph_models.py desktop\tests\test_industry_graph_importers.py desktop\tests\test_industry_graph_pipeline.py desktop\tests\test_industry_graph_review.py desktop\tests\test_contracts.py -q` | PASS：115 项收集，全部通过（exit 0） |
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `DslInterpreterTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

验收角色未修改实现代码。
