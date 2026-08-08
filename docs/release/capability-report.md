# 能力报告（FULL-900 封板准备，2026-08-06）

版本：0.1.0（desktop `pyproject.toml`/`__init__.py` 与 Android `versionName` 一致；versionCode=1）

## 桌面端能力

| 模块 | 能力 | 证据 |
|---|---|---|
| Provider 契约 v2 | Provider/Schema 迁移、能力登记、未知能力拒绝 | `docs/deliveries/FULL-100.md`；桌面 pytest 全量 |
| 配置与脱敏 | 本地配置加载、日志/报告脱敏、CLI 退出码 | `docs/deliveries/FULL-101.md` |
| 数据源适配 | AKShare/BaoStock/JQData/Tushare/期货/港股/同花顺探针 | `docs/deliveries/FULL-110~113/600~602.md`；`reports/provider-capabilities*.json` |
| 能力路由 | 按角色烘焙/回退、禁逐行混源 | `docs/deliveries/FULL-120.md` |
| 契约层 | 标的/K线/日历/复权/公司行动/来源追踪 Schema（23 个共享夹具） | `docs/deliveries/FULL-121.md` |
| 数据链 | Bronze/Silver、质检、签名包/账本、DELTA | `docs/deliveries/FULL-122/204.md` |
| 主数据与日历 | 标的目录/范围、交易时段、复权、公司行动 | `docs/deliveries/FULL-200/201.md` |
| 增量与质量 | 增量采集/锁/恢复、OHLCV/时区/跨源校验 | `docs/deliveries/FULL-202/203.md` |
| 运维 | 每晚任务、健康看板、凭据扫描/密钥轮换/备份演练/依赖审计 | `docs/deliveries/FULL-800~802.md` |
| DSL | Strategy DSL Schema、参考解释器、扫描/回测 | `docs/deliveries/FULL-400/401.md` |
| 图谱 | 实体/关系/证据模型、导入器、金标评估、审核/审计 | `docs/deliveries/FULL-700~703.md` |

## Android 端能力（Kotlin/Compose，minSdk 33）

| 模块 | 能力 | 证据 |
|---|---|---|
| 行情 | SQLCipher 个人库/行情库边界、导入/激活/清理 | `docs/deliveries/FULL-123/300~303.md` |
| K线/市场 | 自选/详情/K线交互、指标/异常状态 | `docs/deliveries/FULL-301/302.md` |
| DSL | Kotlin DSL 解释器、资源限制、共享向量一致 | `docs/deliveries/FULL-402/403/404.md` |
| 交易 | 账本/统计/加密备份恢复/复盘 UI | `docs/deliveries/FULL-500~504.md` |
| 图谱 | 搜索/关系/证据追溯 UI | `docs/deliveries/FULL-704.md` |

## 真实数据源状态（2026-08-06）

| 来源 | 状态 | 证据 |
|---|---|---|
| AKShare 日历 | PASS 8797 行 | `artifacts/full-110-akshare/provider-capabilities.json` |
| AKShare 快照/资金 | FAILED/NETWORK（东财端点） | 同上 |
| BaoStock | FAILED/NETWORK（TCP :10030 超时） | `reports/provider-capabilities.json`（02:09） |
| JQData/Tushare | BLOCKED/CONFIGURATION（无凭据） | `reports/full111-cli-check/`、`reports/full112-cli-check/` |
| 期货 IF0 | PASS 2317 行 | `docs/deliveries/FULL-601.md` |
| 港股/同花顺 | FAILED/NETWORK、FAILED/PROVIDER | `docs/deliveries/FULL-600/602.md` |

## 测试基线

桌面 pytest 434 项全过；Ruff 全过；23 个共享 Schema 夹具全过；Android JVM 68 项（20 suite/0 失败）；
lint 0 errors；金标图谱 P/R/F1=1.0（10/10、8/8）。详见 `docs/release/quality-report.md`。
