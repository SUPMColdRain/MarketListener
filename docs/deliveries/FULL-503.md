# FULL-503 实现交付：个人数据加密备份/恢复与错误回滚

日期：2026-08-06
状态：实现完成（密码/篡改/截断/旧版本/中断回滚测试全绿），等待系列统一审查
角色：`impl_trading` 实现

## 范围与边界

实现个人库（策略、交易、费用、资金、拆分、持仓快照、导入批次、自选）的加密导出与事务化恢复：PBKDF2-HmacSHA256 + AES/GCM、版本头、明文 JSON、恢复计划校验与事务回滚。不涉及行情库备份；不写入任何明文密码或私钥。

## 修改文件

- `android/app/src/main/java/com/marketmonitor/app/trading/PersonalBackup.kt`（新增）：`PersonalBackupCodec`（导出/导入、版本与错误分类）、`RestorePlanner`（表白名单、列校验、删除/插入顺序）。
- `android/app/src/main/java/com/marketmonitor/app/trading/TradingRepository.kt`：`exportBackup`/`restoreBackup`（`withTransaction` 内清表+重建，失败自动回滚）。
- `android/app/src/test/java/com/marketmonitor/app/trading/PersonalBackupTest.kt`（新增）：8 项备份专项。
- `android/app/src/test/java/com/marketmonitor/app/trading/TradingSchemaMigrationTest.kt`：`interruptedRestoreRollsBackToOriginalLedger`（SQL 层中断回滚）。

## 验收要点对应证据

| 验收标准 | 证据 |
|---|---|
| 正确密码往返 | 导出→导入 8 张表逐表一致（含 null 字段与空表） |
| 错误密码 | GCM 认证失败 → `BackupException.WrongPassword`，不返回任何数据 |
| 篡改/截断 | 密文末字节翻转 → 认证失败；头部不足 → `Truncated` |
| 旧版本/未知格式 | 版本字节非 1 → `UnsupportedVersion`；魔数错误 → `InvalidFormat` |
| 恢复中断回滚 | SQLite 事务中注入外键违例行 → 回滚后原账本（策略/交易/费用）逐行不变 |
| 恢复前校验 | 未知表/未知列/非标量值在写入前被 `RestorePlanner` 拒绝 |
| 恢复前后一致 | 恢复在单事务内完成，`RestoreResult` 返回逐表行数供核对 |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| Android JVM 全量测试 | `gradlew.bat -p android testDebugUnitTest --no-daemon` | PASS，54 项，0 失败（含备份 8 项与回滚 1 项） |
| Android lint | `gradlew.bat -p android lintDebug --no-daemon` | PASS |

## 风险与未完成项

- 密码不保存、不写入仓库；KDF 迭代数 210000（测试 5000）。若用户遗忘密码，数据不可恢复——已在 UI 文案说明。
- 真实文件选择器往返、SQLCipher 加密库上的完整导出/恢复流程需 Android 13+ 设备验收；JVM 覆盖容器与 SQL 层语义。

## 状态建议

实现完成，等待系列统一审查。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTED`。本机重跑验收命令均通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`。真机 SAF/SQLCipher 完整导出-恢复往返作为已知设备缺口如实记录；P2（主线程 PBKDF2/文件 IO）与 P3（storedIterations 下限、恢复无二次确认）保留为已知缺口，不阻塞本次结论。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `PersonalBackupTest`、中断回滚） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

验收角色未修改实现代码。
