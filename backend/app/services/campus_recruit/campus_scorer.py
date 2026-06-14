"""校招评分引擎 - 真实大厂HR筛选逻辑.

评分维度（权重根据真实校招流程调整）：
1. 学校层级 (25%): 清北 > 华五 > 985 > 211 > 普本
2. 学历 (15%): 博士 > 硕士 > 本科
3. 专业匹配 (10%): CS/软件工程 > 转专业
4. 实习经历 (20%): 大厂 > 独角兽 > 创业公司 > 无
5. 项目质量 (15%): 核心项目 > 课程作业
6. 技能基础 (10%): 数据结构/算法 + 编程语言
7. 成绩/奖项 (5%): GPA 3.5+ > 3.0+, 竞赛奖项
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional

from .university_tier import UniversityTier, UniversityTierLevel
from .company_tier import CompanyTier, CompanyTierLevel
from .project_analyzer import ProjectAnalyzer, ProjectQuality

logger = logging.getLogger(__name__)


@dataclass
class CampusScore:
    """校招评分结果."""
    total_score: int  # 总分 0-100
    grade: str  # 评级 S/A/B/C/D
    # 各维度得分
    university_score: int  # 学校层级分数
    degree_score: int  # 学历分数
    major_score: int  # 专业匹配分数
    internship_score: int  # 实习经历分数
    project_score: int  # 项目质量分数
    skill_score: int  # 技能基础分数
    achievement_score: int  # 成绩/奖项分数
    # 详情
    university_tier: str  # 学校层级描述
    degree_level: str  # 学历描述
    internship_companies: List[str]  # 实习公司列表
    top_projects: List[Dict]  # 最好的项目
    matched_skills: List[str]  # 匹配的技能
    missing_skills: List[str]  # 缺失的技能
    strengths: List[str]  # 优势
    weaknesses: List[str]  # 劣势
    recommendation: str  # 建议


class CampusRecruitScorer:
    """校招评分引擎 - 真实大厂HR级."""

    # 权重配置（根据真实校招流程）
    WEIGHTS = {
        "university": 0.25,    # 学校层级 25%
        "degree": 0.15,        # 学历 15%
        "major": 0.10,         # 专业匹配 10%
        "internship": 0.20,    # 实习经历 20%
        "project": 0.15,       # 项目质量 15%
        "skill": 0.10,         # 技能基础 10%
        "achievement": 0.05,   # 成绩/奖项 5%
    }

    # CS相关专业
    CS_MAJORS = {
        "计算机科学与技术", "软件工程", "计算机", "软件",
        "Computer Science", "CS", "Software Engineering",
        "人工智能", "AI", "Artificial Intelligence",
        "数据科学", "Data Science", "大数据",
        "信息安全", "Information Security",
        "网络工程", "Network Engineering",
        "电子工程", "Electrical Engineering", "EE",
        "电子信息", "Electronic Information",
    }

    # 基础技能要求（校招核心）
    BASE_SKILLS = {
        "编程语言": ["Python", "Java", "C++", "Go", "JavaScript", "TypeScript"],
        "数据结构": ["数据结构", "算法", "链表", "树", "图", "排序", "查找"],
        "数据库": ["MySQL", "PostgreSQL", "MongoDB", "Redis", "SQL"],
        "网络": ["HTTP", "TCP/IP", "网络协议"],
    }

    def __init__(self):
        """初始化评分器."""
        self.university_tier = UniversityTier()
        self.company_tier = CompanyTier()
        self.project_analyzer = ProjectAnalyzer()

    def score(self, resume: Dict, job: Optional[Dict] = None) -> CampusScore:
        """计算校招评分.

        Args:
            resume: 简历数据
            job: 岗位要求（可选）

        Returns:
            CampusScore
        """
        scores = {}
        details = {}

        # 1. 学校层级评分
        scores["university"], details["university_tier"] = self._score_university(resume)

        # 2. 学历评分
        scores["degree"], details["degree_level"] = self._score_degree(resume)

        # 3. 专业匹配评分
        scores["major"], details["major"] = self._score_major(resume)

        # 4. 实习经历评分
        scores["internship"], details["internship_companies"] = self._score_internship(resume)

        # 5. 项目质量评分
        scores["project"], details["top_projects"] = self._score_projects(resume)

        # 6. 技能基础评分
        scores["skill"], details["matched_skills"], details["missing_skills"] = self._score_skills(resume, job)

        # 7. 成绩/奖项评分
        scores["achievement"] = self._score_achievements(resume)

        # 计算总分
        total_score = int(sum(
            scores[k] * self.WEIGHTS[k]
            for k in self.WEIGHTS
        ))

        # 评级
        grade = self._get_grade(total_score)

        # 优势和劣势
        strengths, weaknesses = self._analyze_strengths(scores, details)

        # 建议
        recommendation = self._generate_recommendation(grade, strengths, weaknesses)

        return CampusScore(
            total_score=total_score,
            grade=grade,
            university_score=scores["university"],
            degree_score=scores["degree"],
            major_score=scores["major"],
            internship_score=scores["internship"],
            project_score=scores["project"],
            skill_score=scores["skill"],
            achievement_score=scores["achievement"],
            university_tier=details["university_tier"],
            degree_level=details["degree_level"],
            internship_companies=details["internship_companies"],
            top_projects=details["top_projects"],
            matched_skills=details.get("matched_skills", []),
            missing_skills=details.get("missing_skills", []),
            strengths=strengths,
            weaknesses=weaknesses,
            recommendation=recommendation,
        )

    def _score_university(self, resume: Dict) -> tuple:
        """评分学校层级."""
        education = resume.get("education", [])
        if not education:
            return 50, "未知"

        edu = education[0]
        school = edu.get("institution", "")

        tier = self.university_tier.get_tier(school)
        score = self.university_tier.get_tier_score(tier)

        return score, tier.value

    def _score_degree(self, resume: Dict) -> tuple:
        """评分学历."""
        education = resume.get("education", [])
        if not education:
            return 50, "未知"

        edu = education[0]
        degree = edu.get("degree", "")

        degree_lower = degree.lower()

        # 博士
        if "博士" in degree_lower or "phd" in degree_lower:
            return 100, "博士"

        # 硕士
        if "硕士" in degree_lower or "master" in degree_lower or "研究生" in degree_lower:
            return 85, "硕士"

        # 本科
        if "学士" in degree_lower or "本科" in degree_lower or "bachelor" in degree_lower:
            return 70, "本科"

        # 大专
        if "大专" in degree_lower or "专科" in degree_lower:
            return 40, "大专"

        return 50, "未知"

    def _score_major(self, resume: Dict) -> tuple:
        """评分专业匹配."""
        education = resume.get("education", [])
        if not education:
            return 50, ""

        edu = education[0]
        major = edu.get("field", "") or edu.get("major", "")
        if not major:
            return 50, ""

        major_lower = major.lower()

        # CS相关专业直接满分
        for cs_major in self.CS_MAJORS:
            if cs_major.lower() in major_lower or major_lower in cs_major.lower():
                return 100, cs_major

        # 相关专业（电子/数学等）
        related_keywords = ["电子", "通信", "数学", "物理", "自动化", "信息"]
        if any(kw in major for kw in related_keywords):
            return 70, major

        # 转专业/其他
        return 40, major

    def _score_internship(self, resume: Dict) -> tuple:
        """评分实习经历."""
        experiences = resume.get("workExperience", [])
        companies = []

        if not experiences:
            return 20, []  # 无实习经历低分

        total_score = 0
        max_score = 100
        valid_count = 0

        for exp in experiences:
            company = exp.get("company", "")
            if not company:
                continue

            # 跳过非实习
            title = exp.get("title", "")
            if "实习" not in title and "intern" not in title.lower():
                continue

            companies.append(company)
            valid_count += 1

            # 按公司层级评分
            tier = self.company_tier.get_tier(company)
            tier_score = self.company_tier.get_tier_score(tier)

            # 大厂实习加分更多
            if tier == CompanyTierLevel.TIER_1_TOP:
                total_score += 100
            elif tier == CompanyTierLevel.TIER_2_MAJOR:
                total_score += 85
            elif tier == CompanyTierLevel.TIER_3_UNICORN:
                total_score += 70
            else:
                total_score += 50

        # 最多取2份实习
        if valid_count > 2:
            total_score = int(total_score / valid_count * 2)

        return min(100, total_score), companies

    def _score_projects(self, resume: Dict) -> tuple:
        """评分项目质量."""
        projects = resume.get("personalProjects", [])
        if not projects:
            return 20, []

        project_scores = []
        for project in projects[:5]:  # 最多评估5个项目
            quality = self.project_analyzer.analyze(project)
            project_scores.append({
                "name": quality.name,
                "score": quality.overall_score,
                "complexity": quality.complexity.value,
            })

        # 按分数排序，取top 2
        project_scores.sort(key=lambda x: x["score"], reverse=True)
        top_projects = project_scores[:2]

        # 平均分
        avg_score = int(sum(p["score"] for p in top_projects) / len(top_projects)) if top_projects else 0

        return avg_score, top_projects

    def _score_skills(self, resume: Dict, job: Optional[Dict] = None) -> tuple:
        """评分技能基础."""
        # 提取简历技能
        summary = resume.get("summary", "")
        original = resume.get("original_markdown", "")
        text = f"{summary} {original}".lower()

        matched = []
        missing = []

        # 检查基础技能
        for category, skills in self.BASE_SKILLS.items():
            for skill in skills:
                if skill.lower() in text:
                    matched.append(skill)
                else:
                    missing.append(skill)

        # 计算匹配率
        total_skills = len(matched) + len(missing)
        if total_skills == 0:
            return 50, [], []

        match_rate = len(matched) / total_skills
        score = int(match_rate * 100)

        # 如果有JD，检查JD要求的技能
        if job:
            job_content = job.get("content", "").lower()
            jd_skills = []
            # 简单提取JD中的技能
            for skill in ["Python", "Java", "C++", "Go", "React", "Vue", "MySQL", "Redis"]:
                if skill.lower() in job_content:
                    jd_skills.append(skill)

            if jd_skills:
                jd_matched = sum(1 for s in jd_skills if s.lower() in text)
                score = int((jd_matched / len(jd_skills)) * 100)

        return score, matched, missing

    def _score_achievements(self, resume: Dict) -> int:
        """评分成绩/奖项."""
        summary = resume.get("summary", "")
        text = summary.lower()

        score = 50  # 基础分

        # GPA相关
        if "gpa" in text or "绩点" in text:
            # 尝试提取GPA
            import re
            gpa_match = re.search(r'gpa\s*[:：]?\s*([3-5]\.?\d*)', text)
            if gpa_match:
                gpa = float(gpa_match.group(1))
                if gpa >= 3.8:
                    score = 100
                elif gpa >= 3.5:
                    score = 85
                elif gpa >= 3.0:
                    score = 70
                else:
                    score = 50
            else:
                score = 70  # 有GPA说明但未提取到具体值

        # 奖学金
        if "奖学金" in text or "国家奖学金" in text:
            score = max(score, 85)
            if "国家奖学金" in text:
                score = 100

        # 竞赛奖项
        competitions = ["acm", "icpc", "数学建模", "kaggle", "挑战杯", "互联网+"]
        for comp in competitions:
            if comp in text:
                score = max(score, 90)
                if comp in ["acm", "icpc"] and "金奖" in text:
                    score = 100

        return score

    def _get_grade(self, score: int) -> str:
        """获取评级."""
        if score >= 85:
            return "S"
        elif score >= 75:
            return "A"
        elif score >= 60:
            return "B"
        elif score >= 45:
            return "C"
        else:
            return "D"

    def _analyze_strengths(self, scores: Dict, details: Dict) -> tuple:
        """分析优势和劣势."""
        strengths = []
        weaknesses = []

        # 学校优势
        if scores["university"] >= 95:
            strengths.append("顶尖名校背景")
        elif scores["university"] >= 85:
            strengths.append("985/211高校")
        elif scores["university"] < 60:
            weaknesses.append("学校层级一般")

        # 学历优势
        if scores["degree"] >= 85:
            strengths.append("硕士学历")
        elif scores["degree"] < 50:
            weaknesses.append("学历偏低")

        # 实习优势
        if scores["internship"] >= 85:
            strengths.append("大厂实习经历")
        elif scores["internship"] < 30:
            weaknesses.append("缺少实习经历")

        # 项目优势
        if scores["project"] >= 80:
            strengths.append("项目质量高")
        elif scores["project"] < 50:
            weaknesses.append("项目经验不足")

        # 技能优势
        if scores["skill"] >= 80:
            strengths.append("技能基础扎实")
        elif scores["skill"] < 50:
            weaknesses.append("技能基础薄弱")

        return strengths, weaknesses

    def _generate_recommendation(self, grade: str, strengths: List[str], weaknesses: List[str]) -> str:
        """生成建议."""
        if grade == "S":
            return "强烈推荐面试，候选人各方面优秀。"
        elif grade == "A":
            return "推荐面试，候选人条件良好。"
        elif grade == "B":
            return "可考虑面试，重点关注技能和项目深度。"
        elif grade == "C":
            return "谨慎考虑，建议技术面试进一步核实能力。"
        else:
            return "不推荐，继续寻找更合适的候选人。"


# 单例
_campus_scorer: Optional[CampusRecruitScorer] = None


def get_campus_scorer() -> CampusRecruitScorer:
    """获取校招评分器单例。"""
    global _campus_scorer
    if _campus_scorer is None:
        _campus_scorer = CampusRecruitScorer()
    return _campus_scorer
