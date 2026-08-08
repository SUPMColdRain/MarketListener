# FULL-301 实现交付：自选、标的列表、详情和专业 K 线交互

日期：2026-08-06
状态：实现完成（JVM/构建验证通过；真机查询/缩放/周期切换/截止时间待设备验收）
角色：既有实现 + root（自选接线与文档补齐）

## 结果

- 标的列表/详情：`ImportedMarketDataReader` 按标的+周期读取；行情页标的切换、周期 Tab（1d/分钟）、当前数据/截止时间/来源/质量状态卡。
- K 线交互：WebView lightweight-charts 离线渲染，缩放/平移由图表库提供，`blockNetworkLoads=true` 断网可用。
- 自选：加入/移出/清单显示（FULL-300 接线）。

## 状态建议

实现完成，真机真实包查询/缩放/周期切换/截止时间显示待设备验收。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTANCE`（维持）。本机可执行部分重跑通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`；真机真实包操作未验收，如实不标 `ACCEPTED`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `ImportedMarketDataTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors（`SetJavaScriptEnabled` 为存量非阻断项） |

**设备解除条件**：Android 13+ 设备导入真实签名包后完成标的查询、K 线缩放/平移、周期切换与截止时间/来源/质量显示。已知 P3（WebView `allowFileAccess`、`readActive` 吞错、无 WebView 仪器化测试）保留。
