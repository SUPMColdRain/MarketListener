# MarketListener 电脑端组件目录

组件事实来源：`desktop/web/src/`。本目录记录工作台可复用组件、职责与数据来源，
供后续 Android / Web 对齐与回归维护参考。

## 1. 应用外壳

### App.vue

- 统一顶栏：品牌、研究工作台导航（行情/数据/策略/统计/产业链）、管理区导航
  （首页/F10/日志）、主题下拉（跟随系统/浅色/深色）。
- `router.ts` 路由表：`/`、`/market/`、`/data/`、`/strategy/`、`/stats/`、
  `/f10/`、`/f10/company/:instrumentKey`、`/industry/`、`/logs/`；
  `/industry-v2/` 重定向到 `/industry/`。

## 2. 图表组件（`src/components/charts/`）

| 组件 | 能力 | 数据来源 |
| --- | --- | --- |
| `KLineChart.vue` | ECharts Candlestick + Volume，Crosshair 联动，主题色注入 | `GET /api/market/instruments/{id}/bars` |
| `SeriesChart.vue` | 多序列折线/面积图，时间范围裁剪，主题 Tooltip | `GET /api/dashboard/{id}` |
| `HeatmapChart.vue` | 热力图，真实数据范围归一化，无数据不渲染 | `GET /api/metrics/heatmap` |
| `RankingChart.vue` | 动态排名，真实时间帧 + 播放/暂停，动画只做帧间过渡 | `GET /api/metrics/ranking` |

图表约束：本地 ECharts；背景透明、颜色全部来自 `theme.palette`；动画不制造
中间交易数据；数据不足时显示空状态。

## 3. 页面视图（`src/views/`）

| 路由 | 视图 | 内容 |
| --- | --- | --- |
| `/` | HomeView | 首页操作台（既有） |
| `/market/` | MarketView | 标的表 + 搜索/分页/质量状态 + K 线 + 自选（loopback 写） |
| `/data/` | DataView | Dashboard 定义自动加载、多序列图、Ranking、Heatmap、受控数据浏览器（≤500 行） |
| `/strategy/` | StrategyView | 策略定义表、运行历史、手动触发 run（operation 校验）、信号展示 |
| `/stats/` | StatsView | 账本/统计聚合（Android ledger 兼容） |
| `/f10/` | F10View | F10 企业资料库、搜索筛选、`/f10/company/:instrumentKey` 详情 |
| `/industry/` | IndustryView | 产业链唯一正式入口（industry-atlas） |
| `/logs/` | LogsView | 结构化事件日志浏览 |

## 4. 状态与领域层

- `src/stores/theme.ts`：主题模式 + 持久化 + 系统跟随。
- `src/domain/api.ts`：`apiGet/apiPost/apiDelete` 封装与严格格式化函数。
- 后端对应 `desktop/src/market_monitor/web_api/`：`market.py`、`dashboard.py`、
  `strategy.py`、`stats.py`、`watchlist.py`、`common.py`，全部只读/受控适配器。

## 5. 验收相关测试

- Playwright E2E：`desktop/web/e2e/terminal.spec.ts`（8 条）、
  `industry-hover.spec.ts`（5 条）。
- Python API 测试：`desktop/tests/test_web_*_api.py` + `web_fixtures.py`。
