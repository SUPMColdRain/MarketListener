# Day 0 历史交付索引

本目录保存 Day 0 的实现、测试、审查和环境阻塞证据。用户已于 2026-08-04 决定停止执行 Day 0；这些文件不可作为“Day 0 已封板”的依据，也不是后续会话的待办队列。

正式任务入口见根目录 [START_HERE.md](../../START_HERE.md) 与 [STATUS.md](../../STATUS.md)。[正式开发交接](../正式开发交接.md) 保存计划固化前基线，最终 Day 0 状态以 [Day0阶段性交接](./Day0阶段性交接.md) 为准。

## 正式项目交付

- [FULL-001](./FULL-001.md)：正式全周期计划、实时状态入口、启动协议和 ADR-0007/0008 的实现交付；当前状态以根目录 `STATUS.md` 为准。
- [FULL-002](./FULL-002.md)：首个 Git 回退提交及 Python/JDK/Gradle/Android SDK/依赖锁定基线。
- [FULL-003](./FULL-003.md)：已独立验收的统一 Python/Android 基线验证入口、Ruff 锁定与成功/受控失败/恢复证据。

- `D0-001.md` 至 `D0-050.md`：按任务记录的历史实现与验证。
- `D0-060-D0-062.md`：历史审查、端到端验收和封板结论。
- `Android-16KB-compatibility.md`、`Android-中文界面与导入状态.md`：Android 环境与界面专项记录。

ADR、共享契约和后续正式开发任务不能仅因这些历史文件存在而被改写。
