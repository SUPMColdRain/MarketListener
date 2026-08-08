# FULL-500 实现交付：个人库交易/费用/资金/持仓/策略归属数据模型

日期：2026-08-06
状态：实现完成（Android JVM 测试全绿），等待系列统一审查
角色：`impl_trading` 实现

## 范围与边界

在个人加密库 `user.db` 中新增交易账本数据模型：策略、交易、交易费用、资金流水、拆分、持仓快照与导入批次实体，DAO、v1→v2 迁移和 SQLCipher 打开路径。未改动行情库（`market_hot.db`/`market-cold`）与个人库边界常量。

## 修改文件

- `android/app/src/main/java/com/marketmonitor/app/trading/TradingEntities.kt`（新增）：7 张交易表实体、`TradingDao`、`TradingSchema`（迁移 DDL，含 CHECK 与 FK）和 `TradingMigrations.MIGRATION_1_2`。
- `android/app/src/main/java/com/marketmonitor/app/data/DatabaseBoundary.kt`：`UserDatabase` 升级为 version 2 并登记交易实体/DAO，`DatabaseFactory.user` 挂载 `MIGRATION_1_2`（SQLCipher 打开路径不变）。
- `android/app/schemas/com.marketmonitor.app.data.UserDatabase/2.json`（kapt 导出）：version 2 官方 Schema 证据。
- `android/app/build.gradle.kts` + `gradle.lockfile`：新增测试依赖 `org.xerial:sqlite-jdbc:3.41.2.2`（真实 SQLite 迁移/回滚测试，锁文件已更新）。
- `android/app/src/test/java/com/marketmonitor/app/trading/TradingSchemaMigrationTest.kt`（新增）：迁移建表、列/外键/索引、CHECK 拒绝非法行、事务回滚。

## 验收要点对应证据

| 验收标准 | 证据 |
|---|---|
| Room 迁移 | `MIGRATION_1_2` 与 kapt 导出 `2.json`；迁移测试用真实 SQLite 执行同一 DDL 并验证 8 张表、列类型、FK、索引和 watchlist 数据保留 |
| 约束 | SQL CHECK（方向/数量/价格/状态/金额/换股比例）与域层 `TradeInputValidator` 双重校验；非法行插入被 SQLite 拒绝 |
| 加密打开/重启 | `DatabaseFactory.user` 仍走 SQLCipher `SupportOpenHelperFactory` + AndroidKeyStore 包装密钥并挂载迁移；本机无设备，真实打开/重启列入设备验收 |
| CRUD 与行情库隔离 | `DatabaseBoundaryTest` 保持个人库/行情库名称边界断言；行情库文件与个人库文件路径未变 |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| Android JVM 全量测试 | `gradlew.bat -p android testDebugUnitTest --no-daemon`（JDK 21 + 临时 subst 盘） | PASS，54 项，0 失败（含本任务 4 项迁移测试） |
| Android lint | `gradlew.bat -p android lintDebug --no-daemon` | PASS（仅存量依赖版本/WebView 警告） |
| 锁文件 | `--write-locks` 持久化 `sqlite-jdbc` 条目 | 已提交到工作区 |

## 风险与未完成项

- CHECK 约束只在迁移 DDL 中（Room 的 TableInfo 不比较 CHECK），域层校验同步兜底；已写入本交付记录。
- SQLCipher 加密库的真实打开、迁移后重启、个人数据保留需 Android 13+ 设备验收，当前如实未验收。

## 状态建议

实现完成，等待系列统一审查（依赖：FULL-300 的行情/个人库边界语义已由既有 `DatabaseBoundary` 保证）。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTED`。本机重跑验收命令均通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`。SQLCipher 真机打开/迁移后重启作为已知设备缺口如实记录，未视为已实测；P2/P3（Room 迁移未用 MigrationTestHelper 对照、重复 Room 实例、热库未接线）保留为已知缺口，不阻塞本次结论。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `TradingSchemaMigrationTest`、`DatabaseBoundaryTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

验收角色未修改实现代码。
