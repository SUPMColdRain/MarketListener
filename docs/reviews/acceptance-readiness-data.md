# 数据链验收就绪扫描（accept_data2，2026-08-06）

角色：验收角色（只读就绪扫描，未修改任何业务代码，未给出 `ACCEPTED` 结论）。
依据：`STATUS.md`、`Plan_full.md` 状态机与验收标准、`docs/deliveries/FULL-*.md`、`docs/reviews/*.md`、`artifacts/`。

## 方法

1. 逐一核验数据链 25 个交付记录文件存在且包含结构化章节；
2. 核验独立审查证据文件及其对各任务的显式结论；
3. 核验被引用的真实探测工件存在；
4. 按 `Plan_full.md` 依赖链与“验收角色只领取 ACCEPTANCE”规则判断正式验收可启动性；
5. 外部条件（凭据/网络/设备/付费批准）以交付记录与状态表原文为准，不擅自改写为成功。

## 交付记录核验（全部存在，结构完整）

`FULL-101/110/111/112/113/120/121/122/123/200/201/202/203/204/400/401/600/601/602/700/701/702/703/800/801/802`
均有 `docs/deliveries/FULL-*.md`，含“结果/实际验证/数据源状态/风险与未完成项/状态建议”等必要章节。

## 审查结论核验

| 证据文件 | 显式结论 |
|---|---|
| `docs/reviews/unified-review-data.md` | `FULL-110/111/112/113/120/121/200/201/204`：ACCEPTANCE；`FULL-122/123/202/203`：CHANGES_REQUIRED（修复后需复审） |
| `docs/reviews/rereview-data-fixes.md` | `FULL-122/123/202/203`：ACCEPTANCE（P1-1~P1-4、P2-1~P2-5、P3 修复核验通过；真实 Provider→签名包仍受外部数据源条件限制） |
| `docs/reviews/unified-review-cross.md` | 跨切面无遗留 P0/P1；`FULL-610/804` 如实 BLOCKED |
| `docs/reviews/review-android-chain.md` + `review-android-fixes-rereview.md` | Android 集群 13 项 ACCEPTANCE（本扫描不重复验收，属于 `accept_android` 范围） |

## 工件核验

- `artifacts/full-110-akshare/`：3 个文件存在；
- `artifacts/full-113-baostock/`：5 个文件存在；
- `artifacts/full-702-gold-eval.json`：753 B 存在；
- `artifacts/pytest-review.txt` 等证据文件存在。

## 各任务就绪判定

| 任务 | 交付记录 | 审查结论 | 正式验收可启动性 | 判定 |
|---|---|---|---|---|
| FULL-101 | 有（含 terra7 全部 P1/P2 修复记录） | 最新为 terra7 `CHANGES_REQUIRED`，修复已完成但无修复后独立复审结论 | 否（状态仍 `REVIEW`） | PENDING_REVIEW |
| FULL-110/111/112/113 | 有 | ACCEPTANCE（unified-review-data） | 依赖 FULL-101 未 ACCEPTED；真实数据条件：AKShare 部分 FAILED/NETWORK、JQData/Tushare 缺凭据、BaoStock 不可达 | GATED_BY_101 + EXTERNAL_DATA |
| FULL-120 | 有 | ACCEPTANCE（unified-review-data） | 依赖 110–113 至少三个 ACCEPTED；真实三源门槛未满足 | GATED_BY_101 + EXTERNAL_DATA |
| FULL-121 | 有 | ACCEPTANCE（unified-review-data） | 依赖 120 | GATED_BY_101 |
| FULL-122/123 | 有 | ACCEPTANCE（rereview-data-fixes） | 依赖 121/122；真实签名包与断网真机验收待设备/数据源 | GATED_BY_101 + EXTERNAL_DEVICE |
| FULL-200/201/202/203/204 | 有 | ACCEPTANCE（unified-review-data / rereview-data-fixes） | 依赖链 121→200/201→202→203→204 | GATED_BY_101 |
| FULL-400/401 | 有 | 无独立审查文件覆盖 | 否（缺审查结论） | PENDING_REVIEW |
| FULL-600/601/602 | 有 | 列于统一审查范围行，但审查文件未给单列结论 | 否（缺显式结论） | PENDING_VERDICT |
| FULL-700/701/702/703 | 有 | 无独立审查文件覆盖（704 属 Android 集群） | 否（缺审查结论） | PENDING_REVIEW |
| FULL-800/801/802 | 有 | 列于统一审查范围行，但审查文件未给单列结论；800 真实连续夜间运行未达成 | 否 | PENDING_VERDICT + EXTERNAL_RUN |
| FULL-610 | 有（BLOCKED 记录） | 门控 | 用户未开通 QMT | BLOCKED_EXTERNAL |
| FULL-804 | 有（BLOCKED 记录） | 门控 | 连续 20 次成功未达成且付费需用户书面批准 | BLOCKED_EXTERNAL |

## 结论与建议

1. 数据链中**唯一持有正面审查结论且依赖链完整**的候选集为
   `FULL-110/111/112/113/120/121/122/123/200/201/202/203/204`，
   但正式验收一律被 `FULL-101`（未 ACCEPTED）门禁，现阶段按状态机不得领取。
2. `FULL-400/401/700/701/702/703` 与 `FULL-600/601/602/800/801/802`
   缺少可引用的独立审查结论，需要审查角色补齐后再进入验收入口。
3. 本扫描未执行任何测试命令（父代理正在实施 FULL-101 修复，避免并发污染）；
   待状态表将上述任务置为 `ACCEPTANCE` 后，`accept_data2` 将逐任务重跑
   交付记录中的实际命令、核验工件并写独立验收章节，再更新状态。

本文件为就绪扫描，不构成任何任务的 `ACCEPTED` 验收。
