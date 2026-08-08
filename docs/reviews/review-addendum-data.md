# 审查补遗指令（review_data_chain，2026-08-06）

请追加单列审查结论到 `docs/reviews/unified-review-data.md`（只读审查，不修改代码）：

1. FULL-100：Provider Contract v2 契约/迁移/共享夹具审查结论（复跑 desktop\tests\test_provider_contract_v2.py、test_contracts.py）。
2. FULL-101：terra7 P1/P2 全部修复与性能修复（216s→0.96s）后的独立复审结论（复跑 test_configuration.py、test_provider_runner.py、test_cli.py、test_joinquant_provider.py；抽查 terra7 反例与四边界）。
3. FULL-600/601/602：按 docs/deliveries/FULL-600~602.md 与 market_expansion 实现/固定样本/真实探针证据给出单列结论（港股 FAILED、IF0 PASS 2317 行、同花顺 FAILED 如实记录）。
4. FULL-800/801/802：按 ops/dashboard/security_audit 实现、专项测试与计划任务创建证据给出单列结论。
5. FULL-400/401/700/701/702/703 如不在你的范围，在结论表中注明“由 Android 链审查文件覆盖（docs/reviews/review-android-chain.md / rereview-android-fixes.md）”。

每项输出：任务/结论（ACCEPTANCE 或 CHANGES_REQUIRED）/证据/问题清单（P0-P3，无则“无”）。追加后给出总体结论。不要改 STATUS.md。
