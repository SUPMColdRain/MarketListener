---
status: superseded
superseded_by: ADR-0008
---

# Android 通过签名策略包运行嵌入式 Python

> 本决策已由 ADR-0008 取代，仅保留为 Day 0 历史背景。Android 正式实现使用声明式策略 DSL，不再嵌入 Python。

用户需要运行任意 Python 策略逻辑，因此 Android 使用嵌入式 Python，并通过策略包交付脚本、参数、输入契约和测试向量。为控制兼容性和代码来源，App 不允许运行时安装依赖，只执行由个人电脑签名且依赖位于白名单中的策略包。

## Consequences

Day 0 白名单仅包含 Python 标准库和 NumPy。嵌入式 Python 不被视为不可信代码沙箱；脚本在独立进程中运行并设置超时，但安全前提仍是策略包由用户本人生成和签名。
