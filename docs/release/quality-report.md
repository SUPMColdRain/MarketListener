# 质量报告（FULL-900 封板准备，2026-08-06）

## 自动化基线（本轮实测）

| 项 | 命令 | 结果 |
|---|---|---|
| 统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS（2026-08-06 02:17，42s） |
| Python | `python --version`（verify 内） | 3.11.0 |
| JDK | `java -version`（verify 内） | 21.0.11 |
| 锁定依赖 | verify 内 requirements.lock 核对 | 55 项 exact 一致 |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | 全部通过 |
| Schema 夹具 | verify 内共享夹具专项 | 23 项全过 |
| 桌面测试 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests -q` | 434 项全过（收集计数）；仅既有 ZIP 同名 `manifest.json` 警告 |
| Android lint | `gradlew -p android lintDebug --no-daemon`（JDK21+subst） | BUILD SUCCESSFUL，0 errors |
| Android JVM | `gradlew -p android testDebugUnitTest --no-daemon` | BUILD SUCCESSFUL，20 suite / 68 tests / 0 failures |
| Android APK | `gradlew -p android assembleDebug/assembleRelease --no-daemon` | BUILD SUCCESSFUL |
| 空白检查 | `git diff --check` | exit 0（仅 gradle.lockfile CRLF 提示） |
| 金标图谱 | `python -m market_monitor.industry_graph.evaluate` | 实体 P/R/F1=1.0（10/10）；关系 1.0（8/8），超阈值 |

## 质量门禁

- OHLC 必填且为正有限数、成交量必填非负；缺失/负值/空 bar 阻断（`docs/reviews/rereview-data-fixes.md`）。
- 时区偏移经 Silver→Parquet→签名包往返无损（`+08:00` 断言）；naive 时间被 Android 解码拒绝。
- 任一 ingest FAILED 不产出签名包（`INGEST_FAILED`）；陈旧锁 TTL 抢占；分区合并去重不丢历史。
- 仓库/APK/日志无真实凭据命中（`scan_for_credentials`，FULL-802）。
- 依赖审计 `pip check` 无冲突（FULL-802）。

## 已知缺口（完整清单见 `docs/release/known-gaps.md`）

- P2：FULL-303 清理 IOException 未捕获；FULL-404 主线程解释器/历史参数重启丢失；FULL-503 PBKDF2/文件 IO 主线程、`storedIterations` 无下限；FULL-504 多标的收盘价回退、备份主线程；FULL-704 快照无大小限制/解析失败提示。
- P3：Android 端多处已知可维护性缺口（双 UserDatabase、WebView allowFileAccess、无 Compose/仪器化测试等）。
- 外部条件：凭据（JQData/Tushare）、网络端点（东财/BaoStock/同花顺/港股）、Android 13+ 16KB 真机、Release keystore、FULL-800 连续运行、FULL-804 用户批准。
