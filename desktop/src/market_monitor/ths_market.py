"""同花顺市场宽度与沪深指数快照采集（含登录态受阻状态）。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


_BASE = "https://q.10jqka.com.cn"
_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": f"{_BASE}/"}


def run_ths_market_snapshot(data_root: Path, *, session: requests.Session | None = None) -> dict[str, Any]:
    """Collect public pages and persist a precise Chinese status/partial result.

    同花顺的市场宽度接口及索引后续分页在未携带已登录浏览器会话时会
    返回 403/401；此处明确记录受阻项，不把缺失数据伪造成零值。
    """
    client = session or requests.Session()
    root = Path(data_root) / "ths_market"
    root.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {"状态": "运行中", "数据源": "同花顺行情中心", "更新时间": _now(), "市场宽度": {}, "沪深指数": {}}

    breadth, breadth_issue = _fetch_breadth(client)
    status["市场宽度"] = {"状态": "完成" if breadth else "受阻", "字段": breadth or {}, "说明": breadth_issue}

    indices, pages, index_issue = _fetch_indices(client)
    status["沪深指数"] = {
        "状态": "完成" if pages == 12 and len(indices) >= 575 else "部分完成" if indices else "受阻",
        "目标数量": 575,
        "已获取数量": len(indices),
        "已获取页数": pages,
        "字段": ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "昨收", "今开", "最高价", "最低价", "成交量", "成交额"],
        "说明": index_issue,
    }
    if breadth and len(indices) >= 575:
        status["状态"] = "完成"
    elif breadth or indices:
        status["状态"] = "部分完成"
    else:
        status["状态"] = "受阻"
    status["更新时间"] = _now()
    _write_json(root / "状态.json", status)
    _write_json(root / f"沪深指数快照-{datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()}.json", {"更新时间": _now(), "记录": indices})
    print(f"【同花顺市场任务】{status['状态']}：指数 {len(indices)}/575；市场宽度 {status['市场宽度']['状态']}。", flush=True)
    return status


def _fetch_breadth(client: requests.Session) -> tuple[dict[str, Any] | None, str]:
    response = client.get(f"{_BASE}/api.php?t=indexflash&", headers=_HEADERS, timeout=30)
    if response.status_code != 200:
        fallback = _breadth_from_stock_page(client)
        if fallback:
            return fallback, f"实时宽度接口返回 HTTP {response.status_code}；已按公开 A 股列表页的涨跌幅计算上涨/横盘/下跌，涨停、跌停和昨日涨停收益仍需已登录会话。"
        return None, f"接口返回 HTTP {response.status_code}；需要同花顺已登录浏览器会话后重试。"
    try:
        payload = json.loads(response.content.decode("gbk", "ignore"))
    except (ValueError, UnicodeDecodeError) as error:
        return None, f"接口响应无法解析：{type(error).__name__}"
    try:
        distribution = payload["zdfb_data"]
        limit_data = payload["zdt_data"]
        yesterday_limit = payload["jrbx_data"]
        return {
            "涨跌分布": distribution.get("zdfb"),
            "涨停个股数量": limit_data.get("last_zdt", {}).get("ztzs") or distribution.get("znum"),
            "跌停个股数量": limit_data.get("last_zdt", {}).get("dtzs") or distribution.get("dnum"),
            "昨日涨停今日平均收益率": yesterday_limit.get("last_zdf"),
            "数据时间": yesterday_limit.get("time") or limit_data.get("zd_time"),
        }, ""
    except (AttributeError, KeyError) as error:
        return None, f"接口字段变更：{type(error).__name__}"


def _breadth_from_stock_page(client: requests.Session) -> dict[str, Any] | None:
    """公开第一页只作降级快照，不将其伪称为全市场统计。"""
    response = client.get(f"{_BASE}/", headers=_HEADERS, timeout=30)
    if response.status_code != 200:
        return None
    soup = BeautifulSoup(response.content.decode("gbk", "ignore"), "html.parser")
    changes: list[float] = []
    for row in soup.select("tbody tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
        if len(cells) < 5:
            continue
        try:
            changes.append(float(cells[4]))
        except ValueError:
            continue
    if not changes:
        return None
    return {
        "上涨个股数量": sum(value > 0 for value in changes),
        "横盘个股数量": sum(value == 0 for value in changes),
        "下跌个股数量": sum(value < 0 for value in changes),
        "统计范围": f"同花顺公开 A 股列表页前 {len(changes)} 条，非全市场",
    }


def _fetch_indices(client: requests.Session) -> tuple[list[dict[str, Any]], int, str]:
    records = _parse_index_page(client.get(f"{_BASE}/zs/", headers=_HEADERS, timeout=30).content)
    pages = 1 if records else 0
    issue = ""
    for page in range(2, 13):
        response = client.get(f"{_BASE}/zs/index/field/zdf/order/desc/page/{page}/ajax/1/", headers=_HEADERS, timeout=30)
        if response.status_code != 200:
            issue = f"第 {page} 页返回 HTTP {response.status_code}；需要同花顺已登录浏览器会话后续抓取。"
            break
        rows = _parse_index_page(response.content)
        if not rows:
            issue = f"第 {page} 页未返回可解析指数记录。"
            break
        records.extend(rows)
        pages += 1
    unique = {item["代码"]: item for item in records if item.get("代码")}
    return list(unique.values()), pages, issue


def _parse_index_page(content: bytes) -> list[dict[str, Any]]:
    soup = BeautifulSoup(content.decode("gbk", "ignore"), "html.parser")
    records: list[dict[str, Any]] = []
    for row in soup.select("tbody tr"):
        values = [cell.get_text(" ", strip=True) for cell in row.select("td")]
        if len(values) != 12:
            continue
        records.append(dict(zip(("序号", "代码", "名称", "最新价", "涨跌额", "涨跌幅", "昨收", "今开", "最高价", "最低价", "成交量", "成交额"), values, strict=True)))
    return records


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")


__all__ = ("run_ths_market_snapshot",)
