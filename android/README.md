# android（Android 13+ 消费端）

Android 消费端基于 Kotlin + Jetpack Compose，`minSdk=33`。当前基线包含签名行情包导入、中文导入状态、已激活 `payload.sqlite` 的只读查询和本地 Lightweight Charts K 线转换代码；Day 0 已停止且未完成真实数据验收。正式任务从 `../START_HERE.md` 和 `../STATUS.md` 启动，历史事实见 `../docs/正式开发交接.md`。

## 环境

- JDK 20（当前按用户要求使用 `C:\Program Files\OpenJDK\jdk-20.0.2`；Plan 默认 JDK 21 LTS 可后续恢复）
- Android SDK（`local.properties` 的 `sdk.dir` 指向本机 SDK；缺失平台 AGP 会自动下载）
- Gradle Wrapper 8.5、AGP 8.3.2、Kotlin 2.0.0、Compose BOM 2024.06.00

## 命令

```powershell
android\gradlew.bat -p android testDebugUnitTest
android\gradlew.bat -p android assembleDebug
```

注意：Windows 中文路径会导致 JVM 单元测试 worker 加载测试类失败。请通过英文 junction
`C:\Users\qingd\Documents\MarketListener` 打开项目并在其中执行命令。

后续开发不自动继续 `Plan.md` 的 D0 任务；架构和数据边界仍以 `../ADR.md` 为准。
