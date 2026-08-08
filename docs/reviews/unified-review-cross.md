# 跨切面统一审查（review_cross_cutting，2026-08-06）

审查范围：STATUS/交付索引一致性、门控合规、凭据与夹具、发布准备、跨模块接线。

## 发现与处理

### P1：复盘净值功能未接线真实收盘价

- 现象：`TradingScreen(repository)` 的 `prices` 初始为空且无外部数据源；`repository.stats(prices)` 以空收盘价计算净值，`markedWithFallback` 会标记但界面净值曲线缺少真实行情。
- 修复：`TradingScreen(repository, marketData)` 从行情包首只标的口线初始化 `DailyClose`（epochDay/close），MainActivity 传入 `marketData`；保留手动价格输入覆盖能力。已编译验证（Android JVM 68 项全绿）。

## 一致性核验（本次执行）

- `verify.ps1` 全量通过；桌面 pytest/Ruff 全绿；Android JVM 68 项全绿。
- STATUS 无重复行、无虚假 ACCEPTED（仅 001/002/003/100 为 ACCEPTED）；交付索引已补全全部 FULL-*。
- 门控：FULL-610（QMT 未开通）、FULL-804（连续 20 次成功与用户批准未达成）如实 BLOCKED；无未批准付费/云资源。
- 凭据：交付记录中的 `REVIEW_*` 等为合成值；仓库扫描未发现真实凭据。
- 发布准备：`scripts/check-16kb.ps1` 在 Debug APK 实测 PASS；`docs/release-checklist.md` 覆盖 803/900 要求。

## 结论

阻断问题已修复；跨切面无遗留 P0/P1。
