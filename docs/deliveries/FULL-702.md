# FULL-702 实现交付：企业名称归一、实体消歧、关系抽取和重复合并

日期：2026-08-06
状态：实现完成（金标评估通过）
角色：impl_graph2 + root（评估复核与文档补齐）

## 结果

- `industry_graph/pipeline.py`：名称归一（空白/标点/公司后缀/大小写/数字）、实体消歧（同归一化名→同一实体，属性冲突进待确认）、确定性规则关系抽取（供应商/客户/生产商等句式与表格行）、重复合并（保留证据与审计；人工确认实体不被自动覆盖）、低置信进待确认。
- `industry_graph/evaluate.py`：金标评估（`tests/fixtures/graph/gold-standard.json`，实体 10、关系 8），COMPETES_WITH 按无向匹配。
- 测试：`test_industry_graph_pipeline.py`。

## 金标评估（真实结果）

| 指标 | 值 | 阈值 |
|---|---|---|
| 实体精确率/召回率/F1 | 1.0 / 1.0 / 1.0（10/10/10） | ≥0.8 / ≥0.7 |
| 关系精确率/召回率/F1 | 1.0 / 1.0 / 1.0（8/8/8） | ≥0.8 / ≥0.7 |

命令：`evaluate_fixtures()`（`evaluate.py`）；`passes=True`。

## 状态建议

实现完成，等待系列统一审查与验收。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTED`。本机重跑验收命令与金标评估均通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| 金标评估（真实数字） | `desktop\.venv\Scripts\python.exe -m market_monitor.industry_graph.evaluate` | 实体 P/R/F1=1.0/1.0/1.0（10/10/10）；关系 P/R/F1=1.0/1.0/1.0（8/8/8）；阈值 precision≥0.8、recall≥0.7，超阈值 |
| 图谱管线专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_industry_graph_pipeline.py -q` | PASS：9 项（含金标阈值与受控指标数学），exit 0 |
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

验收角色未修改实现代码。
