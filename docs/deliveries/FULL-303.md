# FULL-303 实现交付：热缓存、冷分片加载、存储清理和性能优化

日期：2026-08-06
状态：实现完成（策略逻辑与 JVM 测试通过；清理入口已接线；真机基准待设备验收）
角色：root 实现

## 结果

- `StoragePolicy`：冷分片清理（只删 `coldRoot/packages/` 下非活跃包、按最近访问最旧优先、保留 64MB 预算）；测试覆盖活跃包跳过、个人库不触碰、预算不足如实返回。
- 行情页“清理冷数据”按钮：读取 `StatFs` 可用空间并执行清理，显示释放字节；冷分片加载复用 `ImportedMarketDataReader`（按包目录读取）。
- 性能：K 线读取上限 600 根/周期；脱敏大文本性能回归已在 FULL-101 修复。

## 状态建议

实现完成，目标数据量基准与低空间真机验收待设备。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTANCE`（维持）。本机可执行部分重跑通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`；真机基准与低空间清理未验收，如实不标 `ACCEPTED`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `StoragePolicyTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

**设备解除条件**：Android 13+ 设备完成目标数据量冷分片加载基准与低空间清理，确认个人库零删除。**已知缺口**：P2（清理按钮未捕获删除中的 `IOException`，中途失败留下半删除包目录）；P3（`StatFs` 失败回退 `Long.MAX_VALUE`、空间不足策略失效且 UI 无失败提示）——均保留。
