# FULL-801 实现交付：数据质量、运行历史、存储与来源健康看板

日期：2026-08-06
状态：实现完成（等待系列统一审查）
角色：root 实现

## 范围与边界

本地健康看板：从 MarketStore 目录读取运行历史（含 FAILED 与 detail）、分区状态与陈旧标记、隔离区条目、Bronze/Silver/隔离区存储占用，输出 JSON 与 Markdown。失败/陈旧/空间告警可定位到来源运行、分区与质量问题。

## 修改文件

- `desktop/src/market_monitor/dashboard.py`：`build_health_report`（stale 阈值可注入、时钟可注入）、`render_markdown`；损坏的隔离区报告按阻断显示。
- `desktop/tests/test_dashboard.py`：构造 FAILED run、3 天前分区（stale）、隔离区条目并断言全部可见；损坏报告降级为阻断。

## 自动化证据

| 验证项 | 实际命令 | 结果 |
|---|---|---|
| 看板专项 | `desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_dashboard.py desktop\tests\test_ops.py -q` | PASS（7 项） |
| 静态检查 | `desktop\.venv\Scripts\python.exe -m ruff check desktop\src desktop\tests` | PASS |

## 风险与未完成项

- 看板 Web/桌面 UI 与告警通知渠道留待 FULL-803/用户验收；当前为 CLI/文件输出。

## 状态建议

实现完成，等待系列统一审查与验收。
