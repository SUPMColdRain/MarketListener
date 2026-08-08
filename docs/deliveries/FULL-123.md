# FULL-123 实现交付：Android 导入真实签名包并离线显示 K 线

日期：2026-08-06
状态：实现完成（导入/验证/离线读取链路通过 JVM 与构建验证；真机断网验收待设备）
角色：既有实现（MarketPackageImporter/Reader）+ root（文档补齐）

## 结果

- `MarketPackageImportWorker`：SAF 选包 → 缓存 → WorkManager 验证签名/哈希/Schema/空间/重复/降级 → 激活；`ImportedMarketDataReader` 从冷目录 payload.sqlite 离线读取标的与 K 线；`MainActivity` 行情页展示截止时间、来源与质量，WebView lightweight-charts 离线渲染日线/分钟线并支持周期切换。
- JVM 测试：`MarketPackageVerifierTest`、`ImportedMarketDataTest`、`DatabaseBoundaryTest` 等；Android JVM 全量（当前 65+ 项）全绿。

## 验收门槛与阻塞

- 真实签名行情包需 FULL-122 真实 Provider 产物（当前外部阻塞：东财断连/BaoStock 不可达/缺凭据）。
- Android 13+ 且 16 KB 页面设备（或等效模拟器）断网导入与显示为真实验收，当前无设备证据，如实待验收。

## 状态建议

实现完成，真实断网设备验收待设备与真实包条件满足后执行。

## 统一审查修复（2026-08-06）

按 `docs/reviews/unified-review-data.md` P1-1/P2-4：流水线签名包 payload 现保留 `+08:00` 偏移（`DecodeMarketCandleTest` 覆盖偏移保留与 naive 拒绝）；`decodeMarketCandle` 读取路径有 JVM 测试。

## 独立验收（accept_android2，2026-08-06）

**结论**：`ACCEPTANCE`（维持）。本机可执行部分重跑通过，证据见 `docs/reviews/acceptance-android-dsl-graph.md`；真机断网导入与离线显示未验收，如实不标 `ACCEPTED`。

| 验收项 | 实际命令 | 真实结果 |
|---|---|---|
| Android JVM 全量 | `gradlew -p android testDebugUnitTest --no-daemon --rerun-tasks`（JDK 21 + 临时 subst 盘） | BUILD SUCCESSFUL：20 个 suite / 68 tests / 0 failures / 0 errors / 0 skipped（含 `DecodeMarketCandleTest`、`MarketPackageVerifierTest`、`ImportedMarketDataTest`） |
| Android lint | `gradlew -p android lintDebug --no-daemon` | BUILD SUCCESSFUL：0 errors |

**设备解除条件**：Android 13+ 且 16 KB 页面设备（或等价模拟器）断网导入真实签名行情包并离线显示日线/分钟线；真实签名包依赖 FULL-122 真实 Provider 产物（当前外部阻塞：东财断连/BaoStock 不可达/缺凭据）。
