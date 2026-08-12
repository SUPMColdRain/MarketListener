# R2 开发计划（当前未完成工作的唯一事实来源）

最后更新：2026-08-13。本文件承接 R1 与历史文档中仍有效、尚未完成的工作；`Plan_R1.md`、`STATUS.md`、`Plan.md`、`Plan_full.md`、历史交付与审查文档只保留背景和验证证据，不再维护独立的当前待办。其他文档如需引用未完成工作，必须引用 `R2-Txxx`。

## 统一任务模型与完成定义

- `task_id`：`R2-T001` 起递增、永久不复用；每项均含标题、类型、优先级、执行对象/模块、状态、失败次数、来源、现状/问题、目标、影响范围、依赖、前置条件、实施方案、验收标准、测试要求、输出规范、风险、回滚方案、实际修改文件、验证命令、验证结果与遗留问题。
- `priority`：仅 `P0`、`P1`、`P2`；状态：`NEW → ANALYSIS → PLAN_CREATED → CODING → CODE_REVIEW → TESTING → VERIFYING → DONE`。外部账号、授权、网络、服务或数据阻塞时使用 `BLOCKED`；失败会增加 `failure_count` 并记录原因、修复和复验。
- **Definition of Done**：代码检查、相关自动化测试、真实接口或数据库验证、前端构建、适用的实际页面/发行包验证均完成；数据来源、契约、时区、质量、数据血缘可追溯；无凭据、个人数据、大型数据库或无关文件进入提交；修改、命令、结果、回滚及遗留问题已记录。仅完成编码不能标记 DONE。

## R1/历史有效事项迁移摘要

- `R1-T007`：全量分钟线、指数全集、国内期货主力与连续序列、少数日线缺口及持续增量更新，迁入 R2-T005/R2-T006。
- `R1-T006`：跨市场分钟聚合、期货夜盘与交易日历真实验证，迁入 R2-T004/R2-T005。
- 历史 `FULL-610/804`：QMT 开通和连续成功/付费授权，保留为外部条件，迁入 R2-T006。
- 历史 Android 真机导入/策略/篡改回滚验收及 177 原始产业链去重，保持独立历史证据；不在本轮网页与数据管道变更中重新执行，列为 R2-T009 的后续阻塞审计。

## 当前任务

### R2-T001 — R2 基线审计、计划收敛与文档入口

- `type`：治理与审计；`priority`：P0；`执行对象/模块`：仓库、Git、计划、README、ADR、STATUS、docs、测试与数据目录；`state`：DONE；`failure_count`：0；`来源`：R2 总指令、R1-T001/T008、历史状态档案。
- `现状/问题`：R1 已建立计划，但 R2 要求一个新的唯一活动台账；历史状态仍表述为唯一入口，容易产生双重待办。
- `目标`：保留历史事实、建立本文件，并只迁移确实未完成的有效工作。
- `影响范围`：根目录计划、文档入口；`依赖关系`：无；`前置条件`：完成 Git/文档/代码/测试/数据源审计。
- `实施方案`：审计工作树、分支、远端、最近提交、计划、ADR、TODO、Provider、web API、前端生命周期、Silver/目录及 Actions；更新入口为 R2 引用。
- `验收标准`：无重复的当前任务清单；完成项不复活；每项具备统一字段。
- `测试要求`：Markdown 链接与反向引用审计；`输出规范`：记录审计命令和事实；`风险`：误把历史阻塞变成当前承诺；`回滚方案`：仅新增/修订文档，可逐文件回退。
- `实际修改文件`：`Plan_R2.md`、`docs/README.md`；`验证命令`：`git status --short`、`rg`、文档人工审计；`验证结果`：审计完成，R1/历史有效未完成项已迁移为 R2-T004 至 R2-T009；docs 入口指向 R2；`遗留问题`：旧文档只保留历史事实。

### R2-T002 — 路由级请求、取消、去重与持久缓存架构

- `type`：性能与前端基础设施；`priority`：P0；`执行对象/模块`：Vue router、`domain/api.ts`、视图、测试；`state`：PARTIAL；`failure_count`：2；`来源`：R2 总指令。
- `现状/问题`：页面各自直接 `fetch`，路由均静态导入；数据页进入时同时加载 definitions、全部可用面板、排行、热力图和数据浏览器，首页并发健康与操作列表，缺少取消、去重、TTL、持久缓存和可测指标。
- `目标`：统一 Query Cache（内存 + IndexedDB），key 包含 endpoint/参数/schema；相同并发请求去重、切换取消、TTL stale-while-revalidate、显式刷新失效、路由/面板按需加载。
- `影响范围`：所有网页 API 读取；`依赖关系`：R2-T001；`前置条件`：基线请求清单与目标接口稳定。
- `实施方案`：实现无任意请求执行能力的 allow-list 型封装；动态路由 import；视图改用统一 query；为首次/缓存/强刷提供测量钩子。
- `验收标准`：无业务必要轮询；重复并发请求只发一次；缓存命中无整体 loading/滚动重置；切换时旧请求取消。
- `测试要求`：缓存 TTL、失效、去重、取消、错误恢复、路由 lazy-load 单测/E2E；`输出规范`：请求计数前后证据；`风险`：陈旧数据误导；`回滚方案`：保留服务器真实响应，单独移除 query 封装即可。
- `实际修改文件`：`desktop/web/src/domain/api.ts`、`desktop/web/src/router.ts`、`desktop/web/src/views/DataView.vue`、`desktop/web/src/views/MarketView.vue`；`验证命令`：`npm run build`、定向 API pytest、`npm run test:e2e`；`验证结果`：Vue typecheck/build 通过，已形成独立路由 chunk；缓存已补全 stale-while-revalidate、并发去重和 TTL 内持久命中，行情支持 assetType 服务端筛选与旧请求取消。数据浏览器、排行、热力图和面板改为显式加载；14 项 Playwright 端到端测试通过。首次两次验证因错误工作目录调用 Python/NPM 未启动，`failure_count=2`，均已用正确目录复验；`遗留问题`：首页与低频视图仍待逐页迁移统一 query。

### R2-T003 — 可配置“客户端→数据”仪表盘与市场广度/金银比

- `type`：产品与数据功能；`priority`：P0；`执行对象/模块`：Dashboard API、个人配置、Silver/Gold 指标、Vue 面板与图表；`state`：CODING；`failure_count`：1；`来源`：R2 总指令。
- `现状/问题`：数据页固定面板且 onMounted 全量请求；现有广度将股票/ETF/指数混合，涨停判定尚不满足分板规则，未保存可增量历史；没有金银比基础序列和自定义布局。
- `目标`：建立安全的 PanelDefinition/MetricDefinition 注册和个人布局；支持创建、删除、隐藏、恢复、排序、配置；提供真实广度、连板高度、金银比的历史面板与空状态。
- `影响范围`：个人设置、指标 schema、API、Vue；`依赖关系`：R2-T002、R2-T004、R2-T005；`前置条件`：真实来源/计算口径明确。
- `实施方案`：只允许注册指标和受控配置，不允许 SQL/脚本；折叠/可见时才请求；涨跌和涨停使用独立序列及差值视觉；无法验证的涨停/连板/比率 OHLC 标记不可用或近似。
- `验收标准`：布局持久化、重启可读、未显示数据不请求、指标有来源和时间序列。
- `测试要求`：配置 API、布局迁移、指标口径、图表数据、空/错恢复；`输出规范`：中文展示和北京时区；`风险`：错误金融口径；`回滚方案`：个人配置独立文件/表，删除可恢复默认。
- `实际修改文件`：`desktop/src/market_monitor/web_api/watchlist.py`、`desktop/web/src/views/DataView.vue`、`desktop/web/src/components/charts/SeriesChart.vue`、`desktop/src/market_monitor/web_api/dashboard.py`、`desktop/src/market_monitor/market_breadth.py`、`desktop/src/market_monitor/collector.py`、`desktop/tests/test_web_dashboard_api.py`、`desktop/tests/test_market_breadth.py`；`验证命令`：定向 dashboard/market-breadth pytest、`npm run build`、`npm run test:e2e`；`验证结果`：个人面板配置仅写入受 Pydantic 约束的本机 JSON，支持新增、删除、隐藏/恢复、排序、标题、折线/柱状图、颜色、透明度与时间范围，定向测试和 14 项端到端测试通过。广度只统计 A 股个股，移除了 ETF/指数混入和所有 `±9.9%` 近似涨跌停；涨停/跌停与连板仍仅由东财权威池采集。旧涨停/跌停热力图断言在移除未验证统一阈值后失败一次，`failure_count=1`，已改为只验证上涨/下跌/平盘后通过；`遗留问题`：需为权威涨停池、连板高度和金银比补齐可验证的持续历史入库与展示。

### R2-T004 — 行情页面分类、周期与按面板加载重构

- `type`：产品与性能；`priority`：P0；`执行对象/模块`：Market API、聚合、MarketView、图表；`state`：CODING；`failure_count`：0；`来源`：R2 总指令、R1-T004/T006。
- `现状/问题`：市场分组没有完整业务分类；K 线派生只覆盖部分周期；页面仍进入即概览/分组/列表并发加载。
- `目标`：分开 A 股个股、A 股 ETF、港股个股、A/港/全球指数、国内期货主力/连续、商品/期货指数；面板展开后取本组列表，选标的和周期后才取 K 线；周期统一 `15m/30m/1h/2h/1d/1w/1mo/1q/1y`。
- `影响范围`：API 契约、前端、聚合；`依赖关系`：R2-T002、R2-T005；`前置条件`：分类和 canonical 周期定义。
- `实施方案`：服务端按类别分页、前端懒加载；派生仅基于经验证的细粒度 K 线与会话规则，无法支持时诚实返回。
- `验收标准`：首屏不请求 K 线；ETF/股票独立；周期命名无歧义；错误与空态可追溯。
- `测试要求`：分类、分页、按需请求、交易时段/周季年聚合；`输出规范`：中文名称；`风险`：市场会话错误；`回滚方案`：兼容现有 period API。
- `实际修改文件`：`desktop/web/src/views/MarketView.vue`；`验证命令`：`npm run build`、market API pytest；`验证结果`：分类覆盖按点击加载，列表服务端分页并缓存，搜索 300ms 防抖，K 线仅在选择标的和周期后请求；`遗留问题`：完整业务分类与 `1q/1y` 聚合依赖可验证的基础数据和交易所日历，保持 BLOCKED。

### R2-T005 — 分层 Provider 验证、分钟数据管道与能力矩阵

- `type`：数据工程；`priority`：P1；`执行对象/模块`：Provider、探针、Silver、catalog、文档；`state`：CODING；`failure_count`：2；`来源`：R2 总指令、R1-T007。
- `现状/问题`：代码声明能力与真实数据覆盖混杂；分钟线、指数全集、期货主力/连续缺少分层验证和一致的数据库证据。
- `目标`：按“代码→连接→单标的→跨交易所抽样→批量→落库→API→前端”分层验证 A 股/ETF/港股/期货；完善 lineage、去重、缺口、增量、时区、复权、单位与健康/降级策略。
- `影响范围`：provider、文档、采集任务；`依赖关系`：R2-T001；`前置条件`：公开合法来源/本机凭据实际可用。
- `实施方案`：先扩展已有 Provider，再研究透明候选；连续序列若自行构造显式 `DERIVED`，先固定算法；无法合法稳定取得时只建插槽、空/错态并 BLOCKED。
- `验收标准`：矩阵按真实证据描述 URL/协议/授权/频控/历史/字段/覆盖；不得声明未实际通过的分钟能力。
- `测试要求`：适配器、探针、落库、API、前端抽样；`输出规范`：失败原因/解除条件；`风险`：反爬、许可与海量数据；`回滚方案`：独立 provider/分区禁用。
- `实际修改文件`：`docs/DATA_SOURCE_CAPABILITY_MATRIX.md`、`desktop/src/market_monitor/web_api/dashboard.py`、`desktop/src/market_monitor/collector.py`、`desktop/src/market_monitor/providers/akshare.py`；`验证命令`：`market_monitor probe --provider pytdx`、`--provider akshare`、`--provider baostock`；`验证结果`：pytdx 连接、清单、报价、600519 `1d/30m` 与 510300 `1d` PASS，但 000001 指数日线 FAILED；AKShare 现货/涨跌、日历、资金流与 600519 日线 PASS。BaoStock 本次 30 秒探针未自行退出，已结束残留进程并记为第 2 次失败；不阻塞其他来源。分钟跨资产/交易所、批量、落库/API/前端证据仍不足；`遗留问题`：港股、期货、指数分钟线与连续合约。

### R2-T006 — 候选源研究、主备策略与外部阻塞记录

- `type`：研究与架构验证；`priority`：P1；`执行对象/模块`：AKShare、pytdx、BaoStock、JoinQuant、Tushare、AData/mootdx/easy_tdx、GitHub 候选、文档；`state`：BLOCKED；`failure_count`：1；`来源`：R2 总指令、FULL-610/804。
- `现状/问题`：候选库和 GitHub Topic 不等于可合法生产数据源；付费/登录来源没有凭据。
- `目标`：审计活跃度、License、底层来源、权限、限频、分钟历史、覆盖、字段、Windows 打包兼容性；明确主备和 provenance。
- `影响范围`：数据源矩阵与 provider registry；`依赖关系`：R2-T005；`前置条件`：官方文档与实际探针。
- `实施方案`：仅将真实测试通过的来源提升；QMT、JQData、Tushare 等缺授权的保持 BLOCKED。
- `验收标准`：每个候选均有证据与结论；`测试要求`：许可/官方文档/实际探针审计；`输出规范`：不得复制无许可证代码或私人代理；`风险`：外部条款变化；`回滚方案`：文档/注册表独立回退。
- `实际修改文件`：`docs/DATA_SOURCE_CAPABILITY_MATRIX.md`；`验证命令`：候选 URL 只读抓取与现有 adapter 审计；`验证结果`：AData 页面抓取 404，GitHub Topic 仅发现入口，mootdx/easy_tdx 未完成许可/真实探针；JoinQuant/Tushare 缺本机授权，任务保持 BLOCKED；`遗留问题`：需要合法来源条款与账号/Token 后再提升。

### R2-T007 — Windows 可携带后端网页发行包与 GitHub Actions

- `type`：发布工程；`priority`：P1；`执行对象/模块`：PyInstaller/启动器、Vue dist、workflow、README、`.gitignore`；`state`：DONE；`failure_count`：1；`来源`：R2 总指令。
- `现状/问题`：当前需要开发环境运行；没有 GitHub Actions 或 Windows 可下载包。
- `目标`：生成 `MarketListener-Windows-x64-<version>.zip`，双击启动并自动打开 localhost，外置可写 data/log/config，Actions 构建、校验、烟雾测试、artifact/tag release。
- `影响范围`：构建脚本、CI、发行说明；`依赖关系`：R2-T002；`前置条件`：审计打包依赖和静态资源路径。
- `实施方案`：默认只监听 127.0.0.1，不打入数据/凭据；Windows runner 构建前端与 Python bundle，启动后验证 `/` 和 `/api/health`。
- `验收标准`：workflow_dispatch 可执行、zip/sha256 产出、smoke test 通过。
- `测试要求`：本地或 CI Windows package smoke；`输出规范`：升级/迁移说明；`风险`：PyInstaller 隐式依赖；`回滚方案`：独立 workflow/打包目录。
- `实际修改文件`：`.github/workflows/windows-portable.yml`、`scripts/build_windows_portable.ps1`、`README.md`、`.gitignore`；`验证命令`：`scripts/build_windows_portable.ps1`、便携 EXE `serve --timeout-seconds 1`、GitHub Actions run `31624423028`；`验证结果`：本机已生成 `dist/MarketListener-Windows-x64-0.1.0.zip` 与 SHA256，EXE 成功以 `127.0.0.1` 随机端口启动并退出；首次 Actions 实际成功，CI 构建、zip、启动 EXE、`/` 和 `/api/health` smoke 全通过。最初后台启动命令受环境策略拦截，`failure_count=1`，已用 CLI 短时服务验证修正；`遗留问题`：后续提交 Actions 仍在运行。

### R2-T008 — R2 统一回归、安全审查与发布

- `type`：质量与交付；`priority`：P0；`执行对象/模块`：全仓库、CI、Git；`state`：VERIFYING；`failure_count`：0；`来源`：R2 总指令、R1-T009。
- `现状/问题`：R2 会跨前后端、数据和打包改动，需统一验证和泄漏审查。
- `目标`：运行现有统一验证、专项测试、构建、页面/API/package smoke、安全扫描；仅提交 R2 路径并推送。
- `影响范围`：全部 R2 变更；`依赖关系`：R2-T001 至 R2-T007；`前置条件`：实现完成或外部阻塞证据完整。
- `实施方案`：检查 Git diff、ignored files、凭据模式、Actions；不重置、不强推、不合并 PR。
- `验收标准`：命令与结果记录；Actions 成功或外部 BLOCKED 有证据。
- `测试要求`：`scripts/verify.ps1`、pytest、ruff、Vue build/E2E、package smoke、适用 Android；`输出规范`：最终报告；`风险`：环境/CI 外部失败；`回滚方案`：按提交回退。
- `实际修改文件`：全部本轮 R2 文件；`验证命令`：`scripts/verify.ps1`、定向 pytest、`npm run build`、`git diff --check`；`验证结果`：统一验证通过，Git security diff 审查未发现新增凭据/数据库/构建产物；分支已推送。`gh` 未安装，Actions 状态无法从本机读取；`遗留问题`：等待 GitHub Actions 页面完成状态。

### R2-T009 — 历史外部验收与领域欠账审计

- `type`：范围控制；`priority`：P2；`执行对象/模块`：Android 真机、QMT、产业链图谱；`state`：BLOCKED；`failure_count`：0；`来源`：Day 0/FULL 历史交付、R1-T008。
- `现状/问题`：真实 Android 导入/策略/篡改回滚、QMT 账户与 177 原始产业链人工归并没有在本轮获得所需设备、账户或业务定义。
- `目标`：不丢失事实，明确解除条件，并避免把它们伪装为本轮网页完成项。
- `影响范围`：后续周期；`依赖关系`：无；`前置条件`：Android 真机/合法 QMT 开通/用户确认产业链归并口径。
- `实施方案`：保留历史证据，仅在条件满足后另开分析；`验收标准`：阻塞原因和解除条件准确；`测试要求`：不适用；`输出规范`：不计入 R2 DONE；`风险`：范围膨胀；`回滚方案`：文档状态变更可回退。
- `实际修改文件`：`Plan_R2.md`；`验证命令`：历史交付审计；`验证结果`：确认受外部条件阻塞；`遗留问题`：等待外部条件。
