# MarketListener 终端设计 Token

本文档是电脑端 Web 工作台（`desktop/web`）与 Android 设计语言共用的设计令牌说明。
单一事实来源是 `desktop/web/src/design/tokens.ts`；页面与图表一律从这里取色，
禁止在组件里散落硬编码 RGB。

## 1. 主题模式

- `ThemeMode = "system" | "light" | "dark"`，默认 `system`。
- `useThemeStore`（`desktop/web/src/stores/theme.ts`）读取
  `localStorage["marketlistener.theme"]` 持久化，并监听
  `prefers-color-scheme` 的 `change` 事件，系统主题变化即时生效。
- `applyTokens(theme)` 把完整 Palette 写成 `--ml-*` CSS 变量并设置
  `html[data-theme]` 与 `.dark` class；所有页面、Element Plus 组件、ECharts
  图表在主题切换时同步刷新。

## 2. 语义色 Token

金融状态色是稳定语义，不随主题漂移：

| Token | 含义 |
| --- | --- |
| `priceUp` | 上涨 = 红（Dark `#f0414e` / Light `#d92d20`） |
| `priceDown` | 下跌 = 绿（Dark `#22b07d` / Light `#0e9f6e`） |
| `flat` | 平盘 = 灰 |
| `warning` / `error` / `info` / `highlight` | 警告 / 错误 / 信息 / 高亮 |

## 3. Dark Palette

| Token | 值 |
| --- | --- |
| background | `#0b0e14` |
| surface | `#10151e` |
| surfaceElevated | `#151c27` |
| surfaceSelected | `#1b2534` |
| divider | `#232d3d` |
| textPrimary | `#e8edf5` |
| textSecondary | `#929eaf` |
| textDisabled | `#586273` |
| accent | `#2962ff` |
| accentSoft | `#1e3a8a` |
| chartGrid / chartAxis | `#232d3d` / `#7c8899` |
| chartTooltip / chartTooltipBorder | `#1b2534` / `#31415c` |

## 4. Light Palette

| Token | 值 |
| --- | --- |
| background | `#f5f7fa` |
| surface | `#ffffff` |
| surfaceElevated | `#f0f3f8` |
| surfaceSelected | `#e8eef8` |
| divider | `#e1e6ee` |
| textPrimary | `#11151c` |
| textSecondary | `#687386` |
| textDisabled | `#9aa5b4` |
| accent | `#2962ff` |
| accentSoft | `#dbe6ff` |
| chartGrid / chartAxis | `#e1e6ee` / `#687386` |
| chartTooltip / chartTooltipBorder | `#ffffff` / `#d7dee9` |

## 5. 数据展示规则

- `desktop/web/src/domain/api.ts` 提供 `formatNumber / formatPct / formatMoney /
  formatBytes / formatTime`；缺失、`null`、`NaN`、`Infinity`、非法日期一律渲染
  “暂无数据”。
- 后端 `web_api/common.py::clean/json_dumps` 递归把 `NaN/Infinity` 清洗为
  `null`，JSON 输出永不包含 `undefined/Invalid Date`。
- 图表组件只接收有限数值；空数据不画 0 线，显示空状态。

## 6. 使用约束

- 新增组件颜色必须来自 `useThemeStore().palette` 或 `--ml-*` CSS 变量。
- ECharts 本地化（npm 依赖，不使用 CDN/远程字体）。
- 上涨/下跌不能只靠颜色表达，重要状态必须同时有文字或符号。
