# Release 验收清单（FULL-803/900 执行记录，2026-08-06）

本文档是 FULL-803 全模块回归与 FULL-900 封板的执行清单；已执行项填写实际命令、结果与证据链接，
未满足项保持未勾选并注明外部解除条件，不得将未满足项标记完成。

## 1. 自动化基线

- [x] `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1` 全绿（2026-08-06 02:17 实测）：
  Python 3.11.0 / JDK 21.0.11 / 55 项锁定依赖一致 / Ruff 全过 / 23 个共享 Schema 夹具全过 /
  桌面 pytest 434 项全过（仅既有 ZIP 同名 `manifest.json` 警告）/ Android lintDebug、testDebugUnitTest、
  assembleDebug 均 BUILD SUCCESSFUL。
- [x] `git diff --check` 无空白错误（exit 0；仅 `android/app/gradle.lockfile` CRLF 提示，非错误）。
- [x] 凭据扫描：`scan_for_credentials`（FULL-802 专项，`docs/deliveries/FULL-802.md`）对仓库源码/文档/APK/日志
  无真实凭据命中；合成测试值均在测试与夹具中明示。

## 2. 真实数据与来源

- [x] FULL-110 AKShare：日历 PASS 8797 行（`artifacts/full-110-akshare/`）；快照/资金 FAILED/NETWORK
  （东财端点，2026-08-06 02:09 最新探针报告一致），如实记录。
- [ ] FULL-111/112：JQData/Tushare 凭据未在本机配置，真实登录/行数/额度/权限/积分探测保持
  BLOCKED/CONFIGURATION；解除条件=用户在本机配置凭据（不写入仓库）。
- [ ] FULL-113 BaoStock：`www.baostock.com:10030` TCP 超时，最新探针 FAILED/NETWORK；解除条件=可达后
  真实日线与跨源重叠对比（长期不可达不阻塞离线主链）。
- [ ] FULL-122：真实 Provider → Bronze/Silver → 质检 → 签名包端到端受数据源条件限制；本地链路
  （Bronze 写入、`package_from_silver`、签名包+账本）已复审通过（`docs/reviews/rereview-data-fixes.md`）。

## 3. 真机/设备

- [ ] Android 13+ 且满足 16 KB 页面设备（或等效模拟器）未连接（`adb devices` 无设备），
  FULL-123/300~303/404/504/704 真机项保持 ACCEPTANCE：
  - [ ] FULL-123 断网导入真实签名包并显示日线/分钟线。
  - [ ] FULL-300~303 行情体验、替换/删除行情库不影响个人库。
  - [ ] FULL-404 策略参数/启停/信号解释。
  - [ ] FULL-504 交易录入→复盘→加密备份→清库恢复→错误回滚。
  - [ ] FULL-704 图谱搜索与关系溯源。
- [x] `scripts/check-16kb.ps1 -ApkPath android\app\build\outputs\apk\release\app-release-unsigned.apk`
  通过：`16 KiB page alignment check PASSED`（2026-08-06 02:22 实测）。

## 4. 恢复与安全

- [x] FULL-503 备份恢复专项（正确/错误密码、篡改/截断、恢复中断）JVM 全过，错误密码不破坏原库
  （`docs/reviews/acceptance-android-dsl-graph.md`）；真机 SAF/SQLCipher 完整往返待设备。
- [x] FULL-802 密钥轮换矩阵（旧钥验证/新钥拒绝旧包）、备份演练哈希一致、依赖审计（pip check）无冲突，
  专项全过（`docs/deliveries/FULL-802.md`、`docs/reviews/rereview-data-fixes.md`）。
- [ ] FULL-800 连续夜间运行记录（含至少一次受控中断/恢复）未达成：计划任务 `MarketMonitorNightly`
  已创建 Ready（每日 18:30），真实连续运行待时间积累。

## 5. 发布产物

- [ ] Release APK 签名：本机构建出 `android\app\build\outputs\apk\release\app-release-unsigned.apk`
  （41,324,716 B，2026-08-06 02:21，SHA256 `BA5E9163CE3B02D12FFF0765C3AB5A7945AAEA549CFF83C3E87327EB0217886A`）；
  当前未签名，keystore 需用户在本机仓库外配置后签名（解除条件=用户提供 keystore）。
- [ ] 能力报告、质量报告、验收报告、已知缺口清单齐全（FULL-900 封板时完成）。
- [ ] 年持续成本 ≤2000 元且无未批准付费资源（FULL-804 决策记录；当前 BLOCKED=连续 20 次成功未达成
  且付费资源需用户单独书面批准）。

## 结论

本机可执行项全部通过；FULL-803 进入 ACCEPTANCE。解除条件=真实数据源条件（凭据/端点恢复）、
Android 13+ 16 KB 真机、Release 签名 keystore、FULL-800 连续运行记录与 FULL-804 用户批准。
