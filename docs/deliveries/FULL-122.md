# FULL-122 实现交付：真实数据进入 Bronze/Silver、质检、签名行情包

日期：2026-08-06
状态：实现完成（编排链路与固定样本通过；真实 Provider 运行证据受 FULL-110~113 外部条件限制，如实记录）
角色：root 实现

## 范围与边界

把既有存储（Bronze/Silver）、质检、隔离区、签名、打包、账本组件编排为一条端到端流水线：增量采集 → Silver → 质检 → 阻断进隔离区 → 签名包 → 账本激活。包内数据可追溯到来源 run、数据截止时间与质量报告；单元测试使用固定夹具（明确非真实行情），真实 Provider 运行按 FULL-110~113 的状态如实受控。

## 修改文件

- `desktop/src/market_monitor/pipeline.py`（新增）：`IngestUnit`、`MarketPipeline`（ingest/quality/package/run），Parquet 读回做递归 JSON 安全归一（date/datetime/bytes），签名后立即自校验，账本注册并激活。
- `desktop/tests/test_pipeline.py`（新增）：全链路成功（签名包+账本 ACTIVE+自校验通过）与阻断隔离（负成交量 → QUARANTINED、不打包）。

## 验收要点对应证据

| 验收标准 | 证据 |
|---|---|
| 存储/质检/签名单元 | `test_pipeline_ingests_quality_signs_and_activates_ledger`：PASS 采集 → 质检通过 → 签名包生成 → `verify_market_package` 为真 → ledger ACTIVE |
| 包内不存在模拟行情 | 单元测试固定数据仅用于链路验证并在交付记录明示；真实包必须来自 Provider 真实能力，当前因 AKShare 快照/资金 FAILED、BaoStock 不可达、JQData/Tushare 缺凭据而无法完成“真实运行到签名包”，不伪造 |
| 来源、截止时间和质量可追溯 | 包 manifest 含 source_run_summaries、data_cutoff、partition/files 哈希；质量报告随包写入 |
| 阻断进隔离区 | `test_pipeline_quarantines_blocking_bars_without_packaging`：blocking 报告写入 quarantine，不产出包 |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 流水线 + 烘焙专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_pipeline.py desktop\tests\test_baking.py -q` | PASS（7 项） |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src\market_monitor\pipeline.py desktop\tests\test_pipeline.py` | PASS |

## 风险与未完成项

- 真实 Provider→签名包的端到端验收需等待：东财端点恢复（FULL-110）、BaoStock 可达（FULL-113）、用户配置 JQData/Tushare 凭据（FULL-111/112）；届时由验收角色重跑 `MarketPipeline.run` 并核对包内无模拟数据。
- Android 导入真实包（FULL-123）与设备验收待此链路的真实产物。

## 状态建议

实现完成，等待系列统一审查；真实运行证据按外部条件如实 BLOCKED。

## 统一审查修复（2026-08-06）

按 `docs/reviews/unified-review-data.md`：P1-1（Parquet 往返保留时区偏移，`bar_json` 无损存储）、P1-2（分区合并去重不丢历史）、P2-2（任一 ingest FAILED 即 `INGEST_FAILED` 不打包）、P2-3（采集写 Bronze；CLI 新增 `package_from_silver` 步骤）、P2-5（质检接入 expected_offset/reference_bars）；修复后桌面全量与 Android JVM 68 项全绿。
