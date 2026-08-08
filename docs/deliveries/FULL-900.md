# FULL-900 交付记录（封板准备，2026-08-06）

**任务**：FULL-900 正式版本封板

**角色**：实现/封板准备（root 代行；独立验收结论见 `docs/reviews/`）
**状态建议**：`IN_PROGRESS`（报告包与产物就绪；封板需 FULL-803 外部解除条件）

## 已就绪

1. 版本号一致性：desktop `pyproject.toml`/`__init__.py`=0.1.0，Android `versionName`=0.1.0、
   `versionCode`=1，三处一致。
2. Release APK：`android\app\build\outputs\apk\release\app-release-unsigned.apk`
   （41,324,716 B，SHA256 `BA5E9163CE3B02D12FFF0765C3AB5A7945AAEA549CFF83C3E87327EB0217886A`），
   16 KiB 页对齐检查 PASSED（未签名）。
3. 封板报告包（`docs/release/`）：
   - `capability-report.md`：能力报告（桌面/Android/数据源/测试基线）。
   - `quality-report.md`：质量报告（434 项桌面、68 项 Android JVM、lint 0 errors、金标 F1=1.0、门禁与缺口）。
   - `acceptance-report.md`：验收报告（状态汇总与证据索引）。
   - `known-gaps.md`：已知缺口清单（P2/P3 + 外部解除条件）。
4. 执行清单：`docs/release-checklist.md` 已按 FULL-803 实测结果填表。

## 封板仍需满足（如实，不伪造）

| 项 | 状态 | 解除条件 |
|---|---|---|
| FULL-803 外部条件 | 未满足 | 真实数据源/Android 13+ 16KB 真机/FULL-800 连续运行 |
| Release 签名 | 未签名 | 用户在本机仓库外配置 keystore 后签名 |
| Git 标签 | 未创建 | 需在工作提交后打 `v0.1.0` 标签（当前实现均在未提交工作树中，先打标签会指向不含实现的基线，故不提前创建） |
| 最终哈希/版本/标签核对 | 未执行 | 签名产物生成后重算哈希并三处核对 |
| FULL-804 | BLOCKED | 连续 20 次成功证据 + 用户书面批准（年成本≤2000 元） |

## 修改文件

- 新增 `docs/release/` 四份报告、`docs/deliveries/FULL-900.md`；更新 `docs/deliveries/README.md`。
- 本轮未修改任何业务代码（FULL-900 禁止新增功能）。
