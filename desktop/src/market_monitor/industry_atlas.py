"""Brokerage-style industry-chain atlas generator (v2).

Reads the 720-report ``chain_index.json``, the CN/HK F10 jsonl tables and the
legacy ``A股企业产业链精细定位.html`` snapshot, then emits:

- ``industry-atlas.json``  structured parent chains with stage cards
- ``industry-atlas.html``  self-contained offline panorama (zero CDN)

v2 changes over the first atlas:

- the 177 report-extracted chains are merged into canonical parent chains
  (sub-chains become tabs inside the parent)
- companies are attached directly under product / material / service cards
  (ProcessOn-style industry research map) instead of separate side piles
- every chain and every stage card carries an evidence-based intro
- HK companies are displayed as ``HK:01801``, CN companies as ``603650``
- junk names extracted from report prose are cleaned and filtered
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from market_monitor.chain_taxonomy import (
    STANDARD_REFERENCES,
    canonical_chain,
    clean_company_name,
)


SCHEMA_VERSION = "atlas-v2"
STAGE_ORDER = ("upstream", "midstream", "downstream", "service", "related")
STAGE_LABELS = {
    "upstream": "上游",
    "midstream": "中游",
    "downstream": "下游",
    "service": "服务与配套",
    "related": "产业链相关",
}
STAGE_COLORS = {
    "upstream": "#3d7fb8",
    "midstream": "#7c6ee8",
    "downstream": "#d8729f",
    "service": "#4a9b76",
    "related": "#8b929a",
}

MAX_CARD_COMPANIES = 40
MAX_CHAIN_COMPANIES = 800
MAX_CARDS_PER_STAGE = 28
MAX_EVIDENCE = 3
EVIDENCE_CHARS = 160
MAX_PROFILE_CHARS = 420
MIN_F10_MATCH_LEN = 2
MAX_F10_NEW_PER_CARD = 8
MAX_F10_MATCHES_PER_COMPANY = 3

# Market / board / exchange terms that are never industry-chain products,
# materials or services. They leak into report facts because sentences like
# "公司于深交所创业板上市" get extracted as a PRODUCT entity.
_MARKET_BOARD_TERMS = frozenset({
    "创业板", "科创创业板", "创业板指", "创业板注册制", "创业板改革", "创业板首批",
    "科创板", "科创板注册制", "科创50",
    "主板", "中小板", "新三板", "三板", "北交所", "北证", "北证50",
    "沪深", "沪深300", "沪深两市", "深市", "沪市", "京市",
    "深交所", "上交所", "港交所",
    "上证", "上证指数", "深证", "深证成指", "中证", "中证500", "中证1000",
    "恒生指数", "恒指",
    "A股", "B股", "H股", "港股",
    "上市", "上市公司", "注册制", "次新股", "新股", "股票", "指数",
})

# Substring matching for market/board terms. "主板" is excluded: in PC and
# electronics research reports it can legitimately mean "motherboard", so it is
# only rejected when it is the exact card name.
_MARKET_SUBSTRING_TERMS = frozenset(t for t in _MARKET_BOARD_TERMS if t != "主板")


def _is_market_board_name(text: str) -> bool:
    """True when a card name is (or contains) a market/board/exchange term."""
    if text in _MARKET_BOARD_TERMS:
        return True
    return any(term in text for term in _MARKET_SUBSTRING_TERMS)


# Generic card names too common for F10 text matching (would cause false positives).
_GENERIC_CARD_NAMES = frozenset({
    "设备", "系统", "技术", "材料", "产品", "服务", "部件", "组件",
    "模块", "装置", "器械", "用品", "设施", "平台", "方案", "软件",
    "硬件", "业务", "领域", "环节", "产业链", "相关", "其他", "主要",
    "新型", "高端", "智能", "数字化", "自动化", "成套", "整机", "零部件",
    "配件", "备件", "生产", "制造", "加工", "应用", "市场", "行业",
    "项目", "工程", "建设", "运营", "管理", "中心", "基地", "企业",
    "公司", "集团", "股份", "控股", "科技", "研发", "设计", "测试",
    "检测", "认证", "咨询", "服务商", "供应商", "装备", "机械", "电气",
    "电子", "化工", "医药", "食品", "材料商", "厂商", "产品线",
}) | _MARKET_BOARD_TERMS

_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "股份有限公司",
    "股份公司",
    "有限公司",
    "集团有限公司",
    "控股集团有限公司",
    "有限责任公司（外商投资）",
    "控股股份有限公司",
    "新能源科技",
    "新材料科技",
    "生物科技",
    "电子科技",
    "信息科技",
    "网络科技",
    "智能科技",
    "能源科技",
    "光电科技",
    "半导体科技",
    "数字科技",
    "汽车科技",
    "集团公司",
    "控股集团",
    "控股公司",
    "集团",
    "控股",
    "股份",
    "科技",
    "公司",
)

_NON_WORD = re.compile(
    r"[\s·•–—()（）\[\]【】{}<>《》\"''`~!@#$%^&*_+=|\\/:;,.\-，。、；：！？…]+"
)


def _norm_name(name: str) -> str:
    """Normalize a company name for fuzzy matching."""
    if not name:
        return ""
    text = unicodedata.normalize("NFKC", str(name))
    text = _NON_WORD.sub("", text).upper()
    return _strip_suffixes(text)


def _norm_industry_segment(name: str) -> str:
    """Normalize an industry taxonomy segment for map lookup.

    Unlike _norm_name(), company suffixes are NOT stripped: industry names
    legitimately end with 科技/制造/服务 etc., and the keys in
    _INDUSTRY_TO_CHAINS use the raw taxonomy names.
    """
    if not name:
        return ""
    text = unicodedata.normalize("NFKC", str(name))
    return _NON_WORD.sub("", text).upper()


def _strip_suffixes(text: str) -> str:
    if len(text) < 3:
        return text
    changed = True
    while changed and len(text) >= 3:
        changed = False
        for suffix in _SUFFIXES:
            if text.endswith(suffix) and len(text) - len(suffix) >= 2:
                text = text[: -len(suffix)]
                changed = True
                break
    return text


def _truncate(text: str, limit: int) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[:limit] + "…"


def _compact_f10(record: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only useful F10 fields for the offline atlas."""

    keys = (
        "code",
        "market",
        "name",
        "full_name",
        "total_market_cap",
        "float_market_cap",
        "industry",
        "csrc_industry",
        "profile",
        "main_business",
        "revenue_breakdown",
        "products",
        "source",
        "fetched_at",
        "status",
    )
    out: dict[str, Any] = {}
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        if key in ("profile", "main_business") and isinstance(value, str):
            value = _truncate(value, MAX_PROFILE_CHARS)
        if isinstance(value, list):
            value = value[:8]
        out[key] = value
    return out


def _market_of(record: Mapping[str, Any]) -> str:
    market = str(record.get("market") or "").upper()
    code = str(record.get("code") or "")
    if market.startswith("HK") or (len(code) == 5 and code.isdigit()):
        return "HK"
    if market.startswith("CN") or (len(code) == 6 and code.isdigit()):
        return "CN"
    return "OTHER"


def _read_json(path: Path) -> Any:
    with io.open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_legacy_html(path: Path) -> list[dict[str, Any]]:
    """Parse ``const DATA = [...]`` from the legacy chain-positioning HTML.

    Returns a list of company records (code/name/market_cap/industry/...)
    carrying ``source: "legacy_html"``.  Returns [] when the file is absent.
    """

    if not Path(path).is_file():
        return []
    text = Path(path).read_text(encoding="utf-8")
    match = re.search(r"const\s+DATA\s*=\s*(\[.*?\])\s*;", text, re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    records: list[dict[str, Any]] = []
    for chain in data:
        for stage in chain.get("stages") or []:
            for company in stage.get("companies") or []:
                code = str(company.get("code") or "").strip()
                if not code:
                    continue
                records.append(
                    {
                        "code": code,
                        "market": "CN",
                        "name": str(company.get("name") or ""),
                        "total_market_cap": company.get("market_cap"),
                        "revenue": company.get("revenue"),
                        "industry": company.get("industry"),
                        "products": company.get("products") or [],
                        "l1": company.get("l1"),
                        "l2": company.get("l2"),
                        "l3": company.get("l3"),
                        "source": "legacy_html",
                        "chain": chain.get("name"),
                        "stage_label": stage.get("label"),
                    }
                )
    return records


def load_f10(f10_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read CN/HK jsonl F10 tables plus meta.json."""

    f10_dir = Path(f10_dir)
    records: list[dict[str, Any]] = []
    meta: dict[str, Any] = {}
    meta_path = f10_dir / "meta.json"
    if meta_path.is_file():
        try:
            meta = _read_json(meta_path)
        except (OSError, json.JSONDecodeError):
            meta = {}
    for filename in ("cn_f10.jsonl", "hk_f10.jsonl"):
        path = f10_dir / filename
        if not path.is_file():
            continue
        with io.open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("code") and record.get("name"):
                    records.append(record)
    return records, meta


def _build_f10_text_index(f10_records: list[Mapping[str, Any]]) -> dict[str, str]:
    """Build company name -> combined searchable text from F10 records."""
    index: dict[str, str] = {}
    for record in f10_records:
        name = str(record.get("name") or "").strip()
        if not name:
            continue
        parts: list[str] = [
            str(record.get("industry") or ""),
            str(record.get("csrc_industry") or ""),
            str(record.get("profile") or ""),
            str(record.get("main_business") or ""),
        ]
        for item in record.get("revenue_breakdown") or []:
            if isinstance(item, Mapping):
                parts.append(str(item.get("item") or ""))
        for prod in record.get("products") or []:
            parts.append(str(prod))
        text = " ".join(p for p in parts if p)
        if text:
            index[name] = text
    return index


def _build_f10_by_industry(f10_records: list[Mapping[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    """Map industry keyword -> list of (company_name, text) for pre-filtering."""
    by_industry: dict[str, list[tuple[str, str]]] = {}
    for record in f10_records:
        name = str(record.get("name") or "").strip()
        if not name:
            continue
        industry = str(record.get("industry") or "").strip()
        text = str(record.get("main_business") or "") + " " + str(record.get("profile") or "")
        if not text.strip():
            continue
        by_industry.setdefault(industry, []).append((name, text))
    return by_industry


# Normalized industry segment -> parent chains, in priority order.
# Keys are produced by _norm_name() (uppercase, punctuation/suffix stripped).
_INDUSTRY_TO_CHAINS: dict[str, tuple[str, ...]] = {
    # Eastmoney A-share taxonomy
    "机械设备": ("机械设备",),
    "机械设备-通用设备": ("机械设备",),
    "机械设备-专用设备": ("机械设备",),
    "机械设备-金属制品": ("机械设备",),
    "机械设备-机器人": ("机器人", "机械设备"),
    "电子设备": ("消费电子",),
    "电子设备-半导体": ("半导体",),
    "电子设备-电子设备制造": ("消费电子",),
    "电子设备-电子元件": ("消费电子",),
    "电子设备-光电子器件": ("激光", "消费电子"),
    "电子设备-消费电子设备": ("消费电子",),
    "电子设备-电子器件": ("面板", "消费电子"),
    "电子设备-电子器件-显示器件": ("面板",),
    "基础化工": ("化工",),
    "基础化工-化学制品": ("化工",),
    "基础化工-化学原料": ("化工",),
    "基础化工-化肥农药": ("化工", "农业"),
    "基础化工-橡胶制品": ("轮胎", "化工"),
    "基础化工-合成纤维及树脂": ("化工", "纺织服装"),
    "基础化工-化学新材料": ("化工", "复合材料"),
    "医药生物": ("医药生物",),
    "医药生物-化学制药": ("医药生物",),
    "医药生物-生物医药": ("医药生物",),
    "医药生物-医疗器械": ("医疗器械", "医药生物"),
    "医药生物-中药生产": ("医药生物",),
    "医药生物-医药商业": ("医药生物",),
    "医药生物-医疗服务": ("医疗服务", "医药生物"),
    "医药生物-保健护理": ("医疗服务", "美容护理"),
    "信息技术": ("计算机",),
    "信息技术-计算机软件": ("计算机",),
    "信息技术-计算机硬件": ("计算机",),
    "信息技术-通信设备": ("通信",),
    "信息技术-通信运营": ("通信",),
    "信息技术-卫星应用": ("卫星互联网", "通信"),
    "交运设备": ("汽车",),
    "交运设备-汽车": ("汽车",),
    "交运设备-其他交运设备": ("机械设备",),
    "交运设备-铁路设备": ("交通运输", "机械设备"),
    "交运设备-轨道交通设备": ("交通运输",),
    "交运设备-摩托车": ("两轮车",),
    "建筑": ("建材",),
    "建筑-建筑施工": ("建材",),
    "建筑-基础建设": ("建材",),
    "建筑-装修装饰": ("家居", "建材"),
    "建筑-钢结构": ("钢铁", "建材"),
    "建筑-建筑安装": ("建材",),
    "电气设备": ("电力",),
    "电气设备-输变电设备": ("电力",),
    "电气设备-电源设备": ("光伏", "储能"),
    "电气设备-电源设备-太阳能": ("光伏",),
    "电气设备-电源设备-储能设备": ("储能",),
    "电气设备-电源设备-风电设备": ("风电",),
    "电气设备-电机": ("机械设备", "电力"),
    "电气设备-其他电气设备": ("电力",),
    "公用事业": ("电力",),
    "公用事业-电力": ("电力",),
    "公用事业-环保": ("环保",),
    "公用事业-燃气": ("石油天然气",),
    "公用事业-水务": ("环保",),
    "房地产": ("房地产",),
    "房地产-房地产开发": ("房地产",),
    "房地产-房地产服务": ("房地产",),
    "轻工制造": ("家居",),
    "轻工制造-造纸印刷": ("造纸", "印刷"),
    "轻工制造-家具": ("家居",),
    "轻工制造-珠宝首饰": ("珠宝",),
    "轻工制造-文娱用品": ("体育", "传媒"),
    "轻工制造-其他轻工": ("家居",),
    "食品饮料": ("食品饮料",),
    "食品饮料-食品": ("食品饮料",),
    "食品饮料-饮料": ("食品饮料", "白酒"),
    "食品饮料-饮料-白酒": ("白酒",),
    "食品饮料-饮料-啤酒": ("食品饮料",),
    "食品饮料-饮料-乳品": ("乳品", "食品饮料"),
    "食品饮料-食品-调味品": ("调味品", "食品饮料"),
    "食品饮料-食品-乳品": ("乳品", "食品饮料"),
    "农林牧渔": ("农业",),
    "农林牧渔-畜牧业": ("农业",),
    "农林牧渔-农业": ("农业",),
    "农林牧渔-渔业": ("农业",),
    "农林牧渔-林业": ("农业",),
    "农林牧渔-农产品加工": ("农业", "食品饮料"),
    "交通运输": ("交通运输",),
    "交通运输-物流": ("交通运输",),
    "交通运输-港口航运": ("交通运输",),
    "交通运输-公路铁路": ("交通运输",),
    "交通运输-航空机场": ("交通运输",),
    "纺织服装": ("纺织服装",),
    "纺织服装-服装家纺": ("纺织服装",),
    "纺织服装-纺织": ("纺织服装",),
    "商贸零售": ("零售",),
    "商贸零售-零售": ("零售",),
    "商贸零售-贸易": ("零售",),
    "商贸零售-商业物业经营": ("零售", "房地产"),
    "国防与装备": ("军工",),
    "国防与装备-航空航天装备": ("航空航天", "军工"),
    "国防与装备-地面装备": ("军工",),
    "国防与装备-船舶与海洋装备": ("船舶", "军工"),
    "互联网": ("计算机",),
    "互联网-互联网服务": ("计算机",),
    "互联网-互联网技术": ("计算机",),
    "互联网-互联网商务": ("零售", "计算机"),
    "互联网-互联网金融": ("金融", "计算机"),
    "化石能源": ("石油天然气",),
    "化石能源-石油天然气": ("石油天然气",),
    "化石能源-煤炭": ("煤炭",),
    "有色金属": ("有色金属",),
    "有色金属-金属非金属新材料": ("有色金属", "复合材料"),
    "有色金属-基本金属": ("有色金属",),
    "有色金属-稀有金属": ("有色金属",),
    "有色金属-贵金属": ("有色金属", "珠宝"),
    "钢铁": ("钢铁",),
    "钢铁-钢铁": ("钢铁",),
    "钢铁-铁矿石": ("钢铁",),
    "建材": ("建材",),
    "建材-水泥": ("建材",),
    "建材-玻璃": ("建材",),
    "建材-陶瓷": ("建材",),
    "建材-耐火材料": ("建材",),
    "建材-其他建材": ("建材",),
    "家电": ("家电",),
    "家电-小家电": ("家电",),
    "家电-白色家电": ("家电",),
    "家电-照明设备": ("家电",),
    "家电-视听器材": ("消费电子", "家电"),
    "家电-其他家电": ("家电",),
    "文化传媒": ("传媒",),
    "文化传媒-营销服务": ("传媒",),
    "文化传媒-平面媒体": ("传媒",),
    "文化传媒-影视动漫": ("传媒",),
    "文化传媒-广播电视": ("传媒",),
    "文化传媒-教育": ("教育",),
    "文化传媒-体育": ("体育",),
    "休闲生活及专业服务": ("旅游酒店",),
    "休闲生活及专业服务-休闲服务": ("旅游酒店",),
    "休闲生活及专业服务-专业服务": ("检测",),
    "金融": ("金融",),
    "金融-非银行金融": ("金融",),
    "金融-银行": ("金融",),
    "半导体": ("半导体",),
    # HKEX industry names
    "地产": ("房地产",),
    "工业工程": ("机械设备", "建材"),
    "软件服务": ("计算机",),
    "药品及生物科技": ("医药生物",),
    "其他金融": ("金融",),
    "旅游及消闲设施": ("旅游酒店",),
    "其他医疗保健": ("医疗服务", "医药生物"),
    "纺织及服饰": ("纺织服装",),
    "家庭电器及用品": ("家电",),
    "支援服务": ("交通运输",),
    "专业零售": ("零售",),
    "一般金属及矿石": ("有色金属",),
    "资讯科技器材": ("计算机", "消费电子"),
    "工用运输": ("交通运输",),
    "原材料": ("有色金属", "化工"),
    "汽车": ("汽车",),
    "工用支援": ("机械设备",),
    "石油及天然气": ("石油天然气",),
    "银行": ("金融",),
    "消费者主要零售商": ("零售",),
    "煤炭": ("煤炭",),
    "农业产品": ("农业",),
    "保险": ("金融",),
    "电讯": ("通信",),
    "黄金及贵金属": ("有色金属", "珠宝"),
    "食物饮品": ("食品饮料",),
    "媒体及娱乐": ("传媒",),
    # CSRC industry names (second level)
    "计算机通信和其他电子设备制造业": ("计算机", "通信", "消费电子"),
    "专用设备制造业": ("机械设备",),
    "化学原料和化学制品制造业": ("化工",),
    "电气机械和器材制造业": ("电力", "机械设备"),
    "软件和信息技术服务业": ("计算机",),
    "医药制造业": ("医药生物",),
    "通用设备制造业": ("机械设备",),
    "汽车制造业": ("汽车",),
    "橡胶和塑料制品业": ("化工", "轮胎"),
    "非金属矿物制品业": ("建材",),
    "金属制品业": ("机械设备",),
    "仪器仪表制造业": ("机械设备", "检测"),
    "零售业": ("零售",),
    "电力热力生产和供应业": ("电力",),
    "批发业": ("零售",),
    "有色金属冶炼和压延加工业": ("有色金属",),
    "房地产业": ("房地产",),
    "专业技术服务业": ("检测",),
    "铁路船舶航空航天和其他运输设备制造业": ("船舶", "航空航天", "交通运输"),
    "食品制造业": ("食品饮料",),
    "商务服务业": ("检测",),
    "农副食品加工业": ("食品饮料", "农业"),
    "土木工程建筑业": ("建材", "房地产"),
    "生态保护和环境治理业": ("环保",),
    "互联网和相关服务": ("计算机",),
    "资本市场服务": ("金融",),
    "酒饮料和精制茶制造业": ("食品饮料", "白酒"),
    "纺织业": ("纺织服装",),
    "货币金融服务": ("金融",),
    "造纸和纸制品业": ("造纸",),
    "纺织服装服饰业": ("纺织服装",),
    "水上运输业": ("交通运输",),
    "燃气生产和供应业": ("石油天然气",),
    "道路运输业": ("交通运输",),
    "黑色金属冶炼和压延加工业": ("钢铁",),
    "研究和试验发展": ("检测",),
    "新闻和出版业": ("传媒",),
    "有色金属矿采选业": ("有色金属",),
    "家具制造业": ("家居",),
    "化学纤维制造业": ("化工", "纺织服装"),
    "公共设施管理业": ("环保",),
    "煤炭开采和洗选业": ("煤炭",),
    "建筑装饰装修和其他建筑业": ("家居", "建材"),
    "文教工美体育和娱乐用品制造业": ("体育", "传媒"),
    "电信广播电视和卫星传输服务": ("通信", "传媒"),
    "水的生产和供应业": ("环保",),
    "废弃资源综合利用业": ("环保",),
    "广播电视电影和录音制作业": ("传媒",),
    "畜牧业": ("农业",),
    "卫生": ("医疗服务",),
    "石油煤炭及其他燃料加工业": ("石油天然气", "煤炭"),
    "开采专业及辅助性活动": ("石油天然气",),
    "印刷和记录媒介复制业": ("印刷",),
    "其他金融业": ("金融",),
    "航空运输业": ("交通运输",),
    "教育": ("教育",),
    "木材加工和木竹藤棕草制品业": ("家居",),
    "多式联运和运输代理业": ("交通运输",),
    "皮革毛皮羽毛及其制品和制鞋业": ("纺织服装",),
    "石油和天然气开采业": ("石油天然气",),
    "农业": ("农业",),
    "农林牧渔专业及辅助性活动": ("农业",),
    "铁路运输业": ("交通运输",),
    "装卸搬运和仓储业": ("交通运输",),
    "黑色金属矿采选业": ("钢铁",),
    "渔业": ("农业",),
    "保险业": ("金融",),
    "建筑安装业": ("建材",),
    "住宿业": ("旅游酒店",),
    "餐饮业": ("餐饮",),
    "邮政业": ("交通运输",),
    "文化艺术业": ("传媒",),
    "租赁业": ("机械设备",),
    "房屋建筑业": ("房地产",),
    "金属制品机械和设备修理业": ("机械设备",),
    "科技推广和应用服务业": ("计算机",),
    "体育": ("体育",),
    "林业": ("农业",),
    "非金属矿采选业": ("建材",),
    "水利管理业": ("环保",),
    "机动车电子产品和日用产品修理业": ("汽车",),
}

# Product-topic keywords -> parent chains, used as a fallback when the
# exchange industry taxonomy does not name the chain directly.
_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "半导体": ("半导体", "晶圆", "集成电路", "芯片", "光刻", "封装测试", "封测"),
    "光伏": ("光伏", "太阳能电池", "组件", "逆变器", "硅料", "硅片"),
    "风电": ("风电", "风机", "风电机组", "叶片", "塔筒"),
    "储能": ("储能", "电化学储能", "储能电池", "储能系统"),
    "氢能": ("氢能", "氢燃料", "燃料电池", "电解槽", "加氢"),
    "锂电池": ("锂电", "锂电池", "动力电池", "电池材料", "正极材料", "负极材料", "电解液", "隔膜", "电芯"),
    "机器人": ("机器人", "减速器", "伺服电机", "机器视觉", "人形机器人"),
    "人工智能": ("人工智能", "大模型", "机器学习", "深度学习", "智能语音", "计算机视觉", "AI"),
    "低空经济": ("低空", "无人机", "EVTOL", "飞行汽车", "通航"),
    "卫星互联网": ("卫星互联网", "卫星通信", "低轨卫星", "北斗"),
    "量子科技": ("量子", "量子计算", "量子通信"),
    "网络安全": ("网络安全", "信息安全", "数据安全", "密码"),
    "数据要素": ("数据要素", "大数据", "数据交易"),
    "工业软件": ("工业软件", "CAD", "CAE", "PLM", "MES", "EDA"),
    "碳纤维": ("碳纤维"),
    "复合材料": ("复合材料", "玻纤", "芳纶"),
    "电子烟": ("电子烟"),
    "两轮车": ("两轮车", "摩托车", "电动自行车"),
    "调味品": ("调味品", "酱油", "蚝油", "复合调味料"),
    "乳品": ("乳制品", "奶粉", "奶酪", "低温奶"),
    "宠物经济": ("宠物食品", "宠物医疗", "宠物用品", "动物保健"),
    "眼镜": ("眼镜", "镜片", "镜架", "隐形眼镜"),
    "检测": ("检测服务", "检验检测", "第三方检测", "认证服务"),
    "珠宝": ("珠宝", "黄金首饰", "钻石", "银饰"),
    "白酒": ("白酒", "酱酒", "浓香型", "清香型"),
    "面板": ("显示面板", "LCD", "OLED", "MINILED", "MICROLED", "显示屏"),
    "医疗美容": ("医美", "医疗美容", "玻尿酸", "肉毒素"),
    "美容护理": ("化妆品", "护肤品", "彩妆", "个护"),
    "养老服务": ("养老", "养老服务", "康复医疗"),
    "体育": ("体育用品", "运动装备", "健身器材", "赛事运营"),
    "教育": ("教育信息化", "职业教育", "在线教育", "培训"),
    "印刷": ("印刷", "包装印刷", "数码印刷"),
    "造纸": ("造纸", "纸浆", "特种纸", "生活用纸"),
    "餐饮": ("餐饮", "预制菜", "连锁餐饮", "火锅"),
    "旅游酒店": ("旅游", "酒店", "景区", "免税"),
    "家电": ("家电", "空调", "冰箱", "洗衣机", "厨电"),
    "核电": ("核电", "核岛", "核燃料", "乏燃料"),
    "船舶": ("船舶", "造船", "船用", "海洋工程"),
    "航空航天": ("航空航天", "航空发动机", "卫星", "火箭", "飞机"),
    "军工": ("军工", "国防", "雷达", "弹药", "导弹"),
    "信创": ("信创", "国产操作系统", "国产数据库", "自主可控"),
    "云计算": ("云计算", "云服务", "IAAS", "SAAS"),
    "数据中心": ("数据中心", "IDC", "服务器", "算力"),
    "医疗器械": ("医疗器械", "医疗设备", "体外诊断", "IVD", "高值耗材"),
    "医疗服务": ("医疗服务", "医院", "体检", "专科医疗"),
    "工业气体": ("工业气体", "特种气体", "电子气体", "空分"),
    "轮胎": ("轮胎", "子午线轮胎"),
    "汽车": ("汽车零部件", "整车", "智能驾驶", "汽车电子"),
    "通信": ("光模块", "光通信", "光纤光缆", "基站", "5G"),
    "消费电子": ("消费电子", "智能手机", "TWS", "智能穿戴", "VR", "AR"),
}


def _f10_chain_candidates(record: Mapping[str, Any]) -> list[str]:
    """Return parent chains for an F10 record from exchange/CSRC industries."""
    out: list[str] = []
    seen: set[str] = set()
    for field in ("industry", "csrc_industry"):
        raw = str(record.get(field) or "")
        if not raw:
            continue
        segments = [_norm_industry_segment(part) for part in raw.split("-") if part.strip()]
        if not segments:
            continue
        # Prefer the most specific multi-segment key. Individual segments are
        # only consulted when no multi-segment key matched, so e.g.
        # "电子设备-半导体" resolves to 半导体 alone instead of also falling
        # through to 电子设备 -> 消费电子.
        keys: list[str] = []
        if len(segments) >= 3:
            keys.append("-".join(segments))
        if len(segments) >= 2:
            keys.append("-".join(segments[:2]))
        matched = False
        for key in keys:
            chains = _INDUSTRY_TO_CHAINS.get(key, ())
            if chains:
                matched = True
                for chain in chains:
                    if chain not in seen:
                        seen.add(chain)
                        out.append(chain)
        if matched:
            continue
        for segment in segments:
            for chain in _INDUSTRY_TO_CHAINS.get(segment, ()):
                if chain not in seen:
                    seen.add(chain)
                    out.append(chain)
    return out


def _build_f10_by_chain(f10_records: list[Mapping[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    """Map parent chain -> list of (company_name, text) from F10 industries."""
    by_chain: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for record in f10_records:
        name = str(record.get("name") or "").strip()
        if not name:
            continue
        chains = _f10_chain_candidates(record)
        if not chains:
            text = (
                str(record.get("industry") or "")
                + " "
                + str(record.get("csrc_industry") or "")
                + " "
                + str(record.get("main_business") or "")
                + " "
                + str(record.get("profile") or "")
            )
            normalized = _norm_name(text)
            if normalized:
                for chain, keywords in _TOPIC_KEYWORDS.items():
                    if any(_norm_name(kw) in normalized for kw in keywords):
                        chains.append(chain)
        text = (
            str(record.get("main_business") or "")
            + " "
            + str(record.get("profile") or "")
        )
        for chain in chains[:3]:
            by_chain[chain].append((name, text))
    return dict(by_chain)


def _build_index(records: Iterable[Mapping[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Map normalized names to records; second map uses full names."""

    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_full: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        name = _norm_name(record.get("name") or "")
        if name:
            by_name[name].append(dict(record))
        full_name = _norm_name(record.get("full_name") or "")
        if full_name and full_name != name:
            by_full[full_name].append(dict(record))
    return dict(by_name), dict(by_full)


def resolve_company(
    name: str,
    by_name: Mapping[str, list[dict[str, Any]]],
    by_full: Mapping[str, list[dict[str, Any]]],
    all_names: set[str],
) -> list[dict[str, Any]]:
    """Resolve a report-mentioned company name to F10/legacy records."""

    normalized = _norm_name(name)
    if not normalized:
        return []
    hits: list[dict[str, Any]] = []
    seen_codes: set[str] = set()

    def append_hits(records: Iterable[Mapping[str, Any]]) -> None:
        for record in records:
            code = str(record.get("code") or "")
            if code and code in seen_codes:
                continue
            if code:
                seen_codes.add(code)
            hits.append(dict(record))

    append_hits(by_name.get(normalized, []))
    stripped = _strip_suffixes(normalized)
    if stripped != normalized:
        append_hits(by_name.get(stripped, []))
    append_hits(by_full.get(normalized, []))
    if stripped != normalized:
        append_hits(by_full.get(stripped, []))
    if not hits and len(normalized) >= 4:
        contained = [candidate for candidate in all_names if normalized in candidate]
        if len(contained) == 1:
            append_hits(by_name.get(contained[0], []))
    return hits


def _stage_key(raw: str) -> str:
    if not raw:
        return "related"
    if "上游" in raw:
        return "upstream"
    if "中游" in raw:
        return "midstream"
    if "下游" in raw:
        return "downstream"
    if "服务" in raw or "配套" in raw or "支持" in raw:
        return "service"
    return "related"


# ---------------------------------------------------------------------------
# Card / product-name cleaning
# ---------------------------------------------------------------------------

_CARD_LEADING = re.compile(
    r"^(的|是|为|由|与|及|并|和|在|对|将|已|曾|经|后|前|年|月|日|等|如|像|"
    r"例如|比如|其中|包括|以及|并且|随着|基于|根据|按照|依据|通过|依托|借助|"
    r"围绕|目前|当前|未来|近年|近年来|此外|另外|同时|主要|本土|国产|海外|"
    r"全球|国际|我国|国内)"
)

_CARD_TRAILING = re.compile(r"(等|等企业|等公司|等厂商|领域|环节|相关|产业链)$")

_CARD_JUNK = re.compile(
    r"(是一种|是一种的|包括|其中|以及|并且|分为|来自|用于|为.*提供|覆盖|"
    r"公司|集团|股份|控股|[，。、；：（）()《》「」“”‘’·—–/])"
)

_CODE_LIKE = re.compile(r"^\d{5,6}$")


def clean_card_name(name: str, company_names: set[str]) -> str:
    """Return a usable product/material/service card name, or ""."""

    text = str(name or "").strip()
    if not text or len(text) < 2 or len(text) > 24:
        return ""
    if _CODE_LIKE.match(text):
        return ""
    if _CARD_LEADING.match(text) or _CARD_TRAILING.search(text):
        return ""
    if _CARD_JUNK.search(text):
        return ""
    if text in company_names:
        return ""
    if _is_market_board_name(text):
        return ""
    return text


# ---------------------------------------------------------------------------
# Chain aggregation
# ---------------------------------------------------------------------------


def _fact_key(fact: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(fact.get("entity") or ""),
        str(fact.get("entity_type") or ""),
        str(fact.get("evidence") or ""),
        str(fact.get("page") or ""),
        str(fact.get("report_id") or ""),
    )


def _coo_key(coo: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(coo.get("company") or ""),
        str(coo.get("product") or ""),
        str(coo.get("evidence") or ""),
    )


def _new_bucket(parent: str) -> dict[str, Any]:
    return {
        "name": parent,
        "sub_chains": {},
        "facts": {},
        "coos": {},
        "companies": {},
        "products": {},
        "materials": {},
        "services": {},
        "reports": {},
    }


def _aggregate_chains(chains: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Merge the 177 report chains into canonical parent buckets."""

    buckets: dict[str, dict[str, Any]] = {}
    for raw in chains:
        name = str(raw.get("chain") or "").strip()
        parent = canonical_chain(name) or name
        if not parent:
            continue
        bucket = buckets.setdefault(parent, _new_bucket(parent))
        bucket["sub_chains"][name] = {
            "name": name,
            "report_count": int(raw.get("report_count") or 0),
            "fact_count": int(raw.get("fact_count") or 0),
        }

        for fact in raw.get("facts") or []:
            if not fact.get("entity"):
                continue
            item = dict(fact)
            item["chain"] = name
            bucket["facts"][_fact_key(item)] = item

        for coo in raw.get("cooccurrences") or []:
            if not coo.get("company") or not coo.get("product"):
                continue
            item = dict(coo)
            item["chain"] = name
            bucket["coos"][_coo_key(item)] = item

        for item in raw.get("companies") or []:
            cleaned = clean_company_name(item.get("name"))
            if not cleaned:
                continue
            entry = bucket["companies"].setdefault(
                cleaned, {"name": cleaned, "count": 0, "raw": [], "fact_rows": 0}
            )
            entry["count"] += int(item.get("count") or 0)
            raw_name = str(item.get("name") or "").strip()
            if raw_name and raw_name != cleaned and raw_name not in entry["raw"]:
                entry["raw"].append(raw_name)

        for attr, mapping in (
            ("products", bucket["products"]),
            ("materials", bucket["materials"]),
            ("services", bucket["services"]),
        ):
            for item in raw.get(attr) or []:
                card_name = clean_card_name(item.get("name"), set(bucket["companies"]))
                if not card_name:
                    continue
                entry = mapping.setdefault(card_name, {"name": card_name, "count": 0})
                entry["count"] += int(item.get("count") or 0)

        for report in raw.get("reports") or []:
            rid = str(report.get("report_id") or "")
            if rid:
                bucket["reports"][rid] = report

    for bucket in buckets.values():
        company_names = set(bucket["companies"])
        for fact in bucket["facts"].values():
            if str(fact.get("entity_type") or "").upper() != "COMPANY":
                continue
            cleaned = clean_company_name(fact.get("entity"))
            if cleaned in bucket["companies"]:
                bucket["companies"][cleaned]["fact_rows"] += 1
            elif cleaned:
                entry = bucket["companies"].setdefault(
                    cleaned, {"name": cleaned, "count": 0, "raw": [], "fact_rows": 0}
                )
                entry["fact_rows"] += 1
                company_names.add(cleaned)
        # Re-filter product names now that all company names are known.
        for attr in ("products", "materials", "services"):
            bucket[attr] = {
                card_name: entry
                for card_name, entry in bucket[attr].items()
                if clean_card_name(card_name, company_names)
            }
    return buckets


# ---------------------------------------------------------------------------
# Stage / card building
# ---------------------------------------------------------------------------


def _resolve_display(cleaned: str, resolver: Any) -> dict[str, Any]:
    records = resolver(cleaned)
    codes: list[str] = []
    markets: list[str] = []
    seen: set[tuple[str, str]] = set()
    display = cleaned
    f10: dict[str, Any] | None = None
    for record in records:
        code = str(record.get("code") or "")
        market = _market_of(record)
        if not code or market == "OTHER":
            continue
        key = (market, code)
        if key in seen:
            continue
        seen.add(key)
        codes.append(code)
        markets.append(market)
        if f10 is None and record.get("name"):
            f10 = record
    if f10 and str(f10.get("name") or "").strip():
        display = str(f10.get("name") or cleaned).strip()
    return {"name": display, "codes": codes, "markets": markets}


def _evidence_item(evidence: Mapping[str, Any]) -> dict[str, Any] | None:
    text = str(evidence.get("evidence") or "").strip()
    if not text:
        return None
    return {
        "t": text[:EVIDENCE_CHARS],
        "p": evidence.get("page"),
        "r": str(evidence.get("report_id") or ""),
        "f": str(evidence.get("file_name") or "")[:70],
        "c": evidence.get("confidence"),
    }


def _ensure_card(cards: dict[str, dict[str, dict[str, Any]]], stage: str, name: str, kind: str) -> dict[str, Any]:
    stage_cards = cards.setdefault(stage, {})
    card = stage_cards.get(name)
    if card is None:
        card = {
            "name": name,
            "kind": kind,
            "count": 0,
            "evidence": [],
            "sub_chains": set(),
            "companies": {},
        }
        stage_cards[name] = card
    return card


def _add_company_to_card(
    card: dict[str, Any],
    cleaned: str,
    resolver: Any,
    chain_company_count: dict[str, int],
    *,
    count: int = 1,
    evidence: Mapping[str, Any] | None = None,
    chain_name: str = "",
) -> None:
    info = _resolve_display(cleaned, resolver)
    entry = card["companies"].get(cleaned)
    if entry is None:
        if chain_company_count["n"] >= MAX_CHAIN_COMPANIES:
            return
        chain_company_count["n"] += 1
        entry = {
            "name": info["name"],
            "count": 0,
            "codes": info["codes"],
            "markets": info["markets"],
            "evidence": [],
            "sub_chains": set(),
        }
        card["companies"][cleaned] = entry
    entry["count"] += count
    if chain_name:
        entry["sub_chains"].add(chain_name)
    if evidence:
        ev = _evidence_item(evidence)
        if ev and len(entry["evidence"]) < MAX_EVIDENCE and ev not in entry["evidence"]:
            entry["evidence"].append(ev)


def _company_stage_map(bucket: Mapping[str, Any]) -> tuple[dict[str, Counter], dict[str, list[dict[str, Any]]]]:
    stages: dict[str, Counter] = defaultdict(Counter)
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in bucket["facts"].values():
        if str(fact.get("entity_type") or "").upper() != "COMPANY":
            continue
        cleaned = clean_company_name(fact.get("entity"))
        if not cleaned:
            continue
        stages[cleaned][_stage_key(fact.get("stage"))] += 1
        rows[cleaned].append(fact)
    return dict(stages), dict(rows)


def _facts_by_evidence(bucket: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in bucket["facts"].values():
        evidence = str(fact.get("evidence") or "")
        if evidence:
            index[evidence].append(fact)
    return dict(index)


def _stage_of_coo(coo: Mapping[str, Any], facts_by_evidence: Mapping[str, list[dict[str, Any]]], company_stages: Mapping[str, Counter]) -> str:
    for fact in facts_by_evidence.get(str(coo.get("evidence") or ""), []):
        if fact.get("entity") == coo.get("company"):
            return _stage_key(fact.get("stage"))
    cleaned = clean_company_name(coo.get("company"))
    counter = company_stages.get(cleaned)
    if counter:
        return max(counter, key=lambda st: (counter[st], -STAGE_ORDER.index(st)))
    return "related"


def _stage_for_card_name(card_name: str, bucket: Mapping[str, Any], company_stages: Mapping[str, Counter]) -> str:
    hits: Counter = Counter()
    scanned = 0
    for fact in bucket["facts"].values():
        if card_name in str(fact.get("evidence") or ""):
            cleaned = clean_company_name(fact.get("entity"))
            counter = company_stages.get(cleaned)
            if counter:
                for stage, n in counter.items():
                    hits[stage] += n
            scanned += 1
            if scanned >= 60:
                break
    if hits:
        return max(hits, key=lambda st: (hits[st], -STAGE_ORDER.index(st)))
    return "related"


def _card_intro(name: str, card: Mapping[str, Any]) -> str:
    picks: list[str] = []
    for ev in card.get("evidence") or []:
        text = str(ev.get("t") or ev.get("evidence") or "").strip()
        if text and text not in picks:
            picks.append(text[:EVIDENCE_CHARS])
        if len(picks) >= MAX_EVIDENCE:
            break
    if picks:
        return "研报摘要：" + "；".join(picks)
    return f"研报中「{name}」环节累计出现 {int(card.get('count') or 0)} 次，暂无更详细事实摘要。"


def _build_stages(bucket: Mapping[str, Any], resolver: Any, *, f10_text_index: dict[str, str] | None = None, f10_by_industry: dict[str, list[tuple[str, str]]] | None = None, f10_by_chain: dict[str, list[tuple[str, str]]] | None = None, bucket_name: str = "") -> list[dict[str, Any]]:
    company_names = set(bucket["companies"])
    company_stages, company_rows = _company_stage_map(bucket)
    facts_by_evidence = _facts_by_evidence(bucket)
    cards: dict[str, dict[str, dict[str, Any]]] = {}
    chain_company_count = {"n": 0}

    # 1) Company <-> product co-occurrences are the primary association.
    for coo in bucket["coos"].values():
        cleaned = clean_company_name(coo.get("company"))
        card_name = clean_card_name(coo.get("product"), company_names)
        if not cleaned or not card_name:
            continue
        stage = _stage_of_coo(coo, facts_by_evidence, company_stages)
        card = _ensure_card(cards, stage, card_name, "product")
        card["count"] += 1
        card["sub_chains"].add(str(coo.get("chain") or ""))
        ev = _evidence_item(coo)
        if ev and len(card["evidence"]) < MAX_EVIDENCE and ev not in card["evidence"]:
            card["evidence"].append(ev)
        _add_company_to_card(
            card,
            cleaned,
            resolver,
            chain_company_count,
            count=1,
            evidence=coo,
            chain_name=str(coo.get("chain") or ""),
        )

    # 2) Product / material / service facts create cards in their own stage.
    kind_of_entity = {"PRODUCT": "product", "RAW_MATERIAL": "material", "SERVICE": "service"}
    for fact in bucket["facts"].values():
        entity_type = str(fact.get("entity_type") or "").upper()
        kind = kind_of_entity.get(entity_type)
        if not kind:
            continue
        card_name = clean_card_name(fact.get("entity"), company_names)
        if not card_name:
            continue
        stage = _stage_key(fact.get("stage"))
        card = _ensure_card(cards, stage, card_name, kind)
        card["count"] += 1
        card["sub_chains"].add(str(fact.get("chain") or ""))
        ev = _evidence_item(fact)
        if ev and len(card["evidence"]) < MAX_EVIDENCE and ev not in card["evidence"]:
            card["evidence"].append(ev)

    # 3) Chain-level product/material/service directories fill remaining cards.
    for kind, mapping in (
        ("product", bucket["products"]),
        ("material", bucket["materials"]),
        ("service", bucket["services"]),
    ):
        for card_name, entry in mapping.items():
            existing = None
            for stage_cards in cards.values():
                if card_name in stage_cards:
                    existing = stage_cards[card_name]
                    break
            if existing is not None:
                existing["count"] = max(existing["count"], int(entry["count"] or 0))
                continue
            stage = _stage_for_card_name(card_name, bucket, company_stages)
            card = _ensure_card(cards, stage, card_name, kind)
            card["count"] = max(card["count"], int(entry["count"] or 0))

    # 3.5) F10 reverse match: place companies on product cards by F10 business text.
    if f10_text_index:
        # Collect searchable card names (filter generic terms and short names).
        search_cards: list[tuple[str, str]] = []  # (card_name, stage)
        for stage in STAGE_ORDER:
            stage_cards = cards.get(stage)
            if not stage_cards:
                continue
            for name in stage_cards:
                if name == "__companies__":
                    continue
                if len(name) >= MIN_F10_MATCH_LEN and name not in _GENERIC_CARD_NAMES:
                    search_cards.append((name, stage))

        # Track companies already attached to any card in this chain.
        attached: set[str] = set()
        for stage_cards in cards.values():
            for card in stage_cards.values():
                attached.update(card["companies"])

        # 3.5a) For unattached companies in the bucket, look up F10 text and
        #        attach them to cards whose product name appears in their text.
        for cleaned in list(bucket["companies"]):
            if cleaned in attached or chain_company_count["n"] >= MAX_CHAIN_COMPANIES:
                continue
            text = f10_text_index.get(cleaned)
            if text is None:
                for rec in resolver(cleaned):
                    t = f10_text_index.get(str(rec.get("name") or ""))
                    if t:
                        text = t
                        break
            if not text:
                continue
            matches = 0
            for card_name, stage in search_cards:
                if matches >= MAX_F10_MATCHES_PER_COMPANY:
                    break
                if card_name in text:
                    card = cards[stage][card_name]
                    _add_company_to_card(
                        card, cleaned, resolver, chain_company_count,
                        count=1, evidence=None, chain_name="",
                    )
                    matches += 1
            if matches:
                attached.add(cleaned)

        # 3.5b) Discover NEW companies from F10 not in the report bucket.
        #        Candidates come from the curated industry -> chain mapping,
        #        with the exchange-industry pre-filter as a compatibility fallback.
        if chain_company_count["n"] < MAX_CHAIN_COMPANIES and (f10_by_chain or f10_by_industry):
            bucket_company_set = set(bucket["companies"])
            new_per_card: dict[str, int] = {}
            candidates = list(f10_by_chain.get(bucket_name, []) if f10_by_chain else [])
            if not candidates and f10_by_industry:
                for industry_key, companies in f10_by_industry.items():
                    if bucket_name and bucket_name not in industry_key:
                        continue
                    candidates.extend(companies)
            fallback = None
            for company_name, text in candidates:
                if chain_company_count["n"] >= MAX_CHAIN_COMPANIES:
                    break
                cleaned = clean_company_name(company_name)
                if not cleaned or cleaned in bucket_company_set or cleaned in attached:
                    continue
                matches = 0
                for card_name, stage in search_cards:
                    if matches >= MAX_F10_MATCHES_PER_COMPANY:
                        break
                    per_card_key = stage + "|" + card_name
                    if new_per_card.get(per_card_key, 0) >= MAX_F10_NEW_PER_CARD:
                        continue
                    if card_name in text:
                        card = cards[stage][card_name]
                        _add_company_to_card(
                            card, cleaned, resolver, chain_company_count,
                            count=1, evidence=None, chain_name="",
                        )
                        new_per_card[per_card_key] = new_per_card.get(per_card_key, 0) + 1
                        matches += 1
                if matches:
                    attached.add(cleaned)
                    continue
                # No product-card text hit: keep the company on the chain's
                # "其他相关公司" card so the full A/H universe is represented.
                if fallback is None:
                    fallback = _ensure_card(cards, "related", "__companies__", "companies")
                _add_company_to_card(
                    fallback, cleaned, resolver, chain_company_count,
                    count=1, evidence=None, chain_name="",
                )
                attached.add(cleaned)

    # 4) Companies that never attached to a product card get one fallback card.
    attached_anywhere: set[str] = set()
    for stage_cards in cards.values():
        for card in stage_cards.values():
            attached_anywhere.update(card["companies"])

    for cleaned, entry in bucket["companies"].items():
        if cleaned in attached_anywhere:
            continue
        counter = company_stages.get(cleaned)
        if counter:
            stage = max(counter, key=lambda st: (counter[st], -STAGE_ORDER.index(st)))
        else:
            stage = "related"
        card = _ensure_card(cards, stage, "__companies__", "companies")
        card["sub_chains"].update(str(name) for name in entry.get("raw") or [])
        _add_company_to_card(
            card,
            cleaned,
            resolver,
            chain_company_count,
            count=max(1, int(entry.get("fact_rows") or 0) or int(entry.get("count") or 0)),
            chain_name="",
        )

    # 5) Finalize per-stage cards.
    stages: list[dict[str, Any]] = []
    for stage in STAGE_ORDER:
        stage_cards = cards.get(stage)
        if not stage_cards:
            continue
        card_list: list[dict[str, Any]] = []
        for name, card in sorted(stage_cards.items(), key=lambda kv: (-kv[1]["count"], kv[0])):
            if name == "__companies__":
                continue
            companies = sorted(card["companies"].values(), key=lambda c: (-c["count"], c["name"]))
            companies = companies[:MAX_CARD_COMPANIES]
            card_list.append(
                {
                    "name": card["name"],
                    "kind": card["kind"],
                    "count": card["count"],
                    "intro": _card_intro(card["name"], card),
                    "sub_chains": sorted(card["sub_chains"]),
                    "companies": [
                        {
                            "name": c["name"],
                            "count": c["count"],
                            "codes": c["codes"],
                            "markets": c["markets"],
                            "evidence": c["evidence"],
                            "sub_chains": sorted(c["sub_chains"]),
                        }
                        for c in companies
                    ],
                }
            )
            if len(card_list) >= MAX_CARDS_PER_STAGE:
                break
        fallback = stage_cards.get("__companies__")
        if fallback and fallback["companies"]:
            companies = sorted(fallback["companies"].values(), key=lambda c: (-c["count"], c["name"]))
            card_list.append(
                {
                    "name": "其他相关公司",
                    "kind": "companies",
                    "count": len(fallback["companies"]),
                    "intro": "未与具体产品/环节卡片关联的产业链相关公司。",
                    "sub_chains": sorted(fallback["sub_chains"]),
                    "companies": [
                        {
                            "name": c["name"],
                            "count": c["count"],
                            "codes": c["codes"],
                            "markets": c["markets"],
                            "evidence": c["evidence"],
                            "sub_chains": sorted(c["sub_chains"]),
                        }
                        for c in companies
                    ],
                }
            )
        if card_list:
            stages.append(
                {
                    "stage": stage,
                    "label": STAGE_LABELS[stage],
                    "color": STAGE_COLORS[stage],
                    "cards": card_list,
                }
            )
    return stages


def _chain_counts(stages: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    a: set[str] = set()
    h: set[str] = set()
    for stage in stages:
        for card in stage.get("cards") or []:
            for company in card.get("companies") or []:
                for code, market in zip(company.get("codes") or [], company.get("markets") or []):
                    if market == "CN":
                        a.add(code)
                    elif market == "HK":
                        h.add(code)
    return {"a_share": len(a), "hk_share": len(h)}


def _chain_intro(parent: str, bucket: Mapping[str, Any]) -> str:
    parts: list[str] = []
    reference = STANDARD_REFERENCES.get(parent)
    if reference:
        parts.append(reference)
    ranked = sorted(
        bucket["facts"].values(),
        key=lambda fact: float(fact.get("confidence") or 0),
        reverse=True,
    )
    seen: set[str] = set()
    picks: list[str] = []
    for fact in ranked:
        evidence = str(fact.get("evidence") or "").strip()
        if not evidence or evidence in seen:
            continue
        seen.add(evidence)
        picks.append(evidence[:EVIDENCE_CHARS])
        if len(picks) >= 2:
            break
    if picks:
        parts.append("研报摘要：" + "；".join(picks))
    if not parts:
        parts.append(
            f"「{parent}」产业链相关研报共 {len(bucket['reports'])} 篇，暂未提取到可引用的事实摘要。"
        )
    return "。".join(parts)


def _build_company_index(atlas_chains: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for chain in atlas_chains:
        for stage in chain.get("stages") or []:
            for card in stage.get("cards") or []:
                for company in card.get("companies") or []:
                    key = _norm_name(company.get("name"))
                    if not key or key in index:
                        continue
                    index[key] = {
                        "name": company.get("name"),
                        "codes": company.get("codes") or [],
                        "markets": company.get("markets") or [],
                    }
    return index


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------


def build_atlas(
    output_root: Path,
    *,
    data_root: Path | None = None,
    chain_index_path: Path | None = None,
    legacy_html_path: Path | None = None,
    f10_dir: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the atlas JSON/HTML and sync the PC/Android copies."""

    output_root = Path(output_root)
    chain_index_path = Path(chain_index_path or output_root / "chain_index.json")
    legacy_html_path = Path(legacy_html_path or Path("docs") / "A股企业产业链精细定位.html")
    f10_dir = Path(f10_dir or (data_root or output_root.parent) / "industry" / "f10")
    data_root = Path(data_root or (output_root.parent if output_root.name == "industry" else output_root))

    chain_index = _read_json(chain_index_path)
    chains = list(chain_index.get("chains") or [])
    legacy_records = load_legacy_html(legacy_html_path)
    f10_records, f10_meta = load_f10(f10_dir)
    all_records = f10_records + legacy_records
    by_name, by_full = _build_index(all_records)
    all_names = set(by_name)

    def resolver(name: str) -> list[dict[str, Any]]:
        return resolve_company(name, by_name, by_full, all_names)

    f10_text_index = _build_f10_text_index(f10_records)
    f10_by_industry = _build_f10_by_industry(f10_records)
    f10_by_chain = _build_f10_by_chain(f10_records)
    buckets = _aggregate_chains(chains)
    atlas_chains: list[dict[str, Any]] = []
    company_codes: set[str] = set()

    ordered = sorted(
        buckets.values(),
        key=lambda bucket: (-len(bucket["facts"]), bucket["name"]),
    )
    for index, bucket in enumerate(ordered):
        stages = _build_stages(
            bucket,
            resolver,
            f10_text_index=f10_text_index,
            f10_by_industry=f10_by_industry,
            f10_by_chain=f10_by_chain,
            bucket_name=bucket["name"],
        )
        counts = _chain_counts(stages)
        for stage in stages:
            for card in stage["cards"]:
                for company in card["companies"]:
                    company_codes.update(company.get("codes") or [])
        sub_chains = sorted(
            bucket["sub_chains"].values(),
            key=lambda sub: (-int(sub["fact_count"] or 0), sub["name"]),
        )
        atlas_chains.append(
            {
                "id": f"chain-{index}",
                "name": bucket["name"],
                "sub_chains": sub_chains,
                "active_sub": None,
                "report_count": len(bucket["reports"]),
                "fact_count": len(bucket["facts"]),
                "counts": counts,
                "intro": _chain_intro(bucket["name"], bucket),
                "stages": stages,
            }
        )

    # Global company table (code -> compact F10) shared by every tooltip.
    company_table: dict[str, dict[str, Any]] = {}
    for record in all_records:
        code = str(record.get("code") or "")
        if not code or code not in company_codes:
            continue
        company_table.setdefault(code, _compact_f10(record))

    company_index = _build_company_index(atlas_chains)

    generated_at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "chain_count": len(atlas_chains),
        "fact_count": int(chain_index.get("fact_count") or 0),
        "f10": {
            "cn": sum(1 for record in f10_records if _market_of(record) == "CN"),
            "hk": sum(1 for record in f10_records if _market_of(record) == "HK"),
            "legacy": len(legacy_records),
            "meta": f10_meta,
        },
        "company_index": company_index,
        "companies": company_table,
        "chains": atlas_chains,
    }

    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "industry-atlas.json"
    _write_json(json_path, payload)
    html_path = output_root / "industry-atlas.html"
    render_atlas_html(payload, html_path)

    sync_target = data_root / "industry" / "industry-atlas.html"
    if str(sync_target.resolve()) != str(html_path.resolve()):
        sync_target.parent.mkdir(parents=True, exist_ok=True)
        sync_target.write_bytes(html_path.read_bytes())

    return {
        "json": str(json_path),
        "html": str(html_path),
        "synced_html": str(sync_target),
        "chain_count": len(atlas_chains),
        "company_codes": len(company_table),
    }


def render_atlas_html(payload: Mapping[str, Any], path: Path) -> None:
    """Write the self-contained offline atlas HTML."""

    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = _HTML_TEMPLATE.replace("__ATLAS_JSON__", serialized)
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(page)


_HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MarketListener 产业链全景图</title>
<style>
:root{
  --bg:#f4f6f9; --panel:#ffffff; --text:#1f2733; --muted:#6b7686;
  --line:#dfe5ec; --accent:#4a82f2; --chip:#eef3fb; --chip-text:#24406e;
  --shadow:0 1px 3px rgba(23,43,77,.08); --intro:#5b6675;
}
html[data-theme="dark"]{
  --bg:#12161d; --panel:#1a2029; --text:#e7ecf3; --muted:#98a3b3;
  --line:#2a3340; --accent:#6da1ff; --chip:#22314a; --chip-text:#c9d9f3;
  --shadow:0 1px 3px rgba(0,0,0,.35); --intro:#a9b4c2;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}
a{color:var(--accent)}
.topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:12px;
  padding:10px 16px;background:var(--panel);border-bottom:1px solid var(--line);box-shadow:var(--shadow)}
.topbar h1{font-size:17px;margin:0;white-space:nowrap}
.topbar .meta{color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.topbar .spacer{flex:1}
.btn{padding:5px 10px;border:1px solid var(--line);border-radius:7px;background:var(--panel);
  color:var(--text);cursor:pointer;font:inherit}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.layout{display:flex;align-items:flex-start;min-height:calc(100vh - 53px)}
aside{width:280px;min-width:280px;position:sticky;top:53px;height:calc(100vh - 53px);
  overflow:auto;padding:12px;border-right:1px solid var(--line);background:var(--panel)}
aside input{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;
  background:var(--bg);color:var(--text);margin-bottom:10px}
.chain-item{display:flex;align-items:center;gap:6px;padding:7px 9px;border-radius:8px;cursor:pointer}
.chain-item:hover{background:var(--chip)}
.chain-item.active{background:var(--chip);box-shadow:inset 3px 0 0 var(--accent)}
.chain-item .nm{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chain-item .cnt{color:var(--muted);font-size:11px;white-space:nowrap}
main{flex:1;padding:18px 22px 90px;overflow:auto}
.chain-head{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin:2px 0 6px}
.chain-head h2{font-size:26px;margin:0}
.counts{display:flex;gap:8px;flex-wrap:wrap}
.count-pill{padding:3px 10px;border-radius:999px;background:var(--chip);color:var(--chip-text);font-size:12px}
.chain-intro{color:var(--intro);font-size:13px;line-height:1.7;margin:0 0 12px;max-width:1000px}
.sub-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 16px}
.sub-tabs .tab{padding:4px 12px;border:1px solid var(--line);border-radius:999px;background:var(--panel);
  color:var(--text);cursor:pointer;font:inherit;font-size:12px}
.sub-tabs .tab:hover{border-color:var(--accent);color:var(--accent)}
.sub-tabs .tab.active{background:var(--accent);border-color:var(--accent);color:#fff}
.stage{border-radius:12px;margin:0 0 20px;overflow:hidden;border:1px solid var(--line);background:var(--panel)}
.stage-bar{display:flex;align-items:center;gap:10px;padding:9px 14px;color:#fff;font-weight:600}
.stage-bar .count{opacity:.85;font-size:12px;font-weight:400}
.stage-body{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px;padding:14px}
.card{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:11px 13px}
.card-head{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.card-name{font-size:14px;font-weight:700}
.kind-tag{padding:1px 8px;border-radius:999px;background:var(--panel);border:1px solid var(--line);
  color:var(--muted);font-size:11px}
.card-count{color:var(--muted);font-size:11px;margin-left:auto;white-space:nowrap}
.card-intro{color:var(--intro);font-size:12px;line-height:1.6;margin:0 0 8px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{border:1px solid var(--line);background:var(--chip);color:var(--chip-text);
  border-radius:999px;padding:3px 9px;cursor:pointer;font:inherit;font-size:12px;max-width:100%}
.chip:hover{border-color:var(--accent);color:var(--accent)}
.chip .code{opacity:.65;font-size:11px;margin-left:5px}
.chip.no-code{opacity:.72;border-style:dashed}
.tooltip{position:fixed;z-index:50;max-width:380px;min-width:260px;background:var(--panel);
  border:1px solid var(--line);border-radius:12px;box-shadow:0 8px 28px rgba(0,0,0,.22);
  padding:12px 14px;pointer-events:none;display:none}
.tooltip h4{margin:0 0 6px;font-size:15px}
.tooltip .code-line{color:var(--muted);font-size:12px;margin-bottom:8px}
.tooltip .row{display:flex;gap:8px;margin:3px 0;font-size:12px}
.tooltip .row .k{color:var(--muted);min-width:64px;flex-shrink:0}
.tooltip .row .v{word-break:break-word}
.tooltip .missing{color:var(--muted);font-style:italic}
.drawer{position:fixed;left:280px;right:0;bottom:0;max-height:44vh;overflow:auto;
  background:var(--panel);border-top:1px solid var(--line);box-shadow:0 -6px 24px rgba(0,0,0,.18);
  padding:14px 18px;display:none;z-index:40}
.drawer h3{margin:0 0 10px}
.ev{margin:0 0 10px;padding:9px 12px;border:1px solid var(--line);border-radius:9px;background:var(--bg)}
.ev .src{color:var(--muted);font-size:12px;margin-top:4px}
.ev .pg{color:var(--accent);font-size:12px}
.empty{color:var(--muted);padding:30px;text-align:center}
.search-results{position:absolute;top:46px;right:16px;width:340px;max-height:60vh;overflow:auto;
  background:var(--panel);border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow);display:none;z-index:60}
.search-results .hit{padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--line)}
.search-results .hit:hover{background:var(--chip)}
.search-results .hit .s{color:var(--muted);font-size:11px}
@media (max-width:900px){
  .layout{display:block}
  aside{width:100%;min-width:0;position:static;height:auto;border-right:0;border-bottom:1px solid var(--line);max-height:32vh}
  .drawer{left:0}
  .search-results{width:auto;left:12px;right:12px}
}
</style>
</head>
<body>
<script id="atlas-data" type="application/json">__ATLAS_JSON__</script>

<div class="topbar">
  <h1>产业链全景图</h1>
  <span class="meta" id="head-meta"></span>
  <div class="spacer"></div>
  <input id="global-search" type="search" placeholder="搜索公司 / 产品 / 产业链" style="width:220px;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text)">
  <button class="btn" id="zoom-out" title="缩小">−</button>
  <button class="btn" id="zoom-in" title="放大">＋</button>
  <button class="btn" id="theme-toggle" title="切换主题">🌓</button>
</div>
<div class="search-results" id="global-results"></div>

<div class="layout">
  <aside>
    <input id="chain-filter" type="search" placeholder="筛选产业链">
    <div id="chain-list"></div>
  </aside>
  <main id="main">
    <div class="empty">正在加载产业链全景图…</div>
  </main>
</div>

<div class="tooltip" id="tooltip"></div>
<div class="drawer" id="drawer">
  <h3 id="drawer-title"></h3>
  <div id="drawer-body"></div>
</div>

<script>
"use strict";
const ATLAS = JSON.parse(document.getElementById("atlas-data").textContent);
const COMPANIES = ATLAS.companies || {};
const INDEX = ATLAS.company_index || {};
const CHAINS = ATLAS.chains || [];
let activeChain = CHAINS[0] || null;
let activeSub = null;
let zoom = 1;

const chainList = document.getElementById("chain-list");
const mainEl = document.getElementById("main");
const tooltip = document.getElementById("tooltip");
const drawer = document.getElementById("drawer");
const globalResults = document.getElementById("global-results");

function esc(s){ const d=document.createElement("div"); d.textContent = s==null?"":String(s); return d.innerHTML; }
function stageColor(stage){ return {"upstream":"#3d7fb8","midstream":"#7c6ee8","downstream":"#d8729f","service":"#4a9b76","related":"#8b929a"}[stage]||"#8b929a"; }
function stageLabel(stage){ return {"upstream":"上游","midstream":"中游","downstream":"下游","service":"服务与配套","related":"产业链相关"}[stage]||stage; }
function kindLabel(kind){ return {"product":"产品","material":"材料","service":"服务","companies":"公司"}[kind]||kind||"环节"; }
function marketName(m){ return m==="CN"?"A股":(m==="HK"?"港股":(m||"其他")); }
function fmtCap(v){ if(v==null||isNaN(v)) return null; const n=Number(v); if(n>=1e12) return (n/1e12).toFixed(2)+" 万亿"; if(n>=1e8) return (n/1e8).toFixed(1)+" 亿"; if(n>=1e4) return (n/1e4).toFixed(1)+" 万"; return String(n); }
function fmtPct(v){ if(v==null||isNaN(v)) return null; return (Number(v)*100).toFixed(1)+"%"; }
function displayCodes(codes, markets){
  codes = codes||[]; markets = markets||[];
  return codes.map((c,i)=> markets[i]==="HK" ? "HK:"+c : c).join(" · ");
}

function renderChainList(){
  const q = (document.getElementById("chain-filter").value||"").trim().toLowerCase();
  chainList.innerHTML = "";
  CHAINS.forEach(chain=>{
    const name = chain.name||"";
    if(q && !name.toLowerCase().includes(q)) return;
    const row = document.createElement("div");
    row.className = "chain-item" + (activeChain && activeChain.id===chain.id ? " active" : "");
    const nm = document.createElement("span"); nm.className="nm"; nm.textContent = name;
    const cnt = document.createElement("span"); cnt.className="cnt";
    cnt.textContent = "A"+chain.counts.a_share+" · H"+chain.counts.hk_share;
    row.appendChild(nm); row.appendChild(cnt);
    row.addEventListener("click", ()=>{ activeChain=chain; activeSub=null; renderChainList(); renderChain(); });
    chainList.appendChild(row);
  });
}

function chipHtml(company){
  const code = displayCodes(company.codes, company.markets);
  const cls = "chip company" + (code ? "" : " no-code");
  return '<button class="'+cls+'" data-name="'+esc(company.name)+'" data-codes="'+esc(JSON.stringify(company.codes||[]))+'" data-markets="'+esc(JSON.stringify(company.markets||[]))+'">'
    + esc(company.name) + (code ? '<span class="code">'+esc(code)+'</span>' : "")
    + '</button>';
}

function renderChain(){
  if(!activeChain){ mainEl.innerHTML = '<div class="empty">暂无产业链数据</div>'; return; }
  const chain = activeChain;
  let html = '';
  html += '<div class="chain-head"><h2>'+esc(chain.name)+'</h2><div class="counts">'
    + '<span class="count-pill">'+chain.report_count+' 篇研报</span>'
    + '<span class="count-pill">'+chain.fact_count+' 条事实</span>'
    + '<span class="count-pill" style="background:#e3f0e5;color:#2c6e3f">A股 '+chain.counts.a_share+' 家</span>'
    + '<span class="count-pill" style="background:#fdeaf0;color:#a13c63">港股 '+chain.counts.hk_share+' 家</span>'
    + '</div></div>';
  if(chain.intro) html += '<div class="chain-intro">'+esc(chain.intro)+'</div>';
  html += '<div class="sub-tabs">'
    + '<button class="tab'+(activeSub===null?' active':'')+'" data-sub="__all__">全部</button>'
    + (chain.sub_chains||[]).map(s=>'<button class="tab'+(activeSub===s.name?' active':'')+'" data-sub="'+esc(s.name)+'">'+esc(s.name)+'</button>').join("")
    + '</div>';
  const stages = (chain.stages||[]).filter(st=>{
    if(!activeSub) return true;
    return (st.cards||[]).some(c=> (c.sub_chains||[]).indexOf(activeSub)>=0);
  });
  if(!stages.length){
    mainEl.innerHTML = html + '<div class="empty">该产业链暂无可用事实（共 '+chain.report_count+' 篇研报）。</div>';
    return;
  }
  stages.forEach(stage=>{
    const cards = (stage.cards||[]).filter(c=> !activeSub || (c.sub_chains||[]).indexOf(activeSub)>=0);
    if(!cards.length) return;
    html += '<div class="stage"><div class="stage-bar" style="background:'+stageColor(stage.stage)+'">'
      + esc(stage.label)
      + '<span class="count">'+cards.length+' 个环节</span></div><div class="stage-body">';
    cards.forEach(card=>{
      html += '<div class="card"><div class="card-head">'
        + '<span class="card-name">'+esc(card.name)+'</span>'
        + '<span class="kind-tag">'+esc(kindLabel(card.kind))+'</span>'
        + '<span class="card-count">'+card.count+' 次</span></div>';
      if(card.intro) html += '<div class="card-intro">'+esc(card.intro)+'</div>';
      html += '<div class="chips">'+(card.companies||[]).map(chipHtml).join("")+'</div>';
      html += '</div>';
    });
    html += '</div></div>';
  });
  mainEl.innerHTML = html;
  bindSubTabs();
  bindChips();
}

function bindSubTabs(){
  mainEl.querySelectorAll(".sub-tabs .tab").forEach(btn=>{
    btn.addEventListener("click", ()=>{
      activeSub = btn.dataset.sub === "__all__" ? null : btn.dataset.sub;
      renderChain();
    });
  });
}

function bindChips(){
  mainEl.querySelectorAll(".chip.company").forEach(chip=>{
    chip.addEventListener("mouseenter", ev=>{
      const codes = JSON.parse(chip.dataset.codes||"[]");
      const markets = JSON.parse(chip.dataset.markets||"[]");
      const rec = codes.map(c=>COMPANIES[c]).find(r=>r);
      if(!rec){ tooltip.innerHTML = '<h4>'+esc(chip.dataset.name)+'</h4><div class="missing">非 A/H 上市或暂无 F10 数据</div>'; }
      else{
        const rows = [
          ["证券代码", displayCodes([rec.code],[rec.market])],
          ["市场", marketName(rec.market)],
          ["总市值", rec.total_market_cap!=null?fmtCap(rec.total_market_cap):null],
          ["流通市值", rec.float_market_cap!=null?fmtCap(rec.float_market_cap):null],
          ["数据更新", rec.fetched_at],
          ["所属行业", rec.industry],
          ["证监会行业", rec.csrc_industry],
          ["主营构成", (rec.revenue_breakdown||[]).slice(0,4).map(x=>(x.item||"")+(x.ratio!=null?" "+fmtPct(x.ratio):"")).join("、")],
          ["公司简介", (rec.profile||"").slice(0,240)],
          ["主营业务", (rec.main_business||"").slice(0,240)],
        ].filter(r=>r[1]!=null && r[1]!=="");
        tooltip.innerHTML = '<h4>'+esc(rec.name||chip.dataset.name)+'</h4>'
          + '<div class="code-line">'+rows.filter(r=>r[0]==="证券代码"||r[0]==="市场").map(r=>esc(r[0])+" "+esc(r[1])).join(" · ")
          + (rec.source? ' · 来源：'+esc(rec.source) : "") + '</div>'
          + rows.filter(r=>r[0]!=="证券代码"&&r[0]!=="市场").map(r=>'<div class="row"><span class="k">'+esc(r[0])+'</span><span class="v">'+esc(r[1])+'</span></div>').join("")
          + (rows.length<=2?'<div class="missing">暂无更多 F10 字段</div>':"");
      }
      tooltip.style.display="block";
      positionTooltip(ev);
    });
    chip.addEventListener("mousemove", positionTooltip);
    chip.addEventListener("mouseleave", ()=>{ tooltip.style.display="none"; });
    chip.addEventListener("click", ()=>{
      openDrawer(chip.dataset.name, JSON.parse(chip.dataset.codes||"[]"));
    });
  });
}

function positionTooltip(ev){
  const w = tooltip.offsetWidth, h = tooltip.offsetHeight;
  let x = ev.clientX + 14, y = ev.clientY + 14;
  if(x + w > window.innerWidth - 8) x = ev.clientX - w - 10;
  if(y + h > window.innerHeight - 8) y = ev.clientY - h - 10;
  tooltip.style.left = Math.max(6,x)+"px";
  tooltip.style.top = Math.max(6,y)+"px";
}

function openDrawer(name, codes){
  const rec = codes.map(c=>COMPANIES[c]).find(r=>r);
  drawer.style.display="block";
  document.getElementById("drawer-title").textContent = name + (rec && rec.code ? "（"+displayCodes([rec.code],[rec.market])+"）" : "");
  const body = document.getElementById("drawer-body");
  body.innerHTML = "";
  if(rec){
    const rows = [
      ["公司名称", rec.full_name||rec.name],
      ["市场", marketName(rec.market)],
      ["总市值", rec.total_market_cap!=null?fmtCap(rec.total_market_cap):null],
      ["流通市值", rec.float_market_cap!=null?fmtCap(rec.float_market_cap):null],
      ["数据更新", rec.fetched_at],
      ["所属行业", rec.industry],
      ["证监会行业", rec.csrc_industry],
      ["公司简介", rec.profile],
      ["主营业务", rec.main_business],
      ["主营构成", (rec.revenue_breakdown||[]).map(x=>(x.item||"")+(x.amount!=null?" "+fmtCap(x.amount):"")+(x.ratio!=null?"（"+fmtPct(x.ratio)+"）":"")).join("；")],
    ].filter(r=>r[1]!=null && r[1]!=="");
    rows.forEach(r=>{
      const div=document.createElement("div"); div.className="ev";
      div.innerHTML = '<div><b>'+esc(r[0])+'：</b></div><div class="src">'+esc(r[1])+'</div>';
      body.appendChild(div);
    });
    if(!rows.length) body.innerHTML = '<div class="empty">暂无 F10 详情</div>';
  }
  const h = document.createElement("h4"); h.textContent="研报证据"; body.appendChild(h);
  const chain = activeChain;
  const items = [];
  (chain.stages||[]).forEach(st=>(st.cards||[]).forEach(c=>(c.companies||[]).forEach(co=>{
    if(co.name===name) items.push(...(co.evidence||[]));
  })));
  const uniq = [];
  const seen = new Set();
  items.forEach(e=>{ const k=e.t+e.p; if(!seen.has(k)){ seen.add(k); uniq.push(e); } });
  if(!uniq.length){ body.innerHTML += '<div class="empty">该企业暂无研报证据句（可能来自产业链聚合统计）。</div>'; }
  else uniq.slice(0,8).forEach(e=>{
    const div=document.createElement("div"); div.className="ev";
    div.innerHTML = '<div>'+esc(e.t)+'</div>'
      + '<div class="src">'+esc(e.f||e.r||"")+' <span class="pg">第'+esc(e.p!=null?e.p:"-")+' 页</span>'
      + (e.c!=null?' · 置信度 '+Math.round(e.c*100)+'%':'')+'</div>';
    body.appendChild(div);
  });
}

function setZoom(v){ zoom = Math.min(2, Math.max(0.6, v)); mainEl.style.fontSize = (zoom*100)+"%"; }

function globalSearch(q){
  q = (q||"").trim();
  if(!q){ globalResults.style.display="none"; return; }
  const hits=[];
  Object.keys(INDEX).forEach(key=>{
    if(INDEX[key].name.toLowerCase().includes(q.toLowerCase())) hits.push(INDEX[key]);
  });
  if(hits.length<40) CHAINS.forEach(c=>{ if((c.name||"").toLowerCase().includes(q.toLowerCase())) hits.push({name:c.name+"（产业链）",chain:c.id}); });
  globalResults.innerHTML = "";
  hits.slice(0,30).forEach(hit=>{
    const row=document.createElement("div"); row.className="hit";
    row.innerHTML = '<div>'+esc(hit.name)+'</div><div class="s">'+esc(displayCodes(hit.codes, hit.markets))+'</div>';
    row.addEventListener("click", ()=>{
      globalResults.style.display="none";
      if(hit.chain){
        const c = CHAINS.find(x=>x.id===hit.chain); if(c){ activeChain=c; activeSub=null; renderChainList(); renderChain(); }
        return;
      }
      let target=null;
      CHAINS.forEach(c=>{
        if(target) return;
        (c.stages||[]).forEach(st=>(st.cards||[]).forEach(card=>(card.companies||[]).forEach(co=>{
          if(!target && co.name===hit.name) target={chain:c, name:co.name};
        })));
      });
      if(!target) return;
      activeChain=target.chain; activeSub=null; renderChainList(); renderChain();
      setTimeout(()=>{
        const chip=[...mainEl.querySelectorAll(".chip.company")].find(c=>c.dataset.name===target.name);
        if(chip){ chip.scrollIntoView({behavior:"smooth",block:"center"}); chip.style.outline="2px solid var(--accent)"; setTimeout(()=>chip.style.outline="",1600); }
      },60);
    });
    globalResults.appendChild(row);
  });
  globalResults.style.display = hits.length? "block":"none";
}

document.getElementById("chain-filter").addEventListener("input", renderChainList);
document.getElementById("global-search").addEventListener("input", ev=>globalSearch(ev.target.value));
document.addEventListener("click", ev=>{ if(!ev.target.closest("#global-search")&&!ev.target.closest("#global-results")) globalResults.style.display="none"; });
document.getElementById("zoom-in").addEventListener("click", ()=>setZoom(zoom+0.15));
document.getElementById("zoom-out").addEventListener("click", ()=>setZoom(zoom-0.15));
document.getElementById("theme-toggle").addEventListener("click", ()=>{
  const root=document.documentElement;
  root.dataset.theme = root.dataset.theme==="dark" ? "light" : "dark";
});

function init(){
  const meta = document.getElementById("head-meta");
  meta.textContent = ATLAS.chain_count+" 条产业链 · "+ATLAS.fact_count+" 条事实 · 生成于 "+ATLAS.generated_at
    + " · F10: A股 "+ATLAS.f10.cn+" / 港股 "+ATLAS.f10.hk;
  renderChainList();
  renderChain();
}
init();
</script>
</body>
</html>
"""
