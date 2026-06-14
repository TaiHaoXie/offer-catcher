"""校招HR级筛选系统 - 真实大厂逻辑.

核心模块：
- UniversityTier: 学校层级数据库（清北/985/211/普本/海外）
- CompanyTier: 公司层级数据库（大厂/独角兽/创业公司）
- CampusScorer: 校招评分引擎
- ProjectAnalyzer: 项目质量分析
"""

from .university_tier import UniversityTier, get_university_tier
from .company_tier import CompanyTier, get_company_tier
from .campus_scorer import CampusRecruitScorer, CampusScore, get_campus_scorer
from .project_analyzer import ProjectAnalyzer, ProjectQuality, get_project_analyzer

__all__ = [
    "UniversityTier",
    "get_university_tier",
    "CompanyTier",
    "get_company_tier",
    "CampusRecruitScorer",
    "CampusScore",
    "get_campus_scorer",
    "ProjectAnalyzer",
    "ProjectQuality",
    "get_project_analyzer",
]
