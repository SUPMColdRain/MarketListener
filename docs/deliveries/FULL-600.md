# FULL-600 实现交付：港股代表样本、日历、复权和市场范围

日期：2026-08-06
状态：实现完成（领域逻辑与固定样本通过；真实港股拉取受外部端点阻塞，如实记录）
角色：root 实现

## 结果

- `desktop/src/market_monitor/market_expansion.py`：`HK_SAMPLE_INSTRUMENTS`（00700/00005/09988）、AKShare `stock_hk_hist` 中文列归一为跨源英文名（`normalize_hk_bar`）、`probe_hk_daily`（有界超时探针）。
- 日历/复权复用 FULL-121/201：`aggregation.SESSION_RULES["HK_STOCK"]`（午休 12:00-13:00、16:00 收盘）与 `corporate_actions` 复权引擎；市场范围以 `country_or_market=HK, exchange=HKEX` 在 catalog 中表示。
- 测试：`test_market_expansion.py`（列归一、主力选择、连续拼接、ETF 去重、指标校验）。

## 真实探测（2026-08-06，NO_PROXY=*）

| 样本 | 结果 | 原因 |
|---|---|---|
| 00700.HK | FAILED/NETWORK | 东财 `RemoteDisconnected`（与 FULL-110 同源端点问题） |
| 00005.HK | FAILED/NETWORK | 同上 |
| 09988.HK | FAILED/NETWORK | 同上 |

解除条件：东财端点恢复后由验收角色重跑 `probe_hk_daily` 与跨源重叠对比；长期不可达按 PLAN §7 不阻塞主链。

## 自动化证据

`desktop\.venv\Scripts\python.exe -m pytest desktop\tests\test_market_expansion.py -q`：PASS（5 项）；Ruff PASS。

## 状态建议

实现完成，真实港股闭环待外部网络恢复后验收。
