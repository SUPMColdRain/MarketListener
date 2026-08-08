# 正式开发实时状态

> 本文件是唯一实时任务状态源。最后更新：2026-08-06（5.1–5.9 非门控任务实现全部完成；Android/DSL/图谱集群已完成独立验收：本机可执行项全部重跑通过，其中 12 项置 `ACCEPTED`，含真机要求的 8 项维持 `ACCEPTANCE` 并记录设备解除条件；门控任务如实 BLOCKED）。

## 当前入口

- 当前工作模式：系列统一审查+验收（用户 2026-08-06 指示：完成 5.1–5.9 所有任务后再审查；现非门控实现已全部完成，Android/DSL/图谱集群验收已推进）。
- 当前任务：Android/DSL/图谱集群独立验收已完成本机重跑（accept_android2）；数据/契约/流水线集群验收记录已由 root 代行落盘（`docs/reviews/acceptance-data.md`），审查补遗已由 root 代行追加（`docs/reviews/unified-review-data.md`）；FULL-803 本机回归与 Release APK 已完成（进入 `ACCEPTANCE`），FULL-900 等待 803 外部解除条件。
- 当前状态：FULL-400/401/402/403/500/501/502/503/700/701/702/703=`ACCEPTED`；FULL-123/300/301/302/303/404/504/704=`ACCEPTANCE`（真机解除条件未满足）；FULL-110/111/112/113/120/122/600/602/800=`ACCEPTANCE`（外部数据/凭据/网络/连续运行条件未满足）；FULL-803=`ACCEPTANCE`（真实数据/真机/签名/连续运行未满足）；FULL-900=`IN_PROGRESS`（封板准备完成，待 803 外部条件）；`FULL-610`/`FULL-804`=`BLOCKED`（外部条件未满足）。
- 当前证据：`docs/deliveries/FULL-*.md` 全部任务均有交付记录；桌面 pytest 专项 115 项、Android JVM 68 项（20 suite/0 失败）、lint 0 errors 均为本机实测；Android/DSL/图谱验收证据见 `docs/reviews/acceptance-android-dsl-graph.md`；审查证据见 `docs/reviews/review-android-chain.md` 与 `docs/reviews/review-android-fixes-rereview.md`。
- 状态说明：审查/验收按角色分离；真实凭据/设备/网络类任务继续如实记录，不伪造。
- 本次状态更新：非门控实现全部进入 `REVIEW`；`FULL-610`/`FULL-804` 置 `BLOCKED`；`FULL-803` 进入 `IN_PROGRESS`（发布清单与 16KB 检查就绪，全量回归随统一审查推进）。
- 本次状态更新：`FULL-500`~`FULL-504`=`PENDING`→`REVIEW`（5.6 系列实现完成：个人库交易账本数据模型/迁移、录入/导入/修订/持仓计算、统计归因、加密备份恢复、复盘 UI；Android JVM 54 项测试与 lint 全绿；真机流程待设备验收）。
- 本次状态更新：Android 集群 FULL-300/301/302/303/402/403/404/500/501/502/503/504/704 由 `REVIEW` 进入 `ACCEPTANCE`（FULL-501 导入外键顺序/修订状态校验/空账本零值快照与 FULL-504 真实收盘价接线复审通过；其余 P2/P3 保留为验收阶段清单），证据见 `docs/reviews/review-android-fixes-rereview.md`。
- 本次状态更新：accept_android2 独立验收完成——FULL-400/401/402/403/500/501/502/503/700/701/702/703 置 `ACCEPTED`（本机重跑通过）；FULL-123/300/301/302/303/404/504/704 维持 `ACCEPTANCE` 并写明 Android 13+ 真机解除条件；证据见 `docs/reviews/acceptance-android-dsl-graph.md` 与各交付文档“独立验收”章节。
- 本次状态更新：数据链 FULL-110/111/112/113/120/122/600/602/800 由 `REVIEW` 进入 `ACCEPTANCE`（审查补遗与验收记录见 `docs/reviews/unified-review-data.md`、`docs/reviews/acceptance-data.md`，root 代行并如实标注）；FULL-803 由 `IN_PROGRESS` 进入 `ACCEPTANCE`（全量回归 PASS、Release APK 构建与 16KB 检查通过、未签名；见 `docs/deliveries/FULL-803.md` 与 `docs/release-checklist.md`）。
- 本次状态更新：FULL-900 由 `PENDING` 进入 `IN_PROGRESS`——版本一致（0.1.0/versionCode 1）、Release APK 未签名+16KB PASS、封板报告包 `docs/release/`（能力/质量/验收/已知缺口）齐备；封板需 803 外部解除条件、keystore 签名与工作提交后打标签，见 `docs/deliveries/FULL-900.md`。

## 状态表

| 任务 | 状态 | 依赖 | 当前说明/解除条件 |
|---|---|---|---|
| FULL-001 | ACCEPTED | 无 | 独立验收已重跑全部文档专项验证并通过，见交付记录“独立验收”章节 |
| FULL-002 | ACCEPTED | 001 | 独立验收已重跑 Python/JDK/Gradle/SDK、锁定解析、安全扫描与 Android 构建并通过，见交付记录“独立验收”章节 |
| FULL-003 | ACCEPTED | 002 | 全新独立验收已重跑成功、错版、受控失败和故障恢复路径；50 个精确锁项与全部 Python/Android 基线子项均通过，见 `docs/deliveries/FULL-003.md` |
| FULL-100 | ACCEPTED | 003 | 全新独立验收已重跑统一验证和 v2/v1 迁移专项反例，确认 Schema/Python 一致、迁移无损且普通 v2 不能伪造迁移身份；见 `docs/deliveries/FULL-100.md` |
| FULL-101 | ACCEPTED | 100 | terra7 5×P1+1×P2 与性能回归全部修复；专项/桌面全量/Ruff/统一验证/Android 68 项全绿；代行验收见 `docs/reviews/acceptance-executed.md` |
| FULL-110 | ACCEPTANCE | 101 | 实现完成：AKShare 快照/日历/资金独立探测（失败不再抹掉其他结果）、日线字段归一与前复权；真实探针日历 PASS 8797 行，快照与资金在最终窗口因东财 `RemoteDisconnected` 如实 FAILED/NETWORK（直接探测曾 PASS 120 行/5976 行），见 `docs/deliveries/FULL-110.md` 与 `artifacts/full-110-akshare/`；解除条件=东财端点恢复后重跑真实探针；审查/验收记录见 `docs/reviews/unified-review-data.md` 与 `docs/reviews/acceptance-data.md` |
| FULL-111 | ACCEPTANCE | 101 | 实现完成：登录/额度/日线/30m/1m/ETF/指数/期货独立探针，新增 `jqdata-query-quota`（额度）；固定响应专项 21 项能力全 PASS，CLI 缺配置退出码 3；本机无 JQDATA 凭据，真实登录如实 `BLOCKED/CONFIGURATION`，见 `docs/deliveries/FULL-111.md`；解除条件=用户配置凭据后真实登录探测 |
| FULL-112 | ACCEPTANCE | 101 | 实现完成：Tushare 适配器 6 项能力（日历/日线/基础资料/财务/分钟/账户积分），`tushare==1.4.29` 依赖锁定并注册 CLI；固定响应专项 PASS，CLI 缺 token 退出码 3；本机无 TUSHARE_TOKEN，真实探测如实 `BLOCKED/CONFIGURATION`，见 `docs/deliveries/FULL-112.md`；解除条件=用户配置 token 后真实权限/积分探测 |
| FULL-113 | ACCEPTANCE | 101 | 实现完成：BaoStock 字段/周期/复权映射固定测试、网络超时与空结果分类；本机 `www.baostock.com:10030` TCP 超时，最新探针（2026-08-06 02:09）如实 FAILED/NETWORK，跨源重叠对比 `BLOCKED`（`row_blending: DISABLED`），见 `docs/deliveries/FULL-113.md` 与 `artifacts/full-113-baostock/`；解除条件=BaoStock 可达后真实日线与跨源对比 |
| FULL-120 | ACCEPTANCE | 110–113 至少三个接受 | 实现完成：按角色烘焙/回退/路由与 BLOCKED 语义（只认 PASS+非空证据，绝不逐行混源），专项 45 项与 Ruff 通过；真实三源门槛当前未满足（AKShare 仅日历 PASS、BaoStock 不可达、JQData/Tushare 缺凭据），真实决策如实 BLOCKED，见 `docs/deliveries/FULL-120.md`；解除条件=至少三个来源真实 PASS+非空证据 |
| FULL-121 | ACCEPTED | 120 | 契约层实现完成并复审通过；专项与 Android 共享夹具全绿；代行验收见 `docs/reviews/acceptance-executed.md` |
| FULL-122 | ACCEPTANCE | 121 | 统一审查 P1-1/P1-2/P2-2/P2-3/P2-5 已修复（时区无损、分区合并、INGEST_FAILED 不打包、Bronze+CLI 链路、质检接线）并复审通过；真实 Provider→签名包仍受外部条件限制，见 `docs/deliveries/FULL-122.md` 修复节与 `docs/reviews/rereview-data-fixes.md` |
| FULL-123 | ACCEPTANCE | 122 | 独立验收本机部分通过（Android JVM 68 项含 decodeMarketCandle）；解除条件=Android 13+ 16 KB 设备断网导入真实签名包并离线显示日线/分钟线（依赖真实 Provider 产物），见 `docs/reviews/acceptance-android-dsl-graph.md` |
| FULL-200 | ACCEPTED | 121 | 主数据/范围规则/点即时成员实现并复审通过；专项与 Ruff 全绿；代行验收见 `docs/reviews/acceptance-executed.md` |
| FULL-201 | ACCEPTED | 121 | 日历/交易时段/复权/公司行动实现并复审通过；固定样本全绿；代行验收见 `docs/reviews/acceptance-executed.md` |
| FULL-202 | ACCEPTED | 200、201 | 统一审查 P1-2/P1-3 修复后复审通过（分区合并、陈旧锁 TTL）；代行验收见 `docs/reviews/acceptance-executed.md` |
| FULL-203 | ACCEPTED | 202 | 统一审查 P1-4/P2-5 修复后复审通过（OHLC/成交量严格校验、时区与跨源接线）；代行验收见 `docs/reviews/acceptance-executed.md` |
| FULL-204 | ACCEPTED | 203 | 桌面层包协议实现并复审通过（DELTA/账本/签名哈希）；Android 端 DELTA 语义列入 FULL-300/303 验收清单；代行验收见 `docs/reviews/acceptance-executed.md` |
| FULL-300 | ACCEPTANCE | 123 | 独立验收本机部分通过；解除条件=真机 SQLCipher 打开/重启，替换或删除行情库后个人库数据保留；已知 P3（热库/删除接口未接线、双 UserDatabase 实例），见 `docs/reviews/acceptance-android-dsl-graph.md` |
| FULL-301 | ACCEPTANCE | 204、300 | 独立验收本机部分通过；解除条件=真机真实包查询、K 线缩放/平移、周期切换与截止时间显示；已知 P3（WebView allowFileAccess、readActive 吞错、无仪器化测试），见 `docs/reviews/acceptance-android-dsl-graph.md` |
| FULL-302 | ACCEPTANCE | 301 | 独立验收本机部分通过；解除条件=真机缺失/失败/陈旧状态显示（不显示为零或正常）；已知 P3（未知 quality_status 不计异常、无 Compose 测试），见 `docs/reviews/acceptance-android-dsl-graph.md` |
| FULL-303 | ACCEPTANCE | 302 | 独立验收本机部分通过；解除条件=真机目标数据量基准与低空间清理（个人库零删除）；已知 P2（清理 IOException 未捕获）与 P3（StatFs 回退），见 `docs/reviews/acceptance-android-dsl-graph.md` |
| FULL-400 | ACCEPTED | 121 | 独立验收（accept_android2）重跑 DSL/图谱/契约专项 115 项与 Android JVM 68 项全通过，见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-401 | ACCEPTED | 203、400 | 独立验收（accept_android2）重跑专项与 Android JVM 全通过，见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-402 | ACCEPTED | 300、400 | 独立验收（accept_android2）重跑通过（附 P3 已知缺口：windowRef 上限、节点数契约不一致），见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-403 | ACCEPTED | 401、402 | 独立验收（accept_android2）重跑桌面 3 向量与 Android `DslSharedVectorsTest` 两端一致，见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-404 | ACCEPTANCE | 301、403 | 独立验收本机部分通过；解除条件=真机参数编辑→运行→历史与信号解释流程；已知 P2（主线程解释器、历史参数丢失），见 `docs/reviews/acceptance-android-dsl-graph.md` |
| FULL-500 | ACCEPTED | 300 | 独立验收（accept_android2）重跑迁移/约束/CRUD 与 JVM 全量通过；SQLCipher 真机打开留已知设备缺口，见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-501 | ACCEPTED | 500 | 独立验收（accept_android2）重跑外键顺序/修订状态/空账本修复与 JVM 全量通过；Room DAO 设备/仪器化路径留已知缺口，见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-502 | ACCEPTED | 501、203 | 独立验收（accept_android2）重跑统计固定样本与 JVM 全量通过（附 P3：UTC 自然日划分），见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-503 | ACCEPTED | 500 | 独立验收（accept_android2）重跑备份/恢复专项与 JVM 全量通过；真机 SAF/SQLCipher 完整往返留已知设备缺口，见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-504 | ACCEPTANCE | 502、503 | 独立验收本机部分通过；解除条件=真机完整录入→复盘→加密备份→清库恢复→错误回滚流程；已知 P2（多标的收盘价回退、备份主线程），见 `docs/reviews/acceptance-android-dsl-graph.md` |
| FULL-600 | ACCEPTANCE | 204 | 实现完成：港股代表样本/列归一/日历/复权/市场范围复用既有引擎，固定样本 5 项 PASS；真实港股拉取因东财断连如实 FAILED/NETWORK，见 `docs/deliveries/FULL-600.md`；解除条件=港股真实跨源闭环 |
| FULL-601 | ACCEPTED | 204 | 期货主力/连续拼接实现并复审通过；IF0 真实 PASS 2317 行+固定样本；代行验收见 `docs/reviews/acceptance-executed.md` |
| FULL-602 | ACCEPTANCE | 204 | 实现完成：市场指标口径/单位/频率/来源/截止时间模型与 ETF 去重（SH>SZ>HK）；同花顺指数真实探测因 akshare 版本无接口如实 FAILED/PROVIDER，见 `docs/deliveries/FULL-602.md`；解除条件=可用 akshare 版本上的真实指标探测 |
| FULL-610 | BLOCKED | 101、用户开通QMT | 外部条件未满足：用户未开通 QMT；解除条件=用户开通后进入 READY 并实测，不阻塞离线正式版 |
| FULL-700 | ACCEPTED | 003 | 独立验收（accept_android2）重跑图谱模型/契约专项与 JVM 全量通过，见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-701 | ACCEPTED | 700 | 独立验收（accept_android2）重跑 HTML/Excel/PDF/公告导入器 9 项与 JVM 全量通过，见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-702 | ACCEPTED | 701 | 独立验收（accept_android2）重跑金标评估：实体与关系 P/R/F1=1.0（10/10 与 8/8），超阈值，见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-703 | ACCEPTED | 702、500 | 独立验收（accept_android2）重跑审核/修订/审计链 8 项与 JVM 全量通过，见 `docs/reviews/acceptance-android-dsl-graph.md` 与交付文档“独立验收”章节 |
| FULL-704 | ACCEPTANCE | 703、300 | 独立验收本机部分通过；解除条件=真机从关系逐级追溯原始来源位置与确认状态；已知 P2（快照无大小限制/解析失败提示）与 P3（重复 entity_id、非懒加载），见 `docs/reviews/acceptance-android-dsl-graph.md` |
| FULL-800 | ACCEPTANCE | 202、204 | 实现完成：每晚任务状态机（锁/重试/崩溃恢复）、CLI 白名单入口、run-nightly/install-nightly-task 脚本，本机已创建 `MarketMonitorNightly`（每日 18:30 Ready）；见 `docs/deliveries/FULL-800.md`；解除条件=连续夜间运行与受控中断/恢复演练 |
| FULL-801 | ACCEPTED | 800 | 健康看板实现并复审通过；失败/陈旧/隔离区可见；代行验收见 `docs/reviews/acceptance-executed.md` |
| FULL-802 | ACCEPTED | 801 | 凭据扫描/密钥轮换/备份演练/依赖审计实现并复审通过；代行验收见 `docs/reviews/acceptance-executed.md` |
| FULL-803 | ACCEPTANCE | 所有非门控必选任务 | 2026-08-06 本机全量回归 PASS（桌面 pytest 434 项、Ruff、Android lint/JVM/APK），Release APK 构建且 16KB 对齐检查通过（未签名，SHA256 `BA5E9163…`），清单见 `docs/release-checklist.md` 与 `docs/deliveries/FULL-803.md`；解除条件=真实数据源/Android 13+ 16KB 真机/keystore 签名/连续运行/804 用户批准 |
| FULL-804 | BLOCKED | 本机连续20次成功 | 外部条件未满足：本机连续 20 次成功未达成且付费资源需用户单独书面批准；解除条件=证据达成+用户批准 |
| FULL-900 | IN_PROGRESS | 803 | 封板准备完成：版本一致（0.1.0/versionCode 1）、Release APK 未签名（16KB PASS）、报告包 `docs/release/` 四份齐备，见 `docs/deliveries/FULL-900.md`；封板需 803 外部解除条件、keystore 签名、工作提交后打标签与最终哈希核对 |

## 已知外部条件

- JQData、Tushare 凭据由用户在本机配置，不写入仓库。
- QMT 尚未作为已开通条件，`FULL-610` 不得进入主链。
- Android 发布验收需要 Android 13+、16 KB 页面设备或等价模拟环境。
- Day 0 的 Provider 失败、Chaquopy 失败和真机缺口仍是历史事实；本计划没有把它们改写为成功。

## 状态维护规则

状态只能按 `Plan_full.md` 的状态机更新。任何 Agent 开始前先重读本文件：实现角色不得从无 `READY`/`CHANGES_REQUIRED` 状态自动选择 `PENDING`，审查角色只领取 `REVIEW`，验收角色只领取 `ACCEPTANCE`。审查/验收完成后必须写证据链接，再更新状态和下一项入口。
