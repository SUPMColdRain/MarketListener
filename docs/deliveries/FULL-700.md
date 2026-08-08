# FULL-700 实现交付：图谱实体、关系、证据、置信度与人工确认模型

日期：2026-08-06
状态：实现完成（等待系列统一审查）
角色：impl_graph（模型/存储/契约）+ root（文档补齐）

## 结果

- `contracts/industry-graph-entity.schema.json`、`industry-graph-relationship.schema.json`、`industry-graph-evidence.schema.json`：实体类型/关系类型/方向/置信度 0..1/确认状态（PENDING/AUTO_ACCEPTED/HUMAN_CONFIRMED/REJECTED/SUPERSEDED）/证据定位（page/cell/dom/line/offset）+ 共享正反例（已接入 `cases.json`，Python 与 Android 共用）。
- `desktop/src/marketmonitor/industry_graph/models.py`：Entity/Relationship/Evidence/ConfirmationStatus 等领域模型与 GraphStore（SQLite：实体按归一化名唯一、关系唯一键、证据关联、审计日志；自动结果不覆盖人工确认）。
- `docs/industry-graph-terminology.md`：公司/产品/行业/上下游等术语定义。
- 测试：`test_industry_graph_models.py` + 共享契约用例。

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 图谱模型/导入/契约专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_industry_graph_models.py desktop\tests\test_industry_graph_importers.py desktop\tests\test_industry_graph_pipeline.py desktop\tests\test_industry_graph_review.py desktop\tests\test_contracts.py -q` | PASS |

## 状态建议

实现完成，等待系列统一审查与验收。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTED`。本机重跑验收命令均通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| 图谱模型/导入/契约专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_industry_graph_models.py desktop\tests\test_industry_graph_importers.py desktop\tests\test_industry_graph_pipeline.py desktop\tests\test_industry_graph_review.py desktop\tests\test_contracts.py -q` | PASS：72 项（6+9+9+8+40），全部通过（exit 0） |
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

验收角色未修改实现代码。
