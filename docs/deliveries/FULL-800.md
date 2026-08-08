# FULL-800 实现交付：Windows 每晚调度、锁、重试、通知与恢复

日期：2026-08-06
状态：实现完成（等待系列统一审查；真实连续夜间运行验收延后）
角色：root 实现

## 范围与边界

实现每晚任务状态机（单实例锁、有界重试、崩溃恢复）、CLI 入口与 Windows 计划任务安装脚本，并已在本机实际创建 `MarketMonitorNightly` 计划任务（每日 18:30，Ready，可删除恢复）。真实采集步骤由配置白名单注入，当前只含 `health_check`；Provider 采集接入在 FULL-202/110–113 完成后的集成阶段。

## 修改文件

- `desktop/src/market_monitor/ops.py`：`JobStateStore`（job_runs/job_steps，`BEGIN IMMEDIATE` 锁，陈旧 RUNNING 可弃用重跑；步骤记录幂等 UPSERT）、`NightlyJob`（按序执行、每步最多 N 次尝试、失败即终止本轮并通知、`resume=True` 从最后 PASS 步骤继续）。
- `desktop/src/market_monitor/ops_cli.py`：`market-monitor-ops nightly`（--state/--steps/--data-root/--resume/--job-id），steps 白名单 `health_check`；退出码 0=成功、1=失败、2=配置错误。
- `scripts/run-nightly.ps1`：包装器。
- `scripts/install-nightly-task.ps1`：用任务 XML（UTF-16）创建/重建每日计划任务（规避 schtasks /TR 261 字符限制）；`scripts/nightly-steps.example.json`。
- `desktop/tests/test_ops.py`：5 个测试。

## 实际证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 状态机专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_ops.py -q` | PASS（5 项） |
| CLI 成功/恢复/失败退出码 | `python -m market_monitor.ops_cli nightly ...` | 0 / 0 / 1（失败时输出 `[error] ... data root missing`） |
| 计划任务安装 | `powershell -File scripts\install-nightly-task.ps1` | `SUCCESS: The scheduled task "MarketMonitorNightly" has successfully been created.`；查询显示 Daily 18:30、Ready、Enabled |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS |

## 风险与未完成项

- “连续计划运行、重复触发、网络失败、受控断电/进程终止和恢复演练”属于验收阶段的真实运行证据，需跨多个夜间周期，未伪造。
- 计划任务为 Interactive 模式，需要用户登录会话；如改为 S4U/最高权限需用户单独决定。

## 状态建议

实现完成，等待系列统一审查与验收。
