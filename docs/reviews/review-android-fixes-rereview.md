# Android 修复复审记录（review_android_fixes_rereview）

日期：2026-08-06
角色：独立复审（只读，未修改任何实现代码）
范围：针对 `docs/reviews/review-android-chain.md` 结论的修复复审：FULL-501（P1/P2）与 `docs/reviews/unified-review-cross.md` P1（FULL-504 真实收盘价接线），并复跑 Android 行情/策略/交易/图谱集群。

## 复审证据

- 逐项核对代码：`TradingRepository.importLedger` 现按 strategies → ledger_imports → trades → trade_fees → cash_events 的父行优先顺序插入；`reviseTrade` 校验父交易必须为 `EXECUTED`；`PositionResult.finalSnapshot` 空账本回退零值快照；`TradingScreen(repository, marketData)` 从行情包首只标的口线构造 `DailyClose` 并接入 `stats(prices)`。
- 独立 SQLite `PRAGMA foreign_keys=ON` 复现：旧序（先插 trades 再插 ledger_imports）立即报 `FOREIGN KEY constraint failed`；新序（父行优先）插入成功。与 Room 导出 Schema `UserDatabase/2.json` 中 trades→strategies/ledger_imports、trade_fees→trades 的外键定义一致。
- Android JVM 全量：JDK 21 + 临时 subst 盘执行 `testDebugUnitTest --rerun-tasks`：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped，BUILD SUCCESSFUL。
- Android lint：`lintDebug`：0 errors / 9 warnings（依赖版本、`SetJavaScriptEnabled`、kapt、autoboxing、缺应用图标；均为既有非阻断项）。
- 桌面共享向量：`desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_strategy_dsl.py -q`：PASS 43 项（FULL-403 桌面侧）。
- `git diff --check`：通过（仅 CRLF 提示）。

## 修复核验结论

| 原审查项 | 结论 |
|---|---|
| FULL-501 P1：导入事务外键父行后插 | 已修复：先插 `strategies`/`ledger_imports` 父行，再插 `trades`/`trade_fees`/`cash_events`；SQL 复现通过 |
| FULL-501 P2：`reviseTrade` 可修订已修订/已撤销父交易 | 已修复：父交易状态非 `EXECUTED` 时抛 `IllegalArgumentException` |
| FULL-501 P2：空账本 `positions()`/`stats()` 抛 `NoSuchElementException` | 已修复：`finalSnapshot` 回退零值快照，空账本返回空持仓与零值统计；新增 `EmptyLedgerTest` |
| unified-review-cross P1：复盘净值缺真实收盘价 | 已修复：`TradingScreen` 从行情包日线初始化 `DailyClose`，`MainActivity` 传入 `marketData` |

## 结论

原 `CHANGES_REQUIRED` 的阻断项已关闭；Android 集群 FULL-300/301/302/303/402/403/404/500/501/502/503/504/704 无遗留 P0/P1，复审结论：`ACCEPTANCE`。以下 P2/P3 保留为修复与验收阶段清单，不阻塞本次结论。

## 遗留 P2/P3（复审确认仍在）

- FULL-303 P2：`StoragePolicy.cleanup` 删除中的 `IOException` 未在 `MainActivity` 清理按钮捕获，中途失败会留下半删除包目录；P3：`StatFs` 失败回退 `Long.MAX_VALUE`，空间不足策略失效且 UI 无失败提示路径。
- FULL-404 P2：`StrategyViewModel.run` 同步在主线程执行（`StrategyTab` onClick 直调），默认 2s/500k ops 预算下会卡 UI 且无取消/进度；`PreferencesStrategyHistoryStore.decode` 仍把 `parameters` 恢复为 `emptyMap`，重启后历史丢失参数信息。
- FULL-502 P3：`PositionCalculator` 仍按 UTC `epochDay`（`floor(millis/86400000)`）划分自然日，早盘/跨日现金事件可能偏移一日。
- FULL-503 P2：备份导出/恢复的 PBKDF2 与文件读写仍在主线程协程执行；P3：`import` 未校验备份头 `storedIterations` 下限（损坏/恶意文件可声明 1 次迭代降低爆破成本）；恢复前无二次确认。
- FULL-504 P2：`prices` 仅接线行情包首只标的口线，多标的持仓仍回退成本价（`markedWithFallback` 未在 UI 展示）；同会话切换行情包后 `prices` 已非空则不会刷新；备份主线程问题同 FULL-503；P3：无 Compose 仪器化测试。
- FULL-704 P2：图谱快照导入无大小上限，`file.readText()` 大 JSON 有 OOM 风险（`catch Exception` 不捕获 `Error`），解析失败经 `loaded(null)` 提示“尚未导入”易误导；P3：重复 `entity_id` 时 `associateBy` 后值胜出，关系列表 `Column.forEach` 非懒加载。
- FULL-300 P3：`MarketHotDatabase`/`MarketPackageDao.history()`/`deleteMarketData` 仍无调用方；`MainActivity` 中 `TradingRepository` 与 `WatchlistRepository` 各自创建 `UserDatabase` 实例，组合期在主线程执行 KeyStore/SharedPreferences 工作。
- FULL-301 P3：K 线 WebView 仍开启 `allowFileAccess=true`；`readActive()` 对读取异常统一返回 null，UI 无法区分“包损坏/读取失败”与“确实无数据”；无 WebView/交互仪器化测试。
- FULL-302 P3：`MarketOverview` 只累计 PASS/WARNING/FAILED，未知 `quality_status` 不计入异常；无 Compose 层测试。
- FULL-402 P3：`windowRef` 运行值仅受参数 `minimum/maximum` 约束，未与 schema 的 1000 上限对齐；契约 `nodes.maxProperties: 200` 与代码 `limits.max_nodes` 可配置到 2000 不一致。
- FULL-501 测试缺口：Room DAO 事务路径仍无 JVM 覆盖（需设备/仪器化），本次以外键 SQL 复现与代码核对确认。

## 状态建议

建议协调方将 FULL-300/301/302/303/402/403/404/500/501/502/503/504/704 由 `REVIEW` 更新为 `ACCEPTANCE`，P2/P3 作为验收阶段修复清单保留；真机验收项（SQLCipher 打开、行情库替换、16KB、断网导入、完整录入-复盘-备份-恢复、图谱导入）仍按原计划列入设备验收。
