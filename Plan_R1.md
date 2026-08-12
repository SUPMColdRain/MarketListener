# R1 开发计划（唯一进行中任务源）

最后更新：2026-08-13。本文是 R1 尚未完成工作的唯一事实来源；历史 `Plan.md`、`Plan_full.md`、`docs/*CURRENT_ANALYSIS*` 和 `*TASK_QUEUE*` 仅保留背景与证据，不再新建待办。长期能力事实见 [docs/DATA_SOURCE_CAPABILITY_MATRIX.md](docs/DATA_SOURCE_CAPABILITY_MATRIX.md)。

## 任务规范与状态机

- `task_id` 使用永不复用的 `R1-TNNN`；`priority` 仅可为 `P0/P1/P2`。
- 状态依次可为 `NEW → ANALYSIS → PLAN_CREATED → CODING → CODE_REVIEW → TESTING → VERIFYING → DONE`；外部条件无法由代码解除时转为 `BLOCKED`，依赖解除后回到 `ANALYSIS`。
- 每次失败增加 `failure_count`，记录原因与下一次调整；不以模拟数据、降级断言或写死响应消除失败。
- **Definition of Done**：实现与审查完成；适用 lint/typecheck/unit/integration/build 全部通过；公共 API/数据迁移已验证；实际功能路径已验证；修改文件、命令、结果和遗留问题已记录。代码写完不等于 DONE。

## R1 任务

### R1-T001 — R1 基线审计与计划收敛

- `priority`：P0；`执行对象/模块`：仓库、计划、docs；`state`：DONE；`failure_count`：0。
- `现状/问题`：历史计划、阶段分析和验收材料并存，未有 R1 单一进行中计划。
- `目标`：建立任务规范、当前工作台账和长期文档入口。
- `影响范围`：根目录计划与 docs 索引；`依赖关系`：无；`前置条件`：阅读 README、START_HERE、STATUS、Provider/市场代码和测试。
- `实施方案`：保留历史资料，创建本文与 docs 索引；不移动仍可能被引用的历史文件。
- `验收标准`：所有 R1 未完成项在本文有编号；历史资料只作引用；`测试要求`：链接与 Markdown 人工检查。
- `输出规范`：任务字段、状态和真实验证证据齐全；`风险与回滚方案`：删除新增索引/计划即可回到旧入口。
- `实际修改文件`：`Plan_R1.md`、`docs/README.md`；`验证结果`：基线审计完成；`遗留问题`：历史材料的物理归档需在引用图审计后单列处理。

### R1-T002 — 桌面端导航语义重构

- `priority`：P0；`执行对象/模块`：`desktop/web/src/App.vue`、路由与 E2E；`state`：DONE；`failure_count`：0。
- `现状/问题`：导航将用户功能称为“研究”、服务功能称为“管理”，不表达客户端/后端边界。
- `目标`：显示“客户端”和“后端”，更新 aria label，并在后端组纳入数据源入口。
- `影响范围`：桌面前端导航、路由可达性测试；`依赖关系`：R1-T003；`前置条件`：现有 Vue 路由存在。
- `实施方案`：更名导航数组/可访问标签并添加数据源路由；不改业务 API 路径。
- `验收标准`：新旧路由正常、界面无旧组名；`测试要求`：Vue typecheck/build、路由 E2E。
- `输出规范`：导航标签、aria-label 和路由同步；`风险与回滚方案`：仅前端文字与路由表，回滚对应文件即可。
- `实际修改文件`：`desktop/web/src/App.vue`、`desktop/web/src/router.ts`、`desktop/web/e2e/terminal.spec.ts`；`验证结果`：`npm run build` 通过；`遗留问题`：完整 Playwright 浏览器回归归入 R1-T009。

### R1-T003 — 真实数据源盘点与持久化路由配置

- `priority`：P0；`执行对象/模块`：FastAPI、Silver parquet、Vue 数据源页；`state`：DONE；`failure_count`：1。
- `现状/问题`：仅有 `/api/health` 覆盖统计，管理员不能审计具体来源或保存主/备路由。
- `目标`：以本地 Silver 真实条目按市场/资产/周期统计；注册已实现 Provider 的访问方式、端点、能力和认证状态；持久化三层来源优先级/自定义来源。
- `影响范围`：`/api/data-sources`、`/data-sources/`、本地 `data_source_preferences.json`；`依赖关系`：R1-T001；`前置条件`：DuckDB 与现有 Silver 格式可读。
- `实施方案`：扫描 `bar_json` 而非猜测数据集；Provider 元数据只列仓库已实现适配器；写 API 受现有 loopback-only middleware 保护。
- `验收标准`：盘点包含行数、标的、时间、来源、质量、字段完整度；未知/未配置付费源不显示为可用；配置重启后可读。
- `测试要求`：API 单测覆盖真实 fixture、配置持久化、远程写拒绝；前端 build/E2E 路由覆盖。
- `输出规范`：API 用 camelCase，NaN/Infinity 清理；`风险与回滚方案`：删除独立偏好 JSON 与新增路由即可，不修改 Silver。
- `实际修改文件`：`desktop/src/market_monitor/web_api/sources.py`、`desktop/src/market_monitor/web_app.py`、`desktop/web/src/views/DataSourcesView.vue`、API/前端测试；`验证结果`：首次测试把跨市场 STOCK 标的错误断言为同一类别，已修正，随后 `8 passed` 与 `npm run build` 通过；`遗留问题`：Provider 实时探测状态仍由 `probe` 命令/报告负责，页面不发起第三方请求。

#### R1-T003 follow-up evidence (2026-08-12)
- `actual modified files`: `desktop/src/market_monitor/web_api/sources.py`, `desktop/web/src/views/DataSourcesView.vue`, `desktop/tests/test_web_market_api.py`, `docs/DATA_SOURCE_CAPABILITY_MATRIX.md`.
- `verification result`: every registered provider now exposes default `priority` and `enabled` metadata. Credential-gated JQData and Tushare are explicitly disabled/unconfigured; this does not change their capability status to available. API regression (9 passed), Ruff, and Vue production build passed.
- `traceability follow-up`: local inventory categories now include `sourceDetails` joining the actual stored source id to the registered endpoint, periods, fields, and status; unregistered ids are explicitly marked `UNREGISTERED_SOURCE` with no fabricated endpoint. API regression (9 passed) passed.

### R1-T004 — 客户端行情分类折叠展示

- `priority`：P0；`执行对象/模块`：市场 API 与 Vue 行情页；`state`：DONE；`failure_count`：0。
- `现状/问题`：行情只以标的表平铺，不能首先理解市场/资产类型覆盖。
- `目标`：在保留筛选、K 线和自选行为的同时，按真实市场/资产类型/周期提供折叠概览。
- `影响范围`：`/api/market/groups` 与 `MarketView.vue`；`依赖关系`：R1-T003；`前置条件`：本地 Silver 可读。
- `实施方案`：复用数据源盘点的只读聚合，不复制或重新抓取行情数据。
- `验收标准`：每组显示覆盖标的、行数、来源、质量和更新时间；`测试要求`：API fixture 断言与前端 build/E2E。
- `输出规范`：空值显示“暂无数据”；`风险与回滚方案`：新增端点与独立 UI 区块，原列表不受影响。
- `实际修改文件`：`desktop/src/market_monitor/web_api/market.py`、`desktop/web/src/views/MarketView.vue`、`desktop/web/src/styles.css`、测试；`验证结果`：`8 passed`、`npm run build` 通过；`遗留问题`：覆盖程度仍受现有抓取任务限制，见 R1-T007。

### R1-T005 — 数据源能力矩阵与数据口径固化

- `priority`：P0；`执行对象/模块`：采集器、Provider、数据契约文档；`state`：DONE；`failure_count`：0。
- `现状/问题`：代码中已有多个 SDK/协议，但能力边界和实际存量分散。
- `目标`：明确已实现、当前存量、认证条件、周期与字段，固定 OHLC/NULL/派生周期口径。
- `影响范围`：长期数据源文档；`依赖关系`：R1-T001；`前置条件`：完成 collector/provider/static API 审计。
- `实施方案`：只记录可从代码和当前 Silver 验证的事实；把目标但未实现能力转交 R1-T006/R1-T007。
- `验收标准`：来源精确到函数/协议/URL；不以候选来源冒充已实现；`测试要求`：文档与 API 注册表交叉人工核对。
- `输出规范`：可维护的矩阵；`风险与回滚方案`：文档新增，无运行时风险。
- `实际修改文件`：`docs/DATA_SOURCE_CAPABILITY_MATRIX.md`；`验证结果`：与 `collector.py`、providers 和当前 `/api/market/overview` 核对；`遗留问题`：实时外网可达性不由静态审计替代。

### R1-T006 — Canonical timeframe 与聚合/存储审计

- `priority`：P1；`执行对象/模块`：`aggregation.py`、storage、contracts；`state`：DONE；`failure_count`：0。
- `现状/问题`：已有分时会话聚合和日转周/月，但 Silver 当前主要是 1d/30m，尚无统一派生查询策略。
- `目标`：在不重复存储可推导周期前提下，定义 canonical 周期、索引、增量和质量策略。
- `影响范围`：数据模型、API、Android 包；`依赖关系`：R1-T005；`前置条件`：确认上游真实可提供的基础周期。
- `实施方案`：先补覆盖测试/ADR，再实现派生读路径；保持现有 silver partition 兼容。
- `验收标准`：午休、夜盘、交易日历、周/月边界、NULL 语义均有测试；`测试要求`：聚合单测、增量/重复写入回归。
- `输出规范`：ADR + 迁移计划；`风险与回滚方案`：不做全库重写，使用可回滚的新读路径。
- `实际修改文件`：`docs/adr/0009-canonical-timeframe-and-derived-bars.md`；`验证结果`：审计确认 Silver 按市场/资产/周期/年份分区，以 `(instrument_id, period, bar_open_time)` 去重；`aggregation.py` 和 `test_aggregation.py` 覆盖午休、夜盘和日转周/月；全量 pytest 已通过；`遗留问题`：需新增实际分钟覆盖后才能验证全链路。

#### R1-T006 follow-up evidence (2026-08-12)
- `actual modified files`: `desktop/src/market_monitor/web_api/market.py`, `desktop/web/src/views/MarketView.vue`, `desktop/tests/test_web_market_api.py`, `docs/DATA_SOURCE_CAPABILITY_MATRIX.md`, `docs/adr/0009-canonical-timeframe-and-derived-bars.md`.
- `verification result`: the local bars API now exposes `availablePeriods`; it derives `1h/2h/4h` from locally stored minute bars using market session rules and `1w/1mo` from local daily bars without writing derived rows back to Silver. Targeted API/aggregation tests (16 passed), Ruff, and Vue production build passed.
- `remaining issue`: real cross-market minute coverage, holiday calendars, and futures night-session calendars remain dependent on actual upstream data and are tracked by R1-T007.
- `NULL semantics evidence`: if any input has unavailable/non-numeric volume, amount, high, or low, the corresponding derived metric stays `NULL`; it is never converted to zero. Aggregation/API regression (17 passed) and full desktop pytest passed (one pre-existing duplicate ZIP-entry warning).

### R1-T007 — 六类行情全覆盖与 Provider 扩展

- `priority`：P1；`执行对象/模块`：collector、Provider、catalog、contracts；`state`：BLOCKED；`failure_count`：8。
- `现状/问题`：全量 A/H 股和 ETF 日线任务已接入并完成主要覆盖；全量分钟、指数全集和少数上游返回异常的标的仍未完成。
- `目标`：在已授权、可审计来源下扩展六类目标覆盖与字段。
- `影响范围`：抓取、存储、API、Android 同步；`依赖关系`：R1-T005、R1-T006；`前置条件`：可用来源的授权、配额和完整标的清单。
- `实施方案`：先接入 Provider adapter/capability，再按基础周期增量采集；不使用来源不明爬虫或伪造零值。
- `验收标准`：每个市场/资产/周期有实际抓取、字段、质量和覆盖证据；`测试要求`：Provider、集成、聚合、数据质量和回归测试。
- `输出规范`：能力矩阵和失败细节同步；`风险与回滚方案`：按新 Provider/分区独立上线并可禁用。
- `实际修改文件`：`desktop/src/market_monitor/full_market.py`、`desktop/src/market_monitor/cli.py`、`desktop/tests/test_full_market.py`；`验证结果`：本机 Silver 实测为 9,937 标的/3,090,089 行，CN 7,118、HK 2,807、ETF 1,559；`/api/market/overview`、`/api/market/instruments`、`/api/market/groups` 均可读。`遗留问题`：1 只港股与 14 只 ETF 上游未返回可写入日线；全量分钟、575 个同花顺指数及实时持续更新仍需独立任务。

#### R1-T007 probe evidence (2026-08-12)
- `attempts / failure_count`: 7 public-source probe attempts. First combined runs exposed a pytdx ISO-evidence defect; it was fixed and unit-tested. pytdx rerun returned PARTIAL_FAILURE: instrument list, quotes, 600519 `1d/30m`, and 510300 `1d` passed; 000001 index `1d` failed because the upstream supplied an invalid calendar tuple. AKShare 30-second rerun passed health, A-share statistics, calendar, and 600519 `1d`, while Eastmoney market-fund-flow failed through the configured proxy. Baostock first exceeded 10 seconds and its 30-second rerun produced no report before the local runner limit.
- `artifacts`: `artifacts/r1-provider-probe-20260812-pytdx-fixed/`, `artifacts/r1-provider-probe-20260812-akshare/`, and `artifacts/r1-provider-probe-20260812-baostock/`.
- `adjustment`: do not promote static adapter support into verified coverage. Continue to require a stable provider, full instrument universe, and field/period evidence before removing BLOCKED.

#### R1-T007 full-market follow-up evidence (2026-08-13)
- `actual modified files`: `desktop/src/market_monitor/full_market.py`, `desktop/src/market_monitor/ths_market.py`, `desktop/src/market_monitor/cli.py`, `desktop/src/market_monitor/web_api/common.py`, `desktop/src/market_monitor/web_api/sources.py`, `desktop/src/market_monitor/web_api/market.py`, `desktop/tests/test_full_market.py`, `desktop/tests/test_web_market_api.py`.
- `verification result`: resumable A/H stock and domestic ETF daily-bar commands persist state below ignored `data_control/`. The completed local store contains 3,090,089 rows across 1,563 parquet partitions. The market API was changed from Python-level full JSON scans to DuckDB aggregation and latest-row indexing: cold index build measured 1.2 seconds, group aggregation 8.2 seconds, and a restarted local server returned overview/list/groups successfully.
- `same-day market snapshots`: `ths-market` stores A-share breadth and index-table snapshots with Chinese fields and Beijing time. The public THS endpoint only returned its first page; subsequent pages were rejected by the website's login/anti-bot controls, therefore the task remains partial.

### R1-T008 — docs 信息架构与历史归档

- `priority`：P2；`执行对象/模块`：docs；`state`：DONE；`failure_count`：0。
- `现状/问题`：阶段分析、队列、架构与验收文档混放。
- `目标`：建立分类入口且不误删被引用的资料。
- `影响范围`：docs 导航；`依赖关系`：R1-T001；`前置条件`：只读引用审计。
- `实施方案`：先添加索引，后续在全量反向引用确认后再执行物理移动。
- `验收标准`：长期规范、架构、契约、验收和历史入口清晰；`测试要求`：链接检查。
- `输出规范`：其他文档的未来工作仅引用 `R1-TNNN`；`风险与回滚方案`：索引新增，无丢失风险。
- `实际修改文件`：`docs/README.md`；`验证结果`：索引已建立；`遗留问题`：物理 archive/history 迁移待独立引用审计。

#### R1-T008 follow-up evidence (2026-08-12)
- `actual modified files`: `docs/README.md`; moved `docs/INDUSTRY_GRAPH_TASK_QUEUE.md` to `docs/history/industry/INDUSTRY_GRAPH_TASK_QUEUE.md`.
- `verification result`: reverse-reference audit found no active code, test, README, or documentation link to the historical queue. The file is preserved in an explicit history location; the docs index no longer treats task queues as active planning sources.

### R1-T009 — R1 全量回归与实际运行验证

- `priority`：P1；`执行对象/模块`：Python、Vue、Android；`state`：DONE；`failure_count`：2。
- `现状/问题`：本轮新增 API/界面已做定向测试，完整仓库回归尚未重跑。
- `目标`：运行可用 lint、Python、前端 build/E2E 和适用 Android 检查。
- `影响范围`：交付证据；`依赖关系`：R1-T002 至 R1-T005；`前置条件`：构建环境可用。
- `实施方案`：先运行定向与前端 build，再运行完整桌面测试；Android 仅在接口契约无变化时执行回归。
- `验收标准`：真实命令和结果记录；`测试要求`：pytest、npm build、Playwright、必要 Gradle；`输出规范`：失败如实记录。
- `风险与回滚方案`：无运行时写入；`实际修改文件`：无；`验证结果`：Ruff 通过；全量 pytest 通过（含 1 个既有 zip duplicate-name warning）；`npm run build` 通过（仅 Vite 既有大 bundle 提示）；Playwright 14/14 通过；JDK 21 下 Android `testDebugUnitTest`、`lintDebug`、`assembleDebug` 通过。首次 Ruff 报告未使用导入；首次 Android 命令误用系统 JDK 26.0.2（Gradle 失败），切换项目锁定 JBR 21 后通过；`遗留问题`：无。
