"""Fixed terminology samples for unambiguous industry-graph terms.

FULL-700 keeps the graph vocabulary unambiguous by fixing the mapping between
common mentions and entity types.  Any mention that maps to more than one
entity type in this table is a terminology bug and must fail the test suite.
"""

from __future__ import annotations

from typing import Final

#: Fixed sample: mention -> expected entity type.  The table is deliberately
#: small and deterministic; FULL-702 uses it to disambiguate mentions before
#: relationship extraction and to route ambiguous mentions to PENDING.
TERMINOLOGY_SAMPLES: Final[tuple[tuple[str, str], ...]] = (
    ("茅台", "COMPANY"),
    ("贵州茅台", "COMPANY"),
    ("贵州茅台酒股份有限公司", "COMPANY"),
    ("茅台酒", "PRODUCT"),
    ("五粮液", "COMPANY"),
    ("五粮液酒", "PRODUCT"),
    ("白酒", "INDUSTRY"),
    ("动力电池", "PRODUCT"),
    ("宁德时代", "COMPANY"),
    ("锂电池", "PRODUCT"),
    ("碳酸锂", "RAW_MATERIAL"),
    ("半导体", "INDUSTRY"),
    ("晶圆代工", "SERVICE"),
    ("华东地区", "REGION"),
)

#: Canonical definitions used by the terminology documentation and the model.
TERM_DEFINITIONS: Final[dict[str, str]] = {
    "COMPANY": "依法注册、以营利为目的的法人主体，例如上市公司及其子公司。",
    "PRODUCT": "公司生产或销售的可辨识产品或服务形态，例如茅台酒、动力电池。",
    "INDUSTRY": "由同类产品或服务构成的市场/行业分类，例如白酒、半导体。",
    "SUPPLIER": "在特定关系中向上游提供原材料、零部件或服务的实体角色。",
    "CUSTOMER": "在特定关系中向下游购买产品或服务的实体角色。",
    "RAW_MATERIAL": "用于生产过程的原材料或资源，例如碳酸锂、铜箔。",
    "SERVICE": "不形成实物产品的交付物，例如晶圆代工、物流。",
    "REGION": "地理区域或行政区域，例如华东地区。",
    "SUPPLIES": "A 向 B 供应原材料/零部件/服务（有向：A -> B）。",
    "PURCHASES": "A 从 B 采购原材料/零部件/服务（有向：A -> B）。",
    "PRODUCES": "A 生产产品 B（有向：公司 -> 产品）。",
    "PART_OF": "B 是 A 的组成部分或 A 属于 B（有向：部分 -> 整体）。",
    "COMPETES_WITH": "A 与 B 存在竞争关系（无向）。",
    "DISTRIBUTES": "A 分销/代理 B 的产品（有向：A -> B）。",
    "USES": "A 使用 B 的产品/服务（有向：A -> B）。",
    "OWNS": "A 持有/控制 B（有向：A -> B）。",
    "CUSTOMER_OF": "A 是 B 的客户（有向：A -> B；等价于 B SUPPLIES A）。",
}

#: Per-type ambiguity guards.  A mention may appear with several contexts, but
#: its canonical entity type must be unique.
AMBIGUOUS_SAMPLES: Final[tuple[tuple[str, str], ...]] = (
    ("茅台", "贵州茅台酒股份有限公司（公司简称）"),
    ("茅台酒", "贵州茅台生产的产品"),
    ("五粮液", "宜宾五粮液股份有限公司（公司简称）"),
    ("五粮液酒", "五粮液生产的产品"),
    ("白酒", "行业分类而非具体产品"),
)


def entity_type_for_mention(mention: str) -> str | None:
    """Return the fixed canonical entity type for a known mention.

    Duplicate or conflicting entries are treated as a terminology defect:
    the function raises ValueError instead of silently choosing one mapping.
    """

    matches = [sample_type for sample, sample_type in TERMINOLOGY_SAMPLES if sample == mention]
    if len(matches) > 1:
        raise ValueError(f"Terminology table maps {mention!r} to multiple entity types")
    return matches[0] if matches else None
