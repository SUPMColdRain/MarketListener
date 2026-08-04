# Log

本文件记录实际发生的变更与验证，不记录凭据、私钥或个人数据。

## 2026-08-03 - Day 0 实现与自动化验证

- 建立桌面数据生产端、Android 消费端、共享契约、Provider 探针、标准标的、Bronze/Silver、质量规则、交易时段聚合、不可变行情包和 Ed25519 签名校验。
- 建立 Android 个人/行情数据边界、签名行情包原子导入、离线 WebView K 线容器和本地 Lightweight Charts 资产。
- 桌面测试实际执行：`desktop\.venv\Scripts\python.exe -m pytest desktop\tests -q`，结果 `48 passed`。
- Android 自动化验证实际执行：`android\gradlew.bat -p android testDebugUnitTest --no-daemon`，通过。
- 真实 Provider 结果：聚宽因缺少凭据失败；Baostock 与 AkShare 受网络/代理阻塞失败；`tdx_quant` 无可安装的已验证发行包，标记 `UNSUPPORTED`。
- Chaquopy 尝试打包 NumPy 失败；依据 Plan 的停止规则，不切换到联网运行时，D0-050 记录为阻塞。

## 2026-08-04 - Android 构建、16 KB 与中文状态修复

- 确认 Gradle Wrapper 为 8.5，使用 JDK 20.0.2 正常运行；记录 Android Studio 应使用英文 junction 路径。
- 将已弃用 SQLCipher 工件迁移为 `net.zetetic:sqlcipher-android:4.6.1`，将 Room 工厂迁为 `SupportOpenHelperFactory`，并显式加载 `sqlcipher` 原生库。
- 实际执行 `android\gradlew.bat -p android testDebugUnitTest assembleDebug --no-daemon`，结果 `BUILD SUCCESSFUL`。
- 实际执行 APK 16 KB ZIP 对齐检查；四种 ABI 的 `libsqlcipher.so` 所有 `PT_LOAD` 对齐均为 `0x4000`。
- 将 Android 可见界面改为中文；导入 Worker 返回真实成功包 ID/截止时间或失败分类；界面不再把“已排队”显示为导入成功。
- 新增交付文档：`docs/deliveries/Android-16KB-compatibility.md`、`docs/deliveries/Android-中文界面与导入状态.md`、`docs/deliveries/Day0阶段性交接.md`。

## 当前状态

- Day 0 已停止执行且未封板，其历史证据见 `docs/deliveries/Day0阶段性交接.md`。本条是 2026-08-04 的历史状态记录；正式计划固化后的实时入口以根目录 `START_HERE.md` 和 `STATUS.md` 为准。

## 2026-08-04 - Provider 隔离、离线 K 线读取与 16 KB Python 复验

- `ProbeRunner` 新增 Provider 级受控超时，CLI 支持 `probe --timeout-seconds`；桌面测试实际执行为 `49 passed`。20 秒全量真实探针生成报告：聚宽缺凭据、Baostock 超时、AkShare 代理连接关闭、tdx_quant 不受支持，没有任何来源 PASS。
- Android 新增激活 `payload.sqlite` 的只读标的/周期/bars 查询、来源/质量展示和真实 candle JSON 到离线 Lightweight Charts 的转换；新增 JVM JSON 解码回归测试。
- 试验 Chaquopy 17.0.0、Python 3.13、NumPy 1.26.2：APK 离线打包成功，但 `connectedDebugAndroidTest` 在 16 KB 模拟器因 `libgfortran.so.3` 的 4096 对齐失败。已按 Plan 停止规则移除试验代码，未引入联网执行。
- 回退后的 Android JVM 测试与 Debug 构建再次通过；`zipalign -c -P 16` 通过，四种 ABI 的 SQLCipher `PT_LOAD` 仍为 `0x4000`。APK 已安装并启动于 16 KB 模拟器，中文界面真实显示未导入状态；修复了状态栏与标题重叠。
- Git 状态检查显示当前仓库没有已跟踪基线，全部项目文件为未跟踪；未擅自执行 `git add`、初始化或提交。

## 2026-08-04 - Day 0 停止与正式开发转场

- 用户决定不再执行 `Plan.md` 的 Day 0 任务。未完成项、失败报告和验收缺口保留原状，不把停止执行写成 Day 0 完成。
- 新增 `docs/正式开发交接.md` 与 `docs/deliveries/README.md`，更新根入口、模块说明、Plan、经验记录和时序图，使后续对话从整个项目目标而非 D0 任务编号开始。
- ADR、领域词汇、共享 Schema、交付模板和历史 D0 单项交付未改写；它们分别保持规范、契约、模板和历史证据性质。
