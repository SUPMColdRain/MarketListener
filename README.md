# 行情监控和产业链图谱项目文档入口

## 开发前必读

1. [ADR.md](./ADR.md)：不可擅自修改的项目约束与架构决策索引。
2. [CONTEXT.md](./CONTEXT.md)：项目统一术语。
3. [Plan_full.md](./Plan_full.md)：正式项目的完整任务、依赖、测试、审查和验收规范。
4. [STATUS.md](./STATUS.md)：唯一实时任务状态和下一项任务入口。
5. [START_HERE.md](./START_HERE.md)：新实现、审查和验收任务的固定启动协议。
6. [行情监控和产业链图谱项目.md](./行情监控和产业链图谱项目.md)：完整目标、架构和技术方案。
7. [项目开发和Agent分工时序图](./项目开发和Agent分工时序图.html)：全周期依赖与实现/审查/验收分工。
8. [Experience.md](./Experience.md)：可复用的工程经验、环境约束和踩坑记录。
9. [Log.md](./Log.md)：实际变更与验证日志。
10. [正式开发交接](./docs/正式开发交接.md)：正式计划固化前的项目基线。
11. [Plan.md](./Plan.md) 与 [Day0阶段性交接](./docs/deliveries/Day0阶段性交接.md)：只读历史计划与证据。

发生冲突时，以 `ADR.md` 和单项 ADR 为准；时序图用于理解执行顺序，不替代任务验收标准。

## 当前开发状态

正式项目计划已由 `FULL-001` 固化并独立验收通过，实时进度只看 [STATUS.md](./STATUS.md)。`FULL-002` 已建立首个 Git 回退提交并锁定工具链，当前等待独立审查；尚无其他可启动的 `READY` 任务。

Day 0 已于 2026-08-04 停止执行且未封板。`Plan.md` 与 `docs/deliveries/D0-*` 是历史计划和证据，不是后续会话的自动待办队列。

仍然有效的工作规则：数据源能力未逐项实测时只能写“候选”或“待验证”；任何架构变化必须先由用户批准 ADR；实现、审查和验收由独立任务完成并保留可复核证据。

## 仓库结构（D0-001 建立项目骨架）

- `desktop/`：数据生产端，包含 Provider 探针、标准标的、Bronze/Silver、质量检查、聚合、行情包和签名代码。
- `android/`：Android 13+ 消费端，Kotlin + Jetpack Compose，包含个人/行情库边界、签名行情包导入和离线 K 线容器，`minSdk=33`。
- `contracts/`：D0-002 固化的共享 JSON Schema。
- `tests/fixtures/`：跨端共享测试夹具目录。
- `docs/`：架构、交付、验收模板和阶段性交接文档。
- `scripts/run_tests.ps1`：统一测试入口，依次执行 desktop pytest 与 android JVM 单元测试。

## 锁定工具链基线

版本权威清单见 `toolchain.versions.toml`：Python 3.11.0、JDK 21、Gradle Wrapper 8.5、AGP 8.3.2、Kotlin 2.0.0、Android SDK 34（Platform revision 3）和 Build Tools 34.0.0。Python 完整依赖锁见 `desktop/requirements.lock`，Android 传递依赖由 Gradle lockfile 固定。

Windows 中文路径说明：仓库实际目录名为 `阅读行情监控和产业链图谱项目`。JDK 21/Gradle 的测试 worker 会把英文 junction 解析回中文物理路径并导致测试类加载失败；命令行验证应临时执行 `subst M: <仓库绝对路径>`，从 `M:\` 运行 Gradle，结束后执行 `subst M: /D`。盘符 `M:` 已占用时选择其他空闲盘符。Android Studio 仍可从 `C:\Users\qingd\Documents\MarketListener\android` 打开项目。

```powershell
# 数据生产端
py -3.11 -m venv desktop\.venv
desktop\.venv\Scripts\python -m pip install -c desktop\requirements.lock -e "desktop[dev]"
desktop\.venv\Scripts\python -m market_monitor --version
desktop\.venv\Scripts\python -m pytest desktop\tests

# Android
$env:JAVA_HOME = "C:\path\to\jdk-21"
android\gradlew.bat -p android testDebugUnitTest
android\gradlew.bat -p android assembleDebug

# 统一入口
powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1
```

## Day 0 历史状态（只读，2026-08-04）

Day 0 已停止执行且未封板。桌面单元测试（49 passed）、Android JVM 测试、Debug APK 构建、16 KB 原生库对齐和 16 KB 模拟器主界面启动已实际通过；Android 已可中文显示行情包导入状态，并具备读取已激活 `payload.sqlite` 的标的、周期和 bars 代码。

未达到验收标准的项目包括：真实 Provider 数据探针（当前四个来源均 FAILED/UNSUPPORTED）、基于真实数据生成并导入的签名行情包、已导入 bars 的 K 线查询/展示、Android 端到端验收，以及 Chaquopy + NumPy 策略运行时（NumPy 在 16 KB 设备加载 `libgfortran` 失败）。ADR-0008 已决定后续 Android 改用声明式策略 DSL，但该决定不把历史失败改写为成功。
