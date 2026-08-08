# 数据链修复复审（rereview_data_fixes，2026-08-06）

复审范围：`docs/reviews/unified-review-data.md` 中 P1-1～P1-4、P2-1～P2-5、P3 修复项，对应
FULL-122/123/202/203 的“修复后需复审”结论。审查者未修改业务代码。

## 结论

FULL-122、FULL-123、FULL-202、FULL-203：**ACCEPTANCE**。

真实 Provider→签名包端到端验收仍按既有交付记录受外部条件限制（AKShare 端点恢复、BaoStock
可达、JQData/Tushare 凭据），不属于本复审发现的新阻断。

## 修复核验

| 编号 | 修复声明 | 核验结果 |
|---|---|---|
| P1-1 | Silver→Parquet 往返保留时区偏移；签名包 payload 含 `+08:00`；Android 解码偏移保留/naive 拒绝 | `pipeline._read_parquet` 只读 `bar_json` 还原；`test_pipeline_preserves_timezone_offsets_in_package_payload` 断言包内字节含 `+08:00`；`DecodeMarketCandleTest` 2 项（偏移保留、naive 拒绝）在全新 Android JVM 运行中通过 |
| P1-2 | 复用分区键合并去重、不丢历史 | `write_silver_bars` 读旧分区按 `(instrument_id, bar_period, bar_open_time)` 合并后原子重写；`test_cursor_resume_and_idempotent_rerun` 断言分区 `row_count=2` |
| P1-3 | 陈旧锁 TTL 抢占 | `acquire_lock(lock_ttl_seconds=3600)` + `_is_stale_lock`；`test_stale_lock_is_taken_over_after_ttl` 通过 |
| P1-4 | OHLC 必填为正有限数、成交量必填非负 | `_valid_ohlc`/`_valid_volume` 实现；空 bar/负 OHLC/缺 volume 均阻断，专项测试通过 |
| P2-1 | AKShare 日线能力入探针且失败隔离 | `_probe_bars` 产出 `cn_stock_sh.600519_1d`；失败时仅该项 FAILED，其余能力保留，专项测试通过 |
| P2-2 | 任一 ingest FAILED → `INGEST_FAILED` 不打包 | `pipeline.run` 实现；专项测试通过；手工双单元（1 FAILED + 1 PASS）验证聚合为 `INGEST_FAILED`、不打包且 PASS 单元数据仍落盘 |
| P2-3 | 采集写 Bronze；`ops_cli package_from_silver` 白名单步骤 | `IncrementalCollector.collect` 调用 `write_bronze`（手工验证 Bronze 文件落盘）；`ops_cli` 端到端手工验证：分区→签名包→账本 ACTIVE，退出码 0 |
| P2-4 | FULL-123 的 Android 解码测试存在 | `DecodeMarketCandleTest.kt` 存在且 `decodeMarketCandle` 用 `OffsetDateTime.parse`（naive 抛错返回 null），2 项通过 |
| P2-5 | 质检/流水线接入 `expected_offset` 与 `reference_bars` | `pipeline.quality/run` 参数接线；时区不匹配阻断测试通过；手工验证 `reference_bars` 差异经 `pipeline.run` 产出 CROSS_SOURCE ERROR 并 QUARANTINED |
| P3 | manifest status 枚举、`capability_for` ValueError、包哈希核对、DELTA base 校验 | Schema 含 `PARTIAL_FAILURE`/`BLOCKED` 且手工 `validate_contract` 通过；`capability_for` 未烘焙/未知角色抛 ValueError（手工验证）；`verify_market_package` 拒绝篡改 payload（手工验证）；DELTA 未注册 base 拒绝测试通过 |

## 自动化证据

| 验证项 | 结果 |
|---|---|
| 桌面全量 pytest | 434 项收集、全量通过（exit 0） |
| 修复相关专项 pytest（pipeline/incremental/quality/akshare/baking/market_package/signing/contracts/cli/ops） | 88 项通过 |
| Ruff（desktop/src、desktop/tests） | 全部通过 |
| Android JVM 全量（clean 后重跑） | 20 个 suite、68 项测试，0 失败/0 错误/0 跳过 |
| `git diff --check` | 仅 CRLF 提示，无空白错误 |

## 非阻断建议（不要求本轮返工）

- `package_from_silver` CLI 步骤、`capability_for` 的 ValueError、`verify_market_package`
  payload 哈希拒绝暂无专项自动化测试，本复审已手工验证通过；建议后续补固化测试。
- `verify_market_package` 未显式拒绝重复 `manifest.json` 条目；因签名覆盖 manifest 字节且读取为
  最后条目，重复完全相同的 manifest 不影响包内容完整性，仅建议加固。
