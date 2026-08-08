# Android 链独立审查记录（review_android_chain）

日期：2026-08-06
角色：独立审查（只读，未修改任何实现代码）
范围：FULL-300、301、302、303、402、403、404、500、501、502、503、504、704（STATUS.md 中处于 `REVIEW` 的 Android 行情/策略/交易/图谱集群）

## 审查证据

- 逐项阅读 `docs/deliveries/FULL-{300,301,302,303,402,403,404,500,501,502,503,504,704}.md` 及 Android 源码/测试。
- 重新执行（JDK 21 + 临时 subst 盘，`--rerun-tasks`）：
  - `gradlew -p android testDebugUnitTest --no-daemon`：BUILD SUCCESSFUL，18 个 suite / 65 tests / 0 failures / 0 errors / 0 skipped。
  - `gradlew -p android lintDebug --no-daemon`：BUILD SUCCESSFUL。
- `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_strategy_dsl.py -q`：PASS（FULL-403 桌面侧共享向量）。
- 对 FULL-501 的外键插入顺序用 SQLite `PRAGMA foreign_keys=ON` 最小复现：先插 `trades(importBatchId=...)` 再插 `ledger_imports` 在同一事务内立即报 `FOREIGN KEY constraint failed`（与代码顺序一致）。

## 集群结论

**CHANGES_REQUIRED**：FULL-501 存在 P1 缺陷（账本导入事务中外键父行后插，任何含交易的导入在设备上都会失败）。其余 12 项未发现 P0/P1，可单独进入 `ACCEPTANCE`，但均附 P2/P3 改进项；FULL-502/504 与 501 存在依赖链，建议随 501 修复后统一复核。

## 逐项结论与问题

### FULL-300：ACCEPTANCE（附 P3）

- P3：`MarketHotDatabase`/`MarketPackageDao.history()` 从未被调用（`android/app/src/main/java/com/marketmonitor/app/data/DatabaseBoundary.kt:125-146`），`importPackage` 只写 SharedPreferences（`MarketPackageImporter.kt:81-104`），"市场热库"仅有定义未接线；`deleteMarketData` 也无调用方（`DatabaseBoundary.kt:41`），且不清理 `active/imported` 偏好。
- P3：`MainActivity` 为 Trading 与 Watchlist 分别 `remember` 创建两个 `UserDatabase` 实例，且首次创建在组合期做 KeyStore/SharedPreferences 工作（主线程）。

### FULL-301：ACCEPTANCE（附 P3）

- P3：K 线 WebView 开启 `allowFileAccess=true`（`MainActivity.kt:372-374`），页面内容又混入来自签名包的数据；加载 assets 无需该开关，建议关闭。
- P3：`readActive()` 对任何读取异常统一返回 null（`ImportedMarketData.kt:30-51`），UI 无法区分"包损坏/读取失败"与"确实无数据"。
- P3：无 K 线 HTML/WebView/交互的 JVM 或仪器化测试，仅覆盖 bar 解码。

### FULL-302：ACCEPTANCE（附 P3）

- P3：`MarketOverview` 只累计 PASS/WARNING/FAILED，未知 `quality_status` 静默不计为异常（`MarketOverview.kt:57-68`），与"缺失败不能显示为正常"的目标有偏差。
- P3：无 Compose 层测试（交付记录亦只声明逻辑层与编译验证）。

### FULL-303：ACCEPTANCE（附 P2/P3）

- P2：清理按钮无失败处理：`StoragePolicy.cleanup` 删除中任一 `IOException`（只读文件、权限、IO）会沿 `onClick` 直接抛出（`StoragePolicy.kt:55-73`、`MainActivity.kt:107-115,246`），且中途失败会留下半删除的包目录。
- P3：`StatFs` 失败时回退 `Long.MAX_VALUE`（`MainActivity.kt:108-110`），使"空间不足才清理"的策略在异常时失效；UI 无失败提示路径。

### FULL-402：ACCEPTANCE（附 P3）

- P3：参数化 `window` 的运行值只受参数 `minimum/maximum` 约束（`DslProgram.kt:362-370`、`DslInterpreter.kt` 的 `windowOf`），若策略未声明上限可传入远超 schema `windowRef` 1000 上限的值，输出全 null 而非拒绝；建议与契约上限对齐。
- P3：契约 schema `nodes.maxProperties: 200`（`contracts/strategy-dsl.schema.json:31`）与代码 `limits.max_nodes` 上限 2000（`DslProgram.kt:225-230`）不一致。

### FULL-403：ACCEPTANCE

- 桌面 pytest 与 Android `DslSharedVectorsTest` 均重跑通过；3 组向量离散信号全等、浮点容差 1e-9。无阻断问题。

### FULL-404：ACCEPTANCE（附 P2）

- P2：`StrategyViewModel.run` 同步执行解释器（`StrategyViewModel.kt:114-117`），`StrategyTab` 在按钮 onClick 的主线程直接调用（`StrategyTab.kt:117-120`）；按默认 2s/500k ops 预算，最坏会卡住 UI 且无取消/进度。
- P2：历史持久化 `decode` 把保存的 `parameters` 恢复成 `emptyMap`（`StrategyViewModel.kt:63-66`），重启后运行历史丢失参数信息（UI 当前也不展示参数）。

### FULL-500：ACCEPTANCE（附 P2/P3）

- P2：迁移仅用原生 SQLite 手工断言表/列/FK/索引（`TradingSchemaMigrationTest.kt`），未用 Room `MigrationTestHelper` 对照 kapt 导出的 `UserDatabase/2.json` 做真实 Room 迁移；CHECK 约束又不参与 Room TableInfo 比较（交付已注明），真实升级路径风险留待设备。
- P3：同 FULL-300 的重复 Room 实例与未接线的市场热库问题。

### FULL-501：CHANGES_REQUIRED

- **P1**：`importLedger` 先插入 `trades`（带 `importBatchId` 外键）再插入 `ledger_imports` 父行（`TradingRepository.kt:159-176`，`insertTrades` 在 163、`insertLedgerImport` 在 169）。Room 默认启用外键且 SQLite 即时检查，任何含交易的账本导入都会 `SQLiteConstraintException` 回滚。JVM 测试只覆盖解析器与 DDL，未覆盖该 DAO 事务路径（交付记录已注明）。修复应调整顺序：先 `strategies`/`ledger_imports`，再 `trades`/`fees`/`cash`（或对 FK 使用 DEFERRABLE）。
- P2：`reviseTrade` 不校验父交易状态（`TradingRepository.kt:111-128`），可对 REVISED/CANCELLED 父交易再建 EXECUTED 子记录（UI 隐藏入口，但仓库 API/导入/备份路径不受保护）；`cancelTrade` 已有状态校验（148），应对称补齐。
- P2：空账本时 `positions()`/`stats()` 经 `result.finalSnapshot` 抛 `NoSuchElementException`（`PositionCalculator.kt:61`、`TradingRepository.kt:203,214`、`TradingStats.kt:118`）；`TradingScreen.loadAll` 捕获后显示 "List is empty."（`TradingScreen.kt:66-73`），新装用户打开交易页即见错误。

### FULL-502：ACCEPTANCE（附 P2/P3）

- P2：空账本统计路径同上（`TradingStats.kt:118`），被 UI `runCatching` 掩盖为错误提示而非崩溃，但属于失败处理缺口。
- P3：自然日按 UTC `epochDay` 划分（`PositionCalculator.kt:167-169`），早盘/跨日现金事件可能偏移一日；交付已注明未按交易日历裁剪。

### FULL-503：ACCEPTANCE（附 P2/P3）

- P2：备份导出/恢复的 PBKDF2（210k 次）与文件读写均在主线程协程执行（`TradingScreen.kt:125,135,551-568`、`PersonalBackup.kt:143`），导出/恢复期间明显卡 UI。
- P3：`import` 不校验备份头中 `storedIterations` 的下限（`PersonalBackup.kt:99-108`），损坏/恶意文件可声明 1 次迭代降低暴力破解成本。
- P3：恢复前无二次确认，选错合法备份会立即清库（事务回滚只保护失败场景）。

### FULL-504：ACCEPTANCE（附 P2）

- P2：`prices` 恒为空且从未从市场包/`ImportedMarketData` 接线（`TradingScreen.kt:64,71`），复盘页的净值曲线、收益、暴露全部走成本价回退，未使用真实收盘价。交付记录已注明该缺口，但 FULL-301/302 已实现完毕，建议验收前统一接线。
- P2：备份主线程阻塞与空账本错误提示同 FULL-503/502。
- P3：无 Compose 仪器化测试（已注明）。

### FULL-704：ACCEPTANCE（附 P2/P3）

- P2：图谱快照导入无大小限制且解析失败被静默吞掉：`refreshGraphSnapshot` 捕获后不更新任何错误状态（`MainActivity.kt:203-211`），大 JSON `readText` 可能 OOM（`Error` 不被 catch），用户导入坏文件无反馈。
- P3：重复 `entity_id` 时搜索可列出但 `entityFor` 取最后一条；关系列表为 `Column.forEach` 非懒加载（数据量大时卡顿）。

## 状态建议

建议由协调方按上述结论更新 STATUS.md：FULL-501 → `CHANGES_REQUIRED`；FULL-300/301/302/303/402/403/404/500/502/503/504/704 → `ACCEPTANCE`（P2/P3 作为修复与验收阶段清单保留）。真机验收项（SQLCipher 打开/替换行情库/16KB/断网导入/完整录入-复盘-备份-恢复）仍按原计划列入设备验收，不因本次代码审查通过而视为完成。
