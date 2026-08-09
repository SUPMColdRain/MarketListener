"""新版券商研报式产业链全景图（industry atlas）回归测试。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from market_monitor.chain_taxonomy import clean_company_name
from market_monitor.industry_atlas import (
    SCHEMA_VERSION,
    _build_f10_by_chain,
    _f10_chain_candidates,
    _norm_name,
    build_atlas,
    clean_card_name,
    load_legacy_html,
    resolve_company,
)


LEGACY_HTML = """<!doctype html>
<html><body>
<script>
const DATA = [
  {
    "name": "新能源汽车",
    "stages": [
      {
        "label": "上游",
        "companies": [
          {
            "code": "300750",
            "name": "宁德时代",
            "market_cap": 8.1e11,
            "revenue": 4.0e11,
            "industry": "电气机械和器材制造业",
            "products": ["动力电池"]
          }
        ]
      }
    ]
  }
];
</script>
</body></html>
"""


def _chain_index() -> dict[str, object]:
    """Two sub-chains that should merge into parent '半导体'."""
    return {
        "schema_version": 1,
        "chain_count": 2,
        "report_count": 1,
        "fact_count": 4,
        "chains": [
            {
                "chain": "半导体",
                "report_count": 1,
                "fact_count": 2,
                "companies": [{"name": "圣邦股份", "count": 2}],
                "segments": [],
                "products": [
                    {"name": "CMOS", "count": 1},
                    {"name": "创业板", "count": 1},
                ],
                "materials": [],
                "services": [],
                "facts": [
                    {
                        "entity": "圣邦股份",
                        "entity_type": "COMPANY",
                        "stage": "中游",
                        "evidence": "圣邦股份是国内模拟芯片龙头企业。",
                        "page": 3,
                        "report_id": "r1",
                        "file_name": "半导体深度报告.pdf",
                        "confidence": 0.9,
                    },
                    {
                        "entity": "CMOS",
                        "entity_type": "PRODUCT",
                        "stage": "中游",
                        "evidence": "CMOS图像传感器是核心器件。",
                        "page": 5,
                        "report_id": "r1",
                        "file_name": "半导体深度报告.pdf",
                        "confidence": 0.8,
                    },
                ],
                "cooccurrences": [
                    {
                        "company": "圣邦股份",
                        "product": "CMOS",
                        "evidence": "圣邦股份在CMOS领域布局。",
                        "page": 4,
                        "report_id": "r1",
                        "file_name": "半导体深度报告.pdf",
                    },
                    {
                        "company": "圣邦股份",
                        "product": "创业板",
                        "evidence": "公司于深交所创业板上市。",
                        "page": 4,
                        "report_id": "r1",
                        "file_name": "半导体深度报告.pdf",
                    },
                ],
                "reports": [{"report_id": "r1", "file_name": "半导体深度报告.pdf"}],
            },
            {
                "chain": "半导体材料",
                "report_count": 1,
                "fact_count": 2,
                "companies": [{"name": "江丰电子", "count": 1}],
                "segments": [],
                "products": [{"name": "溅射靶材", "count": 1}],
                "materials": [],
                "services": [],
                "facts": [
                    {
                        "entity": "江丰电子",
                        "entity_type": "COMPANY",
                        "stage": "上游",
                        "evidence": "江丰电子是国内高纯溅射靶材龙头。",
                        "page": 7,
                        "report_id": "r2",
                        "file_name": "半导体材料报告.pdf",
                        "confidence": 0.85,
                    },
                    {
                        "entity": "溅射靶材",
                        "entity_type": "PRODUCT",
                        "stage": "上游",
                        "evidence": "溅射靶材是半导体制造关键材料。",
                        "page": 8,
                        "report_id": "r2",
                        "file_name": "半导体材料报告.pdf",
                        "confidence": 0.8,
                    },
                ],
                "cooccurrences": [
                    {
                        "company": "江丰电子",
                        "product": "溅射靶材",
                        "evidence": "江丰电子专注于溅射靶材研发。",
                        "page": 9,
                        "report_id": "r2",
                        "file_name": "半导体材料报告.pdf",
                    },
                ],
                "reports": [{"report_id": "r2", "file_name": "半导体材料报告.pdf"}],
            },
        ],
    }


def test_load_legacy_html_parses_company_records(tmp_path: Path) -> None:
    source = tmp_path / "legacy.html"
    source.write_text(LEGACY_HTML, encoding="utf-8")

    records = load_legacy_html(source)

    assert len(records) == 1
    assert records[0]["code"] == "300750"
    assert records[0]["name"] == "宁德时代"
    assert records[0]["source"] == "legacy_html"
    assert records[0]["chain"] == "新能源汽车"


def test_load_legacy_html_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_legacy_html(tmp_path / "missing.html") == []


def test_name_normalization_strips_suffixes() -> None:
    assert _norm_name("宁德时代") == "宁德时代"
    assert _norm_name("宁德时代新能源科技股份有限公司") == "宁德时代"
    assert _norm_name(" 宁德时代·新能源") == "宁德时代新能源"


def test_f10_chain_candidates_from_exchange_and_csrc() -> None:
    # Eastmoney L2: 电子设备-半导体 -> 半导体
    assert _f10_chain_candidates({"industry": "电子设备-半导体"}) == ["半导体"]
    # HKEX industry name -> 医药生物
    assert _f10_chain_candidates({"industry": "药品及生物科技"}) == ["医药生物"]
    # CSRC second-level name -> 计算机/通信/消费电子
    chains = _f10_chain_candidates({"csrc_industry": "计算机、通信和其他电子设备制造业"})
    assert chains[0] == "计算机"
    assert {"计算机", "通信", "消费电子"} <= set(chains)
    # Eastmoney L3: 电气设备-电源设备-储能设备 keeps 储能 once
    chains = _f10_chain_candidates({"industry": "电气设备-电源设备-储能设备"})
    assert chains.count("储能") == 1
    assert "光伏" in chains
    # Unmapped industry -> empty
    assert _f10_chain_candidates({"industry": "全新未分类行业"}) == []


def test_build_f10_by_chain_groups_and_falls_back_to_topic_keywords() -> None:
    records = [
        {"name": "甲公司", "industry": "电子设备-半导体", "main_business": "设计CMOS芯片"},
        {"name": "乙公司", "industry": "其他未分类行业", "main_business": "锂电池正极材料"},
        {"name": "", "industry": "电子设备-半导体"},
    ]
    by_chain = _build_f10_by_chain(records)
    assert "半导体" in by_chain
    assert "甲公司" in [name for name, _ in by_chain["半导体"]]
    assert "乙公司" not in [name for name, _ in by_chain["半导体"]]
    assert "锂电池" in by_chain
    assert [name for name, _ in by_chain["锂电池"]] == ["乙公司"]


def test_clean_company_name_filters_fragments() -> None:
    assert clean_company_name("年整体改制为宁波三星电气股份") != "年整体改制为宁波三星电气股份"
    assert clean_company_name("宁德时代") == "宁德时代"
    assert clean_company_name("") == ""


def test_clean_card_name_filters_market_board_terms() -> None:
    assert clean_card_name("创业板", set()) == ""
    assert clean_card_name("创业板指数", set()) == ""
    assert clean_card_name("沪深", set()) == ""
    assert clean_card_name("中证500", set()) == ""
    assert clean_card_name("深交所", set()) == ""
    assert clean_card_name("上市", set()) == ""
    assert clean_card_name("CMOS", set()) == "CMOS"
    assert clean_card_name("磷化铟", set()) == "磷化铟"


def test_resolve_company_exact_and_suffix(tmp_path: Path) -> None:
    from market_monitor.industry_atlas import _build_index

    by_name, by_full = _build_index(
        [
            {
                "code": "300750",
                "name": "宁德时代",
                "full_name": "宁德时代新能源科技股份有限公司",
                "market": "CN",
            }
        ]
    )
    all_names = set(by_name)

    assert resolve_company("宁德时代", by_name, by_full, all_names)[0]["code"] == "300750"
    assert resolve_company("宁德时代新能源科技股份有限公司", by_name, by_full, all_names)[0]["code"] == "300750"


def test_build_atlas_emits_offline_html_and_counts(tmp_path: Path) -> None:
    output_root = tmp_path / "reports" / "industry"
    data_root = tmp_path / "data_control"
    output_root.mkdir(parents=True)
    (output_root / "chain_index.json").write_text(
        json.dumps(_chain_index(), ensure_ascii=False),
        encoding="utf-8",
    )
    legacy = tmp_path / "docs" / "A股企业产业链精细定位.html"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(LEGACY_HTML, encoding="utf-8")
    f10_dir = tmp_path / "f10"
    f10_dir.mkdir()
    cn_records = [
        {
            "code": "300661",
            "name": "圣邦股份",
            "full_name": "圣邦微电子(北京)股份有限公司",
            "market": "CN",
            "total_market_cap": 5e10,
            "industry": "计算机、通信和其他电子设备制造业",
        },
        {
            "code": "600001",
            "name": "新公司A",
            "market": "CN",
            "industry": "电子设备-半导体",
            "main_business": "主营CMOS图像传感器芯片设计",
        },
        {
            "code": "600002",
            "name": "新公司B",
            "market": "CN",
            "industry": "电子设备-半导体",
            "main_business": "公司主要从事财务咨询业务",
        },
    ]
    (f10_dir / "cn_f10.jsonl").write_text(
        "".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in cn_records),
        encoding="utf-8",
    )
    (f10_dir / "hk_f10.jsonl").write_text(
        json.dumps(
            {
                "code": "01801",
                "name": "信达生物",
                "full_name": "信达生物制药(苏州)有限公司",
                "market": "HK",
                "total_market_cap": 6e10,
                "industry": "生物制品",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = build_atlas(
        output_root,
        data_root=data_root,
        legacy_html_path=legacy,
        f10_dir=f10_dir,
    )

    assert summary["chain_count"] == 1  # 两子链合并为1父链
    json_path = output_root / "industry-atlas.json"
    html_path = output_root / "industry-atlas.html"
    assert json_path.is_file()
    assert html_path.is_file()
    assert (data_root / "industry" / "industry-atlas.html").is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    chains = payload["chains"]
    assert len(chains) == 1
    chain = chains[0]

    # sub_chains merged
    assert len(chain["sub_chains"]) >= 2
    sub_names = {s["name"] for s in chain["sub_chains"]}
    assert "半导体" in sub_names
    assert "半导体材料" in sub_names

    # stages not sections
    assert "stages" in chain
    assert "sections" not in chain
    stages = chain["stages"]
    assert len(stages) > 0

    # cards have companies directly
    has_card_with_companies = False
    for stage in stages:
        for card in stage.get("cards") or []:
            assert "companies" in card
            if card["companies"]:
                has_card_with_companies = True
    assert has_card_with_companies

    # intro exists
    assert chain.get("intro")

    # F10 reverse mapping: 新公司A attaches to the CMOS product card
    # and 新公司B (no product-text match) lands on the fallback card.
    cmos_companies: list[str] = []
    fallback_companies: list[str] = []
    board_cards: list[str] = []
    for stage in stages:
        for card in stage.get("cards") or []:
            names = [c["name"] for c in card.get("companies") or []]
            if card.get("name") == "CMOS":
                cmos_companies.extend(names)
            if card.get("name") == "其他相关公司":
                fallback_companies.extend(names)
            if "创业板" in str(card.get("name") or ""):
                board_cards.append(str(card.get("name")))
    assert "新公司A" in cmos_companies
    assert "新公司B" in fallback_companies
    assert board_cards == []

    html = html_path.read_text(encoding="utf-8")
    assert "__ATLAS_JSON__" not in html
    assert "http://" not in html and "https://" not in html
    # Placeholder must be fully replaced
    assert "__ATLAS_JSON__" not in html
    # The JSON data block must escape </ to prevent script injection
    data_block = re.search(r'<script id="atlas-data"[^>]*>(.*?)</script>', html, re.DOTALL)
    if data_block:
        assert "</script" not in data_block.group(1)
    assert "产业链" in html
