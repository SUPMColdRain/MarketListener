# MarketListener 产业链图谱现状分析

> 版本：v1.2 · 2026-08-09 · 依据仓库当前代码与数据编写（本阶段未修改代码）；研报数字已于研报补齐+OCR 完成、per-fact 链聚合生效与 F10 合并后更新。

## 1. 结论摘要

MarketListener 已具备一条完整、可用的“研报 → 事实 → 产业链索引 → 图谱 HTML → 电脑端 / Android 同步包”流水线，720+ 篇研报全部落库：721 份 `report_*.json` 全部 REVIEWED（含 1 篇 OCR 补偿、1 篇源缺失保留），产出 177 条原始子链、33,193 条事实、33,193 条链上事实（per-fact 链聚合，无丢弃）；新版 `industry-atlas.json/html` 已合并 F10 CN 5,539 + HK 2,806 + legacy 1,017，7,090 家公司带证券代码（Atlas 展示口径 75 条链；产业链定义待用户人工校验）。

现状的主要差距：

1. 图谱视觉是深色 SVG 知识图谱（节点连线），不是用户要求的券商研报式产业链全景大图。
2. 产业链中的公司只有“名称 + 出现次数”，没有证券代码、市值、证监会行业、主营、收入构成等 F10 字段，无法做 A/H 股精确定位。
3. Android 图谱页目前以 WebView 加载旧版 `industry-map.html`，与新版目标（完全离线、悬浮 F10）不匹配。
4. 本地行情数据目前只覆盖少量股票（CN 5 只、HK 4 只），不足以支撑“全部 A/H 股”企业底表；F10 需要独立数据源。

## 2. 现有数据流

```text
行业产业链研报/ (720 篇 PDF)
   │  pypdf 解析（PDF → 分页文本）
   ▼
desktop/src/market_monitor/report_pipeline.py
   │  _extract_report / _extract_facts_from_page（规则抽取）
   │  状态机：SCANNED → PARSED → EXTRACTED → VERIFIED → REVIEWED
   ▼
reports/industry/report_<sha16>.json   （721 份 JSON 已 REVIEWED，0 失败）
   │  _aggregate_chains()
   ▼
reports/industry/chain_index.json      （177 条链，33,193 条链上事实）
   │  build_industry_map_html()
   ▼
reports/industry/industry-map.html     （自包含 HTML + SVG，约 9.6 MB）
   │  同步
   ▼
data_control/industry/industry-map.html（Android 快照）
   │  package_builder.build_android_package()
   ▼
data_control/packages/market-*.zip      （extra_files 含 industry/industry-map.html）
   │  Android MarketPackageImporter
   ▼
Android GraphTab（WebView 加载 industry-map.html 或 GraphRepository 解析快照）
```

## 3. 现有数据模型

### 3.1 chain_index.json

```json
{
  "generated_at": "...",
  "chain_count": 177,
  "report_count": 721,
  "fact_count": 33193,
  "chains": [
    {
      "chain": "人工智能",
      "report_count": 253,
      "fact_count": 1625,
      "segments": [],
      "companies": [{"name": "华为", "count": 100}, ...],
      "products": [{"name": "PC", "count": 49}, ...],
      "materials": [{"name": "...", "count": 1}, ...],
      "services": [],
      "facts": [
        {
          "entity": "寒武纪",
          "entity_type": "COMPANY",
          "chain": "人工智能",
          "stage": "服务",
          "evidence": "...",
          "page": 9,
          "confidence": 0.95,
          "report_id": "...",
          "file_name": "..."
        }
      ],
      "reports": [{"report_id": "...", "file_name": "...", "title": "...", ...}],
      "cooccurrences": [{"company": "...", "product": "...", "evidence": "...", ...}]
    }
  ]
}
```

关键事实：

- 每条链的 `facts` 被截断到最多 200 条；`companies`/`products`/`materials`/`services` 是“名称 + 计数”聚合，不含证券代码。
- 事实的 `stage` 取值只有 4 类：上游（618）、中游（3,852）、下游（2,773）、服务（1,189）——这正好可以映射到新版“上游/中游/下游/配套支撑”分区。
- 实体类型：COMPANY（4,785）、PRODUCT（3,147）、RAW_MATERIAL（500）。
- 公司名称包含大量非 A/H 上市公司（华为、英伟达、特斯拉、谷歌等），需要区分“A/H 上市 / 非上市 / 境外上市”。

### 3.2 行业图谱领域模型（industry_graph）

- `models.py`：Entity / Evidence / Relationship，契约校验 `contracts/industry-graph-{entity,evidence,relationship}.schema.json`（v1）。
- `pipeline.py`：从 HTML/Excel/PDF/公告导入记录 → 归一化实体 → 抽取关系 → 合并 → `validate_graph_snapshot`。
- `review.py` / `evaluate.py`：人工确认与 gold-standard 评估。
- Android `GraphModels.kt` 解析“graph snapshot JSON”（entities/evidence/relationships），`GraphRepository.kt` 提供离线搜索。

现状：`industry_graph` 是独立于 `chain_index` 的领域模型层；`chain_index` 是研报聚合产物。新版图谱应继续复用 `chain_index` 作为事实来源，同时把 F10 企业底表作为“公司定位层”合并进去，而不是另建一套产业链数据库。

## 4. 现有 HTML 生成路径

`report_pipeline.py`：

- `_aggregate_chains()`：聚合全部 report JSON，生成 chain_index。
- `_chain_graph()` / `_layout_graph()` / `_svg_for_chain()`：把链构建成节点+边并做分层布局（原材料/上游 → 中游 → 下游 → 产品/服务 → 公司）。
- `_build_html()`：深色主题，链 Tab + 搜索 + 图例 + 节点点击详情弹窗，并把完整 INDEX JSON 内嵌为 `window.INDEX`。
- `build_industry_map_html()`：写 `reports/industry/industry-map.html`，并同步 `data_control/industry/industry-map.html`。

生成方式：单文件自包含（无 CDN、无外部请求），可被 file:// 直接打开，可进 Android 同步包。

## 5. 电脑后端与 Android 消费路径

### 5.1 control_center.py（HTTP 8765）

- `/industry`、`/industry/`、`/industry/industry-map.html` → `_send_industry_map()`。
- `_send_industry_map()` 依次尝试 `data_control/industry/industry-map.html` 与 `reports/industry/industry-map.html`。
- 首页 HTML 中有“产业链图谱”入口链接。

### 5.2 package_builder.py / market_package.py

- `build_android_package()` 把 `data_control/industry/industry-map.html` 作为 `extra_files` 打入 `industry/industry-map.html`。
- `market_package.py` 把这些 extra files 写入 zip；Android 侧按白名单解包。

### 5.3 Android

- `MainActivity.kt`：`refreshIndustryHtml()` 从冷数据目录 `packages/<id>/industry/industry-map.html` 复制到 `filesDir/industry-map.html`，并暴露 `industryMapFile`。
- `MarketPackageImporter.kt`：白名单含 `industry/industry-map.html`（第 151、214 行附近）。
- `GraphScreen.kt`：`GraphTab` 有两种视图——WebView 加载 SVG 图（`IndustryMapView`）与 GraphRepository 搜索/详情。

## 6. 改造点（建议顺序）

1. **F10 企业底表**（新增数据层）：
   - 股票 universe：CN 全量 A 股 + HK 全量港股（akshare 一次性列表接口）。
   - F10 字段：代码、名称、总市值、流通市值、证监会/东财行业、公司简介、主营、收入构成、抓取时间。
   - 落盘 `data_control/industry/f10/cn_f10.jsonl`、`hk_f10.jsonl` + `meta.json`（带抓取进度与限速检查点）。
2. **公司名称 → 证券代码映射**：chain_index 公司名 × F10/参考 HTML 名称归一化匹配（精确优先，别名/后缀归一）。
3. **新版产业链全景图生成器**（新模块 `desktop/src/market_monitor/industry_atlas.py`）：
   - 输入：`chain_index.json` + F10 底表 + 参考 `docs/A股企业产业链精细定位.html`（其 1051 家 A 股公司含 market_cap/revenue/industry/products，作为旧数据兜底并标注来源）。
   - 输出：`reports/industry/industry-atlas.json`（数据快照）与 `industry-atlas.html`（自包含浅色全景大图）。
   - 视觉：上游/中游/下游/配套支撑分区，环节与产品卡片，公司芯片密集排列，悬浮 F10 弹窗，搜索/缩放/链导航，无 CDN、完全离线。
4. **PC 接入**：control_center 新增 `/industry-v2/` 路由（保留 `/industry/` 旧版）。
5. **Android 接入**：package_builder 打入 `industry/industry-atlas.html`；MarketPackageImporter 白名单增加该文件；GraphTab 默认加载新版，旧版作为回退。
6. **测试与文档**：pytest 覆盖生成器（数据完备、无 CDN、转义安全、离线），Android JVM 测试覆盖导入白名单，更新 STATUS/Plan 文档。

## 7. 风险

- **F10 抓取频率**：akshare 东财/巨潮接口是网页接口，短时间高频请求会被封 IP。必须限速（建议每个代码 ≥1.5s）、断点续跑、失败重试后退避、识别 403/444/验证码信号并立即暂停。
- **数据时效**：参考 HTML 中市值/营收为旧快照；F10 新抓取数据需带 `fetched_at`，页面明确标注更新时间；无可靠数据的字段显示“暂无”，禁止 LLM 猜测。
- **名称歧义**：公司简称（如“中移动”）与正式名称（“中国移动有限公司”）映射需归一化；无法可靠匹配的不给代码，避免错配。
- **文件体积**：155 条链 × 公司/产品全量内嵌会使 HTML 超过 10 MB；需控制每链公司/产品上限与 JSON 压缩，Android WebView 才能稳定加载。
- **兼容性**：不删除旧 `industry-map.html` 与 graph snapshot 逻辑；新文件与旧文件并行，避免破坏现有同步包。

## 8. 现状更新（2026-08-09 收尾）

以下为 v1.2 之后的最新事实（2026-08-09）：

- F10 明细抓取：CN `data_control/f10/cn/details_20260809.jsonl` 5,539 条（universe 5,539，state done 5539 / failed 0）；HK `data_control/f10/hk/details_20260809.jsonl` 2,806 条（state done 2784 / failed 0）。
- F10 收入构成（revenue）已补齐：CN `revenue_20260809.jsonl` 4,730 条 + `corrupt-1352.bak` 492 条 + `corrupt-1401.bak` 317 条 = 5,539 唯一代码（零重叠、零坏行、全部含 `revenue_breakdown`）；港股收入构成无可用数据源（东财无港股主营构成报表，已实测三种传参均失败）。
- Atlas v2 重建：75 条链（展示口径；`chain_index.json` 原始 177 条子链）、7,090 家带代码公司、公司索引 7,577、F10 CN 5,539 + HK 2,806 + legacy 1,017；`industry-atlas.html` 约 20 MB（20,018,677 字节）自包含离线（零 CDN），同步 `data_control/industry/industry-atlas.html`（SHA256 与 reports 副本一致，CFD56983…）。
- 修复：市场板块名不再作为产品（`_MARKET_BOARD_TERMS`/`_is_market_board_name`，精确+子串；“主板”仅精确过滤避免误伤电子行业 motherboard）；`_f10_chain_candidates()` 多段 key 优先；`_norm_industry_segment()` 行业分段归一化；`test_industry_atlas.py` 9/9，全量桌面 pytest 0 失败，卡片中“创业板/科创板/沪深/中证/主板/北交所/…/上市/指数”命中 0。
- 用户决定自行阅读研报 PDF 人工校验产业链/环节/产品定义；自动化提炼暂停，F10/revenue 由计划任务限速续抓完成。
- 子 Agent `/root/f10_cn`、`/root/reports_retry` 已打断收工；其启动的抓取/构建进程已终止；后端 8765（PID 30108/35652）保留在线；`fetch.lock` 已改名停用。
- Android 同步包已按新版 atlas 重建：`market-20260809-081649-141aff2e`（13,585,044 字节，ed25519+ecdsa 签名），zip 内 Atlas 哈希一致，后端 `/api/android-package` 实测 200 且下载哈希一致。
