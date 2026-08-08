# FULL-802 实现交付：密钥轮换、日志脱敏、备份演练与依赖审计

日期：2026-08-06
状态：实现完成（等待系列统一审查；依赖漏洞库扫描需外部工具，如实记录）
角色：root 实现

## 范围与边界

实现：仓库/制品凭据特征扫描（AWS key、私钥、Bearer、凭据 env 赋值，输出脱敏片段）、签名密钥轮换（旧钥备份 + 新钥生成 + 旧/新钥矩阵验证）、数据目录备份演练（逐文件 SHA-256 校验）、`pip check` 依赖审计。FULL-101 的日志脱敏继续由 runner 输出边界承担；本轮不重复实现。

## 修改文件

- `desktop/src/market_monitor/security_audit.py`：`scan_for_credentials`、`rotate_signing_key`、`verify_old_package_with_rotated_keys`、`backup_store`、`dependency_audit`。
- `desktop/tests/test_security_audit.py`：合成凭据扫描（含排除 .git、片段脱敏）、轮换矩阵（旧钥验证通过/新钥拒绝旧包）、备份哈希校验。

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 安全审计专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_security_audit.py desktop\tests\test_dashboard.py desktop\tests\test_ops.py -q` | PASS（10 项） |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS |

## 风险与未完成项

- 真实仓库/APK/日志敏感扫描在 FULL-803 全量回归中执行（将使用本模块）；扫描规则是特征模式，不能替代人工审查。
- 依赖漏洞库（如 pip-audit/OSV）未安装：不擅自新增依赖，`pip check` 已接入；漏洞库扫描作为外部工具步骤记录在交付说明。
- 备份演练已覆盖文件级哈希；加密备份与恢复的逐表一致性属于 FULL-503。

## 状态建议

实现完成，等待系列统一审查与验收。
