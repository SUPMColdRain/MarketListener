# FULL-120 实现交付：来源烘焙测试与主备决策

日期：2026-08-06
状态：实现完成（决策逻辑与固定样本通过；真实三源门槛未满足，如实记录）
角色：root 实现

## 范围与边界

实现按角色（历史主源/日线校验/日历/分钟/ETF/指数/期货）的主备烘焙决策：只接受“对应能力 PASS 且证据非空”的来源；缺角色时输出 BLOCKED，绝不静默逐行混源。真实三源门槛（110–113 至少三个接受）当前未满足：AKShare 仅日历 PASS（快照/资金因东财断连 FAILED），BaoStock 不可达，JQData/Tushare 缺凭据；因此真实烘焙报告将如实为 BLOCKED，直到验收阶段凭据/网络条件恢复。

## 修改文件

- `desktop/src/market_monitor/baking.py`（新增）：`RoleDefinition`/`ROLE_DEFINITIONS`（含 Plan §7 的偏好顺序：历史主源 JQData→Tushare→AKShare→BaoStock；日历 Tushare→AKShare→…）、`bake_sources`、`SourceRouter`、`write_baking_report`。
- `desktop/tests/test_baking.py`（新增）：首选命中、主源无行/失败时回退、全角色 BLOCKED、JSON/Markdown 报告、未知角色拒绝。

## 验收要点对应证据

| 验收标准 | 证据 |
|---|---|
| 分区级选源/降级 | `test_baking_picks_first_preferred_passing_capability` + `test_baking_falls_back_when_primary_lacks_rows_or_failed` |
| 禁止逐行混源 | 决策只选单一来源；`comparison.py` 的 `row_blending: DISABLED` 语义未变 |
| 至少三个已接受来源及三类真实能力门槛 | 未满足：FULL-110（AKShare 日历 PASS，快照/资金 FAILED/NETWORK）、FULL-113（BaoStock 不可达 BLOCKED）、FULL-111/112（缺凭据 BLOCKED）；真实烘焙为 BLOCKED，解除条件见各交付记录 |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 烘焙专项 + 共享契约 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_baking.py desktop\tests\test_contracts.py -q` | PASS（45 项） |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src\market_monitor\baking.py desktop\tests\test_baking.py` | PASS |

## 风险与未完成项

- 真实决策报告需在验收阶段用 110–113 真实结果作为输入重跑；当前若运行 `bake_sources(probe_results)` 会因能力证据不足输出 BLOCKED，这是诚实结果而非缺陷。
- 角色偏好可按用户后续决策调整（如 RQData 试用），无需改 Schema。

## 状态建议

实现完成，等待系列统一审查；真实三源门槛按外部条件如实 BLOCKED。
