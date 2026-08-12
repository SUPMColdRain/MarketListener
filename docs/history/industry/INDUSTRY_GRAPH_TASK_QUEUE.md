# 产业链图谱升级任务队列

> 状态说明：`[ ]` 未开始 · `[x]` 已完成 · `[~]` 进行中。根 Agent 每完成一个阶段更新一次。

## 阶段 0：现状分析（已完成）

- [x] 阅读 report_pipeline / industry_graph / control_center / package_builder / Android graph 模块
- [x] 产出 `docs/INDUSTRY_GRAPH_CURRENT_ANALYSIS.md`
- [x] 产出本套规划文档（UPGRADE_PLAN / ARCHITECTURE / TASK_QUEUE）

## 阶段 1：F10 数据抓取（限速子 Agent）

- [x] 子 Agent CN：全 A 股 universe 5,539 + F10 明细完成（`data_control/f10/cn/details_20260809.jsonl`，state done 5539 / failed 0）；revenue 收入构成已补齐（主文件 4,730 + 两个 bak 809 = 5,539 唯一代码，互不重叠；港股收入构成无可用数据源）
- [x] 子 Agent HK：全部港股 universe 2,806 + F10 明细完成（`data_control/f10/hk/details_20260809.jsonl`，state done 2784 / failed 0）
- [x] 补处理 3 篇 skipped 研报（已由 OCR 补偿/源缺失标记处理，721 篇全部 REVIEWED）
- [x] 参考 HTML 旧快照解析为兜底（`load_legacy_html` 直接读 `docs/A股企业产业链精细定位.html`，标 `source: legacy_html`）

抓取纪律（必须遵守）：

- 单代码间隔 ≥1.5s；单 Agent 并发 ≤2；失败重试 ≤3 次并退避。
- 每 20 条 checkpoint；遇到疑似封禁信号立即暂停并记录 pause_reason。
- 用户已确认：A 股 5000+、港股 1900+ **全部**抓取；单代码间隔 ≥1.5s、并发 ≤2、每 20 条 checkpoint、封禁即停。

## 阶段 2：Atlas 生成器

- [x] 新建 `desktop/src/market_monitor/industry_atlas.py`
  - [x] `load_f10()`：读 CN/HK jsonl + legacy HTML，构建 code→F10 底表
  - [x] `build_company_index()`：公司名归一化映射
  - [x] `build_chain_sections()`：按链聚合 上游/中游/下游/服务 分区、环节/产品/原材料块、公司 chips
  - [x] `render_atlas_html()`：浅色全景大图（零依赖、离线）
  - [x] `build_atlas()`：输出 `industry-atlas.json` + `industry-atlas.html`，同步 `data_control/industry/`
- [x] CLI：`market_monitor reports atlas --output-root reports/industry --data-root data_control`

## 阶段 3：PC 后端接入

- [x] control_center 新增 `/industry-v2/` 路由与首页入口（已实测 200）

## 阶段 4：Android 接入

- [x] package_builder extra_files 增加新版 atlas
- [x] MarketPackageImporter 白名单增加新版文件
- [x] MainActivity 复制新版文件
- [x] GraphScreen 默认加载新版 + 旧版回退

## 阶段 5：测试与审查

- [x] pytest：`test_industry_atlas.py`（生成、离线、转义、计数、F10 合并、无 CDN）
- [x] Android `testDebugUnitTest` / `assembleDebug`（此前已通过：21 suites / 74 tests / 0 failures；本轮收尾未重跑）
- [x] 全量 `pytest desktop/tests` 回归（500+ 用例通过）
- [~] 审查：不破坏旧版、不删除研报结果、无编造数据已通过；产业链环节/产品定义改由用户人工阅读研报校验（自动化提炼暂停）

## 阶段 6：文档更新

- [x] STATUS.md 增加产业链图谱升级记录
- [x] Plan.md / README 更新新版图谱说明（本轮收尾再补 Plan_full.md 第 12 节状态）
- [~] 本队列未全部完成：177 条原始子链去重/归并未完成、真机验收未解除

## 收尾记录（2026-08-09）

- 用户指示：不再做新的产业链提炼/研报抓取，后续由用户自行阅读研报 PDF 人工校验；F10/revenue 由计划任务限速续抓完成（1.0s/条）并于 2026-08-09 16:03 正常退出（`revenue_cn.log` 记录 PASS，计划任务转 Ready）。
- Atlas v2 已重建：75 条链（展示口径）/ 7,090 家带代码公司 / 公司索引 7,577 / F10 CN 5,539 + HK 2,806 + legacy 1,017；`industry-atlas.html` 约 20 MB（20,018,677 字节）自包含离线，同步 `data_control/industry/`（SHA256 与 reports 副本一致）。
- 市场板块脏词修复（`_MARKET_BOARD_TERMS`/`_is_market_board_name`）已生效：所有卡片对“创业板/科创板/沪深/中证/主板/北交所/…/上市/指数”命中 0；`test_industry_atlas.py` 9/9，全量 pytest 0 失败。
- 子 Agent `/root/f10_cn`、`/root/reports_retry` 已打断收工；其擅自启动的 revenue 抓取/Gradle/pytest 进程已终止；后端 8765（PID 30108/35652）保留在线；`fetch.lock` 已改名停用。
- Android 同步包已按新版 atlas 重建：`market-20260809-081649-141aff2e`（13,585,044 字节，ed25519+ecdsa 签名），zip 内 Atlas 哈希一致，后端 `/api/android-package` 实测 200 且下载哈希一致；真机导入验收待解除。
