# 已知缺口清单（FULL-900 封板准备，2026-08-06）

## P2（建议修复，不阻断当前本机验收）

| 位置/任务 | 缺口 | 出处 |
|---|---|---|
| FULL-303 | 清理按钮未捕获 IOException；StatFs 回退缺口（P3） | `docs/reviews/acceptance-android-dsl-graph.md` |
| FULL-301 | WebView `allowFileAccess`、`readActive` 吞错（P3） | 同上 |
| FULL-302 | 未知 `quality_status` 不计异常（P3） | 同上 |
| FULL-404 | 策略解释器主线程运行、历史参数重启丢失 | 同上 |
| FULL-503 | PBKDF2/文件 IO 主线程、`storedIterations` 无下限 | 同上 |
| FULL-504 | 多标的收盘价回退、备份主线程 | 同上 |
| FULL-704 | 图谱快照无大小限制、解析失败提示缺失；重复 `entity_id`、非懒加载（P3） | 同上 |
| FULL-402 | `windowRef` 上限、节点数契约不一致（P3） | 同上 |
| FULL-300 | 热库删除接口未接线、双 UserDatabase 实例（P3） | 同上 |
| FULL-500/501 | SQLCipher 真机打开、Room DAO 设备/仪器化路径（已知缺口） | 同上 |
| FULL-123 | 真实 Provider→签名包端到端受数据源条件限制 | `docs/reviews/rereview-data-fixes.md` |
| 桌面 | `package_from_silver`/`capability_for` ValueError/`verify_market_package` 哈希拒绝暂无专项自动化测试（已手工验证） | 同上 |

## 外部条件（解除条件，不属代码缺口）

| 条件 | 影响任务 | 解除方式 |
|---|---|---|
| JQData/Tushare 凭据 | FULL-111/112/120 | 用户在本机配置（不写入仓库） |
| 东财端点恢复 | FULL-110/600 | 重跑真实探针 |
| BaoStock 可达 | FULL-113/120 | `www.baostock.com:10030` 连通后真实对比 |
| akshare 版本提供同花顺接口 | FULL-602 | 升级/切换可用版本后真实探测 |
| Android 13+ 16 KB 设备 | FULL-123/300~303/404/504/704/803 | 连接设备或等效模拟器 |
| Release keystore | FULL-803/900 | 用户在本机仓库外配置签名 |
| 连续夜间运行记录 | FULL-800/804 | 时间积累（计划任务已 Ready） |
| 用户书面批准 | FULL-804 | 连续 20 次成功证据 + 年成本≤2000 元决策 |
| QMT 开通 | FULL-610 | 用户开通后进入 READY 并实测 |

## 门控任务

- FULL-610：QMT 未开通，BLOCKED，不阻塞离线正式版。
- FULL-804：连续 20 次成功未达成且付费需批准，BLOCKED。

## 2026-08-09 收尾新增缺口（产业链图谱专项）

| 位置/任务 | 缺口 | 状态 |
|---|---|---|
| FULL-705/F10 | A 股收入构成（revenue）已补齐：CN `revenue_20260809.jsonl` 4,730 条 + `corrupt-1352.bak` 492 条 + `corrupt-1401.bak` 317 条 = 5,539 唯一代码（零重叠、零坏行）；港股收入构成无可用数据源（东财无港股主营构成报表，已实测） | 已解决（2026-08-09 续抓完成）；港股缺口为外部数据源限制 |
| FULL-705/产业链定义 | 用户认为产业链/环节/产品定义仍不理想（例：“创业板”曾被当作通信产业链产品，已由 `_MARKET_BOARD_TERMS` 过滤）；最终定义由用户自行阅读研报 PDF 人工校验 | 自动化提炼暂停 |
| FULL-705/链归并 | `chain_index.json` 177 条原始子链存在重复（如半导体/半导体材料/半导体设备），去重/归并未完成；Atlas 当前为清洗后 75 条链展示口径 | 待用户人工确认口径 |
| FULL-705/体积 | `industry-atlas.html` 约 20 MB（20,018,677 字节），超过架构目标 12 MB（离线、零 CDN 约束已满足） | 已知，暂不优化 |
| FULL-705/离线检查 | HTML 内 11 处 `https://` 为公司简介正文中的官网文字（非资源引用），不触发联网请求 | 已知，非缺陷 |
| FULL-705/Android | 新版约 20 MB atlas 同步包（`market-20260809-081649-141aff2e`）需真机导入验收；港股 F10 弹窗收入构成为空（无数据源） | 真机解除条件未满足 |
