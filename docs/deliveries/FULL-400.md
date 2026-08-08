# FULL-400 实现交付：Strategy DSL v1 Schema、运算符、指标与安全边界

日期：2026-08-06
状态：实现完成（等待系列统一审查）
角色：impl_strategy_dsl（Schema/验证器/夹具）+ root（编译修复与交付补齐）

## 范围与边界

声明式策略 DSL v1：JSON 节点树 Schema、Python 验证器与白名单节点语义；拒绝未知节点类型、任意代码、网络与文件访问；深度/规模上限；共享正反例夹具（Python 与 Android 共用）。

## 修改文件

- `contracts/strategy-dsl.schema.json`（新增）：schema_version=1、strategy/inputs/parameters/nodes/signal/limits；节点类型白名单（series/value/parameter、算术/比较/逻辑、sma/ema/sum/stddev/rolling_max/rolling_min/roc/lag/crosses_above/crosses_below/ifelse/not 等）。
- `desktop/src/market_monitor/strategy_dsl/schema.py`（新增）：Python 验证器（未知节点/任意代码/网络/文件节点拒绝、类型推断、深度/规模上限、窗口引用检查）。
- `desktop/src/market_monitor/strategy_dsl/errors.py`（新增）：SCHEMA/UNKNOWN_NODE/CYCLE/LIMIT/NO_DATA/PARAMETER/TYPE/NUMERIC/TIMEOUT/CANCELLED 错误分类。
- `tests/fixtures/dsl/valid|invalid/*.json` + `cases.json`：合法（ma-cross、volume-confirm-breakout）与非法（arbitrary-code、file-node、network-node、cycle、too-deep、too-many-nodes、unknown-node-type、ifelse 类型不匹配、非布尔信号等）。
- `desktop/tests/test_strategy_dsl.py`（新增）。

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| DSL 专项 + 共享契约 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_strategy_dsl.py desktop\tests\test_contracts.py -q` | PASS |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS |

## 安全边界

节点类型必须命中白名单；未知类型（含任意代码、网络、文件形态）在解析期拒绝；节点数上限 200（可配置 ≤2000）、深度上限 32（可配置 ≤64）；窗口引用只能指向 integer 参数节点。

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
