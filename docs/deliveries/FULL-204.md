# FULL-204 实现交付：热包、冷分片、增量包、签名与回滚

日期：2026-08-06
状态：实现完成（桌面层；等待系列统一审查）
角色：root 实现

## 范围与边界

在既有不可变整包构建与 Ed25519 签名基础上新增：DELTA 增量包契约、包账本与激活/回滚协议；冷分片与热包复用 `build_market_package`（按分区维度切分）。Android 侧增量应用与回滚 UI 接入属于 FULL-300/303（后续任务）。

## 修改文件

- `contracts/market-package-manifest.schema.json`：新增可选 `package_type`（FULL/DELTA）与 `base_package_id`；`package_type=DELTA` 时必须提供 `base_package_id`（`if/then` + `required`，旧 manifest 保持有效）。
- `desktop/src/market_monitor/market_package.py`：
  - `build_market_package` 增加关键字参数 `package_type`/`base_package_id`；DELTA 缺 base 拒绝。
  - `build_delta_package`：增量包快捷构建（manifest 带 `package_type=DELTA` 与 base 引用）。
  - `PackageLedger`：包注册（防重复）、`activate`（旧 ACTIVE→SUPERSEDED）、`rollback_to`（当前→ROLLED_BACK、目标→ACTIVE、未知包拒绝）。
- `tests/fixtures/contracts/`：新增 DELTA 合法/非法 manifest 正反例并接入 `cases.json`（Python 与 Android 共享）。
- `desktop/tests/test_market_package.py`：新增 4 个测试。

## 验收要点对应证据

| 验收标准 | 证据 |
|---|---|
| 正常/重复/篡改/截断 | 既有签名/清单测试（`test_signature_rejects_tampered_old_schema_and_truncated_packages`）+ 包构建哈希校验 |
| 降级/回滚 | `test_package_ledger_activation_and_rollback`：full-1→delta-2 激活、回滚后 delta-2=ROLLED_BACK、full-1=ACTIVE |
| 增量包 | `test_delta_package_requires_base_and_marks_manifest` + Schema 正反例 |
| 空间不足 | 既有 `test_failed_retry_does_not_replace_previous_complete_partition`（storage 原子替换失败保留旧分区） |
| 个人库不变 | Android 设备验证留在 FULL-204 验收阶段/设备任务 |

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 打包专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_market_package.py desktop\tests\test_quality.py desktop\tests\test_incremental.py desktop\tests\test_contracts.py -q` | PASS（47 项） |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS |

## 风险与未完成项

- Android 端 DELTA 应用与回滚状态机（设备验证）在 FULL-300/303 实现；真实签名包发布在 FULL-122/900。

## 状态建议

实现完成（桌面层），等待系列统一审查与验收。
