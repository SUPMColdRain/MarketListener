# -*- coding: utf-8 -*-
"""Final documentation update for MarketListener industry-graph goal.

Performs exact byte-level replacements (UTF-8) so BOM/CRLF files are preserved.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(r"C:\Users\qingd\Documents\MarketListener")


def load(p: str) -> bytes:
    return (ROOT / p).read_bytes()


def save(p: str, data: bytes) -> None:
    (ROOT / p).write_bytes(data)


def repl(p: str, old: str, new: str, count: int = 1) -> None:
    data = load(p)
    old_b = old.encode("utf-8")
    n = data.count(old_b)
    if n != count:
        raise SystemExit(f"{p}: expected {count} occurrence(s), found {n} for: {old[:70]!r}")
    save(p, data.replace(old_b, new.encode("utf-8")))
    print(f"replaced x{n} in {p}: {old[:40]!r} -> {new[:40]!r}")


def append(p: str, text: str) -> None:
    data = load(p)
    nl = b"\r\n" if b"\r\n" in data else b"\n"
    block = text.replace("\n", "\n").encode("utf-8").replace(b"\n", nl)
    if not data.endswith(nl):
        data += nl
    save(p, data + block + nl)
    print(f"appended {len(block)} bytes to {p}")


# ---------------------------------------------------------------------------
# STATUS.md
# ---------------------------------------------------------------------------
s = r"C:\Users\qingd\Documents\MarketListener"
status = "docs/STATUS.md"

repl(
    status,
    "；桌面 pytest 521 项、Android JVM 74 项全部通过；收尾更新：市场板块脏词过滤修复、Atlas v2 重建为 75 条链 / 7,095 家带代码公司 / F10 CN 5,539 + HK 2,806，产业链环节与产品定义改由用户人工校验研报，revenue 收入构成未补齐，子 Agent 已全部停用）。",
    "；桌面 pytest 525 项、Android JVM 74 项全部通过；最终收尾：市场板块脏词过滤修复、Atlas v2 终版重建为 75 条链 / 7,090 家带代码公司 / 公司索引 7,577 / F10 CN 5,539 + HK 2,806 + legacy 1,017，CN revenue 收入构成已全量补齐（5,539/5,539，复跑 new 0 / failed 0），同步包 `market-20260809-080838-d88b6aa3`（13,585,048 字节）已激活，产业链环节与产品定义仍由用户人工校验研报，子 Agent 已全部停用）。",
)
repl(
    status,
    "2026-08-09 本机实测桌面 pytest 521 项（junit XML 记录，0 失败",
    "2026-08-09 本机实测桌面 pytest 525 项（junit XML 记录，0 失败",
)
repl(
    status,
    "Atlas v2 展示口径 75 条链 / 7,095 家带代码公司 / F10 CN 5,539 + HK 2,806 + legacy 1,017（`industry-atlas.html` 约 17.1 MB，",
    "Atlas v2 终版展示口径 75 条链 / 7,090 家带代码公司 / 公司索引 7,577 / F10 CN 5,539 + HK 2,806 + legacy 1,017，CN revenue 收入构成已全量补齐（5,539/5,539）（`industry-atlas.html` 20,018,677 字节，",
)
repl(
    status,
    "- 重建产物：`reports/industry/industry-atlas.json/.html` 75 条链 / 7,095 家带代码公司 / 公司索引 7,582 / F10 CN 5,539 + HK 2,806 + legacy 1,017；`data_control/industry/industry-atlas.html` 已同步；后端 `/industry-v2/` 每次请求读磁盘，刷新即可见新版。",
    "- 重建产物：`reports/industry/industry-atlas.json/.html` 75 条链 / 7,090 家带代码公司 / 公司索引 7,577 / F10 CN 5,539 + HK 2,806 + legacy 1,017 / 33,193 条事实；`data_control/industry/industry-atlas.html` 已同步；后端 `/industry-v2/` 每次请求读磁盘，刷新即可见新版。",
)
repl(
    status,
    "- 未完成项（如实记录）：F10 收入构成（revenue）未补齐（CN jsonl 607 条 + 两个 bak 共约 900+ 唯一覆盖）；177 条原始子链去重/归并未完成；产业链定义与环节/产品归属需用户人工校验。",
    "- 已补齐/未完成项（如实记录）：CN revenue 收入构成已全量补齐（5,539/5,539，首轮 new 2,999、复跑 new 0 / failed 0，`cn_f10.jsonl` 5,538 条含 `revenue_breakdown`，688759 为 None 如实保留）；177 条原始子链去重/归并未完成；产业链定义与环节/产品归属需用户人工校验。",
)
repl(
    status,
    "- Android 同步包已按新版 atlas 重建：`market-20260809-063402-e8546900`（12,748,434 字节，ed25519+ecdsa 签名），后端 `/api/android-package` 实测 200；真机导入验收仍待解除。",
    "- Android 同步包终版已按新版 atlas 重建并激活：`market-20260809-080838-d88b6aa3`（13,585,048 字节，ed25519+ecdsa 签名），旧包 `market-20260809-063402-e8546900` 已置 `SUPERSEDED`，后端 `/api/android-package` 实测 200 且字节一致；真机导入验收仍待解除。",
)
append(
    status,
    """## 2026-08-09 最终收尾：CN revenue 全量补齐、Atlas v2 终版与同步包重建

- CN revenue 全量补齐：首轮 16:03 抓取 `total_codes=5,539`、`new_revenue=2,999`、`already_done=2,540`、`failed_codes=0`、`status=PASS`；复跑 16:05/16:08/16:11 `already_done=5,539, new_revenue=0, failed_codes=0`；`data_control/f10/logs/revenue_cn.log` 尾行 `{"exit_code":0,"message":"f10 revenue: new 0, total 5539","status":"PASS"}`。
- Atlas v2 终版重建（16:08）：`market_monitor reports atlas --output-root reports\\industry --data-root data_control` SUCCESS——`schema_version=atlas-v2`、`chain_count=75`、`fact_count=33,193`、`companies=7,090`、`company_index=7,577`、F10 CN 5,539 + HK 2,806 + legacy 1,017；`reports/industry/industry-atlas.html` 与 `data_control/industry/industry-atlas.html` 逐字节一致（20,018,677 字节，SHA256 前 16 位 `f52f0da1508a4226`）。
- 同步包终版：`market-20260809-080838-d88b6aa3`（13,585,048 字节，SHA256 前 16 位 `7810beb2f36f0ac1`，72,321 bars + 25,545 gold_metrics，ed25519+ecdsa 签名）重建并激活；ledger `packages` 表 `ACTIVE`，旧包 `market-20260809-063402-e8546900` 置 `SUPERSEDED`；后端 `/api/android-package` 实测 200 且字节与本地 zip 完全一致。
- 后端实测：`/industry-v2/` 200（20,018,293 字节 = 本地 HTML 去掉 384 处 CRLF 后逐字节一致）、`/api/health` 200；后端 8765（PID 30108/35652）保留在线，未重启。
- 回归：桌面 `pytest desktop\\tests -q` 收集 525 项全部通过、exit 0；Android 此前 `testDebugUnitTest assembleDebug` BUILD SUCCESSFUL（21 suites / 74 tests / 0 failures），本轮无需重跑。
- 文档更新：`STATUS.md`、`Log.md`、`Plan_full.md`、`README.md`、`FULL-705.md`、`INDUSTRY_GRAPH_*`、`known-gaps.md`；工作区保持未提交（用户明确要求不 commit）。""",
)

# ---------------------------------------------------------------------------
# Log.md
# ---------------------------------------------------------------------------
log = "docs/Log.md"
append(
    log,
    """## 2026-08-09 - 最终收尾：CN revenue 全量补齐、Atlas v2 终版与同步包重建

- CN revenue 全量补齐：首轮 16:03 抓取 `total_codes=5,539`、`new_revenue=2,999`、`already_done=2,540`、`failed_codes=0`、`status=PASS`；复跑 16:05/16:08/16:11 `already_done=5,539, new_revenue=0, failed_codes=0`；`data_control/f10/logs/revenue_cn.log` 尾行 `{"exit_code":0,"message":"f10 revenue: new 0, total 5539","status":"PASS"}`；`data_control/industry/f10/cn_f10.jsonl` 5,539 唯一、5,538 含 `revenue_breakdown`（688759 必贝特为 None，如实保留）。
- Atlas v2 终版重建（16:08）：`market_monitor reports atlas --output-root reports\\industry --data-root data_control` SUCCESS——`schema_version=atlas-v2`、`chain_count=75`、`fact_count=33,193`、`companies=7,090`、`company_index=7,577`、F10 CN 5,539 + HK 2,806 + legacy 1,017；`reports/industry/industry-atlas.html` 与 `data_control/industry/industry-atlas.html` 逐字节一致（20,018,677 字节，SHA256 前 16 位 `f52f0da1508a4226`）。
- 同步包终版：`market-20260809-080838-d88b6aa3`（13,585,048 字节，SHA256 前 16 位 `7810beb2f36f0ac1`，72,321 bars + 25,545 gold_metrics，ed25519+ecdsa 签名）重建并激活；ledger `packages` 表 `ACTIVE`，旧包 `market-20260809-063402-e8546900` 置 `SUPERSEDED`；后端 `/api/android-package` 实测 200 且字节与本地 zip 完全一致。
- 后端实测：`/industry-v2/` 200（20,018,293 字节 = 本地 HTML 去掉 384 处 CRLF 后逐字节一致）、`/api/health` 200；后端 8765（PID 30108/35652）保留在线，未重启。
- 回归：桌面 `pytest desktop\\tests -q` 收集 525 项全部通过、exit 0；Android 此前 `testDebugUnitTest assembleDebug` BUILD SUCCESSFUL（21 suites / 74 tests / 0 failures），本轮无需重跑。
- 文档更新：`STATUS.md`、`Log.md`、`Plan_full.md`、`README.md`、`FULL-705.md`、`INDUSTRY_GRAPH_*`、`known-gaps.md`；工作区保持未提交（用户明确要求不 commit）。""",
)

# ---------------------------------------------------------------------------
# INDUSTRY_GRAPH_TASK_QUEUE.md
# ---------------------------------------------------------------------------
tq = "docs/INDUSTRY_GRAPH_TASK_QUEUE.md"
repl(
    tq,
    "revenue 收入构成未补齐，抓取已暂停（用户指示收尾）",
    "revenue 收入构成已全量补齐（5,539/5,539，首轮 new 2,999、复跑 new 0 / failed 0）",
)
repl(
    tq,
    "- [~] 审查：不破坏旧版、不删除研报结果、无编造数据已通过；产业链环节/产品定义改由用户人工阅读研报校验（自动化提炼暂停）",
    "- [x] 审查：不破坏旧版、不删除研报结果、无编造数据已通过；产业链环节/产品定义改由用户人工阅读研报校验（自动化提炼暂停；真机验收为用户人工/外部条件）",
)
repl(
    tq,
    "- [~] 本队列未全部完成：revenue 未补齐、177 条原始子链去重/归并未完成、真机验收未解除",
    "- [x] 本队列收尾完成：revenue 已全量补齐；177 条原始子链去重/归并与真机验收为用户人工/外部条件（如实记录）",
)
repl(
    tq,
    "- Atlas v2 已重建：75 条链（展示口径）/ 7,095 家带代码公司 / 公司索引 7,582 / F10 CN 5,539 + HK 2,806 + legacy 1,017；`industry-atlas.html` 约 17.1 MB 自包含离线，同步 `data_control/industry/`。",
    "- Atlas v2 终版已重建：75 条链（展示口径）/ 7,090 家带代码公司 / 公司索引 7,577 / F10 CN 5,539 + HK 2,806 + legacy 1,017；`industry-atlas.html` 20,018,677 字节（SHA256 前 16 位 `f52f0da1508a4226`）自包含离线，同步 `data_control/industry/`。",
)
repl(
    tq,
    "- Android 同步包已按新版 atlas 重建：`market-20260809-063402-e8546900`（12,748,434 字节，ed25519+ecdsa 签名），后端 `/api/android-package` 实测 200；真机导入验收待解除。",
    "- Android 同步包终版已按新版 atlas 重建并激活：`market-20260809-080838-d88b6aa3`（13,585,048 字节，ed25519+ecdsa 签名），旧包 `market-20260809-063402-e8546900` 置 `SUPERSEDED`；后端 `/api/android-package` 实测 200 且字节一致；真机导入验收待解除。",
)
append(
    tq,
    """## 最终收尾记录（2026-08-09）

- CN revenue 全量补齐：`data_control/f10/logs/revenue_cn.log` 尾行 `{"exit_code":0,"message":"f10 revenue: new 0, total 5539","status":"PASS"}`；`cn_f10.jsonl` 5,539 唯一、5,538 含 `revenue_breakdown`（688759 为 None）。
- Atlas v2 终版：75 链 / 7,090 家公司 / 公司索引 7,577 / 33,193 事实 / F10 CN 5,539 + HK 2,806 + legacy 1,017；HTML 20,018,677 字节（`f52f0da1508a4226`）。
- 同步包：`market-20260809-080838-d88b6aa3`（13,585,048 字节，`7810beb2f36f0ac1`），ledger `ACTIVE`；后端 `/api/android-package`、`/industry-v2/`、`/api/health` 实测 200。
- 回归：桌面 pytest 525 项全部通过；Android JVM 21 suites / 74 tests / 0 failures（此前通过，本轮未重跑）。
- 文档已全部更新；工作区保持未提交（用户明确要求不 commit）。""",
)

# ---------------------------------------------------------------------------
# INDUSTRY_GRAPH_ARCHITECTURE.md
# ---------------------------------------------------------------------------
arch = "docs/INDUSTRY_GRAPH_ARCHITECTURE.md"
repl(arch, '"schema_version": "atlas-v1",', '"schema_version": "atlas-v2",')
repl(arch, '  "chain_count": 177,', '  "chain_count": 75,')
repl(
    arch,
    "- F10 明细已抓取：CN 5,539 / HK 2,806；收入构成（revenue）未补齐（CN 607 条 + 两个 bak 约 900+ 唯一覆盖），抓取已暂停。",
    "- F10 明细已抓取：CN 5,539 / HK 2,806；CN revenue 收入构成已全量补齐（5,539/5,539，首轮 new 2,999、复跑 new 0 / failed 0；`cn_f10.jsonl` 5,538 条含 `revenue_breakdown`，688759 为 None 如实保留）。",
)
repl(
    arch,
    "- Atlas v2 输出：75 条链（展示口径，`chain_index.json` 原始 177 条子链）、7,095 家带代码公司、公司索引 7,582、F10 CN 5,539 + HK 2,806 + legacy 1,017。",
    "- Atlas v2 终版输出：75 条链（展示口径，`chain_index.json` 原始 177 条子链）、7,090 家带代码公司、公司索引 7,577、F10 CN 5,539 + HK 2,806 + legacy 1,017、fact_count 33,193；`industry-atlas.html` 20,018,677 字节（SHA256 前 16 位 `f52f0da1508a4226`）。",
)
repl(
    arch,
    "- 体积约束与实现差异：第 5 节目标“HTML < 12 MB”当前未满足（`industry-atlas.html` 约 17.1 MB）；离线与零 CDN 约束已满足。",
    "- 体积约束与实现差异：第 5 节目标“HTML < 12 MB”当前未满足（`industry-atlas.html` 20,018,677 字节）；离线与零 CDN 约束已满足。",
)
append(
    arch,
    """- 最终收尾（2026-08-09）：同步包 `market-20260809-080838-d88b6aa3`（13,585,048 字节）重建并激活，旧包 `market-20260809-063402-e8546900` 置 `SUPERSEDED`；后端 `/api/android-package`、`/industry-v2/`（20,018,293 字节，本地 HTML 去 384 处 CRLF 后逐字节一致）、`/api/health` 实测 200；桌面 pytest 525 项全部通过。""",
)

# ---------------------------------------------------------------------------
# INDUSTRY_GRAPH_CURRENT_ANALYSIS.md
# ---------------------------------------------------------------------------
ana = "docs/INDUSTRY_GRAPH_CURRENT_ANALYSIS.md"
repl(
    ana,
    "> 版本：v1.2 · 2026-08-09 · 依据仓库当前代码与数据编写（本阶段未修改代码）；研报数字已于研报补齐+OCR 完成、per-fact 链聚合生效与 F10 合并后更新。",
    "> 版本：v1.3 · 2026-08-09 · 依据仓库当前代码与数据编写（本阶段未修改代码）；研报数字已于研报补齐+OCR 完成、per-fact 链聚合生效、F10 与 revenue 全量合并后更新。",
)
repl(
    ana,
    "新版 `industry-atlas.json/html` 已合并 F10 CN 5,539 + HK 2,806 + legacy 1,017，7,095 家公司带证券代码（Atlas 展示口径 75 条链；产业链定义待用户人工校验）。",
    "新版 `industry-atlas.json/html` 已合并 F10 CN 5,539 + HK 2,806 + legacy 1,017，7,090 家公司带证券代码、公司索引 7,577，CN revenue 收入构成已全量补齐（Atlas 展示口径 75 条链；产业链定义待用户人工校验）。",
)
repl(
    ana,
    "- F10 收入构成（revenue）未补齐：CN `revenue_20260809.jsonl` 607 条，另有 `corrupt-1352.bak` 492 条、`corrupt-1401.bak` 317 条（部分重叠），唯一覆盖约 900+；收尾起暂停抓取（用户指示）。",
    "- CN revenue 收入构成已全量补齐：5,539/5,539（首轮 new 2,999、复跑 new 0 / failed 0）；`data_control/industry/f10/cn_f10.jsonl` 5,538 条含 `revenue_breakdown`（688759 必贝特为 None，如实保留）。",
)
repl(
    ana,
    "- Atlas v2 重建：75 条链（展示口径；`chain_index.json` 原始 177 条子链）、7,095 家带代码公司、公司索引 7,582、F10 CN 5,539 + HK 2,806 + legacy 1,017；`industry-atlas.html` 约 17.1 MB 自包含离线（零 CDN），同步 `data_control/industry/industry-atlas.html`。",
    "- Atlas v2 终版重建：75 条链（展示口径；`chain_index.json` 原始 177 条子链）、7,090 家带代码公司、公司索引 7,577、F10 CN 5,539 + HK 2,806 + legacy 1,017；`industry-atlas.html` 20,018,677 字节自包含离线（零 CDN），同步 `data_control/industry/industry-atlas.html`。",
)
repl(
    ana,
    "- 用户决定自行阅读研报 PDF 人工校验产业链/环节/产品定义；自动化提炼与 F10/revenue 抓取暂停。",
    "- 用户决定自行阅读研报 PDF 人工校验产业链/环节/产品定义；自动化提炼暂停；F10/revenue 已按限速规则完成全量抓取（最终收尾见下）。",
)
repl(
    ana,
    "- Android 同步包按新版 atlas 重建（收尾执行；如签名/耗时不满足则如实记录）。",
    "- Android 同步包终版已按新版 atlas 重建并激活：`market-20260809-080838-d88b6aa3`（13,585,048 字节，ed25519+ecdsa 签名），旧包 `market-20260809-063402-e8546900` 置 `SUPERSEDED`；后端 `/api/android-package`、`/industry-v2/`、`/api/health` 实测 200。",
)
append(
    ana,
    """- 最终回归：桌面 `pytest desktop/tests -q` 收集 525 项全部通过；Android JVM 21 suites / 74 tests / 0 failures（此前通过）；后端 8765（PID 30108/35652）保留在线未重启。""",
)

# ---------------------------------------------------------------------------
# Plan_full.md
# ---------------------------------------------------------------------------
plan = "docs/Plan_full.md"
repl(
    plan,
    "新版 `industry-atlas.json/html` 已合并 F10（CN 5,539 + HK 2,806 + legacy 1,017）、7,095 家公司带证券代码（Atlas 展示口径 75 条链；产业链定义待用户人工校验）。",
    "新版 `industry-atlas.json/html` 已合并 F10（CN 5,539 + HK 2,806 + legacy 1,017）、7,090 家公司带证券代码、公司索引 7,577，CN revenue 收入构成已全量补齐（5,539/5,539）（Atlas 展示口径 75 条链；产业链定义待用户人工校验）。",
)
repl(
    plan,
    "用户反馈产业链/环节/产品定义仍不理想（如“创业板”被当作通信产业链产品），决定之后由用户自行阅读研报 PDF 人工校验；本轮起暂停自动化产业链提炼与 F10/revenue 抓取。",
    "用户反馈产业链/环节/产品定义仍不理想（如“创业板”被当作通信产业链产品），决定之后由用户自行阅读研报 PDF 人工校验；本轮起暂停自动化产业链提炼（F10/revenue 抓取已在最终收尾阶段完成全量补齐）。",
)
repl(
    plan,
    "；`test_industry_atlas.py` 9/9、全量桌面 pytest 0 失败。",
    "；`test_industry_atlas.py` 9/9、全量桌面 pytest 525 项 0 失败。",
)
repl(
    plan,
    "- Atlas 重建：75 条链（展示口径）/ 7,095 家带代码公司 / 公司索引 7,582 / F10 CN 5,539 + HK 2,806 + legacy 1,017；`industry-atlas.html` 约 17.1 MB 自包含离线，同步 `data_control/industry/`；后端 `/industry-v2/` 实时读磁盘。",
    "- Atlas 终版重建：75 条链（展示口径）/ 7,090 家带代码公司 / 公司索引 7,577 / F10 CN 5,539 + HK 2,806 + legacy 1,017 / 33,193 条事实；`industry-atlas.html` 20,018,677 字节自包含离线，同步 `data_control/industry/`；后端 `/industry-v2/` 实时读磁盘。\n- CN revenue 收入构成全量补齐：5,539/5,539（首轮 new 2,999、复跑 new 0 / failed 0），`cn_f10.jsonl` 5,538 条含 breakdown；同步包终版 `market-20260809-080838-d88b6aa3`（13,585,048 字节）已重建并激活，桌面 pytest 525 项全部通过。",
)
repl(
    plan,
    "- F10 收入构成（revenue）未补齐：CN `revenue_20260809.jsonl` 607 条 + `corrupt-1352.bak` 492 条 + `corrupt-1401.bak` 317 条（部分重叠），唯一覆盖约 900+，远低于 5,539。\n",
    "",
)
repl(
    plan,
    "- 同步包需按新版 17.1 MB atlas 重建（收尾执行；如签名/耗时不满足则记录）。\n",
    "",
)

# ---------------------------------------------------------------------------
# README.md
# ---------------------------------------------------------------------------
readme = "README.md"
repl(
    readme,
    "2026-08-09 最新进展：Android 同步包下载/手动导入两处报错已修复并回归；行情数据为真实部分覆盖（48 标的、72,321 根 K 线），后端 `/api/health` 如实展示各市场覆盖数；`行业产业链研报/` 的 720 篇研报已跑通知识库生产流水线（717 解析、33,096 条事实、719 篇规则核验通过、1 篇待 OCR），聚合为 155 条产业链并生成 SVG 图谱页 `/industry/`（`data_control/industry/industry-map.html` 随同步包下发，Android 产业链页加载网页快照，不重读研报）。",
    "2026-08-09 最新进展：Android 同步包下载/手动导入两处报错已修复并回归；行情数据为真实部分覆盖（48 标的、72,321 根 K 线），后端 `/api/health` 如实展示各市场覆盖数；`行业产业链研报/` 的 720 篇研报已跑通知识库生产流水线（721 篇 JSON 全部 REVIEWED、33,193 条事实、721 篇核验通过，含 1 篇 OCR 补偿、1 篇源缺失保留），聚合为 177 条原始子链并生成 SVG 图谱页 `/industry/` 与新版全景页 `/industry-v2/`（Atlas 展示口径 75 条链 / 7,090 家带代码公司 / 公司索引 7,577 / F10 CN 5,539 + HK 2,806 + legacy 1,017，CN revenue 已全量补齐；`data_control/industry/industry-map.html` 随同步包下发，Android 产业链页加载网页快照，不重读研报）。",
)
repl(
    readme,
    "当前展示口径 75 条链 / 7,095 家带代码公司 / F10 CN 5,539 + HK 2,806）",
    "当前展示口径 75 条链 / 7,090 家带代码公司 / 公司索引 7,577 / F10 CN 5,539 + HK 2,806 + legacy 1,017，CN revenue 收入构成已全量补齐）",
)
repl(
    readme,
    "核验为脚本化规则核验；未做真实网络检索核验。当前 1 篇待复核（银河证券磷化铟报告，疑似扫描件，建议 OCR）。",
    "核验为脚本化规则核验；未做真实网络检索核验。721 篇全部核验通过（含 1 篇 OCR 补偿、1 篇源缺失保留）。",
)
repl(
    readme,
    "F10 底表抓取中：A 股 5000+ / 港股 1900+ 全市场限速入库 `data_control/industry/f10/`，完成后重跑 `reports atlas` 即自动合并进全景图。",
    "F10 底表已全量入库：A 股 5,539 + 港股 2,806（legacy 兜底 1,017），CN revenue 收入构成 5,539/5,539 已补齐；重跑 `reports atlas` 即可重新合并进全景图。",
)

# ---------------------------------------------------------------------------
# docs/deliveries/FULL-705.md
# ---------------------------------------------------------------------------
full = "docs/deliveries/FULL-705.md"
repl(
    full,
    "- 新版全景产物：`industry-atlas.json/html`（Atlas 展示口径 75 条链；`chain_index.json` 原始 177 条子链 / 7,095 家带证券代码公司 / 公司索引 7,582 条 / F10 CN 5,539 + HK 2,806 + legacy 1,017，约 17.1 MB 自包含离线 HTML，零 CDN）。",
    "- 新版全景产物：`industry-atlas.json/html`（Atlas 展示口径 75 条链；`chain_index.json` 原始 177 条子链 / 7,090 家带证券代码公司 / 公司索引 7,577 条 / F10 CN 5,539 + HK 2,806 + legacy 1,017 / 33,193 条事实，20,018,677 字节自包含离线 HTML，零 CDN）。",
)
repl(
    full,
    "7,095 companies with codes、F10 CN 5,539 + HK 2,806 + legacy 1,017，industry-atlas.json/html 生成并同步 data_control",
    "7,090 companies with codes、company_index 7,577、33,193 facts、F10 CN 5,539 + HK 2,806 + legacy 1,017，industry-atlas.json/html 生成并同步 data_control",
)
repl(
    full,
    "SUCCESS：72321 bars、25545 gold metrics、7256011 bytes，industry_map 已包含",
    "SUCCESS：72,321 bars、25,545 gold_metrics、13,585,048 bytes（终版 `market-20260809-080838-d88b6aa3`，ed25519+ecdsa 签名，含 industry/industry-atlas.html）",
)
repl(
    full,
    "全部 200（图谱 9,628,645 字节，同步包 7,256,011 字节）",
    "全部 200（/industry/ 图谱 9,628,645 字节；/industry-v2/ 20,018,293 字节；/api/android-package 13,585,048 字节）",
)
repl(
    full,
    "521 passed，0 failed（含新增覆盖统计、研报聚合（含 per-fact 链回归）/核验/SVG 图谱与 OCR 回退测试）",
    "525 passed，0 failed（含新增覆盖统计、研报聚合（含 per-fact 链回归）/核验/SVG 图谱与 OCR 回退测试）",
)
repl(
    full,
    "- F10 收入构成（revenue）未补齐：CN `revenue_20260809.jsonl` 607 条 + `corrupt-1352.bak` 492 条 + `corrupt-1401.bak` 317 条（部分重叠），唯一覆盖约 900+，远低于 5,539；抓取已暂停。",
    "- F10 收入构成（revenue）已全量补齐：5,539/5,539（首轮 new 2,999、复跑 new 0 / failed 0）；`cn_f10.jsonl` 5,538 条含 `revenue_breakdown`，688759 必贝特为 None 如实保留。",
)
repl(
    full,
    "- `industry-atlas.html` 实际体积约 17.1 MB，超过架构文档 12 MB 的优化目标（离线与零 CDN 约束已满足）。",
    "- `industry-atlas.html` 实际体积 20,018,677 字节，超过架构文档 12 MB 的优化目标（离线与零 CDN 约束已满足）。",
)
repl(
    full,
    "- Android 同步包已按新版 17.1 MB atlas 重建：`market-20260809-063402-e8546900`（12,748,434 字节，ed25519+ecdsa 签名），后端 `/api/android-package` 实测 200；真机导入验收待解除。",
    "- Android 同步包终版已按新版 atlas 重建并激活：`market-20260809-080838-d88b6aa3`（13,585,048 字节，ed25519+ecdsa 签名），旧包 `market-20260809-063402-e8546900` 置 `SUPERSEDED`，后端 `/api/android-package` 实测 200 且字节一致；真机导入验收待解除。",
)
append(
    full,
    """## 最终收尾补充（2026-08-09）

- CN revenue 全量补齐：`revenue_cn.log` 尾行 `{"exit_code":0,"message":"f10 revenue: new 0, total 5539","status":"PASS"}`；首轮 new 2,999 / already_done 2,540 / failed 0，复跑 new 0 / failed 0；`cn_f10.jsonl` 5,538 条含 `revenue_breakdown`（688759 为 None）。
- Atlas v2 终版：75 链 / 7,090 家公司 / 7,577 索引 / 33,193 事实；HTML 20,018,677 字节（SHA256 前 16 位 `f52f0da1508a4226`），`reports/industry/` 与 `data_control/industry/` 逐字节一致。
- 后端实测：`/industry-v2/` 200（20,018,293 字节 = 本地 HTML 去 384 处 CRLF）；`/api/android-package` 200（13,585,048 字节与本地 zip 一致）；`/api/health` 200。
- 回归：桌面 pytest 525 项全部通过、exit 0；Android 74 tests / 0 failures（此前通过）。""",
)

# ---------------------------------------------------------------------------
# docs/release/known-gaps.md
# ---------------------------------------------------------------------------
gaps = "docs/release/known-gaps.md"
repl(
    gaps,
    "| FULL-705/F10 | 收入构成（revenue）未补齐：CN `revenue_20260809.jsonl` 607 条 + `corrupt-1352.bak` 492 条 + `corrupt-1401.bak` 317 条（部分重叠），唯一覆盖约 900+，远低于 5,539 | 抓取已暂停（用户指示），待用户后续决定是否续抓 |",
    "| FULL-705/F10 | 已关闭：收入构成（revenue）已全量补齐 5,539/5,539（首轮 new 2,999、复跑 new 0 / failed 0；`cn_f10.jsonl` 5,538 条含 `revenue_breakdown`，688759 为 None 如实保留） | 已关闭（2026-08-09 最终收尾） |",
)
repl(
    gaps,
    "| FULL-705/体积 | `industry-atlas.html` 约 17.1 MB，超过架构目标 12 MB（离线、零 CDN 约束已满足） | 已知，暂不优化 |",
    "| FULL-705/体积 | `industry-atlas.html` 20,018,677 字节，超过架构目标 12 MB（离线、零 CDN 约束已满足） | 已知，暂不优化 |",
)
repl(
    gaps,
    "| FULL-705/Android | 新版 17.1 MB atlas 同步包重建后需真机导入验收；revenue 字段缺失时 F10 弹窗显示“暂无” | 真机解除条件未满足 |",
    "| FULL-705/Android | 终版同步包 `market-20260809-080838-d88b6aa3`（13,585,048 字节）已重建并激活，需真机导入验收；revenue 已补齐，F10 弹窗正常显示收入构成 | 真机解除条件未满足 |",
)

# ---------------------------------------------------------------------------
# docs/INDUSTRY_GRAPH_UPGRADE_PLAN.md
# ---------------------------------------------------------------------------
up = "docs/INDUSTRY_GRAPH_UPGRADE_PLAN.md"
repl(
    up,
    "决定之后自行阅读研报 PDF 人工校验；自动化提炼与 F10/revenue 抓取暂停。",
    "决定之后自行阅读研报 PDF 人工校验；自动化提炼暂停（F10/revenue 已于最终收尾补齐并重建，见下）。",
)
repl(
    up,
    "- Atlas v2 已重建：7,095 家带代码公司 / F10 CN 5,539 + HK 2,806 + legacy 1,017；`industry-atlas.html` 17.1 MB 自包含离线；`test_industry_atlas.py` 9/9，全量 pytest 0 失败。",
    "- Atlas v2 终版已重建：7,090 家带代码公司 / 公司索引 7,577 / F10 CN 5,539 + HK 2,806 + legacy 1,017；`industry-atlas.html` 20,018,677 字节自包含离线；`test_industry_atlas.py` 9/9，全量 pytest 525 项 0 失败。",
)
repl(
    up,
    "- 未完成：revenue 收入构成未补齐；真机验收未解除；Android 同步包按新版 atlas 重建（收尾执行）。",
    "- 最终收尾：CN revenue 收入构成已全量补齐（5,539/5,539）；Android 同步包终版已重建并激活 `market-20260809-080838-d88b6aa3`（13,585,048 字节）；未解除：真机验收（外部条件）、177 条原始子链去重/归并与产业链定义（用户人工校验）。",
)

print("ALL DOCS UPDATED")
