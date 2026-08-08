# FULL-803 交付记录

**任务**：FULL-803 全模块回归、Release APK 和用户验收清单

**角色**：实现/回归执行（root 代行；独立审查与验收结论见 `docs/reviews/`）
**状态建议**：`ACCEPTANCE`（本机可执行项全部通过；真实数据/真机/签名/连续运行等外部条件未满足）

## 结果

1. 全模块回归通过：`scripts/verify.ps1` 全绿（2026-08-06 02:17 实测，42 秒）。
2. Release APK 构建成功：`android\app\build\outputs\apk\release\app-release-unsigned.apk`
   （41,324,716 B；SHA256 `BA5E9163CE3B02D12FFF0765C3AB5A7945AAEA549CFF83C3E87327EB0217886A`）。
3. 16 KiB 页对齐检查通过：`scripts/check-16kb.ps1` → `16 KiB page alignment check PASSED`。
4. 发布验收清单已按实测结果填表：`docs/release-checklist.md`。

## 实际验证（2026-08-06 本机）

| 验证项 | 实际命令 | 真实结果 |
|---|---|---|
| 统一验证 | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` | PASS：Python 3.11.0、JDK 21.0.11、55 项锁定依赖一致、Ruff 全过、23 个共享 Schema 夹具全过、桌面 pytest 434 项全过（仅既有 ZIP 同名 `manifest.json` 警告）、Android lintDebug/testDebugUnitTest/assembleDebug 均 BUILD SUCCESSFUL |
| 桌面测试总数 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests --collect-only -q` | 434 项收集（逐文件计数求和） |
| 空白检查 | `git diff --check` | exit 0；仅 `android/app/gradle.lockfile` CRLF 提示 |
| Release 构建 | `gradlew -p android assembleRelease --no-daemon`（JDK 21 + 临时 subst 盘，构建后卸载） | BUILD SUCCESSFUL；产物 `app-release-unsigned.apk` 41,324,716 B |
| 16 KB 检查 | `scripts\check-16kb.ps1 -ApkPath android\app\build\outputs\apk\release\app-release-unsigned.apk` | `16 KiB page alignment check PASSED` |
| APK 哈希 | `Get-FileHash -Algorithm SHA256` | Release：`BA5E9163CE3B02D12FFF0765C3AB5A7945AAEA549CFF83C3E87327EB0217886A`；Debug：`E09F7EAA18D86CEAAF87032C1825312E57596B78276CFB7E3029E32A92188BA5` |

## 修改文件

- `docs/release-checklist.md`：按本轮实测结果填表并写明未满足项与解除条件。
- 本轮未修改任何业务代码或构建配置（Release 构建直接使用既有 `android/app/build.gradle.kts`）。

## 真实数据/设备/签名状态（如实）

| 项 | 状态 | 解除条件 |
|---|---|---|
| AKShare 日历 | PASS 8797 行 | 无 |
| AKShare 快照/资金 | FAILED/NETWORK（东财端点） | 端点恢复后重跑 |
| JQData/Tushare | BLOCKED/CONFIGURATION（无凭据） | 用户配置凭据 |
| BaoStock | FAILED/NETWORK（TCP :10030 超时） | 可达后真实日线与跨源对比 |
| 港股/同花顺 | FAILED/NETWORK、FAILED/PROVIDER | 端点/akshare 版本条件 |
| Android 真机 | 无设备连接 | Android 13+ 16 KB 设备或等效模拟器 |
| Release 签名 | 未签名（无 keystore） | 用户在本机仓库外配置 keystore |
| FULL-800 连续运行 | 计划任务已 Ready，连续记录未达成 | 时间积累 + 受控中断/恢复演练 |
| FULL-804 | BLOCKED | 连续 20 次成功 + 用户书面批准 |

## 接口、迁移与安全

- 无公开契约、数据库或数据包变化。
- 无真实凭据、私钥或大体积真实行情写入仓库；Release APK 未签名、未安装。

## 风险与未完成项

- 本任务验收标准“自动化、真机、数据、恢复和安全测试全部通过”中的真机、真实数据与签名
  依赖外部条件，按 `Plan_full.md` §10 如实保留为 `ACCEPTANCE`，不伪称 ACCEPTED。
