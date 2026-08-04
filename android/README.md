# android（Android 13+ 消费端）

Android 消费端基于 Kotlin + Jetpack Compose，`minSdk=33`。当前基线包含签名行情包导入、中文导入状态、已激活 `payload.sqlite` 的只读查询和本地 Lightweight Charts K 线转换代码；Day 0 已停止且未完成真实数据验收。正式任务从 `../START_HERE.md` 和 `../STATUS.md` 启动，历史事实见 `../docs/正式开发交接.md`。

## 环境

- JDK 21（`.java-version`；Gradle 配置会拒绝其他主版本）
- Android SDK Platform 34 revision 3、Build Tools 34.0.0（`local.properties` 的 `sdk.dir` 只保存本机路径，不入库）
- Gradle Wrapper 8.5（分发 SHA-256 已固定）、AGP 8.3.2、Kotlin 2.0.0、Compose BOM 2024.06.00
- `gradle.lockfile` 固定 Android 传递依赖；权威版本清单见 `../toolchain.versions.toml`

## 命令

```powershell
$env:JAVA_HOME = "C:\path\to\jdk-21"
android\gradlew.bat -p android testDebugUnitTest
android\gradlew.bat -p android assembleDebug
```

注意：Windows 中文物理路径会导致 JVM 单元测试 worker 加载测试类失败，而且 JDK 21 会把英文 junction 解析回物理路径。命令行测试应先把仓库临时映射到空闲盘符（示例：`subst M: <仓库绝对路径>`），从 `M:\` 执行上述 Gradle 命令，最后用 `subst M: /D` 释放盘符。Android Studio 可继续从英文 junction `C:\Users\qingd\Documents\MarketListener\android` 打开。

完整基线请从仓库根目录运行 `powershell -ExecutionPolicy Bypass -File scripts\verify.ps1`。该脚本显式验证并使用 `C:\Users\qingd\.jdks\jbr-21.0.11`，自动选择空闲临时盘符，且在失败时仍清理该映射。

后续开发不自动继续 `Plan.md` 的 D0 任务；架构和数据边界仍以 `../ADR.md` 为准。
