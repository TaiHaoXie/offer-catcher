"""公司层级数据库 - 真实大厂HR筛选逻辑.

公司层级：
- Tier 1: 顶尖大厂（BAT/TMD + 字节跳动等）
- Tier 2: 知名大厂/独角兽
- Tier 3: 成熟创业公司
- Tier 4: 初创公司/其他
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Set

logger = __import__("logging").getLogger(__name__)


class CompanyTierLevel(Enum):
    """公司层级."""
    TIER_1_TOP = "顶尖大厂"         # BAT/TMD + 字节等
    TIER_2_MAJOR = "知名大厂"       # 其他大厂/知名外企
    TIER_3_UNICORN = "独角兽"       # 独角兽/准上市公司
    TIER_4_STARTUP = "创业公司"     # 初创公司
    TIER_5_OTHER = "其他"


@dataclass
class CompanyInfo:
    """公司信息."""
    name: str
    tier: CompanyTierLevel
    aliases: Set[str] = None
    industry: str = "互联网"  # 行业

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = {self.name}


class CompanyTier:
    """公司层级数据库 - 大厂HR级."""

    # Tier 1: 顶尖大厂（校招最认可）
    TIER_1_TOP = {
        # 国内巨头
        "字节跳动", "ByteDance", "抖音", "TikTok",
        "阿里巴巴", "Alibaba", "阿里", "淘宝", "天猫", "支付宝",
        "腾讯", "Tencent", "微信", "QQ",
        "百度", "Baidu",
        "美团", "Meituan", "美团点评",
        "拼多多", "PDD", "Pinduoduo",
        "京东", "JD.com", "JD",

        # 知名外企中国分部
        "Google", "谷歌",
        "Microsoft", "微软", "MS",
        "Apple", "苹果",
        "Meta", "Facebook", "脸书",
        "Amazon", "亚马逊", "AWS",
        "Netflix", "网飞",
    }

    # Tier 2: 知名大厂
    TIER_2_MAJOR = {
        # 国内知名互联网
        "网易", "NetEase",
        "小米", "Xiaomi",
        "华为", "Huawei",
        "蚂蚁集团", "Ant Group",
        "滴滴出行", "Didi",
        "快手", "Kuaishou",
        "哔哩哔哩", "Bilibili", "B站",
        "小红书", "Xiaohongshu",
        "携程", "Ctrip",
        "58同城", "58.com",
        "新浪", "Sina", "微博", "Weibo",

        # 知名外企
        "Oracle", "甲骨文",
        "IBM",
        "Intel", "英特尔",
        "NVIDIA", "英伟达",
        "Adobe",
        "SAP",
        "Salesforce",
        "Uber", "优步",
        "Airbnb",

        # 游戏大厂
        "腾讯游戏",
        "网易游戏",
        "米哈游", "miHoYo",
        "莉莉丝",
        "叠纸游戏",
        "趣加", "FunPlus",
    }

    # Tier 3: 独角兽/准上市
    TIER_3_UNICORN = {
        # 独角兽
        "大疆", "DJI",
        "商汤科技", "SenseTime",
        "旷视科技", "Megvii",
        "依图科技", "Yitu",
        "云知声",
        "寒武纪",
        "深兰科技",
        "第四范式",
        "出门问问",
        "优刻申", "UCloud",
        "青云", "QingCloud",

        # 准上市公司
        "得物", "POIZON",
        "SHEIN",
        "安克创新", "Anker",
        "石头科技", "Roborock",
        "九号公司", "Segway-Ninebot",
    }

    # Tier 4: 成熟创业公司
    TIER_4_STARTUP = {
        # A轮-C轮公司
        "知乎", "Zhihu",
        "喜马拉雅",
        "陆金所",
        "360数科",
        "乐信",
        "趣店",
        "拍拍贷",
        "找钢网",
        "满帮集团",
        "货拉拉",
        "快狗打车",
        "车好多",
        "瓜子二手车",
        "优信",
        "人人车",
    }

    @classmethod
    def get_tier(cls, company_name: str) -> CompanyTierLevel:
        """获取公司层级."""
        if not company_name:
            return CompanyTierLevel.TIER_5_OTHER

        name = company_name.strip()
        name_lower = name.lower()

        # 检查顶尖大厂
        for top in cls.TIER_1_TOP:
            if name_lower in top.lower() or top.lower() in name_lower:
                return CompanyTierLevel.TIER_1_TOP

        # 检查知名大厂
        for major in cls.TIER_2_MAJOR:
            if name_lower in major.lower() or major.lower() in name_lower:
                return CompanyTierLevel.TIER_2_MAJOR

        # 检查独角兽
        for unicorn in cls.TIER_3_UNICORN:
            if name_lower in unicorn.lower() or unicorn.lower() in name_lower:
                return CompanyTierLevel.TIER_3_UNICORN

        # 检查创业公司
        for startup in cls.TIER_4_STARTUP:
            if name_lower in startup.lower() or startup.lower() in name_lower:
                return CompanyTierLevel.TIER_4_STARTUP

        return CompanyTierLevel.TIER_5_OTHER

    @classmethod
    def get_tier_score(cls, tier: CompanyTierLevel) -> int:
        """获取层级分数（0-100）。"""
        scores = {
            CompanyTierLevel.TIER_1_TOP: 100,
            CompanyTierLevel.TIER_2_MAJOR: 85,
            CompanyTierLevel.TIER_3_UNICORN: 70,
            CompanyTierLevel.TIER_4_STARTUP: 50,
            CompanyTierLevel.TIER_5_OTHER: 30,
        }
        return scores.get(tier, 30)

    @classmethod
    def is_big_tech(cls, company_name: str) -> bool:
        """是否是大厂（Tier 1 + Tier 2）。"""
        tier = cls.get_tier(company_name)
        return tier in {CompanyTierLevel.TIER_1_TOP, CompanyTierLevel.TIER_2_MAJOR}


# 单例
_company_tier: Optional[CompanyTier] = None


def get_company_tier() -> CompanyTier:
    """获取公司层级数据库单例。"""
    global _company_tier
    if _company_tier is None:
        _company_tier = CompanyTier()
    return _company_tier
