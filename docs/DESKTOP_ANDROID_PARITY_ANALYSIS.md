# MarketListener 电脑端 / Android 五大页面一致性分析

## 1. 背景与目标

MarketListener 仓库同时包含 Android App（`android/`）与电脑端本地研究终端
（`desktop/`）。本次目标是在不重写 Python 数据业务逻辑的前提下，让电脑端 Web
工作台覆盖 Android 的五个核心页面——行情、数据、策略、统计、产业链——同时保留
电脑端已有的首页操作台、F10 企业资料库与日志页。

分析结论：Android 与 Web 不是「同一份 UI 代码」，而是共享同一份本地数据与业务
语义。Web 端作为受控只读/loopback 写入口，复用 Android 已定义的账本 JSONL、
Strategy DSL、K 线分区与 F10 模型，避免出现第三套业务数据库。

## 2. 当前电脑端架构

- 后端：`desktop/src/market_monitor/`，FastAPI 宿主 `web_app.py`，标准库/本地
  DuckDB 读取 silver parquet、catalog.duckdb、industry atlas 与 JSON/JSONL 文件。
- 前端：`desktop/web/`，Vue 3 + TypeScript + Vite + Pinia + Vue Router +
  Element Plus + ECharts，构建产物输出到 `desktop/src/market_monitor/web_dist/`。
- 操作台：`operations.py` 的 `OperationManager` 只接受预定义 `OperationKind`，
  串行队列，写 API 由 loopback 中间件保护。
- 数据监查：`/api/data/{view}` 只读、分页、最大 500 行；不暴露任意 SQL。
- F10：`industry_graph/f10` 统一 `CompanySummary/CompanyDetail`，
  `MoneySnapshot(value, currency, asOf, source)` 与结构化 `RevenueSegment`。
- 产业链：`/industry/` 为唯一正式入口，`/industry-v2/` 307 重定向；旧
  `industry-map.html` 不再打包进 Android 同步包。
- 日志：`event_log.EventLog` 写入 `data_control/logs/events-YYYY-MM-DD.jsonl`。

## 3. 与 Android 五大页面的一致性映射

| Android 页面 | 电脑端路由 | 共享数据/语义 | Web 端新增受控 API |
| --- | --- | --- | --- |
| 行情 | `/market/` | silver parquet K 线、instrument/period/quality | `/api/market/*` |
| 数据 | `/data/` | gold_metrics、market_breadth、futures_dashboard、control_center | `/api/dashboard/*`、`/api/metrics/*` |
| 策略 | `/strategy/` | Strategy DSL v1、`scan_strategy`、`write_run_record` | `/api/strategy/*` |
| 统计 | `/stats/` | Android 兼容 ledger JSONL（trade/cash/strategy） | `/api/stats/*` |
| 产业链 | `/industry/` | `industry-atlas.html`、`chain_index.json`、`industry_graph` | 既有 `/api/industry/atlas` |
| 自选 | 行情页内 | `data_control/personal/watchlist.json`（不写 catalog） | `/api/personal/watchlist` |

## 4. 关键数据路径

- K 线：`data_control/silver/**/*.parquet`，行含 `instrument_id/period/bar_open_time/bar_json`。
- Gold 指标：`data_control/catalog.duckdb` 的 `gold_metrics` 表。
- F10：`data_control/industry/f10/`（cn/hk JSONL + meta.json）。
- 产业链：`data_control/industry/industry-atlas.html`、`industry-atlas.json`。
- 账本：`data_control/personal/ledger.jsonl`（Android 导入兼容）。
- 策略：`data_control/strategies/definitions/*.json` 与 `runs/{run_id}.json`。
- Android 包：`data_control/packages/`，由 `package_builder.py` 生成并登记 ledger。

## 5. UI 设计原则（来自 Android UI 重构目标）

- 统一 Design Token：深/浅主题、Accent #2962FF、上涨红/下跌绿/平盘灰。
- 图表优先：K 线 ECharts candlestick、多序列折线、热力图、动态排名、迷你走势。
- 弱卡片化、高信息密度、快速扫读；缺失/陈旧数据明确显示「暂无数据」。
- 主题支持跟随系统/浅色/深色，localStorage 持久化，所有页面与图表同步切换。
- 禁止 CDN/远程字体；ECharts 使用本地 npm 依赖。

## 6. 安全与一致性约束

- mutation 仅 `127.0.0.1/::1`；POST body 全部 `extra="forbid"`；
  operation 只能是预定义 enum；无任意 SQL/shell。
- 数据页只读；服务端分页/筛选/降采样/超时；preview ≤ 500 行，图表点限 ≤ 1000。
- 公司数据只有一份：`CompanySummary/CompanyDetail`；Hover/Drawer/F10 共用。
- 不创建第三套产业链数据库；不删除研报、industry_graph、Evidence、F10。

## 7. 测试与验收

- `desktop\.venv\Scripts\python -m pytest desktop\tests`
- `desktop/web`：`npm ci && npm run build && npm run test:e2e`
- `powershell -ExecutionPolicy Bypass -File scripts\verify.ps1`
- E2E 必须覆盖五个新路由、主题、K 线、Watchlist、策略、统计、产业链 Hover 回归。
