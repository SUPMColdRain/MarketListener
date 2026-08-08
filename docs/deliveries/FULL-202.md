# FULL-202 实现交付：每日增量采集、游标、重试、幂等与断点恢复

日期：2026-08-06
状态：实现完成（等待系列统一审查）
角色：root 实现

## 范围与边界

实现按“source/instrument/period”为单位的增量采集：持久化游标、单实例锁、有界重试、批内去重、部分失败隔离与断点恢复。采集单元独立，一个单元失败不抹掉其他单元结果；真实 Provider 数据接入由 FULL-110～113/122 完成。

## 修改文件

- `desktop/src/market_monitor/incremental.py`（新增）：
  - `CheckpointStore`：`checkpoints` 表（每个采集单元的游标）+ `run_locks` 表（单实例锁，`BEGIN IMMEDIATE` 事务实现，跨平台）。
  - `IncrementalCollector.collect`：读游标→有界重试 fetch（默认最多 2 次重试，共 3 次尝试）→归一化→批内去重→写 Bronze/Silver→成功后推进游标；部分失败（`partial_error`）仍写入已取回数据并把 run 标记 `PARTIAL_FAILURE`；彻底失败不推进游标、run 标记 `FAILED`。
  - `FetchOutcome`/`IncrementalRunSummary`：明确的取回/写入/重试/状态模型。
- `desktop/tests/test_incremental.py`（新增）：5 个场景测试。

## 验收要点对应证据

| 验收标准 | 证据 |
|---|---|
| 首跑/重跑幂等 | `test_cursor_resume_and_idempotent_rerun`：第二次 fetch 从首跑游标开始，批内重复 bar 在写 Silver 前丢弃（`test_duplicate_bars_within_batch_are_dropped_before_silver`） |
| 受控中断/断点续跑 | 游标持久化在 `checkpoints`，失败不推进；恢复后从最后成功位置继续 |
| 重试 | `test_bounded_retries_then_failed_status_without_cursor_advance`：恰好 3 次调用（1+2 重试），游标不变 |
| 部分来源失败 | `test_partial_failure_keeps_written_bars_and_marks_run`：已取回数据落盘，run=`PARTIAL_FAILURE`，游标推进到最后成功位置 |
| 并发锁 | `test_concurrent_collection_is_blocked_by_unit_lock`：第二个 owner 超时后 `LockHeldError` |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_incremental.py -q` | PASS（5 项） |
| 相关回归 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_market_package.py desktop\tests\test_quality.py desktop\tests\test_contracts.py -q` | PASS |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS |

## 风险与未完成项

- CLI 子命令接线与真实调度（Windows 计划任务）留在 FULL-800；真实 Provider fetch 适配留在 FULL-110～113/122。
- 锁在进程崩溃后由数据库事务自动释放（sqlite 连接关闭），无陈旧锁文件问题。

## 状态建议

实现完成，等待系列统一审查与验收。

## 统一审查修复（2026-08-06）

按 `docs/reviews/unified-review-data.md` P1-2/P1-3：Silver 分区合并去重（同键不覆盖、历史保留）；`acquire_lock` 增加 `lock_ttl_seconds`（默认 1h）陈旧锁抢占，崩溃后可续跑；新增对应回归测试。
