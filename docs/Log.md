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

## 2026-08-05 - FULL-002 Git 与工具链基线

- 创建首个 Git 根提交 `b270463bc9fe63932faf4e01858d8d5d870697d9`，保存已验收的 FULL-001 与 Day 0 历史基线；提交前确认无大文件、真实凭据或私钥。
- 锁定 Python 3.11.0及49个运行/测试依赖，固定 setuptools 构建后端；依赖干跑解析、`pip check` 与49项 pytest 通过。
- 锁定 JDK 21、Gradle 8.5及分发哈希、AGP/Kotlin、Android SDK 34 revision 3、Build Tools 34.0.0和151个 Android 传递模块。
- JDK 20 被项目配置明确拒绝；JBR 21.0.11 下6项 Android JVM 测试与 Debug APK 构建通过。中文物理路径仍需临时 `subst` 到英文盘符，单独使用 junction 在 JDK 21 下不足以避免测试类加载失败。

## 2026-08-08/09 - Android 同步修复、真实覆盖展示与 720 篇研报流水线

- 修复 Android 同步包下载与手动导入两处报错：`MainActivity.kt` 默认服务器地址改为电脑当前 IPv4 `http://192.168.1.88:8765`；同步/导入成功后刷新产业链 HTML；导入失败返回 `RESULT_ERROR_DETAIL` 明细；`MarketPackageImporter.kt` 白名单与抽取条目加入 `industry/industry-map.html`，手动导入 zip 不再报“行情包结构无效”。
- 桌面 `/api/health` 新增真实 K 线覆盖统计（扫描 `data_control/silver/**/*.parquet`）：48 标的、72,321 根 K 线（CN ETF 4/1200、CN FUTURE 15/9435、CN INDEX 5/2170、CN STOCK 5/1515、GLOBAL CRYPTO 2/120、GLOBAL FUTURE 4/15461、GLOBAL INDEX 6/20060、HK INDEX 3/7847、HK STOCK 4/14513）；属部分覆盖，接口与文档如实标注，不宣称全 A 股/全港股/全期货。
- 720 篇研报知识库流水线：`reports/industry/` 生成 720 个 `report_*.json`（717 解析 / 3 跳过 / 0 失败，33,096 条事实，版本 4）；`reports verify` 719 通过 / 1 待复核（`20260712-银河证券-光器件行业深度报告：磷化铟…pdf`，未抽取到事实且警告过多，疑似扫描件，建议 OCR）；`reports chains` 聚合 155 条产业链（22,083 条链上事实）并生成 `industry-map.html`（SVG 图谱，9.6 MB），快照同步 `data_control/industry/`。
- 重建并激活同步包 `market-20260808-190946-deaecd38`（7,256,011 字节，含 `signature.ed25519`/`signature.ecdsa`/`payload.sqlite`/`industry/industry-map.html`，72,321 bars + 25,545 gold_metrics）。
- 后端 8765 重启到最新代码并实测：`/`、`/api/health`、`/industry/`、`/industry/industry-map.html`、`/api/android-package` 全部 200。
- 终核验：`/industry/industry-map.html` 服务字节 9,628,645 = 本地新文件 9,647,124 − 18,479 处 CRLF（`read_text` 统一换行符所致），内容逐字节一致；同步包 zip 内图谱与本地原始文件 SHA256 均为 `785EF2FF0AC4C7709B915ED5A38EF0C1234A521B40CE927FCAB82786D1CAA5D1`；`/`、`/api/health`（48 标的 / 72,321 行）、`/industry/industry-map.html`、`/api/android-package` 实测 200。
- 回归：桌面 `pytest desktop\tests -q` 507 项全部通过（新增 `/api/health` 真实 parquet 覆盖统计测试、研报聚合/规则核验/SVG 图谱生成测试 4 项）；Android `gradlew.bat testDebugUnitTest assembleDebug`（JDK 21）BUILD SUCCESSFUL，21 suites / 74 tests / 0 failures / 0 errors。
- 文档更新：`STATUS.md`、`Plan_full.md`（5.8 补充）、`README.md`、`docs/deliveries/FULL-705.md` 与交付索引；工作区保持未提交（用户明确要求不 commit）。
