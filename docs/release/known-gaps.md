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
