"""学校层级数据库 - 真实大厂HR筛选逻辑.

中国高校层级：
- Tier 1 (清北): 清华、北大
- Tier 1.5 (华五): 复旦、上交、浙大、南大、中科大
- Tier 2 (985): 其他985高校
- Tier 2.5 (211): 211高校（非985）
- Tier 3 (普本): 普通一本
- Tier 4 (其他): 二本/三本/专科

海外高校层级：
- Tier 1 (顶尖): QS前50 / 常春藤 / 牛津剑桥
- Tier 2 (知名): QS前100
- Tier 3 (其他)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Set
import re

logger = __import__("logging").getLogger(__name__)


class UniversityTierLevel(Enum):
    """学校层级."""
    TIER_1_TOP = "清北"           # 清华、北大
    TIER_1_5_ELITE = "华五"       # 复旦、上交、浙大、南大、中科大
    TIER_2_985 = "985其他"        # 其他985
    TIER_2_5_211 = "211"         # 211（非985）
    TIER_3_REGULAR = "普本"       # 普通一本
    TIER_4_OTHER = "其他"         # 二本/三本/专科
    TIER_1_OVERSEAS = "海外顶尖"   # QS前50
    TIER_2_OVERSEAS = "海外知名"   # QS前100
    TIER_3_OVERSEAS = "海外其他"


@dataclass
class UniversityInfo:
    """学校信息."""
    name: str
    tier: UniversityTierLevel
    aliases: Set[str] = None
    is_985: bool = False
    is_211: bool = False
    is_double_first: bool = False  # 双一流

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = {self.name}


class UniversityTier:
    """学校层级数据库 - 大厂HR级."""

    # Tier 1: 清北
    TIER_1_TOP = {
        "清华大学",
        "北京大学",
        "Tsinghua University",
        "Peking University",
    }

    # Tier 1.5: 华五
    TIER_1_5_ELITE = {
        "复旦大学",
        "上海交通大学",
        "浙江大学",
        "南京大学",
        "中国科学技术大学",
        "Fudan University",
        "Shanghai Jiao Tong University",
        "Zhejiang University",
        "Nanjing University",
        "USTC",
        "中科大",
        "上交",
        "上交大",
    }

    # Tier 2: 其他985（除去清北华五）
    TIER_2_985 = {
        # 华中地区
        "华中科技大学", "武汉大学", "中南大学", "湖南大学", "国防科技大学",
        # 华南地区
        "中山大学", "华南理工大学",
        # 华东地区
        "同济大学", "华东师范大学", "厦门大学", "山东大学",
        # 华北地区
        "中国人民大学", "北京航空航天大学", "北京理工大学", "北京师范大学",
        "中国农业大学", "中央民族大学", "南开大学", "天津大学",
        "大连理工大学", "东北大学", "吉林大学",
        # 哈尔滨工业大学 (HIT)
        "哈尔滨工业大学",
        # 西北地区
        "西安交通大学", "西北工业大学", "电子科技大学", "四川大学", "重庆大学",
        # 西南地区
        "兰州大学",

        # 英文别名
        "HUST", "WHU", "CSU", "Hunan University", "NUDT",
        "SYSU", "SCUT",
        "Tongji University", "ECNU", "XMU", "SDU",
        "RUC", "BUAA", "BIT", "BNU", "CAU", "MUC", "NKU", "TJU",
        "DUT", "NEU", "JLU",
        "HIT", "Harbin Institute of Technology",
        "XJTU", "NPU", "UESTC", "SCU", "CQU",
        "LZU",
    }

    # Tier 2.5: 211（非985，部分重点211）
    TIER_2_5_211 = {
        # 部分重点211
        "北京科技大学", "北京邮电大学", "北京交通大学", "北京工业大学",
        "北京林业大学", "北京中医药大學", "北京外国语大学", "中国传媒大学",
        "中央财经大学", "对外经济贸易大学", "中国政法大学", "华北电力大学",
        "上海财经大学", "上海外国语大学", "华东理工大学", "东华大学",
        "南京航空航天大学", "南京理工大学", "河海大学", "南京师范大学",
        "苏州大学", "江南大学",
        "浙江大学宁波分校",
        "中国药科大学", "南京农业大学",
        "中国海洋大学", "中国石油大学", "武汉理工大学", "华中师范大学",
        "华中农业大学", "中南财经政法大学",
        "暨南大学", "华南师范大学", "华南农业大学",
        "大连海事大学", "东北师范大学", "东北农业大学",
        "哈尔滨工程大学",
        "西北大学", "西安电子科技大学", "长安大学",
        "陕西师范大学", "四川农业大学", "西南交通大学", "西南大学",
        "西南财经大学",

        # 英文别名
        "USTB", "BUPT", "BJTU", "BJUT",
        "BFU", "UCAS", "CUC",
        "UFC", "UIBE", "CUPL", "NCEPU",
        "SUFE", "SISU", "ECUST", "DHU",
        "NUAA", "NJUST", "HHU", "NJNU",
        "SUDA", "JNU",
        "CPU", "NJAU",
        "OUC", "UPC", "WUT", "CCNU",
        "HZAU", "ZUEL",
        "JNU", "SCNU", "SCAU",
        "DMU", "NENU", "NEAU",
        "HEU",
        "NWU", "Xidian", "CHD",
        "SNNU", "SICAU", "SWJTU", "SWU",
        "SWUFE",
    }

    # 海外顶尖院校（QS前50 / 常春藤 / 牛剑）
    TIER_1_OVERSEAS = {
        # 美国
        "MIT", "Stanford", "Harvard", "Caltech", "UC Berkeley", "Carnegie Mellon",
        "Princeton", "Yale", "Columbia", "Chicago", "UPenn", "Cornell",
        "麻省理工学院", "斯坦福大学", "哈佛大学", "加州理工学院", "加州大学伯克利分校",
        "卡内基梅隆大学", "普林斯顿大学", "耶鲁大学", "哥伦比亚大学", "芝加哥大学",
        "宾夕法尼亚大学", "康奈尔大学",
        # 英国
        "Oxford", "Cambridge", "Imperial College", "UCL", "LSE",
        "牛津大学", "剑桥大学", "帝国理工", "伦敦大学学院", "伦敦政经",
        # 新加坡
        "NUS", "NTU", "新加坡国立大学", "南洋理工大学",
        # 香港
        "HKU", "HKUST", "CUHK", "香港大学", "香港科技大学", "香港中文大学",
        # 澳洲
        "ANU", "墨尔本大学", "悉尼大学",
        # 日本
        "University of Tokyo", "东京大学",
        # 加拿大
        "University of Toronto", "McGill", "UBC", "多伦多大学", "麦吉尔大学",
        # 欧洲
        "ETH Zurich", "苏黎世联邦理工", "PSL", "索邦大学",
    }

    # 海外知名（QS前50-100）
    TIER_2_OVERSEAS = {
        "Duke", "Northwestern", "Michigan", "UCLA", "UCSD",
        "Georgia Tech", "UIUC", "Wisconsin", "Washington",
        "KCL", "Edinburgh", "Manchester", "Bristol", "Warwick",
        "墨尔本大学", "悉尼大学", "新南威尔士大学", "昆士兰大学",
        "早稻田大学", "京都大学", "大阪大学",
        "滑铁卢大学", "西安大略大学",
    }

    @classmethod
    def get_tier(cls, school_name: str) -> UniversityTierLevel:
        """获取学校层级."""
        if not school_name:
            return UniversityTierLevel.TIER_4_OTHER

        # 标准化输入
        name = school_name.strip()
        name_lower = name.lower()

        # 检查海外院校
        for overseas in cls.TIER_1_OVERSEAS:
            if name_lower in overseas.lower() or overseas.lower() in name_lower:
                return UniversityTierLevel.TIER_1_OVERSEAS

        for overseas in cls.TIER_2_OVERSEAS:
            if name_lower in overseas.lower() or overseas.lower() in name_lower:
                return UniversityTierLevel.TIER_2_OVERSEAS

        # 检查清北
        for top in cls.TIER_1_TOP:
            if name_lower in top.lower() or top.lower() in name_lower:
                return UniversityTierLevel.TIER_1_TOP

        # 检查华五
        for elite in cls.TIER_1_5_ELITE:
            if name_lower in elite.lower() or elite.lower() in name_lower:
                return UniversityTierLevel.TIER_1_5_ELITE

        # 检查985
        for uni985 in cls.TIER_2_985:
            if name_lower in uni985.lower() or uni985.lower() in name_lower:
                return UniversityTierLevel.TIER_2_985

        # 检查211
        for uni211 in cls.TIER_2_5_211:
            if name_lower in uni211.lower() or uni211.lower() in name_lower:
                return UniversityTierLevel.TIER_2_5_211

        # 默认返回普本
        return UniversityTierLevel.TIER_3_REGULAR

    @classmethod
    def get_tier_score(cls, tier: UniversityTierLevel) -> int:
        """获取层级分数（0-100）."""
        scores = {
            UniversityTierLevel.TIER_1_TOP: 100,
            UniversityTierLevel.TIER_1_5_ELITE: 95,
            UniversityTierLevel.TIER_2_985: 85,
            UniversityTierLevel.TIER_2_5_211: 75,
            UniversityTierLevel.TIER_3_REGULAR: 60,
            UniversityTierLevel.TIER_4_OTHER: 40,
            UniversityTierLevel.TIER_1_OVERSEAS: 100,
            UniversityTierLevel.TIER_2_OVERSEAS: 90,
            UniversityTierLevel.TIER_3_OVERSEAS: 70,
        }
        return scores.get(tier, 50)

    @classmethod
    def is_key_university(cls, school_name: str) -> bool:
        """是否是重点高校（985/211/海外顶尖）。"""
        tier = cls.get_tier(school_name)
        return tier in {
            UniversityTierLevel.TIER_1_TOP,
            UniversityTierLevel.TIER_1_5_ELITE,
            UniversityTierLevel.TIER_2_985,
            UniversityTierLevel.TIER_2_5_211,
            UniversityTierLevel.TIER_1_OVERSEAS,
        }


# 单例
_university_tier: Optional[UniversityTier] = None


def get_university_tier() -> UniversityTier:
    """获取学校层级数据库单例。"""
    global _university_tier
    if _university_tier is None:
        _university_tier = UniversityTier()
    return _university_tier
