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

正式项目计划已由 `FULL-001` 固化并独立验收通过，实时进度只看 [STATUS.md](./STATUS.md)。`FULL-002` 已建立首个 Git 回退提交并锁定工具链；`FULL-003` 的统一验证入口已由独立验收接受；`FULL-100`（Provider Contract v2）已通过全新独立验收。`FULL-101`（本地配置、日志脱敏、受控 runner 与 CLI 退出码）已完成层数无关转义归一化修复并重新进入 `REVIEW`，等待新的独立审查；详见 `STATUS.md` 与 `docs/deliveries/FULL-101.md`。

2026-08-09 最新进展：Android 同步包下载/手动导入两处报错已修复并回归；行情数据为真实部分覆盖（48 标的、72,321 根 K 线），后端 `/api/health` 如实展示各市场覆盖数；`行业产业链研报/` 的 720 篇研报已跑通知识库生产流水线（717 解析、33,096 条事实、719 篇规则核验通过、1 篇待 OCR），聚合为 155 条产业链并生成 SVG 图谱页 `/industry/`（`data_control/industry/industry-map.html` 随同步包下发，Android 产业链页加载网页快照，不重读研报）。

> 正式开发口径：项目不再区分 P0/FULL 阶段；`FULL-*` 编号仅作历史任务追踪，不代表优先级或阶段。
> 当前按 5.1–5.9 系列统一开发，完成后再集中测试、审查与验收。

Day 0 已于 2026-08-04 停止执行且未封板。`Plan.md` 与 `docs/deliveries/D0-*` 是历史计划和证据，不是后续会话的自动待办队列。

仍然有效的工作规则：数据源能力未逐项实测时只能写“候选”或“待验证”；任何架构变化必须先由用户批准 ADR；实现、审查和验收由独立任务完成并保留可复核证据。

## 仓库结构（D0-001 建立项目骨架）

- `desktop/`：数据生产端，包含 Provider 探针、标准标的、Bronze/Silver、质量检查、聚合、行情包和签名代码。
- `android/`：Android 13+ 消费端，Kotlin + Jetpack Compose，包含个人/行情库边界、签名行情包导入和离线 K 线容器，`minSdk=33`。
- `contracts/`：D0-002 固化的共享 JSON Schema。
- `tests/fixtures/`：跨端共享测试夹具目录。
- `docs/`：架构、交付、验收模板和阶段性交接文档。
- `scripts/verify.ps1`：统一基线验证入口，依次执行 Python 环境、Ruff、Schema、完整 pytest、Android Lint/JVM 单测与 Debug APK 构建。

## 锁定工具链基线

版本权威清单见 `toolchain.versions.toml`：Python 3.11.0、JDK 21、Gradle Wrapper 8.5、AGP 8.3.2、Kotlin 2.0.0、Android SDK 34（Platform revision 3）和 Build Tools 34.0.0。Python 完整依赖锁见 `desktop/requirements.lock`，Android 传递依赖由 Gradle lockfile 固定。

路径说明：仓库当前位于英文路径 `C:\Users\qingd\Documents\MarketListener`，命令行可直接构建；若以后把仓库克隆或移动到中文路径，JDK 21/Gradle 的测试 worker 会把英文 junction 解析回中文物理路径并导致测试类加载失败，届时可临时执行 `subst M: <仓库绝对路径>`，从 `M:\` 运行 Gradle，结束后执行 `subst M: /D`（盘符 `M:` 已占用时选择其他空闲盘符）。

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

# 统一入口（脚本显式使用 JDK 21，并自动映射临时英文盘符运行 Gradle）
powershell -ExecutionPolicy Bypass -File scripts\verify.ps1
```

## Provider 本地配置与安全探针

凭据只可保存在进程环境变量，或在仓库外的显式配置文件中。`.env.example` 只是变量名说明，CLI 不会自动读取仓库内的 `.env`，也不会在输出中回显配置值。

```powershell
# 可选：在仓库外创建配置文件，再显式传入。不要把真实文件放入仓库。
Copy-Item .env.example $env:USERPROFILE\market-monitor.env
desktop\.venv\Scripts\python -m market_monitor probe --config-file $env:USERPROFILE\market-monitor.env --provider joinquant
```

`probe` 总会生成 JSON 和 Markdown 报告，并输出一行机器可读 JSON：`0` 表示没有失败或阻塞，`2` 表示部分能力失败/阻塞，`3` 表示全部选定能力都因本地配置缺失而阻塞，`64` 表示参数或显式配置文件错误。没有真实凭据时，JQData 的用户名和密码分别报告为 `BLOCKED/CONFIGURATION`；该命令不把未探测来源写成成功。

## 研报知识库与产业链图谱

电脑端后端启动后访问 `http://<电脑IP>:8765/industry/` 可查看 SVG 产业链图谱（177 条原始子链，支持搜索公司/产品/原材料/环节与事实定位）；访问 `http://<电脑IP>:8765/industry-v2/` 可查看新版券商研报式产业链全景图（浅色上游/中游/下游/服务分区、公司卡片密集、悬浮 F10、搜索/缩放/证据抽屉，完全离线零 CDN；当前展示口径 75 条链 / 7,090 家带代码公司 / F10 CN 5,539 + HK 2,806）。研报流水线全部本地执行，`行业产业链研报/` 不纳入 Git：

```powershell
# 解析/切块/并发抽取（幂等，已处理自动跳过）
desktop\.venv\Scripts\python -m market_monitor reports process --report-root "行业产业链研报" --output-root reports\industry
# 状态跟踪（每篇 report_*.json 带 status/review 标识）
desktop\.venv\Scripts\python -m market_monitor reports status --output-root reports\industry
# 脚本化核验（schema/事实/证据/链归属/警告）
desktop\.venv\Scripts\python -m market_monitor reports verify --output-root reports\industry
# 按产业链聚合并生成 industry-map.html（SVG 图谱）
desktop\.venv\Scripts\python -m market_monitor reports chains --output-root reports\industry
# 生成新版产业链全景图 industry-atlas.html/json（合并 F10 底表 + 旧快照）
desktop\.venv\Scripts\python -m market_monitor reports atlas --output-root reports\industry --data-root data_control
```

核验为脚本化规则核验；未做真实网络检索核验。当前 1 篇待复核（银河证券磷化铟报告，疑似扫描件，建议 OCR）。产物：`reports/industry/report_*.json`、`batch_summary.json`、`chain_index.json`、`industry-map.html`、`industry-atlas.html/json`，快照同步 `data_control/industry/` 并随同步包下发。F10 底表已抓取：A 股 5,539 / 港股 2,806 全市场限速入库 `data_control/industry/f10/`（A 股含收入构成 `revenue_breakdown`；港股无收入构成数据源），重跑 `reports atlas` 即自动合并进全景图。

## Day 0 历史状态（只读，2026-08-04）

Day 0 已停止执行且未封板。桌面单元测试（49 passed）、Android JVM 测试、Debug APK 构建、16 KB 原生库对齐和 16 KB 模拟器主界面启动已实际通过；Android 已可中文显示行情包导入状态，并具备读取已激活 `payload.sqlite` 的标的、周期和 bars 代码。

未达到验收标准的项目包括：真实 Provider 数据探针（当前四个来源均 FAILED/UNSUPPORTED）、基于真实数据生成并导入的签名行情包、已导入 bars 的 K 线查询/展示、Android 端到端验收，以及 Chaquopy + NumPy 策略运行时（NumPy 在 16 KB 设备加载 `libgfortran` 失败）。ADR-0008 已决定后续 Android 改用声明式策略 DSL，但该决定不把历史失败改写为成功。
