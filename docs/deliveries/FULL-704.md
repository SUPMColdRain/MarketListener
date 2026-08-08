# FULL-704 实现交付：Android 产业链搜索、公司关系和来源查看

日期：2026-08-06
状态：实现完成（等待系列统一审查；真机操作待设备验收）
角色：impl_graph2（代码）+ root（编译验证与文档补齐）

## 结果

- `android/app/src/main/java/com/marketmonitor/app/graph/`：`GraphModels.kt`、`GraphRepository.kt`（实体/关系/证据查询与选择状态机）、`GraphSearchState.kt`（搜索/选择纯逻辑）、`GraphScreen.kt`（Compose 图谱页：搜索、公司关系列表、证据与确认状态查看、快照导入）。
- MainActivity 已接线“图谱”页签。
- JVM 测试：`GraphRepositoryTest.kt`、`GraphSearchStateTest.kt`。

## 自动化证据

`gradlew -p android testDebugUnitTest --no-daemon`：BUILD SUCCESSFUL，65 tests / 0 failures（含图谱 JVM 测试）。

## 风险与未完成项

- 真机从关系逐级追溯原始来源位置与确认状态需设备验收。

## 状态建议

实现完成，等待系列统一审查与验收。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTANCE`（维持）。本机可执行部分重跑通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`；真机从关系逐级追溯来源与确认状态未验收，如实不标 `ACCEPTED`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `GraphRepositoryTest`、`GraphSearchStateTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

**设备解除条件**：Android 13+ 设备从公司关系逐级追溯原始来源位置与确认状态。已知 P2（快照导入无大小上限、解析失败提示误导）与 P3（重复 `entity_id`、关系列表非懒加载）保留。
