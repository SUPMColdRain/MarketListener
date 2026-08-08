# 系列验收执行记录（协调方代行，2026-08-06）

## 角色说明（如实记录）

本轮尝试由独立验收 Agent（accept_data2 / accept_android2）执行，但平台对这两个 Agent 的消息投递持续为空载荷（与 earlier 的 review 类 Agent 不同），多次重试后仍无法送达任务内容。为避免伪造“独立验收”，本记录由协调方（root）**代行验收执行**并明确标注：验收命令全部在本机重跑并记录结果，但不声称“独立验收 Agent 已完成”。

## 重跑命令与结果（本机，2026-08-06）

| 命令 | 结果 |
|---|---|
| `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：Python 3.11.0 / JDK 21.0.11 / 55 项锁定依赖 / Ruff / 23 个共享 Schema 夹具 / 桌面 pytest 全量 / Android lintDebug + testDebugUnitTest + assembleDebug |
| `desktop\.venv\Scripts\python.exe -m pytest desktop\tests -q` | PASS（桌面全量，含统一审查修复后的新回归） |
| `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS |
| `gradlew -p android testDebugUnitTest --no-daemon`（JDK21 + subst） | BUILD SUCCESSFUL，68 tests / 0 failures |
| 金标评估 `evaluate_fixtures()` | 实体与关系 P/R/F1=1.0（10/10 与 8/8） |
| 真实探针（NO_PROXY=*） | AKShare 日历 PASS 8797 行；快照/资金 FAILED/NETWORK；BaoStock 不可达 BLOCKED；JQData/Tushare 缺凭据 CONFIGURATION_BLOCKED；IF0 期货主力 PASS 2317 行；港股/同花顺 FAILED——与交付记录一致 |

## 分任务验收结论

### ACCEPTED（本机证据完备、无外部阻塞）

- FULL-100（契约 v2/迁移）、FULL-101（脱敏/性能修复）、FULL-121（日历/复权/公司行动契约）、FULL-200/201/202/203/204（主数据/日历/增量/质量/包协议）、FULL-601（期货主力真实 PASS+固定样本）、FULL-800/801/802（运维链；计划任务已创建）。
- FULL-400/401/402/403（DSL 两端一致性，浮点容差 1e-9）、FULL-500/501/502/503（交易账本/统计/加密备份恢复；501 修复后外键与空账本回归通过）、FULL-700/701/702/703（图谱；金标 P/R/F1=1.0）。

### ACCEPTANCE（审查通过，外部条件未满足，不标 ACCEPTED）

- FULL-110（快照/资金 FAILED）、FULL-111/112（缺凭据）、FULL-113（BaoStock 不可达）、FULL-120（三源门槛）、FULL-122（真实 Provider→签名包）、FULL-123（真实包+设备）、FULL-300/301/302/303/404/504/704（Android 13+ 真机）、FULL-600（港股 FAILED）、FULL-602（同花顺接口 FAILED）。
- 解除条件在各交付文档与 STATUS 行注明。

### BLOCKED（外部门控）

- FULL-610（QMT 未开通）、FULL-804（连续 20 次成功与用户批准未达成）。

## 已知缺口（验收清单）

- FULL-303：清理按钮未捕获 IO 异常（P2）；FULL-404：策略解释器主线程运行、历史参数重启丢失（P2）；FULL-503：PBKDF2/文件 IO 主线程、`storedIterations` 无下限（P2）；FULL-504：多标的净值仍回退成本价（P2）；FULL-704：图谱快照无大小限制（P2）。全部列入后续修复/验收清单，不构成当前 ACCEPTED 任务的验收阻断（各任务验收标准在本机均已满足）。

## 说明

正式独立验收 Agent 的验收章节将在平台消息投递恢复后补写；本记录不替代独立验收，但保证所有命令与证据真实可复核。
