# 数据源能力矩阵

审计日期：2026-08-13。这里的“已实现”仅指仓库存在 adapter/collector 代码；“当前存量”仅指 `data_control/silver` 已落库数据。两者都不等同于持续可用、实时更新或无缺口的全市场覆盖。

## 统一口径

- 内部 OHLC 使用标准字段 `open/high/low/close`；界面可以显示为 `Start/High/Low/End`，不得反向改变存储字段。
- `volume`、`amount`、`open_interest`、`pct_change`、`amplitude` 缺失时为 `NULL`/能力不可用，绝不写为零。沉淀资金尚无可靠统一口径，当前不支持。
- 原始基础周期优先存 Silver；`aggregation.py` 已按 CN/HK 股票与 CN 期货交易时段聚合 1/5/15/30/60/120/240 分钟，日线可聚合为 `1w`/`1mo`。它尚未连接到通用派生查询/存储流程（R1-T006）。

## 当前本地存量（真实 Silver）

2026-08-13 本机实测 `/api/market/overview` 返回 9,937 个标的、3,090,089 行，基础周期为 `1d` 和 `30m`。其中 CN 7,118、HK 2,807、GLOBAL 12；资产类型为 STOCK 8,343、ETF 1,559、INDEX 14、FUTURE 19、CRYPTO 2。计数会随增量采集变化，具体类别、字段完整度、来源和最后更新时间由 `/api/data-sources` 在运行时读取 parquet 后给出。

| 数据类别 | 当前来源 | 实现/存量 | 当前周期 | 覆盖事实与限制 |
| --- | --- | --- | --- | --- |
| A 股个股 | AKShare、pytdx | 已实现；全量日线回填已完成 | 1d；样本另有 30m | 7,118 个本地 CN 标的（含个股、ETF、指数等）；回填对股票使用 AKShare 历史接口，pytdx 作为可用能力来源。 |
| 港股个股 | AKShare | 已实现；日线回填基本完成 | 1d | 2,807 个本地 HK 标的；1 个标的因上游返回不含日期字段未写入，需后续重试或更换来源。 |
| 境内 ETF | AKShare、pytdx | 已实现；日线回填部分完成 | 1d | 1,559 个 ETF 已写入；14 个 `530xxx` 标的从 pytdx 未返回日线，不能伪造为完成。 |
| A/H 股指数 | AKShare、pytdx、同花顺 | 已实现；当前为部分存量 | 1d | 同花顺指数快照采集已接入；公开访问仅取得首批页面，后续页受登录/反爬限制，不能宣称 575 个指数已完整入库。 |
| 全球指数 | AKShare | 已实现；当前为少量存量 | 1d | `index_global_hist_em` 等适配调用；无全市场承诺。 |
| 国内期货主力、商品指数 | AKShare | 已实现；当前为 15 个主力及指数存量 | 1d | `futures_main_sina`、`futures_index_ccidx`；无加权连续合约与全品种 30m。 |
| 国际重点期货 | AKShare | 已实现；当前为 4 个品种存量 | 1d | `futures_foreign_hist`；成交额可为空。 |
| 加密货币 | Binance 公共接口 | 已实现；BTC/ETH 存量 | 1d | `https://data-api.binance.vision/api/v3/klines`；不属于六类股票/期货目标。 |
| 美元指数、VIX | 东方财富 / CBOE，腾讯回退 | 已实现；Gold 指标 | 1d | 东财 kline API、CBOE VIX CSV；当前为指标而不是统一 bars。 |

## Provider / Adapter 事实

Provider registration exposed by `/api/data-sources` includes an explicit default `priority` and `enabled` flag. A disabled or unconfigured provider remains visible for traceability but is not evidence that it is usable for collection.

Each local inventory category also exposes `sourceDetails`: its stored source id is joined to the registered endpoint, declared periods, fields, and status. A source id not present in the registry is returned as `UNREGISTERED_SOURCE` with no invented endpoint.

| Provider | 获取方式与实际入口 | 已实现能力 | 认证/授权 | 当前验证状态与限制 |
| --- | --- | --- | --- | --- |
| pytdx（通达信） | TDX TCP/7709，`TdxHq_API.get_security_bars`，服务地址可由 `TDX_SERVERS` 配置 | CN 股票/ETF/指数清单、报价、1m/5m/15m/30m/1h/1d/1w/1mo | 无账户；公网服务稳定性非保证 | 2026-08-12 实测：证券清单、报价、600519 `1d/30m`、510300 `1d` PASS；000001 指数 `1d` 因上游非法日期失败。证据：`artifacts/r1-provider-probe-20260812-pytdx-fixed/`。 |
| AKShare | Python SDK；collector 使用 `stock_hk_hist`、`futures_main_sina`、`futures_index_ccidx`、`futures_foreign_hist` 等 | HK/全球/期货日线、CN 指标与多种公共数据 | 当前调用无 token；上游可变 | 2026-08-12 在 30 秒限制内：健康检查、A 股涨跌/涨停统计、交易日历、600519 日线 PASS；市场资金流因东方财富 endpoint 经代理连接被拒绝 FAILED。证据：`artifacts/r1-provider-probe-20260812-akshare-30s/`。 |
| Baostock | `baostock.login`、`query_history_k_data_plus` | CN 股票 1d/30m | SDK 登录 | 2026-08-12 首次 10 秒超时；30 秒复测未在本任务运行时限内产出报告。当前没有可验证 PASS 结论，不能提升为可用来源。 |
| JQData | `jqdatasdk.auth` 和价格接口 | CN 股票/ETF/指数/期货（以探测能力为准） | 用户名/密码、授权 | `BLOCKED_CONFIGURATION`，不能显示为当前可用。 |
| Tushare Pro | `TUSHARE_TOKEN`、`pro_api`、`daily`/`stk_mins`/`stock_basic` | CN 股票日线/分钟、清单与财务（以积分权限为准） | token 与接口积分/权限 | `BLOCKED_CONFIGURATION`，不能显示为当前可用。 |
| Binance | HTTPS JSON：`https://data-api.binance.vision/api/v3/klines` | BTC/ETH 日线 | 公共端点 | collector 已落库；网络可达性需每次会话实测。 |
| 东财/CBOE/腾讯 | 东财 `push2his.eastmoney.com/api/qt/stock/kline/get`；CBOE VIX CSV；腾讯回退 | DXY/VIX 日线指标 | 公共端点 | collector 已实现，TLS/网络可能导致部分失败。 |
| 同花顺行情中心 | `q.10jqka.com.cn` 市场页与指数页快照 | A 股涨跌家数、涨停/跌停家数、昨日涨停平均收益率、指数表格 | 网站会话/反爬策略 | 已实现 `ths-market` 可恢复快照任务；公开页可获取首批指数，翻页请求会返回登录/授权限制。使用已登录浏览器 Cookie 的自动化仍需在可用浏览器会话中另行验证。 |

## 未满足目标与准确原因

| 目标能力 | 状态 | 原因 / 解除条件 |
| --- | --- | --- |
| 全部 A 股、HK 股、ETF 的 30m/1h/2h/4h/1d/1w/1m | PARTIAL | A/H 个股和大部分 ETF 的日线已落库；API 可由已存 30m 或 1d 派生部分周期。仍缺全量分钟基础数据、14 个 ETF 上游缺口及 1 个港股缺口。 |
| 全部指数同周期与成交量 | BLOCKED | 当前仅部分指数日线/快照；同花顺 575 指数分页受登录限制，部分上游不提供成交量；需按字段能力保留 NULL。 |
| 国内期货主力+加权连续的全周期与沉淀资金 | BLOCKED | 当前仅主力日线/部分商品指数；未定义可验证的沉淀资金计算口径和连续合约来源。 |
| 国内外商品分类指数全覆盖 | BLOCKED | 当前只有 CCIDX/少量公开数据；同花顺、Wind、QMT、文华等未实现或需授权，不能伪装接入。 |
