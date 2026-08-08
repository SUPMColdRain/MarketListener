# FULL-110 交付记录

**任务**：FULL-110 修复 AKShare 适配器，快照、日历、资金等接口分别探测

**角色**：独立实现
**状态建议**：`REVIEW`（按用户指示，统一审查延后到 5.1–5.9 全部实现完成后执行）

## 结果

AKShare 适配器现在对每个数据接口独立探测，任一接口失败不再抹掉其他接口结果：

- **快照**（`stock_zh_a_spot_em` → `health_check`）：真实探针期间东方财富 `82.push2.eastmoney.com/api/qt/clist/get` 对所有重复请求返回 `RemoteDisconnected`，状态如实为 `FAILED/NETWORK`，未伪造成 PASS。
- **日历**（`tool_trade_date_hist_sina` → `trading_calendar`）：真实 PASS，8797 行，覆盖 1990-12-19 至 2026-12-31。
- **资金流**（`stock_market_fund_flow` → `market_fund_flow`）：直接探测在 2026-08-05T16:27 UTC 真实返回 120×15 行（起始 2026-02-04），但最终 CLI 探针窗口内东方财富开始丢弃连接，状态如实为 `FAILED/NETWORK`。

`probe_capabilities()` 不再在快照失败时整体抛错，而是返回逐能力记录；`FAILED` 能力现在同时携带结构化 `error`（类别与消息），与 v2 契约一致。

日线抓取（`fetch_bars`）同步修复：AKShare 中文列名归一为跨源英文名（`date/open/high/low/close/volume/amount`），并改为前复权 `adjust="qfq"`，与 BaoStock `adjustflag="3"` 对齐，为 FULL-113 的重叠样本对比和后续 FULL-120/121 打基础。

## 修改文件

- `desktop/src/market_monitor/providers/akshare.py`：快照/日历/资金独立探测；`trading_calendar` 能力；失败能力携带结构化错误；日线字段归一与前复权。
- `desktop/tests/test_akshare_provider.py`：新增快照失败不抹日历/资金、日历失败不抹快照/资金、资金失败不抹快照/日历、日线字段归一与 `qfq` 请求、日线网络错误分类共 5 项测试。
- `desktop/src/market_monitor/providers/baostock.py`：仅把失败能力补充结构化 `error`（与 FULL-113 共用改动）。
- `docs/deliveries/README.md` 与 `STATUS.md`：交付索引与状态更新。

未修改 Provider 契约 Schema、报告 Schema、数据库或 Android 业务行为。

## 实际验证

| 验证项 | 实际命令/方式 | 真实结果 |
|---|---|---|
| AKShare/BaoStock 专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_akshare_provider.py desktop\tests\test_baostock_provider.py -q` | PASS，13 项；覆盖独立探测、部分失败不抹其他、字段/周期/复权、网络超时分类、空结果 `NO_COVERAGE`。 |
| 桌面全量 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests -o addopts='' -q --tb=no` | PASS，366 项；仅既有 ZIP 同名 `manifest.json` 警告。 |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS。 |
| 真实探针 | `python -m market_monitor.cli probe --provider akshare --report-dir artifacts\full-110-akshare --timeout-seconds 120`（`NO_PROXY=*` 绕过系统代理） | 退出码 2（`PARTIAL_FAILURE`）；`health_check` FAILED/NETWORK、`trading_calendar` PASS 8797 行、`market_fund_flow` FAILED/NETWORK，证据见 `artifacts/full-110-akshare/provider-capabilities.json` 与 `direct-probe-evidence.md`。 |
| 直接接口复核 | 内联 Python 逐接口调用 `stock_zh_a_spot_em` / `tool_trade_date_hist_sina` / `stock_market_fund_flow` / `stock_zh_a_hist` | 日历 8797 行 PASS；资金 120×15 行 PASS（16:27 UTC）；快照与资金在 16:33–16:37 UTC 因东方财富断连为 FAILED；日线在 16:27 UTC 真实返回 5976 行（2001-08-27..2026-08-05）。 |
| 统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：Python 3.11.0、JDK 21、锁定依赖、Ruff、共享 Schema 夹具、366 项桌面测试与 Android `lintDebug`/`testDebugUnitTest`/`assembleDebug` 全部通过；仅有既有 ZIP 同名 `manifest.json` 警告。中间两次失败均为其他并行 Agent 未完成的未提交改动（契约夹具并发写入、`DslProgram.kt` 依赖缺失），已通知对应 Agent 修复后复跑通过。 |
| 变更完整性 | `git diff --check` | PASS：无空白错误。 |

## 数据源状态

| 接口 | 真实状态 | 行数/时间范围 | 失败原因 |
|---|---|---|---|
| A股快照（东财 `stock_zh_a_spot_em`） | FAILED/NETWORK（最终探针窗口） | 未取到 | `82.push2.eastmoney.com` 反复 `RemoteDisconnected`，疑似端点限流/封锁；更小参数直连曾成功，非适配器代码错误 |
| 交易日历（新浪 `tool_trade_date_hist_sina`） | PASS | 8797 行，1990-12-19..2026-12-31 | 无 |
| 市场资金流（东财 `stock_market_fund_flow`） | 直接探测 PASS（120×15），最终探针 FAILED/NETWORK | 2026-02-04 起 120 行 | 同上东财断连 |
| 日线（东财 `stock_zh_a_hist`） | 直接探测 PASS（未复权 5976 行）；归一/前复权后未在最终窗口重测 | 2001-08-27..2026-08-05 | 最终窗口东财断连 |

## 接口、迁移与安全

- **公开契约**：ProviderRunResult v2 报告结构未变；AKShare 新增 `trading_calendar` 能力记录（`calendar/CN/GENERAL`，与 BaoStock 同 ID，属来源无关能力）。
- **兼容性**：现有消费者按能力 ID 读取不受影响；日线记录字段由中文列名改为英文名属于适配器输出归一，交付记录明示。
- **安全与隐私**：无凭据、私钥、个人数据或大体积真实行情写入仓库；探针报告经运行器脱敏。

## 风险与未完成项

- **外部阻塞**：东方财富端点在本机当前窗口拒绝连接，快照真实 PASS 未能在最终探针达成；解除条件为端点恢复后由验收角色重跑 `probe --provider akshare`。
- 前复权日线归一后的真实重叠对比依赖 BaoStock 可达（FULL-113 一并记录）。
- 不伪造验收：直接探测成功记录与最终探针失败记录同时保留，供审查/验收核对时间线。

## 统一审查修复（2026-08-06）

按 `docs/reviews/unified-review-data.md` P2-1：`probe_capabilities` 增加 AKShare 日线能力 `cn_stock_sh.600519_1d`（BARS/CN/STOCK/1d，真实调用 `fetch_bars` 并独立 PASS/FAILED），使烘焙可按“真实通过的单项目能力”选中 AKShare 日线；新增失败不抹其他能力与请求映射测试。
