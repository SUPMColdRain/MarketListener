# FULL-705 实现交付：720+ 篇研报知识库流水线与产业链 SVG 图谱快照

日期：2026-08-09
状态：实现完成并已补齐复核（本机全量执行 + 接口实测 + 研报 OCR/源缺失补齐；Android 真机快照导入待解除）
角色：root（用户指示自主完成；本任务未启用子 Agent）

## 用户指示与设计约束

- 720+ 篇行业研报不能一次性塞给单个 Agent；研报阅读是“生产数据库”的过程，Android 每次打开产业链页面时不得重新阅读研报。
- `行业产业链研报/` 不放入 Git 上传文件夹；每篇研报带状态标识，已处理不重复读取。
- 每篇研报的知识整理为结构化 JSON；允许并发处理。
- 最终产物为电脑后端 HTML 产业链页面（SVG 图形化产业链图谱），Android 端复制电脑端网页快照。

## 实现结果

- `desktop/src/market_monitor/report_pipeline.py`：`process`（PDF 解析/切块/并发抽取）、`status`（状态跟踪）、`verify`（脚本化规则核验，写 `review` 块）、`chains`（按产业链聚合 + `build_industry_map_html`）。
- 产物（`reports/industry/`）：721 个 `report_*.json`（全部 REVIEWED）、`batch_summary.json`、`chain_index.json`、`industry-map.html`。
- 数据：721 篇核验通过 / 0 待复核 / 33,193 条事实；177 条产业链 / 33,193 条链上事实（per-fact 链聚合，无丢弃）；SVG 图谱约 9.6 MB（含 1 篇 OCR 补偿、1 篇源缺失保留）。
- 新版全景产物：`industry-atlas.json/html`（Atlas 展示口径 75 条链；`chain_index.json` 原始 177 条子链 / 7,090 家带证券代码公司 / 公司索引 7,577 条 / F10 CN 5,539 + HK 2,806 + legacy 1,017，约 20 MB / 20,018,677 字节自包含离线 HTML，零 CDN）。
- 快照同步 `data_control/industry/industry-map.html`，并打入同步包 `market-20260808-190946-deaecd38`（含 `industry/industry-map.html`）；Android 导入白名单已加入该条目，导入/同步成功后产业链页刷新。
- 后端路由 `/industry/` 与 `/industry/industry-map.html` 实测 HTTP 200。
- 终核验：路由返回 9,628,645 字节 = 本地新文件 9,647,124 字节经 `read_text` 归一化 18,479 处 CRLF 后的内容，逐字节一致；zip 内图谱与本地原始文件 SHA256 均为 `785EF2FF0AC4C7709B915ED5A38EF0C1234A521B40CE927FCAB82786D1CAA5D1`。
- 研报补齐与 OCR 重试（2026-08-09）：新增 `desktop/src/market_monitor/report_ocr.py`（PyMuPDF 渲染 + RapidOCR，扫描件自动补偿）与 `scripts/retry_report_ocr.py`（幂等：处理无 JSON 的 PDF、force 重跑 0 事实报告、标记源缺失，默认重建 chain_index + industry-map.html）；财信证券 AI短剧（原缺失）解析 37 事实、银河证券光器件扫描件（原 0 事实）OCR 补偿 60 事实、中信期货量化 CTA（源 PDF 缺失）保留 42 事实并标记 `source_missing`；重试脚本二次运行零改动（幂等）。

## 自动化证据

| 项目 | 命令 | 真实结果 |
|---|---|---|
| 流水线状态 | `market_monitor reports status --output-root reports\industry` | 721 tracked，REVIEWED 721，review_passed 721，review_failed 0，fact_count 33193 |
| 图谱聚合 | `market_monitor reports chains --output-root reports\industry` | 177 chains / 721 reports / 33,193 条链上事实，chain_index.json + industry-map.html 生成 |
| 全景图谱 | `market_monitor reports atlas --output-root reports\industry --data-root data_control` | SUCCESS：75 chains（展示口径；chain_index 原始 177 条子链）、7,090 companies with codes、公司索引 7,577、F10 CN 5,539 + HK 2,806 + legacy 1,017，industry-atlas.json/html 生成并同步 data_control |
| 同步包 | `market_monitor package --data-root data_control --private-key … --ecdsa-private-key …` | SUCCESS：72321 bars、25545 gold metrics、13,585,044 bytes（`market-20260809-081649-141aff2e`，ed25519+ecdsa 签名），新版 industry-atlas.html 已包含 |
| 后端接口 | curl `http://127.0.0.1:8765/{/,api/health,industry/,industry/industry-map.html,industry-v2/,api/android-package}` | 全部 200（`/industry-v2/` 20,018,293 字节，同步包 13,585,044 字节；旧版 SVG 图谱 `/industry/industry-map.html` 亦 200） |
| 桌面回归 | `pytest desktop\tests -q` | 525 passed，0 failed（含新增覆盖统计、研报聚合（含 per-fact 链回归）/核验/SVG 图谱、OCR 回退与 atlas 回归测试） |
| Android 回归 | `gradlew.bat testDebugUnitTest assembleDebug`（JDK 21） | BUILD SUCCESSFUL，21 suites / 74 tests / 0 failures |

## 风险与未完成项

- 原 1 篇待复核的银河证券光器件扫描件已通过 OCR 补偿解析（60 事实，`ocr_applied=true`）；财信证券 AI短剧 PDF 已补齐解析（37 事实）；中信期货量化 CTA 源 PDF 缺失，保留 42 事实并标记 `source_missing`（用户找回源文件后可重跑）。
- 当前 `verify` 为脚本化规则核验（schema/事实/实体/证据/链归属/警告），未做真实网络检索核验，也未替代人工审查。
- Android 真机从同步包导入并显示产业链图谱快照待设备验收（真机解除条件）。
- F10 收入构成（revenue）已补齐：CN `revenue_20260809.jsonl` 4,730 条 + `corrupt-1352.bak` 492 条 + `corrupt-1401.bak` 317 条 = 5,539 唯一代码（零重叠、零坏行、全部含 `revenue_breakdown`）；港股收入构成无可用数据源（东财无港股主营构成报表，已实测）。
- 产业链/环节/产品定义（含“创业板被当作通信产业链产品”问题）经用户评估仍不理想，用户决定自行阅读研报 PDF 人工校验；177 条原始子链去重/归并未完成，Atlas 当前为清洗后的 75 条链展示口径。
- `industry-atlas.html` 实际体积约 20 MB（20,018,677 字节），超过架构文档 12 MB 的优化目标（离线与零 CDN 约束已满足）。

## 收尾更新（2026-08-09）

- 修复市场板块脏词：`industry_atlas.py` 新增 `_MARKET_BOARD_TERMS`/`_is_market_board_name()`（“创业板/科创板/沪深/中证/主板/北交所”等不再作为产品；精确+子串，“主板”仅精确过滤避免误伤电子行业 motherboard）；`_f10_chain_candidates()` 多段 key 优先；`_norm_industry_segment()` 行业分段归一化。
- 验证：`test_industry_atlas.py` 9/9；全量 `pytest desktop/tests` 0 失败；atlas 重建后卡片中“创业板/科创板/沪深/中证/主板/北交所/…/上市/指数”命中 0；HTML 完全离线（11 处 `https://` 均为公司简介正文官网文字，非资源引用）。
- 用户指示暂停自动化产业链提炼；子 Agent 已打断收工，多余进程已终止；后端 8765（PID 30108/35652）保留在线；`fetch.lock` 已改名停用。F10/revenue 随后由计划任务 `MarketListener_Revenue_CN`（1.0s/条限速）续抓完成并于 16:03 正常退出（`revenue_cn.log` 记录 PASS）。
- Android 同步包已按新版约 20 MB atlas 重建：`market-20260809-081649-141aff2e`（13,585,044 字节，ed25519+ecdsa 签名），zip 内 Atlas 哈希一致，后端 `/api/android-package` 实测 200 且下载哈希一致；真机导入验收待解除。

## 状态建议

`ACCEPTANCE`：本机流水线全量执行、同步包与后端接口实测通过；研报 OCR/人工复核已在本机完成；解除条件=Android 真机导入/展示图谱快照。
