# FULL-401 实现交付：桌面 Python 扫描/回测与 DSL 参考解释器

日期：2026-08-06
状态：实现完成（等待系列统一审查）
角色：impl_strategy_dsl + root 交付补齐

## 范围与边界

桌面 Python 参考解释器与扫描/回测执行：节点 DAG 拓扑求值、无未来函数（信号只用截至当根 bar 收盘的数据）、超时/取消/无数据/数值错误/规模超限分类、运行记录含数据与策略版本。

## 修改文件

- `desktop/src/market_monitor/strategy_dsl/interpreter.py`（新增）：Python 参考解释器（与 Kotlin 语义一致：白名单运算符、滚动窗口、lag、crosses、ifelse、参数解析、超时/取消/操作预算）。
- `desktop/src/market_monitor/strategy_dsl/scanner.py`（新增）：扫描/回测执行器，运行记录包含 strategy_id/version、data 版本、参数版本与信号索引。
- `desktop/tests/test_strategy_dsl.py`：无未来函数固定样本、超时/错误分类、运行记录版本断言。

## 自动化证据

同 FULL-400 专项命令，PASS。

## 状态建议

实现完成，等待系列统一审查与验收。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTED`。本机重跑验收命令均通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| DSL/图谱/契约专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_strategy_dsl.py desktop\tests\test_industry_graph_models.py desktop\tests\test_industry_graph_importers.py desktop\tests\test_industry_graph_pipeline.py desktop\tests\test_industry_graph_review.py desktop\tests\test_contracts.py -q` | PASS：115 项收集，全部通过（exit 0） |
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors（9 warnings + 1 information，均为存量非阻断项） |

验收角色未修改实现代码。
