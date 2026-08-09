# Experience

本文件记录可复用的工程经验、环境约束和踩坑结论。它不是 ADR；任何架构改变仍须以 `ADR.md` 为准。

## 环境与构建

- Android Studio 从 `C:\Users\qingd\Documents\MarketListener\android` 打开项目；命令行 JVM 测试须把仓库临时 `subst` 到纯英文盘符。JDK 21 会把 junction 规范化回中文物理路径，仅使用 junction 仍会导致测试类 `ClassNotFoundException`。
- FULL-002 锁定的构建组合为 Gradle 8.5、AGP 8.3.2、Kotlin 2.0.0、JDK 21；Gradle 配置会拒绝其他 Java 主版本。当前实测 JBR 21.0.11 成功。
- Android Studio 的 Gradle JDK 应选择任一受信任的 JDK 21。出现空 Module 时，先等待 Gradle Sync 成功，不要手工创建空的 Run Configuration。
- Debug APK 需要使用 Gradle Wrapper 构建，避免依赖全局 Gradle 安装。

## Android 原生库与 16 KB 页大小

- 旧工件 `net.zetetic:android-database-sqlcipher:4.5.4` 已弃用，且 `libsqlcipher.so` 不满足 16 KB 页大小要求。
- 当前项目使用 `net.zetetic:sqlcipher-android:4.6.1`，并在创建加密 Room 数据库前执行 `System.loadLibrary("sqlcipher")`。
- 不直接升级到 `sqlcipher-android:4.17.0`：该工件的 Kotlin 2.1 metadata 会被当前 Room 2.6.1 的注解处理器拒绝。升级 SQLCipher、Room、Kotlin 和 AGP 时应作为一个回归组合处理。
- 不能仅以 APK 可以安装判断兼容性。已用 `zipalign -c -P 16` 和 APK 内 ELF `PT_LOAD` 对齐检查验证四种 ABI 均为 `0x4000`。
- 16 KB 检查必须覆盖 APK 中与运行时按需解压的原生依赖。Chaquopy 17.0.0 的 Python 3.13 本体可启动，但 NumPy 1.26.2 所依赖的 `chaquopy-libgfortran` 在 x86_64 16 KB 模拟器实际为 `PT_LOAD=0x1000`，会在 `import numpy` 时被链接器拒绝。

## 数据与验收

- Android 是离线消费端，不直接保存数据源凭据或在线抓取行情。数据闭环应为：电脑端真实 Provider 探测 -> 清洗/质量检查 -> 签名行情包 -> 手机导入。
- 空 K 线或空数据状态不能用演示数据伪装成真实验收。导入状态应显示 Worker 的真实成功或失败分类。
- Android 已实现对激活 `payload.sqlite` 的标的、周期和 bars 读取，并在离线 WebView 中转换为 K 线；在真实签名包导入前，这只是代码与 JVM 测试覆盖，不是数据验收。
- Provider 只有在实际样本、周期、行数和时间范围被记录后才可标记 `PASS`。认证、网络和安装失败必须保留为 `FAILED` 或 `UNSUPPORTED`。
- Provider 探测必须对单一上游挂起设上限。当前 CLI 的 `--timeout-seconds` 会将超时来源记录为 `NETWORK` 并继续其他来源，报告仍须保留全部失败事实。
- Day 0 封板必须同时具备真实数据包、手机离线导入/查询/策略执行和端到端验收；单元测试与 APK 构建不能替代。
- 研报流水线对纯扫描件 PDF 无法抽取事实：720 篇中 1 篇（银河证券磷化铟光器件报告）未抽取到任何事实且警告过多，被规则核验标记为待复核，需要 OCR 或人工处理；流水线状态机保证已 `REVIEWED` 的篇目不会重复解析。
- Windows 中文控制台下，pytest 子进程 reader 可能因 GBK 解码抛 `UnicodeDecodeError` 线程警告（不导致失败），属子进程输出编码问题；运行前设置 `PYTHONIOENCODING=utf-8` 并将控制台输出编码切到 UTF-8 可消除。

## 策略运行时

- Chaquopy 17.0.0 + Python 3.13 能离线打包 NumPy 1.26.2，但在当前 16 KB Android 设备导入失败，根因是 NumPy 的 OpenBLAS/GFortran 依赖尚非 16 KB 对齐。按 Plan 停止 D0-050；不得改成运行时联网安装、桌面替代验收或未经 ADR/用户决定替换工具链。

## 新会话接手顺序

1. 正式任务统一从 `START_HERE.md` 和 `STATUS.md` 启动，并按角色读取 `Plan_full.md`、ADR、当前交付记录以及本文件中的相关环境事实。
2. `docs/正式开发交接.md`、`Plan.md` 与 `docs/deliveries/D0-*` 是计划固化前和 Day 0 的历史证据，不是正式开发入口，也不自动重试 D0 任务。
3. 项目目标和任务依赖已在 `Plan_full.md` 固化；版本控制基线由 `FULL-002` 建立，真实验收条件由各 `FULL-*` 任务定义，不在新会话中重新发明平行计划。
