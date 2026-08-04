---
status: accepted
date: 2026-08-04
supersedes: ADR-0004
---

# ADR-0008：Android 使用声明式策略 DSL

## 背景

ADR-0004 原计划在 Android 内通过 Chaquopy 运行签名 Python 策略。实际验证中，Chaquopy 17.0.0 能离线打包 NumPy，但 NumPy 的 `libgfortran` 在 16 KB 页面设备上以 4 KB 对齐被系统拒绝。继续等待该原生依赖会阻塞 Android 13+、16 KB 发布基线，而且嵌入式 Python 仍不是不可信代码沙箱。

## 决定

Android 不再嵌入或执行 Python 策略。移动端策略使用版本化、声明式、可校验的 Strategy DSL：

- DSL 以 JSON Schema 定义允许的输入、参数、指标、运算符、条件组合和信号输出。
- Android 只执行 Kotlin 实现的白名单节点；未知节点、任意代码、网络访问、文件访问和动态依赖一律拒绝。
- 数据生产端保留 Python，用于扫描、回测、策略研究和 DSL 参考解释器；Python 逻辑只有转换为受支持 DSL 后才能在 Android 运行。
- DSL 包继续签名并携带版本、默认参数、输入要求和共享测试向量。
- 桌面参考解释器与 Kotlin 解释器必须通过共享向量验证离散结果一致，并明确浮点误差阈值。
- 信号仍只包含候选标的、触发条件、观察理由和风险标签，不是交易指令。

## 替代方案

- 继续等待 Chaquopy/NumPy 16 KB 支持：时间和兼容性不可控，拒绝作为主路径。
- 运行时下载 Python 或原生依赖：违反离线、安全和依赖锁定约束，拒绝。
- 在 WebView 中执行任意 JavaScript 策略：扩大攻击面且难以保证一致性，拒绝。
- Android 完全不运行策略：无法满足小范围离线重算需求，拒绝。

## 后果

- 本 ADR 取代 ADR-0004；ADR-0004 保留为历史决策与失败背景，不再指导新实现。
- 既有 Chaquopy 试验失败保持历史事实，不需要继续修复 NumPy 工具链。
- DSL 表达力受白名单约束；新增运算符或指标必须升级 Schema、两端解释器和共享向量。
- Android 不获得数据库连接、Context、网络、文件或个人交易记录等非声明式能力。

