"""Canonical chain taxonomy and company-name validation.

Maps the 177 report-extracted chain names to canonical parent chains, so the
sidebar shows ~60 primary chains instead of 177 overlapping names. Sub-chains
are preserved as tab-style filters within a parent.

Also provides company-name validation to filter out junk "company" names that
are actually sentence fragments extracted from report text.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Canonical chain hierarchy: every chain maps to a parent (possibly itself).
# ---------------------------------------------------------------------------

_GROUPS: dict[str, list[str]] = {
    "半导体": ["半导体材料", "半导体设备", "半导体设备零部件", "算力芯片", "存储"],
    "锂电池": ["锂电设备", "动力电池材料", "固态电池", "钠电池", "电池回收"],
    "光伏": [
        "光伏设备", "光伏银浆", "光伏逆变器", "光伏胶膜", "光伏电站",
        "光伏玻璃", "光伏接线盒", "光伏运维", "光伏支架",
    ],
    "风电": ["风电运维", "海上风电"],
    "医药生物": [
        "创新药", "化学原料药", "疫苗", "疫苗研发", "中药",
        "中药配方颗粒", "CXO", "CXO服务", "血液制品",
    ],
    "医疗器械": ["医疗器械国产化", "医疗器械创新"],
    "白酒": ["白酒渠道", "白酒包装"],
    "调味品": ["调味品渠道"],
    "乳品": ["乳制品"],
    "钢铁": ["钢铁新材料"],
    "造纸": ["造纸包装"],
    "汽车": [
        "新能源汽车", "汽车零部件", "汽车智能化", "智能驾驶",
        "汽车电子", "汽车热管理", "充电桩",
    ],
    "储能": ["储能电池"],
    "氢能": ["氢燃料电池"],
    "核电": ["核电设备"],
    "军工": ["军工电子"],
    "通信": ["通信模块"],
    "人工智能": ["AIGC应用"],
    "数据中心": ["数据中心液冷"],
    "化工": ["电子化学品", "塑料"],
    "美容护理": ["美妆", "医美"],
    "医疗服务": ["口腔", "康复医疗", "眼科"],
    "宠物经济": ["宠物"],
    "石油天然气": ["油服", "天然气设备"],
    "消费电子": ["消费电子代工", "手机产业链", "可穿戴"],
    "电力": ["火电", "水电", "绿电", "电网设备"],
    "传媒": ["数字媒体", "广告营销", "影视", "游戏", "出版"],
    "交通运输": ["公路", "铁路", "航运", "港口", "物流", "航空机场"],
    "食品饮料": ["休闲食品", "预制菜", "烘焙", "啤酒"],
    "建材": ["建筑建材", "水泥", "玻璃", "玻纤", "防水材料"],
    "有色金属": ["小金属", "新能源金属", "稀土永磁", "钛材"],
    "机械设备": ["工程机械"],
    "农业": ["生猪养殖"],
    "航空航天": ["航空材料"],
    "零售": ["跨境电商", "免税"],
    "教育": ["教育信息化"],
    "金融": ["银行", "保险", "券商", "支付"],
    "纺织服装": ["服装"],
}

# Chains that stay as their own parent (no sub-chains).
_STANDALONE: list[str] = [
    "家电", "计算机", "机器人", "信创", "宏观", "策略", "量化", "商品期货",
    "激光", "面板", "低空经济", "两轮车", "煤炭", "环保", "工业气体",
    "网络安全", "碳纤维", "卫星互联网", "区块链", "工业软件", "量子科技",
    "数据要素", "云计算", "房地产", "旅游酒店", "体育", "养老", "检测",
    "船舶", "电子烟", "珠宝", "眼镜", "家居", "印刷", "复合材料", "轮胎",
]

# Real policy/program names that these chain names can be benchmarked
# against.  They are references only; the extracted chain itself comes from
# the 721-report aggregation, not from an official chain list.
STANDARD_REFERENCES: dict[str, str] = {
    "半导体": "国务院《新时期促进集成电路产业和软件产业高质量发展的若干政策》（国发〔2020〕8号）与工信部重点产业链清单",
    "锂电池": "工信部《锂离子电池行业规范条件》及国务院办公厅《新能源汽车产业发展规划（2021—2035年）》",
    "光伏": "国家发改委、国家能源局《“十四五”可再生能源发展规划》与工信部《光伏制造行业规范条件》",
    "风电": "国家发改委、国家能源局《“十四五”可再生能源发展规划》",
    "储能": "国家发改委、国家能源局《关于加快推动新型储能发展的指导意见》（2021年）",
    "氢能": "国家发改委、国家能源局《氢能产业发展中长期规划（2021—2035年）》",
    "核电": "《“十四五”现代能源体系规划》及国家能源局核电中长期发展安排",
    "汽车": "国务院办公厅《新能源汽车产业发展规划（2021—2035年）》及工信部汽车产业政策",
    "电力": "国家发改委、国家能源局《“十四五”现代能源体系规划》",
    "石油天然气": "国家发改委、国家能源局《“十四五”现代能源体系规划》",
    "煤炭": "国家能源局煤炭行业规划与煤炭保供政策",
    "医药生物": "国家药监局、国家医保局行业管理及证监会行业分类（医药制造业）",
    "医疗器械": "国家药监局《医疗器械分类目录》（2017年版）",
    "医疗服务": "国家卫健委医疗机构与医疗服务行业管理",
    "人工智能": "国务院《新一代人工智能发展规划》（国发〔2017〕35号）",
    "数据中心": "工信部《新型数据中心发展三年行动计划（2021—2023年）》",
    "通信": "工信部信息通信行业发展规划",
    "卫星互联网": "国家发改委将卫星互联网纳入新型基础设施建设的相关部署",
    "区块链": "工信部、中央网信办《关于加快推动区块链技术应用和产业发展的指导意见》（2021年）",
    "量子科技": "“十四五”规划纲要关于加快布局量子科技等前沿领域的部署",
    "网络安全": "《网络安全法》《数据安全法》及网信办相关监管框架",
    "信创": "工信部信息技术应用创新（信创）产业政策",
    "工业软件": "工信部《“十四五”智能制造发展规划》及工业软件相关政策",
    "云计算": "工信部云计算发展三年行动计划",
    "数据要素": "中共中央、国务院《关于构建数据基础制度更好发挥数据要素作用的意见》（2022年）",
    "机器人": "工信部等十五部门《“十四五”机器人产业发展规划》",
    "低空经济": "2024年政府工作报告关于发展低空经济的部署及工信部等《通用航空装备创新应用实施方案（2024—2030年）》",
    "航空航天": "工信部、国防科工局航空装备与航天产业政策",
    "船舶": "工信部船舶工业与绿色智能船舶相关政策",
    "机械设备": "工信部等八部门《“十四五”智能制造发展规划》",
    "工程机械": "工信部装备制造业相关政策（归入机械设备）",
    "激光": "“十四五”国家重点研发计划激光制造与增材制造专项",
    "工业气体": "应急管理部危险化学品管理及气体行业标准",
    "化工": "国家统计局《国民经济行业分类》（GB/T 4754-2017）化学原料和化学制品制造业",
    "建材": "国家统计局《国民经济行业分类》（GB/T 4754-2017）非金属矿物制品业及《“十四五”原材料工业发展规划》",
    "钢铁": "国家统计局《国民经济行业分类》（GB/T 4754-2017）黑色金属冶炼和压延加工业",
    "有色金属": "国家统计局《国民经济行业分类》（GB/T 4754-2017）有色金属冶炼和压延加工业及《稀土管理条例》",
    "复合材料": "工信部《“十四五”原材料工业发展规划》新材料相关部署",
    "碳纤维": "工信部《“十四五”原材料工业发展规划》新材料相关部署",
    "纺织服装": "工信部《关于推动轻工业高质量发展的指导意见》及纺织工业规划",
    "家电": "工信部轻工业高质量发展相关政策",
    "家居": "工信部轻工业高质量发展相关政策",
    "珠宝": "市场监管总局珠宝玉石国家标准及轻工业行业管理",
    "眼镜": "市场监管总局眼镜产品标准及药监局医疗器械管理（隐形眼镜）",
    "美容护理": "国家药监局《化妆品监督管理条例》（2021年施行）",
    "食品饮料": "市场监管总局《食品生产许可分类目录》",
    "白酒": "市场监管总局《白酒工业术语》（GB/T 17204-2021）",
    "啤酒": "市场监管总局啤酒产品国家标准",
    "调味品": "市场监管总局《食品生产许可分类目录》调味品类别",
    "乳品": "市场监管总局《食品生产许可分类目录》乳制品类别",
    "预制菜": "市场监管总局等六部门《关于加强预制菜食品安全监管 促进产业高质量发展的通知》（2024年）",
    "农业": "国家统计局《国民经济行业分类》（GB/T 4754-2017）农林牧渔业",
    "环保": "生态环境部环保产业分类与污染治理政策",
    "检测": "市场监管总局（国家认监委）检验检测行业监管",
    "教育": "教育部及国家统计局《国民经济行业分类》（GB/T 4754-2017）教育门类",
    "体育": "国务院《全民健身计划（2021—2025年）》及体育产业政策",
    "养老": "国务院《“十四五”国家老龄事业发展和养老服务体系规划》",
    "旅游酒店": "文化和旅游部《“十四五”文化和旅游发展规划》及住宿业分类",
    "零售": "商务部商贸流通业与跨境电商综合试验区政策",
    "物流": "国家发改委《“十四五”现代物流发展规划》",
    "交通运输": "交通运输部综合交通运输规划",
    "房地产": "住房和城乡建设部房地产业监管及国家统计局行业分类（K70）",
    "金融": "中国人民银行、金融监管总局、证监会金融业监管框架",
    "商品期货": "证监会期货市场法律法规（属于金融/大宗商品主题，非政府标准产业链）",
    "量化": "研究交易主题，非政府标准产业链名称",
    "策略": "研究主题，非政府标准产业链名称",
    "宏观": "宏观经济研究主题，非政府标准产业链名称",
    "面板": "工信部电子信息制造业规划（显示产业）",
    "消费电子": "工信部电子信息制造业规划",
    "电子烟": "国家烟草专卖局《电子烟管理办法》及强制性国标GB 41700-2022",
    "两轮车": "市场监管总局电动自行车强制性国标GB 17761-2018",
    "宠物经济": "农业农村部宠物饲料管理及宠物行业相关标准",
    "数字媒体": "国家新闻出版署、中央网信办数字内容监管（归入传媒）",
    "传媒": "国家新闻出版署、国家广电总局、中央网信办行业监管",
    "出版": "国家新闻出版署出版业管理",
    "游戏": "国家新闻出版署游戏版号与未成年人保护监管",
    "影视": "国家电影局、国家广电总局行业监管",
    "广告营销": "市场监管总局《广告法》及广告行业监管",
    "印刷": "国家新闻出版署印刷业管理",
    "造纸": "国家发改委《“十四五”循环经济发展规划》及轻工业规划",
    "塑料": "国家发改委《“十四五”循环经济发展规划》塑料污染治理及化工行业管理",
    "轮胎": "工信部轮胎行业规范条件",
    "军工": "国防科工局军工行业管理",
    "电池回收": "工信部等《新能源汽车动力蓄电池回收利用管理暂行办法》",
    "充电桩": "国务院办公厅《关于进一步构建高质量充电基础设施体系的指导意见》（2023年）",
}


def _build_canonical_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for parent, children in _GROUPS.items():
        mapping.setdefault(parent, parent)
        for child in children:
            mapping[child] = parent
    for name in _STANDALONE:
        mapping.setdefault(name, name)
    return mapping


CANONICAL_CHAIN_MAP: dict[str, str] = _build_canonical_map()


def canonical_chain(name: str) -> str:
    """Return the canonical parent chain for *name*, or *name* itself."""
    key = (name or "").strip()
    return CANONICAL_CHAIN_MAP.get(key, key)


def get_sub_chains(parent: str) -> list[str]:
    """Return the sub-chain names for a canonical parent."""
    return [c for c, p in CANONICAL_CHAIN_MAP.items() if p == parent and c != parent]


def get_canonical_parents() -> list[str]:
    """Return the sorted list of all canonical parent chain names."""
    return sorted(set(CANONICAL_CHAIN_MAP.values()))


# ---------------------------------------------------------------------------
# Company-name validation
# ---------------------------------------------------------------------------

_INVALID_PREFIXES: tuple[str, ...] = (
    "的", "为", "前", "由", "年", "是", "将", "对", "在", "有", "与",
    "及其", "截至", "公司于", "前身为", "经", "后", "曾",
    "通过", "目前", "同时", "其中", "包括", "以及", "并且",
    "是中国", "是国内", "是一家", "该公司", "本部", "总部位于",
    "系", "已", "曾用", "原名", "更名", "改制", "成立", "设立",
    "隶属于", "属于", "拥有", "持有", "投资", "收购", "合并",
    "随着", "基于", "根据", "按照", "依据",
)

_JUNK_REGEX = re.compile(
    r"(改制|成立|更名|前身为|由.*集团|年.*股份|"
    r"是.*的|有.*的|为.*的|在.*的|"
    r"公司于|系.*公司|曾用名|原名)"
)

_LEADING_JUNK: tuple[str, ...] = (
    "年整体改制为", "整体改制为", "改制为", "前身为", "曾用名", "原名", "更名",
    "公司于", "公司前身", "该公司", "其旗下", "旗下", "总部位于", "总部", "本部",
    "位于", "隶属于", "属于", "控股股东", "第一大股东", "实际控制人", "实控人",
    "创始人", "董事长", "总经理", "总裁", "管理层",
    "截至", "目前", "当前", "未来", "近年", "近年来", "其中", "包括", "以及",
    "并且", "同时", "此外", "另外", "是中国", "是国内", "是一家",
    "通过", "依托", "借助", "围绕", "基于", "根据", "按照", "依据", "随着",
    "持有", "拥有", "投资", "收购", "并购", "合并", "成立", "设立", "注册",
    "海外", "业内", "行业", "全球", "国际", "世界", "知名", "著名", "优秀",
    "领先", "大型", "龙头", "主要", "其中", "如", "像", "例如", "比如",
    "生产", "制造", "有", "是", "为", "由", "与", "并", "及", "和", "等",
    "从", "向", "以", "对", "在", "将", "已", "曾", "经", "后", "前",
    "年", "月", "日", "的", "之", "于", "公司",
)

_TRAILING_JUNK: tuple[str, ...] = (
    "等龙头企业", "等龙头", "龙头", "等企业", "等公司", "公司等",
    "等厂商", "等", "企业", "厂商", "标的",
)

_SUFFIX_CORE = re.compile(
    r"([\u4e00-\u9fff]{2,12}(?:股份有限公司|有限责任公司|集团有限公司|"
    r"股份公司|有限公司|控股集团|控股公司|集团公司|"
    r"公司|集团|控股|股份))$"
)


def _strip_leading_junk(text: str) -> str:
    previous = ""
    while text and text != previous:
        previous = text
        for prefix in _LEADING_JUNK:
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip("，。、；：·•-–— \t")
                break
    return text


def _strip_trailing_junk(text: str) -> str:
    previous = ""
    while text and text != previous:
        previous = text
        for suffix in _TRAILING_JUNK:
            if text.endswith(suffix):
                text = text[: -len(suffix)].rstrip("，。、；：·•-–— \t")
                break
    return text


def is_valid_company_name(name: str) -> bool:
    """Return True if *name* looks like a real company name, not a fragment."""
    if not name or not name.strip():
        return False
    text = name.strip()
    if len(text) < 2 or len(text) > 24:
        return False
    for prefix in _INVALID_PREFIXES:
        if text.startswith(prefix):
            return False
    if _JUNK_REGEX.search(text):
        return False
    if text.endswith(("等", "等企业", "等公司", "等龙头", "等厂商")):
        return False
    sentence_chars = sum(1 for c in text if c in "的了是在和与对为年")
    if sentence_chars >= 2 and len(text) <= 8:
        return False
    if re.match(r"^\d", text) and not re.match(r"^\d{5,6}$", text):
        return False
    return True


def clean_company_name(name: str) -> str:
    """Attempt to extract a clean company name from a fragment.

    Returns empty string if unrecoverable.  Valid names pass through
    unchanged; sentence fragments get their leading/trailing junk stripped
    and, when possible, a company core is recovered from the tail.
    """
    if not name:
        return ""
    text = name.strip()
    if is_valid_company_name(text):
        return text
    text = _strip_leading_junk(text)
    text = _strip_trailing_junk(text)
    if is_valid_company_name(text):
        return text
    match = _SUFFIX_CORE.search(text)
    if match:
        candidate = _strip_leading_junk(match.group(1))
        candidate = _strip_trailing_junk(candidate)
        if is_valid_company_name(candidate):
            return candidate
    return ""


INVALID_NAME_PREFIXES: tuple[str, ...] = _INVALID_PREFIXES
