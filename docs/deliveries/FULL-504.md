# FULL-504 实现交付：交易复盘图表、筛选、备注与备份恢复流程 UI

日期：2026-08-06
状态：实现完成（JVM 状态/筛选测试全绿；真机流程如实待验收），等待系列统一审查
角色：`impl_trading` 实现

## 范围与边界

在主界面新增“交易”区：交易记录（录入/修订/撤销/筛选）、持仓、统计、复盘四个页签；复盘页含净值曲线、加密备份导出/恢复（SAF 文件选择）、密码输入与错误/成功反馈。不修改行情导入与 K 线逻辑（仅主界面加页签入口）。

## 修改文件

- `android/app/src/main/java/com/marketmonitor/app/trading/ui/TradingScreen.kt`（新增）：Compose 界面（TabRow/LazyColumn/表单/筛选/净值 Canvas 图/备份恢复）。
- `android/app/src/main/java/com/marketmonitor/app/trading/ui/TradingStateHolders.kt`（新增）：`TradingUiState`、`TradeFilterState`、`TradeEntryDraft`（校验/费用解析/时间解析）、`BackupUiState`。
- `android/app/src/main/java/com/marketmonitor/app/MainActivity.kt`：顶部“行情/交易”页签接入 `TradingScreen`（`DatabaseFactory.user` 延迟到首次使用时打开）。
- `android/app/src/test/java/com/marketmonitor/app/trading/TradingStateHoldersTest.kt`（新增）：5 项状态/筛选/表单校验测试。

## 验收要点对应证据

| 验收标准 | 证据 |
|---|---|
| 表单校验 | 空标的/数量≤0/价格≤0/时间非法/费用格式错误均给出字段级错误；合法草稿可转换为 `TradeInput` |
| 筛选 | 按标的、策略（忽略大小写）、方向、日范围过滤交易；空筛选返回全部 |
| 修订流程 | `draftFromTrade` 预填原记录 → 保存修订走 `reviseTrade`（父记录 REVISED）；“保存修订/取消”状态转换有测试 |
| 备份/恢复流程 | SAF 创建/打开文件 + 密码 → 仓库导出/恢复；成功/失败消息状态机有测试 |
| 净值图表 | `NavChart` 用 Canvas 绘制净值曲线；数据不足时显示占位文案 |
| 真机完整流程 | 需 Android 13+ 设备：录入→复盘→加密备份→清库恢复→错误回滚；当前如实未验收（无设备） |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| Android JVM 全量测试 | `gradlew.bat -p android testDebugUnitTest --no-daemon` | PASS，54 项，0 失败（含 UI 状态 5 项） |
| Android lint | `gradlew.bat -p android lintDebug --no-daemon` | PASS（Compose 无新警告） |
| 构建 | `assembleDebug` 随 FULL-003 统一验证执行 | 待系列统一验证阶段复跑 |

## 风险与未完成项

- Compose 渲染与文件选择器交互未做仪器化截图测试；真机验收清单（录入、复盘、备份、恢复、错误回滚）留待统一验收。
- 复盘页价格来源目前由调用方提供 `DailyClose`（正式接入行情库读取在 FULL-301/302 完成后统一接线）。

## 状态建议

实现完成，等待系列统一审查。

## 统一审查修复（2026-08-06）

按 `docs/reviews/unified-review-cross.md` P1：`TradingScreen(repository, marketData)` 从行情包首只标的口线初始化 `DailyClose` 收盘价序列，复盘净值曲线使用真实行情；MainActivity 传入 `marketData`；手动价格输入仍可覆盖。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTANCE`（维持）。本机可执行部分重跑通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`；真机完整流程未验收，如实不标 `ACCEPTED`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `TradingStateHoldersTest`、`TradingStatsTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

**设备解除条件**：Android 13+ 设备完成完整录入→复盘→加密备份→清库恢复→错误回滚流程。已知 P2（多标的口径仍回退成本价、备份主线程 PBKDF2/文件 IO）保留。
