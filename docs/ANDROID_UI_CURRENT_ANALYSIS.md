# MarketListener Android UI 现状分析（Phase 1 / T01）

> 状态：审计已完成（Phase 1 / T01 DONE）；Phase 2～10 已按本文件结论实施，
> 最终回归见仓库根 `scripts/verify.ps1`。
> 本文件只记录审计结论，不包含代码修改。审计时间为 2026-08-09，基于仓库当前工作树。

## 1. 当前页面组成

Android 端（`minSdk=33 / targetSdk=34`，Kotlin + Jetpack Compose）目前只有一个
`MainActivity`，内部用 `when (activeSection)` 切换五个“页面”：

| 序号 | 名称 | 实现 | 说明 |
| --- | --- | --- | --- |
| 0 | 行情 | `MarketMonitorScreen`（MainActivity 私有 Composable） | 行情包导入、局域网同步、数据状态、样本标的、周期 Tab、离线 K 线 |
| 1 | 数据 | `ui/DataScreen.kt` | 指标搜索 + `MetricGroupCard` 数字卡片列表 |
| 2 | 策略 | `strategy/ui/StrategyTab.kt` | 内置 DSL 策略、参数输入、运行与历史 |
| 3 | 统计 | `trading/ui/TradingScreen.kt` | 交易录入、持仓、统计、复盘/备份（内部 4 个 Tab） |
| 4 | 产业链 | `graph/GraphScreen.kt`（`GraphTab`） | Atlas HTML WebView + 图谱快照搜索/详情 |

没有独立的路由系统；`activeSection: Int` 是唯一导航状态。底部导航
`NavigationBarItem(icon = { Text("行情") })`，即“文字冒充图标”。

## 2. MainActivity 职责

`MainActivity.kt`（约 557 行）同时承担：

- 页面容器与五段底部导航；
- 行情包导入（`OpenDocument` → 复制到 cache → WorkManager 校验）；
- 局域网同步包下载（`HttpURLConnection` → 同一条导入链路）；
- WorkInfo 观察与导入状态映射；
- 行情数据读取（`ImportedMarketDataReader`，后台线程 + `runOnUiThread`）；
- 图谱快照导入/读取；
- 产业链 Atlas HTML 从冷数据目录复制到 filesDir；
- K 线 HTML 字符串拼接与 WebView 创建（`OfflineKline`，硬编码 `#101418/#d5dde5`）；
- 自选列表读写（`WatchlistRepository`）。

Activity 不是 ViewModel/StateHolder 结构，UI 状态全部是 Activity 字段上的
`mutableStateOf`，业务与 UI 耦合在一起。

## 3. 当前主题实现

- `res/values/themes.xml` 只有 `Theme.MarketMonitor`，parent 为
  `android:Theme.Material.Light.NoActionBar`；
- Compose 侧直接使用默认 `MaterialTheme`（Material 3 dynamic 默认配色），
  没有任何自定义 ColorScheme / Typography / Shape；
- 没有主题持久化，没有浅色/深色/跟随系统三模式；
- `MainActivity` 调用了 `enableEdgeToEdge()`，但未处理状态栏图标深浅色；
- 页面中多处硬编码颜色：K 线 HTML 的 `#101418/#d5dde5`、
  `TradingScreen` 的 `Color(0xFF1B9E77)`（买入/成功）、`Color(0xFFD1495B)`（卖出/失败）、
  `Color(0xFF2563EB)`（净值线）、`Color(0xFF9CA3AF)`（坐标线）。

结论：不存在统一 Design System，颜色散落在页面与 HTML 中。

## 4. 当前导航实现

- 无 Navigation Compose / 路由表；
- `NavigationBar` + 5 个 `NavigationBarItem`，icon 直接是 `Text(...)`；
- 每个页面自行 `statusBarsPadding()` 或 `padding(16.dp)`，没有统一 TopBar；
- 设置入口不存在（无设置页）；
- 页面切换不保存状态（切换 Tab 后 `remember` 状态保留与否取决于组合位置，
  实际上 5 个页面都被 `when` 切换，离开即销毁）。

## 5. 当前 K 线实现

- `OfflineKline(candles, hasImportedMarketData)` 是 MainActivity 的私有 Composable；
- 数据源：`ImportedMarketDataReader.candlesFor()` 从 `payload.sqlite` 的 `bars` 表读取，
  按 `period` 分组、`bar_open_time DESC LIMIT 600` 后反转；
- 渲染：`AndroidView` + `WebView`，HTML 字符串内嵌 candles JSON，
  `<script src='lightweight-charts.standalone.production.js'>`（assets 本地文件，163,684 字节）；
- 周期：`TabRow` 展示所有可用 period（如 `1d`、`60m`…）；
- 主题：硬编码暗色背景 `#101418`、文字 `#d5dde5`，上涨绿 `#1b9e77`、下跌红 `#d1495b`；
- 交互：仅 `fitContent()`；Crosshair 缩放/拖动依赖 Lightweight Charts 默认行为，
  未显式配置；没有 MA/EMA/Volume/信号层；
- 空态：HTML 内 `#empty` div 文本，未导入时提示“尚未导入行情数据”。

可复用资产：`assets/lightweight-charts.standalone.production.js` 保留即可，
不能删除。

## 6. 当前 DataScreen 数据来源

- `ImportedMarketDataReader.readGoldMetrics()` 读取 `gold_metrics` 表；
- `MetricGroups.kt` 把 `MarketMetric` 按 `groupKeyFor(metricId)` 聚合成
  `MetricGroup → MetricSeries（latest + sampleCount）`；
- `DataScreen.kt` 用 `filterMetrics()` 搜索、`aggregateMetrics()` 分组，
  然后每个 group 渲染成 `OutlinedCard`：指标名 + 最新值 + 期数；
- 已有 26 个分组规则：融资融券、A股宽度、涨跌停连板、期货宽度/龙虎榜、
  北向/南向、M1/M2、DR007、CPI/PPI、PMI、利率、美元指数、VIX、金银比、
  金油比、BTC/ETH 等；
- 数据缺口：`MarketMetric` 只有最新值与样本数，UI 不持有完整时间序列；
  `ImportedMarketData` 的 `bars` 才有逐根 K 线（每个标的每周期最多 600 根）。

## 7. 当前各页面状态管理

| 页面 | 状态管理 |
| --- | --- |
| 行情 | Activity 字段 `mutableStateOf` + WorkManager 回调；`MarketImportUiState` data class 描述导入状态 |
| 数据 | `DataScreen` 内部 `remember`（query、filter、groups） |
| 策略 | `StrategyViewModel`（普通类，非 AndroidX ViewModel），历史存 SharedPreferences |
| 统计 | `TradingScreen` 内部 `remember { mutableStateOf(...) }` + `TradingUiState` |
| 产业链 | Activity 字段 `graphState: GraphSearchState`（纯数据类，查询/选中/错误） |

除 `StrategyViewModel` 外没有 ViewModel；所有列表都是 `LazyColumn` 但
`MarketMonitorScreen` 用 `verticalScroll` 包全部内容。

## 8. 可复用组件

- `data/`：`ImportedMarketDataReader`、`MarketPackageImporter/Verifier/Worker`、
  `WatchlistRepository`、`MetricGroups`（聚合/筛选/格式化）、`DatabaseBoundary`；
- `market/`：`MarketOverview`（质量/陈旧度聚合）、`StoragePolicy`（冷数据清理）；
- `graph/`：`GraphRepository`（离线搜索/详情）、`GraphModels`、`GraphSearchState`；
- `strategy/`：`DslProgram/DslInterpreter`、`StrategyViewModel`、历史持久化；
- `trading/`：`TradingRepository`、`PositionCalculator`、`TradingStatsCalculator`、
  `LedgerImport`、`PersonalBackup`、`TradingStateHolders`；
- 资产：`lightweight-charts.standalone.production.js`（163,684 B）。

没有可直接复用的 Compose 主题、图表组件、通用 TopBar/BottomBar 组件。

## 9. UI 重构影响范围

### 必须保留（不改业务语义）

- `MarketPackageImporter/Verifier` 的签名/哈希/结构校验与 WorkManager 导入链路；
- `ImportedMarketDataReader` 只读查询与 600 根限制；
- `WatchlistRepository`、`GraphRepository`、`StrategyViewModel`、`TradingRepository`
  及其计算逻辑；
- `StoragePolicy` 清理规则；
- `assets/lightweight-charts.standalone.production.js`；
- 产业链 Atlas 的 `file://` WebView 加载路径与离线能力；
- 行情/数据/策略/统计/产业链五个核心功能入口。

### 需要重构

- `MainActivity`：拆出 UI Shell（`MarketListenerApp/AppScaffold/AppNavigation`），
  保留业务回调；
- 主题：新增 `ui/theme/`（Color/Type/Shape/Dimensions/MarketColors/ThemeMode/
  ThemeRepository），`MarketListenerTheme` 包裹整个 App；
- 导航：真 Icon + Label 的底部导航；统一 TopBar；新增设置页（三主题切换）；
- K 线：`OfflineKline → TradingChartView`，主题注入；
- DataScreen：新增 UI 模型、Mapper、`DataDashboardViewModel`，图表化；
- 图表基础设施：`ui/chart/`（ChartTheme、EChartsView、OptionBuilder、
  TradingChartView、Sparkline、RankingChart）；新增本地 `echarts.min.js` 资产；
- 其他页面：策略/统计/产业链去掉“卡片堆”，接入语义颜色；
- Splash：`themes.xml` 改 SplashScreen 主题，预留 `app_logo/ic_launcher*`。

### 明确不改

- 不重写行情数据库/`payload.sqlite` 读取；
- 不改 `MarketPackageVerifier` 安全规则（含 `ALLOWED_ENTRIES` 白名单）；
- 不删除 Lightweight Charts；
- 不引入 React Native/Flutter；
- 不使用 CDN/远程字体；
- 不编造市场数据/排行榜/热力图。

## 10. 测试影响

现有单元测试位于 `android/app/src/test`：

- 合约/安全：`ContractValidationTest`、`MarketPackageVerifierTest`、`DatabaseBoundaryTest`；
- 数据：`ImportedMarketDataTest`、`DecodeMarketCandleTest`、`MetricGroupsTest`；
- 图谱：`GraphRepositoryTest`、`GraphSearchStateTest`；
- 市场：`MarketOverviewTest`、`StoragePolicyTest`；
- 策略：`DslInterpreterTest`、`DslSharedVectorTest`、`StrategyViewModelTest`；
- 交易：`EmptyLedgerTest`、`LedgerImportTest`、`PersonalBackupTest`、
  `PositionCalculatorTest`、`TradingSchemaMigrationTest`、`TradingStateHoldersTest`、
  `TradingStatsTest`；
- `SkeletonUnitTest` 冒烟。

影响：

- 纯 Kotlin 业务层（data/market/graph/strategy/trading）不动，测试应保持全绿；
- 主题与 Data Dashboard 是新增纯逻辑，必须新增单测
  （ThemeMode 映射/持久化序列化、Mapper 的系列生成、NaN/Infinity 过滤、
  Ranking 顺序、Heatmap 归一化）；
- 审计时没有 `androidTest`；本次已新增 Compose UI/Instrumented 测试，需要引入
  `androidx.test` + compose ui-test 依赖，且只能在设备/模拟器上运行，
  `scripts/verify.ps1` 只跑 `testDebugUnitTest`，不会执行 connected tests；
  已在本机 AVD 上执行 `connectedDebugAndroidTest` 并通过；
- Gradle 启用了 dependency locking（`android/app/gradle.lockfile`），新增依赖后
  必须 `--write-locks` 更新锁文件，否则 `lintDebug/assembleDebug` 会失败。

## 附加审计发现

1. 仓库中没有正式 MarketListener Logo/launcher 资源（搜索 `logo|launcher|splash`
   仅命中第三方 setuptools 文件）。Phase 3 只搭建 Splash 架构并预留
   `app_logo / ic_launcher / ic_launcher_foreground`，不生成假 Logo，
   Logo 资源记为待补依赖。
2. 没有本地 ECharts 资产；`desktop/web/node_modules/echarts/dist/echarts.min.js`
   可作为同仓库资产复制进 `android/app/src/main/assets/`（Apache-2.0，
   需更新 `THIRD_PARTY_NOTICES.md`）。
3. `MarketPackageImporter.EXTRACT_ENTRIES` 与 `ALLOWED_ENTRIES` 仍包含
   `industry/industry-map.html`（历史兼容）；本次 UI 重构不修改该白名单。
4. `strings.xml` 当前为 UTF-8，app 名称为“行情监控”；可按品牌统一为
   “MarketListener”，但不影响业务逻辑。

## 实施对照（Phase 2～10 摘要）

审计后按原定阶段完成以下改造，业务层（data/market/graph/strategy/trading）语义未改：

| 阶段 | 交付 | 状态 |
| --- | --- | --- |
| Phase 2 Design System | `ui/theme/`（Color/Type/Shape/Dimensions/MarketColors/ThemeMode/ThemeRepository） | DONE |
| Phase 3 Splash | core-splashscreen + `splash_logo_placeholder`（正式 Logo 待补资源） | DONE（资源占位） |
| Phase 4 App Shell | `MarketListenerApp/AppScaffold/AppNavigation`、五 Tab Icon+Label、设置对话框 | DONE |
| Phase 5 图表基础设施 | `TradingChartView`（Lightweight Charts 主题注入）、`EChartsView`、本地 `echarts.min.js`、`Sparkline/AnimatedRanking` | DONE |
| Phase 6 DataScreen | `DataDashboardViewModel` + Mapper、多线/面积/热力图/动态排名，仅显示真实数据 | DONE |
| Phase 7 其他页面 | 行情（紧凑状态行 + 自选名称/代码/最新价/涨跌幅/Sparkline + K 线中心）、策略/统计/产业链接入统一 Design Token，产业链 WebView 主题桥接 `setMarketListenerTheme` | DONE |
| Phase 8 主题 QA | 静态扫描：无页面级硬编码颜色、无 Material Card 堆叠；状态栏/导航栏图标随应用主题切换 | DONE（代码级） |
| Phase 9 性能 | WebView 仅 K 线、当前 ECharts 面板、产业链 3 处受控实例；大列表 LazyColumn；横屏 K 线高度放大 | DONE（代码级，真机横屏仍建议人工验证） |
| Phase 10 测试 | 新增 ThemeMode/Mapper/KlineHtml/ECharts/AppNavigation/Splash/QuoteRowMapper 单测（108 项全绿），并新增 `androidTest`（五页导航、三主题选择、ThemeRepository 持久化、DataScreen 空态、图表 WebView 组合、App Shell 冒烟）；`connectedDebugAndroidTest` 已在本地 Android 13/14/17 三个 AVD 实际执行，每个版本 7 项全部通过 | DONE（单测 + Instrumented 已执行） |

剩余人工验收项：Android 13/14 真机上的 Splash、五页面 Light/Dark/System
切换、横屏图表、DataScreen 滚动与 WebView 数量观察（模拟器已做主要功能覆盖）；这些不在
`scripts/verify.ps1`（只跑 `lintDebug/testDebugUnitTest/assembleDebug`）覆盖范围内。
`connectedDebugAndroidTest` 已在本地 Android 13/14/17 三个 AVD 执行通过，
结果归档见 `docs/evidence/android-instrumented/`
（`TEST-Android-13-ML_API_33.xml`、`TEST-Android-14-ML_API_34.xml`、
`TEST-Android-17-Pixel_10_Pro_XL.xml`，每个 7 项，0 失败）。
正式 MarketListener Logo 仍为占位资源，待用户提供品牌资源。
