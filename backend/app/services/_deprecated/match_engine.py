"""
Offer 捕手 - 匹配计算引擎
"""
from typing import Dict, List, Set, Optional
from app.models import MatchResult, MatchBreakdown, GapItem, KeywordCoverage, JDKeyword, EnhancedMatchResult


class MatchEngine:
    """匹配计算引擎"""

    def __init__(self):
        """初始化引擎"""
        # 匹配权重配置
        self.weights = {
            "hard_skills": 0.40,    # 硬技能 40%
            "soft_skills": 0.20,   # 软技能 20%
            "education": 0.15,     # 教育背景 15%
            "experience": 0.15,    # 经验匹配 15%
            "projects": 0.10       # 项目相关性 10%
        }

        # 大厂名单
        self.big_companies = [
            "字节", "抖音", "今日头条",
            "阿里", "淘宝", "支付宝", "蚂蚁", "高德",
            "腾讯", "微信", "QQ",
            "百度",
            "美团", "大众点评",
            "京东",
            "网易", "有道",
            "小米",
            "华为",
            "微软", "Microsoft",
            "谷歌", "Google",
            "苹果", "Apple",
            "亚马逊", "Amazon",
            "Meta", "Facebook"
        ]

    def calculate(self, resume_data: Dict, job_data: Dict) -> MatchResult:
        """计算匹配度"""

        # 1. 硬技能匹配度
        hard_skill_score, hard_gaps = self._calculate_hard_skill_match(
            resume_data, job_data
        )

        # 2. 软技能匹配度
        soft_skill_score, soft_gaps = self._calculate_soft_skill_match(
            resume_data, job_data
        )

        # 3. 教育背景匹配度
        education_score, edu_gaps = self._calculate_education_match(
            resume_data, job_data
        )

        # 4. 经验匹配度
        experience_score, exp_gaps = self._calculate_experience_match(
            resume_data, job_data
        )

        # 5. 项目相关性
        project_score, proj_gaps = self._calculate_project_match(
            resume_data, job_data
        )

        # 计算总分
        total_score = (
            hard_skill_score * self.weights["hard_skills"] +
            soft_skill_score * self.weights["soft_skills"] +
            education_score * self.weights["education"] +
            experience_score * self.weights["experience"] +
            project_score * self.weights["projects"]
        )

        # 汇总所有差距
        all_gaps = hard_gaps + soft_gaps + edu_gaps + exp_gaps + proj_gaps

        return MatchResult(
            total_score=round(total_score, 1),
            breakdown=MatchBreakdown(
                hard_skills=round(hard_skill_score, 1),
                soft_skills=round(soft_skill_score, 1),
                education=round(education_score, 1),
                experience=round(experience_score, 1),
                projects=round(project_score, 1)
            ),
            gaps=[GapItem(**gap) for gap in all_gaps]
        )

    def _calculate_hard_skill_match(self, resume: Dict, job: Dict) -> tuple:
        """计算硬技能匹配度"""
        resume_skills = set([s.lower().strip() for s in resume.get("skills", [])])
        job_skills = set([s.lower().strip() for s in job.get("requirements", {}).get("hard_skills", [])])

        if not job_skills:
            return 70.0, []  # 没有技能要求，给基础分

        # 找出匹配的技能
        matched = resume_skills & job_skills
        # 找出缺失的技能
        missing = job_skills - resume_skills

        score = len(matched) / len(job_skills) * 100

        # 生成差距项
        gaps = []
        for skill in missing:
            gaps.append({
                "type": "hard_skill",
                "missing": skill,
                "importance": "high",
                "suggestion": f"建议补充{skill}相关经验"
            })

        return score, gaps

    def _calculate_soft_skill_match(self, resume: Dict, job: Dict) -> tuple:
        """计算软技能匹配度"""
        # 从简历文本中提取软技能关键词
        resume_text = self._get_resume_text(resume)
        job_soft_skills = job.get("requirements", {}).get("soft_skills", [])

        if not job_soft_skills:
            return 70.0, []

        matched_count = 0
        gaps = []

        for skill in job_soft_skills:
            # 软技能关键词匹配（宽松匹配）
            keywords = [skill.lower(), skill.replace("能力", "").replace("精神", "")]
            if any(kw in resume_text.lower() for kw in keywords):
                matched_count += 1
            else:
                gaps.append({
                    "type": "soft_skill",
                    "missing": skill,
                    "importance": "medium",
                    "suggestion": f"在项目描述中体现{skill}相关经历"
                })

        score = matched_count / len(job_soft_skills) * 100 if job_soft_skills else 70.0

        return score, gaps

    def _calculate_education_match(self, resume: Dict, job: Dict) -> tuple:
        """计算教育背景匹配度"""
        edu_requirement = job.get("requirements", {}).get("education", "")
        resume_edu = resume.get("basic_info", {})
        resume_degree = resume_edu.get("degree", "")
        resume_major = resume_edu.get("major", "")

        score = 60.0  # 基础分
        gaps = []

        # 学历匹配
        if "博士" in edu_requirement:
            if "博士" in resume_degree:
                score = 100.0
            elif "硕士" in resume_degree:
                score = 80.0
            else:
                score = 60.0
                gaps.append({
                    "type": "education",
                    "missing": "博士学历",
                    "importance": "high",
                    "suggestion": "可通过科研成果或高质量项目弥补"
                })

        elif "硕士" in edu_requirement:
            if resume_degree in ["硕士", "博士"]:
                score = 100.0
            else:
                score = 75.0
                gaps.append({
                    "type": "education",
                    "missing": "硕士学历",
                    "importance": "medium",
                    "suggestion": "可通过实习或项目经验弥补"
                })

        elif "本科" in edu_requirement:
            if resume_degree in ["本科", "硕士", "博士"]:
                score = 100.0

        # 专业匹配（加分）
        if "计算机" in edu_requirement or "软件" in edu_requirement:
            if any(tech in resume_major for tech in ["计算机", "软件", "人工智能", "数据科学"]):
                score = min(score + 10, 100.0)

        return score, gaps

    def _calculate_experience_match(self, resume: Dict, job: Dict) -> tuple:
        """计算经验匹配度"""
        exp_requirement = job.get("requirements", {}).get("experience", "")
        experiences = resume.get("experience", [])

        score = 50.0  # 基础分
        gaps = []

        # 有实习经验加分
        if experiences:
            score += 30.0
        else:
            gaps.append({
                "type": "experience",
                "missing": "实习经验",
                "importance": "high",
                "suggestion": "建议补充相关实习或项目经历"
            })

        # 大厂经验加分
        has_big_company = False
        for exp in experiences:
            company = exp.get("company", "")
            if any(bc in company for bc in self.big_companies):
                has_big_company = True
                break

        if has_big_company:
            score += 20.0
        elif "大厂" in exp_requirement or "知名企业" in exp_requirement:
            gaps.append({
                "type": "experience",
                "missing": "大厂实习经验",
                "importance": "medium",
                "suggestion": "可通过高质量项目或竞赛获奖弥补"
            })

        return min(score, 100.0), gaps

    def _calculate_project_match(self, resume: Dict, job: Dict) -> tuple:
        """计算项目相关性"""
        projects = resume.get("projects", [])
        job_skills = set([s.lower() for s in job.get("requirements", {}).get("hard_skills", [])])

        if not projects:
            if job_skills:
                return 40.0, [{
                    "type": "project",
                    "missing": "相关项目经验",
                    "importance": "high",
                    "suggestion": "建议补充相关领域项目经历"
                }]
            return 60.0, []

        total_relevance = 0.0
        gaps = []

        for project in projects:
            tech_stack = set([s.lower() for s in project.get("tech_stack", [])])
            desc = project.get("description", "").lower()

            # 技术栈匹配
            matched = tech_stack & job_skills
            if job_skills:
                relevance = len(matched) / len(job_skills) * 100
            else:
                relevance = 70.0

            total_relevance += relevance

        avg_relevance = total_relevance / len(projects) if projects else 60.0

        # 如果项目相关性低，添加建议
        if avg_relevance < 50:
            gaps.append({
                "type": "project",
                "missing": "相关技术栈项目",
                "importance": "medium",
                "suggestion": "建议使用岗位要求的技术栈完成项目"
            })

        return min(avg_relevance, 100.0), gaps

    def _get_resume_text(self, resume: Dict) -> str:
        """获取简历的完整文本"""
        parts = []

        # 基本信息
        basic = resume.get("basic_info", {})
        parts.extend([basic.get("name", ""), basic.get("university", ""), basic.get("major", "")])

        # 技能
        skills = resume.get("skills", [])
        parts.extend(skills)

        # 经历描述
        for exp in resume.get("experience", []):
            parts.append(exp.get("description", ""))

        # 项目描述
        for proj in resume.get("projects", []):
            parts.append(proj.get("description", ""))

        return " ".join(parts)

    def calculate_keyword_coverage(
        self,
        resume_data: Dict,
        job_keywords: List[JDKeyword],
        atoms: Optional[List[Dict]] = None
    ) -> Dict:
        """计算关键词覆盖率

        Args:
            resume_data: 简历数据
            job_keywords: JD关键词列表
            atoms: 经历原子列表（可选）

        Returns:
            包含覆盖率、已覆盖和未覆盖关键词的字典
        """
        # 获取简历中的所有文本
        resume_text = self._get_resume_text(resume_data).lower()

        # 如果有经历原子，也提取其中的关键词
        if atoms:
            for atom in atoms:
                resume_text += " " + atom.get("description", "").lower()
                resume_text += " " + " ".join(atom.get("skills", [])).lower()
                resume_text += " " + " ".join(atom.get("keywords", [])).lower()

        covered = []
        missing = []

        for kw in job_keywords:
            keyword = kw.keyword.lower()
            is_covered = keyword in resume_text

            # 查找来源
            source = ""
            if is_covered and atoms:
                for atom in atoms:
                    if keyword in atom.get("description", "").lower() or \
                       keyword in " ".join(atom.get("skills", [])).lower():
                        source = atom.get("title", "")
                        break

            coverage_item = KeywordCoverage(
                keyword=kw.keyword,
                weight=kw.weight,
                covered=is_covered,
                source=source
            )

            if is_covered:
                covered.append(coverage_item)
            else:
                missing.append(kw)

        # 计算加权覆盖率
        total_weight = sum(kw.weight for kw in job_keywords) if job_keywords else 1
        covered_weight = sum(kw.weight for kw in covered if isinstance(kw, KeywordCoverage))

        coverage_rate = covered_weight / total_weight * 100 if total_weight > 0 else 0

        return {
            "coverage_rate": round(coverage_rate, 1),
            "covered": covered,
            "missing": missing,
            "total_keywords": len(job_keywords),
            "covered_count": len(covered)
        }

    def extract_keywords_from_jd(self, job_data: Dict) -> List[JDKeyword]:
        """从JD数据中提取带权重的关键词

        Args:
            job_data: 岗位数据

        Returns:
            关键词列表
        """
        keywords = []

        # 从硬技能提取
        requirements = job_data.get("requirements", {})
        for skill in requirements.get("hard_skills", []):
            keywords.append(JDKeyword(
                keyword=skill,
                weight=3.0,  # 硬技能权重高
                category="skill"
            ))

        # 从软技能提取
        for skill in requirements.get("soft_skills", []):
            keywords.append(JDKeyword(
                keyword=skill,
                weight=1.5,
                category="soft_skill"
            ))

        # 从经验要求提取关键词
        exp_req = requirements.get("experience", "")
        if "实习" in exp_req:
            keywords.append(JDKeyword(keyword="实习经验", weight=2.0, category="experience"))
        if "项目" in exp_req:
            keywords.append(JDKeyword(keyword="项目经验", weight=2.0, category="experience"))

        # 从加分项提取
        for pref in requirements.get("preferred", []):
            keywords.append(JDKeyword(
                keyword=pref,
                weight=1.0,
                category="preferred"
            ))

        return keywords
