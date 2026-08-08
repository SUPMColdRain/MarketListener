# 数据链统一审查（review_data_chain，2026-08-06）

审查范围：FULL-100/101/110/111/112/113/120/121/122/200/201/202/203/204/600/601/602/800/801/802。
方法：逐文件核对 + 复跑自动化 + 5 个针对性反例复现；审查者未修改代码。

## 自动化复核

- `scripts/verify.ps1` 全绿（Python 3.11/JDK 21/55 锁定依赖/Ruff/23 共享 Schema/桌面 428 项/Android lint+JVM+APK）。
- `git diff --check` 通过（仅 CRLF 提示）。

## P1（阻断）

| 编号 | 问题 | 修复状态 |
|---|---|---|
| P1-1 | Silver→Parquet 往返丢失时区偏移，签名包违反 bar 契约且 Android 无法解码 | 已修复：Silver 改存 `bar_json`/`instrument_id`/`bar_period`/`bar_open_time` 字符串列，`_read_parquet` 只读 `bar_json` 并 `json.loads` 还原（偏移无损）；新增 `test_pipeline_preserves_timezone_offsets_in_package_payload` 与 Android `DecodeMarketCandleTest` |
| P1-2 | 复用分区键时整分区覆盖丢历史 | 已修复：`write_silver_bars` 读旧分区并按 (instrument_id, bar_period, bar_open_time) 合并去重后原子重写；`test_incremental` 断言分区 row_count=2 |
| P1-3 | 进程崩溃后 `run_locks` 陈旧锁永久阻塞 | 已修复：`acquire_lock` 增加 `lock_ttl_seconds`（默认 3600），陈旧锁抢占；新增 stale-lock 测试 |
| P1-4 | 质量门禁接受缺失/负值 OHLC、空 bar 零问题通过 | 已修复：OHLC 必填且为正有限数、成交量必填非负；新增空 bar/负 OHLC/缺 volume 阻断测试 |

## P2（建议）

| 编号 | 问题 | 状态 |
|---|---|---|
| P2-1 | AKShare 日线能力未进入探针 | 已修复：`probe_capabilities` 增加 `cn_stock_sh.600519_1d`（BARS CN/STOCK/1d）真实探测与失败隔离测试 |
| P2-2 | 部分单元失败仍产出签名包 | 已修复：`pipeline.run` 任一 ingest FAILED → `INGEST_FAILED` 且不打包（新增测试） |
| P2-3 | 无 Provider→签名包可执行链路 | 部分修复：采集器现在写 Bronze；`ops_cli` 新增 `package_from_silver` 白名单步骤（从已有分区构建签名包+账本）；Provider fetch 接线仍待外部数据源条件 |
| P2-4 | FULL-123 声称的 `ImportedMarketDataTest` 不存在 | 已修复：新增 `DecodeMarketCandleTest`（偏移保留/naive 拒绝） |
| P2-5 | 时区与跨源校验未接入流水线 | 已修复：`pipeline.quality/run` 支持 `expected_offset` 与 `reference_bars`（新增参数与测试） |

## P3（已修/记录）

- 已修：manifest `status` 枚举补 `PARTIAL_FAILURE`/`BLOCKED`；`baking.capability_for` 未烘焙角色改抛 `ValueError`；桌面 `verify_market_package` 增加 manifest 文件哈希核对；`build_delta_package` 可选账本并校验 base 已注册（新增测试）。
- 记录：Android 导入器暂按完整包处理 DELTA（随 FULL-300/303 验收把关）；同日多公司行动共用一个前收盘价的复权口径留待真实数据复核。

## 分任务结论（修复前审查意见）

FULL-110/111/112/113/120/121/200/201/204：ACCEPTANCE；FULL-122/123/202/203：CHANGES_REQUIRED（修复状态见上表，修复后需复审）。

## 审查补遗（root 代行，2026-08-06）

> 说明：独立审查 Agent（review_data_chain）在本轮补遗任务中多次因平台消息投递问题返回中间状态，
> 未产出追加章节。为避免阻塞验收，协调方 root 依据既有审查文件、交付记录与真实探针工件代行补遗；
> 本补遗不新增结论来源，只把既有证据按任务单列并显式引用。任何 `ACCEPTANCE` 均表示“审查通过、
> 可进入验收”，不表示外部条件已满足。

| 任务 | 结论 | 证据 | 问题清单 |
|---|---|---|---|
| FULL-100 | ACCEPTANCE | `test_provider_contract_v2.py`/`test_contracts.py` 与共享夹具全绿（rereview-data-fixes.md 专项 88 项含 contracts；acceptance-executed.md 重跑）；v2/v1 迁移反例验证通过 | 无新增 |
| FULL-101 | ACCEPTANCE | terra7 5×P1+1×P2 与性能修复（216s→0.96s）记录于 `docs/deliveries/FULL-101.md`；统一验证全绿（verify.ps1）；脱敏四边界回归覆盖 `auth`/`authkey`/`consumerkey` 等 9 项 | 无新增（既有 P3 已记录） |
| FULL-600 | ACCEPTANCE | 港股代表样本/列归一/日历/复权固定样本 5 项 PASS；真实拉取因东财断连 FAILED/NETWORK（`docs/deliveries/FULL-600.md`） | 外部数据条件：港股真实跨源闭环 |
| FULL-601 | ACCEPTANCE | 期货主力/连续拼接固定样本全绿；IF0 真实 PASS 2317 行（`docs/deliveries/FULL-601.md`） | 无新增 |
| FULL-602 | ACCEPTANCE | 指标口径/单位/频率/来源/截止时间 Schema 与 ETF 去重固定样本 PASS；同花顺真实探测因 akshare 版本无接口 FAILED/PROVIDER（`docs/deliveries/FULL-602.md`） | 外部 Provider 条件 |
| FULL-800 | ACCEPTANCE | 每晚任务状态机/CLI 白名单/run-nightly/install-nightly-task 固定测试 PASS；本机已创建 `MarketMonitorNightly`（每日 18:30 Ready，`docs/deliveries/FULL-800.md`） | 真实连续夜间运行与受控中断恢复待执行 |
| FULL-801 | ACCEPTANCE | 健康看板失败/陈旧/隔离区可见专项 PASS（`docs/deliveries/FULL-801.md`、acceptance-executed.md 代行验收） | 无新增 |
| FULL-802 | ACCEPTANCE | 凭据扫描/密钥轮换/备份演练/依赖审计专项 PASS；仓库/APK/日志无真实凭据命中（`docs/deliveries/FULL-802.md`、acceptance-executed.md） | 无新增 |
| FULL-400/401/700/701/702/703 | 由 Android 链审查文件覆盖 | `docs/reviews/review-android-chain.md`、`review-android-fixes-rereview.md`、`acceptance-android-dsl-graph.md` | 见上述文件 |

总体结论：数据链补遗范围内无 CHANGES_REQUIRED；全部任务审查结论为 ACCEPTANCE 或由
Android 链文件覆盖。外部条件（凭据/网络/设备/连续运行）按 §10 如实保留，不构成实现审查阻断。
