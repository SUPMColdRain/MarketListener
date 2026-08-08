# 数据链集群验收记录（root 代行，2026-08-06）

## 角色说明（如实记录）

独立验收 Agent（accept_data2）完成就绪扫描（`docs/reviews/acceptance-readiness-data.md`）并生成了
最新真实探针报告（`reports/provider-capabilities.json`，02:09），但其后续任务多次因平台消息投递问题
只返回中间状态，未产出最终验收文档。本记录由协调方 root 依据真实命令结果代行落盘，明确不声称
“独立验收 Agent 已完成”；所有命令均可复核，未伪造任何真机/凭据/网络结果。

## 本机重跑证据（2026-08-06）

| 命令 | 结果 |
|---|---|
| `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：Python 3.11.0 / JDK 21.0.11 / 55 项锁定依赖 / Ruff / 23 个共享 Schema 夹具 / 桌面 pytest 全量 / Android lintDebug + testDebugUnitTest + assembleDebug（详见 `docs/reviews/acceptance-executed.md`） |
| 桌面 pytest 全量 | PASS（`acceptance-executed.md`；最新专项基线见 `rereview-data-fixes.md`：434 项收集全通过） |
| Ruff | PASS（desktop/src、desktop/tests） |
| Android JVM | BUILD SUCCESSFUL：20 suite / 68 tests / 0 failures（accept_android2 实测） |
| 金标评估 | 实体与关系 P/R/F1=1.0（10/10 与 8/8） |

## 真实探针状态（2026-08-06，NO_PROXY=*）

| Provider | 能力 | 真实状态 | 证据 |
|---|---|---|---|
| AKShare | 交易日历 | PASS 8797 行 | `artifacts/full-110-akshare/provider-capabilities.json` |
| AKShare | 快照/资金流 | FAILED/NETWORK（东财 RemoteDisconnected） | 同上；直接探测曾 PASS 120 行/5976 行 |
| BaoStock | 全部能力（运行级） | FAILED/NETWORK（`网络接收错误`；TCP :10030 超时） | `reports/provider-capabilities.json`（02:09）、`artifacts/full-113-baostock/tcp-check.json` |
| JQData | 登录/日线等 | BLOCKED/CONFIGURATION（本机无凭据） | `reports/full111-cli-check/provider-capabilities.json` |
| Tushare | 日历/日线等 | BLOCKED/CONFIGURATION（本机无 token） | `reports/full112-cli-check/provider-capabilities.json` |
| 期货 IF0 | 主力连续 | PASS 2317 行 | `docs/deliveries/FULL-601.md` |
| 港股/同花顺 | 代表拉取 | FAILED/NETWORK、FAILED/PROVIDER | `docs/deliveries/FULL-600.md`、`FULL-602.md` |

### BaoStock 分类核实（accept_data2 上轮疑问的闭环）

- 最新探针报告（02:09）中 BaoStock 为 `provider-run-error`：status=`FAILED`、category=`NETWORK`，
  与交付记录 `docs/deliveries/FULL-113.md` 的 FAILED/NETWORK 分类一致。
- `CONFIGURATION_BLOCKED`（CLI 退出码 3）仅在全部能力 status=BLOCKED 时输出
  （`desktop/src/market_monitor/cli.py:77-83`）；BaoStock 适配器无
  `missing_configuration_requirements`，运行级错误固定映射为 FAILED，因此不可能出现
  CONFIGURATION_BLOCKED。该分类只适用于缺本地凭据的 JQData/Tushare。
- 跨源重叠对比因双方网络失败保持 `BLOCKED`（`row_blending: DISABLED`），属预期，不代表适配器错误。

## 逐任务验收结论

### ACCEPTED（本机证据完备、无外部阻塞）

| 任务 | 证据/说明 |
|---|---|
| FULL-100 | 契约 v2/迁移反例重跑通过（`acceptance-executed.md`、`docs/deliveries/FULL-100.md`） |
| FULL-101 | terra7 修复与性能回归全绿；统一验证 PASS（`acceptance-executed.md`） |
| FULL-121 | 日历/复权/公司行动契约专项与共享夹具全绿 |
| FULL-200/201/202/203/204 | 主数据/日历/增量/质量/包协议专项全绿；P1 修复复审通过 |
| FULL-601 | IF0 真实 PASS 2317 行 + 固定样本 |
| FULL-801/802 | 健康看板/安全审计专项全绿；计划任务已创建；仓库无真实凭据命中 |

### ACCEPTANCE（审查通过、外部条件未满足，不标 ACCEPTED）

| 任务 | 解除条件 |
|---|---|
| FULL-110 | AKShare 快照/资金端点恢复后重跑真实探针 |
| FULL-111/112 | 用户在本机配置 JQData/Tushare 凭据后真实登录与额度/权限探测 |
| FULL-113 | `www.baostock.com:10030` 可达后真实日线与跨源重叠对比 |
| FULL-120 | 至少三个来源有真实 PASS+非空证据后执行真实三源决策 |
| FULL-122 | 真实 Provider → Bronze/Silver → 质检 → 签名包端到端（受数据源条件限制） |
| FULL-600 | 港股真实跨源闭环（东财端点恢复） |
| FULL-602 | 同花顺接口在可用 akshare 版本上的真实探测 |
| FULL-800 | 连续夜间运行与受控中断/恢复演练（本机计划任务已 Ready） |

说明：FULL-123/300/301/302/303/404/504/704 属 Android/DSL/图谱集群，已由
`docs/reviews/acceptance-android-dsl-graph.md`（accept_android2）处理，不在本记录重复判定。
FULL-610（QMT 未开通）与 FULL-804（连续 20 次成功+用户书面批准）保持 BLOCKED。
