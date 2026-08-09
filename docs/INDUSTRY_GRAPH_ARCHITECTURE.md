# 产业链图谱升级架构

## 1. 总体数据流

```text
720+ 篇研报（721 份报告 JSON 全部 REVIEWED）
   │ chain_index.json（177 链 · 33,193 事实）
   ▼
┌─────────────────────────────────────────────┐
│ industry_atlas.build_atlas()                 │
│  ├─ 读取 chain_index.json                    │
│  ├─ 读取 F10 底表（CN/HK jsonl）             │
│  ├─ 读取 docs/A股企业产业链精细定位.html      │
│  │    （1051 家 A 股旧快照，作兜底并标注）    │
│  ├─ 公司名称 → 证券代码映射                  │
│  ├─ 按链聚合：阶段分区 + 环节/产品卡片 + 公司 │
│  └─ 输出 industry-atlas.json / .html         │
└─────────────────────────────────────────────┘
   │ 同步
   ▼
data_control/industry/industry-atlas.html
   │ control_center /industry-v2/
   │ package_builder → Android zip extra_files
   ▼
PC 浏览器 + Android GraphTab（WebView 离线）
```

## 2. F10 底表

位置：`data_control/industry/f10/`

```text
f10/
├── meta.json          # universe 大小、已抓取/失败、fetched_at、来源、限速参数
├── cn_f10.jsonl       # 每行一个 A 股公司 F10
└── hk_f10.jsonl       # 每行一个港股公司 F10
```

单条记录 schema（JSON）：

```json
{
  "code": "600519",
  "market": "CN.SSE",
  "name": "贵州茅台",
  "full_name": "贵州茅台酒股份有限公司",
  "total_market_cap": 190000000000.0,
  "float_market_cap": 190000000000.0,
  "industry": "食品饮料-白酒",
  "csrc_industry": "酒、饮料和精制茶制造业",
  "profile": "公司简介文本",
  "main_business": "主营文本",
  "revenue_breakdown": [{"item": "茅台酒", "amount": 126590000000.0, "ratio": 0.91}],
  "fetched_at": "2026-08-09T12:00:00+08:00",
  "source": "akshare:stock_individual_info_em|stock_profile_cninfo",
  "status": "ok|partial|failed",
  "note": "字段缺失说明"
}
```

抓取约束：

- 每个代码至少 1.5s 间隔（建议 2–3s），单 Agent 内并发 ≤2，总并发由根 Agent 控制在 3 个以内。
- 支持断点续跑：以 `code → done` 集合决定跳过，每 20 条落盘一次。
- 遇到 403/444/验证码/连续 5 次失败即暂停并写 `pause_reason`，禁止硬刚。
- 不覆盖已有字段：`jsonl` 采用“追加新行 + 去重后写回”或“按 code 覆盖单行”，保证可恢复。

## 3. 公司名称 → 证券代码映射

优先级：

1. 名称精确匹配（chain 公司名 == F10 名称或全称）。
2. 归一化匹配：去空格、括号、公司后缀（股份/有限/集团）、大小写、全半角。
3. 参考 HTML 1051 家 A 股（含 code/name/l1/l2/l3/products/market_cap/revenue），作为旧数据兜底，标记 `source: legacy_html`。
4. 无法匹配 → 保留公司名，`code: null`，页面显示“非 A/H 上市或未能匹配”。

映射结果写入 atlas JSON 的 `company_index`，避免每次重复匹配。

## 4. Atlas JSON 结构

```json
{
  "generated_at": "...",
  "schema_version": "atlas-v1",
  "chain_count": 177,
  "facts": 33193,
  "companies": {"600519": {"code":"600519","name":"贵州茅台", ...F10}},
  "chains": [
    {
      "id": "chain-0",
      "name": "人工智能",
      "report_count": 253,
      "fact_count": 1625,
      "counts": {"a_share": 12, "hk_share": 4},
      "sections": [
        {"stage": "upstream", "label": "上游", "blocks": [
          {"kind": "segment", "name": "算力基础设施", "count": 8,
           "companies": [{"code":"688256","name":"寒武纪","count":47}], "evidence": ["..."]},
          {"kind": "product", "name": "GPU", "count": 32, "companies": [...]}
        ]},
        {"stage": "midstream", ...},
        {"stage": "downstream", ...},
        {"stage": "service", ...}
      ]
    }
  ]
}
```

## 5. HTML 页面结构

单文件自包含：

```text
<header>  标题 · 更新说明 · 主题切换 · 数据源状态</header>
<aside>   链导航（名称 + A/H 股计数 + 搜索框）</aside>
<main>    当前链全景图
  ├─ 阶段分区（upstream/midstream/downstream/service 横排）
  │    ├─ 环节/产品卡片（名称 + 公司 chips）
  │    └─ 公司 chip（名称 + 代码，悬浮出 F10 弹窗）
  └─ 底部证据抽屉（点击公司后展示研报证据句 + 页码 + 报告名）
</main>
<script> 内嵌 atlas JSON；搜索/缩放/弹窗/主题均为原生 JS，零依赖</script>
```

性能约束：

- 单链公司 chips 上限（默认 60），产品/环节块上限（默认 40），超出按 count 截断并在卡片上标注“仅显示前 N 项”。
- atlas JSON 使用压缩 JSON 内嵌（去空白），HTML 目标 < 12 MB。
- 图片、图标全部内联（CSS/emoji），无外部资源。

## 6. PC 与 Android 接入

### PC（control_center.py）

- 新增 `/industry-v2/`、`/industry-v2/industry-atlas.html` 路由，优先读 `data_control/industry/industry-atlas.html`，回退 `reports/industry/industry-atlas.html`。
- 首页增加“产业链图谱（新版）”入口。

### Android

- `package_builder.py` extra_files 增加 `("industry/industry-atlas.html", data_control/industry/industry-atlas.html)`。
- `MarketPackageImporter.kt` 白名单增加 `industry/industry-atlas.html`。
- `MainActivity.kt` `refreshIndustryHtml()` 同时复制新版文件；`GraphScreen.kt` 默认 `industry-atlas.html`（保留旧版回退按钮）。

## 7. 不变量

- 旧版 `industry-map.html`、`GraphRepository`、graph snapshot 逻辑保留。
- `industry_graph` 领域模型不删除；F10 底表不进入该模型，作为展示层数据。
- 所有生成物可重复构建（输入不变 → 输出字节不变）。

## 8. 实施差异与收尾说明（2026-08-09）

- F10 落盘路径按实现为 `data_control/f10/{cn,hk}/details_*.jsonl` + `records.json`/`state.json`（不是第 6 节草案中的 `data_control/industry/f10/*.jsonl`）；atlas 的 `load_f10()` 读该路径。
- F10 明细已抓取：CN 5,539 / HK 2,806；A 股收入构成（revenue）已补齐：CN `revenue_20260809.jsonl` 4,730 条 + 两个 bak 809 条 = 5,539 唯一代码（互不重叠），港股收入构成无可用数据源。
- Atlas v2 输出：75 条链（展示口径，`chain_index.json` 原始 177 条子链）、7,090 家带代码公司、公司索引 7,577、F10 CN 5,539 + HK 2,806 + legacy 1,017。
- 体积约束与实现差异：第 5 节目标“HTML < 12 MB”当前未满足（`industry-atlas.html` 约 20 MB / 20,018,677 字节）；离线与零 CDN 约束已满足。
- 市场板块脏词过滤：`_MARKET_BOARD_TERMS`/`_is_market_board_name`（“创业板/科创板/沪深/中证/主板/北交所”等不再作为产品）；“主板”仅精确过滤以保留电子行业 motherboard 语义。
- 后端 `/industry-v2/` 每次请求从磁盘读取 `industry-atlas.html`；Android 同步包按 `data_control/industry/industry-atlas.html` 快照打包。
- 用户指示：产业链/环节/产品定义改由用户自行阅读研报 PDF 人工校验；自动化提炼暂停；子 Agent 已停，后端 8765 保留在线。
