---
status: accepted
---

# Android 13+ 原生单端

项目只服务 Android 13+ 手机，客户端采用 Kotlin 与 Jetpack Compose，不继续保留 Flutter 和 iOS。放弃跨平台能力，换取 Room、WorkManager、系统文件选择器、Android Keystore、独立进程和嵌入式 Python 的直接集成，并减少低成本 Agent 同时维护 Dart 与原生桥接代码的负担。

## Consequences

项目不接受为了“以后可能支持 iOS”而引入的抽象层；如果未来重新支持其他平台，必须新增 ADR 并重新评估策略运行时和本地数据库方案。
