# FULL-403 实现交付：桌面与 Android 共享测试向量与一致性测试

日期：2026-08-06
状态：实现完成（等待系列统一审查）
角色：impl_strategy_dsl（向量文件与 Python 侧）+ root（Kotlin 向量一致性测试与交付）

## 范围与边界

单一共享向量文件驱动两端一致性测试：同一策略/参数/序列在 Python 参考解释器与 Kotlin 离线解释器上产生相同的离散信号索引与节点值（浮点误差阈值明确）。

## 修改文件

- `tests/fixtures/dsl/vectors.json`（新增）：3 组向量（sma_cross、roc_threshold、ema_series），含 strategy/parameters/series/expected（signal_indices、signals、node_values、numeric_tolerance=1e-9）。
- `desktop/tests/test_strategy_dsl.py`：`test_shared_vectors_pass_desktop_reference`（参数化 3 向量，rel/abs 容差 1e-9）。
- `android/app/src/test/java/com/marketmonitor/app/strategy/dsl/DslSharedVectorsTest.kt`（新增）：从测试资源 `dsl/vectors.json` 加载同一文件，逐向量断言信号索引全等、节点值在 `tol * max(1, |a|, |b|)` 容差内。

## 一致性阈值

两端声明的浮点一致性阈值：相对/绝对容差均为 1e-9（向量文件 `numeric_tolerance`）；离散信号索引必须逐位全等。

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| Python 端 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_strategy_dsl.py -q` | PASS（3 向量全过） |
| Android 端 | `gradlew -p android testDebugUnitTest --no-daemon` | BUILD SUCCESSFUL（17 tests 含 3 向量一致性，0 failures） |

## 状态建议

实现完成，等待系列统一审查与验收。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTED`。本机重跑两端一致性测试均通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| 桌面共享向量 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_strategy_dsl.py -q` | PASS：43 项（含 3 组共享向量，容差 1e-9） |
| Android 共享向量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `DslSharedVectorsTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

验收角色未修改实现代码。
