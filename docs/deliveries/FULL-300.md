# FULL-300 实现交付：Android 导航、数据库迁移、行情库与个人库边界

日期：2026-08-06
状态：实现完成（JVM/构建验证通过；真机替换/删除行情库不影响个人库待设备验收）
角色：既有实现 + root（页签接线与文档补齐）

## 结果

- 导航：MainActivity 页签 行情/交易/图谱/策略。
- 数据库边界：`DatabaseBoundary`（user.db 独立、market_hot.db、market-cold 目录；`deleteMarketData` 只删行情）；UserDatabase（个人库，SQLCipher，v1→v2 迁移，含 watchlist/trading 实体）；MarketHotDatabase（市场热库独立）。
- 自选：`WatchlistEntity/WatchlistDao`（含 add/remove/all）+ `WatchlistRepository`；行情页“加入自选/移出自选”与自选清单。
- JVM 测试：`DatabaseBoundaryTest`（行情库替换/删除不触个人库）等；Android JVM 全量全绿。

## 状态建议

实现完成，真机替换/删除行情库后个人库保留待设备验收。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTANCE`（维持）。本机可执行部分重跑通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`；真机 SQLCipher 打开与行情库替换/删除隔离未验收，如实不标 `ACCEPTED`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `DatabaseBoundaryTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

**设备解除条件**：Android 13+ 设备完成 SQLCipher 打开/重启；替换或删除行情库后确认个人库（自选/交易）数据保留。已知 P3（热库/删除接口未接线、双 `UserDatabase` 实例）保留。
