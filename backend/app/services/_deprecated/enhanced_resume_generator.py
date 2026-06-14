"""
Offer 捕手 - 增强简历生成服务
"""
from typing import Dict, List, Optional


class EnhancedResumeGenerator:
    """增强简历生成器 - 提供真正有用的优化建议"""

    def __init__(self):
        """初始化生成器"""
        pass

    def generate(
        self,
        resume_data: Dict,
        job_data: Dict,
        match_result: Dict,
        atoms: Optional[List[Dict]] = None
    ) -> Dict:
        """生成针对该JD优化的简历"""

        basic_info = resume_data.get("basic_info", {})
        job_req = job_data.get("requirements", {})
        gaps = match_result.get("gaps", [])

        # 生成个人简介
        summary = self._create_summary(basic_info, job_data, resume_data)

        # 技能优化建议
        skills_analysis = self._analyze_skills(resume_data, job_req)

        # 经历优化建议
        experience_tips = self._generate_experience_tips(resume_data, job_req, gaps)

        # 关键词建议
        keyword_suggestions = self._suggest_keywords(resume_data, job_req, gaps)

        return {
            "basic_info": basic_info,
            "summary": summary,
            "original_skills": resume_data.get("skills", []),
            "skills_optimization": skills_analysis,
            "experience_tips": experience_tips,
            "keyword_suggestions": keyword_suggestions,
            "match_score": int(match_result.get("total_score", 0)),
            "target_keywords": job_req.get("hard_skills", []),
            "actionable_tips": self._generate_actionable_tips(gaps, job_req)
        }

    def _create_summary(self, basic_info: Dict, job_data: Dict, resume_data: Dict) -> str:
        """创建吸引人的个人简介"""
        name = basic_info.get("name", "求职者")
        university = basic_info.get("university", "")
        major = basic_info.get("major", "")
        degree = basic_info.get("degree", "")

        job_position = job_data.get("position_name", "目标岗位")

        # 构建简介
        summary = f"{name}，{university}{major}{degree}。\n\n"

        # 添加相关技能
        skills = resume_data.get("skills", [])[:4]
        if skills:
            summary += f"熟练掌握{', '.join(skills[:3])}等技能。\n\n"

        # 添加经历亮点
        exp = resume_data.get("experience", [])
        projects = resume_data.get("projects", [])

        if exp:
            latest_exp = exp[0] if exp else {}
            company = latest_exp.get("company", "")
            position = latest_exp.get("position", "")
            if company and position:
                summary += f"曾在{company}担任{position}，积累了实践经验。\n\n"

        if projects:
            summary += f"参与多个项目，包括{projects[0].get('name', projects[0].get('title', '相关项目'))}等。\n\n"

        summary += f"正在寻求{job_position}相关机会，期待为团队创造价值。"

        return summary

    def _analyze_skills(self, resume_data: Dict, job_req: Dict) -> Dict:
        """分析技能匹配情况"""
        resume_skills = [s.lower() for s in resume_data.get("skills", [])]
        required_skills = [s.lower() for s in job_req.get("hard_skills", [])]

        matched = []
        missing = []
        related = []

        for req_skill in required_skills:
            if any(req_skill in rs or rs in req_skill for rs in resume_skills):
                matched.append(req_skill)
            else:
                missing.append(req_skill)

        # 查找相关技能（部分匹配）
        for res_skill in resume_skills:
            if res_skill not in matched and res_skill not in missing:
                related.append(res_skill)

        return {
            "matched": list(set(matched)),
            "missing": list(set(missing)),
            "related": related[:5],
            "suggestions": self._generate_skill_suggestions(missing, resume_skills)
        }

    def _generate_skill_suggestions(self, missing: List, current: List) -> List:
        """生成技能补充建议"""
        suggestions = []

        skill_map = {
            "python": ["数据分析", "机器学习", "自动化"],
            "java": ["后端开发", "Spring框架", "微服务"],
            "javascript": ["前端开发", "Node.js", "全栈"],
            "产品经理": ["用户研究", "需求分析", "Axure", "SQL"],
            "数据分析": ["Excel高级", "数据可视化", "SQL"],
            "claude": ["Prompt工程", "AI应用", "LLM"]
        }

        for miss in missing:
            miss_lower = miss.lower()
            for key, values in skill_map.items():
                if key in miss_lower:
                    suggestions.extend(values)
                    break

        return list(set(suggestions))[:5]

    def _generate_experience_tips(self, resume_data: Dict, job_req: Dict, gaps: List) -> List:
        """生成经历优化建议"""
        tips = []

        exp = resume_data.get("experience", [])
        projects = resume_data.get("projects", [])

        if not exp and not projects:
            tips.append("[建议] 添加实习或项目经历，丰富实践经验")

        # 检查描述是否详细
        all_desc = []
        for e in exp:
            desc = e.get("description", "")
            if desc:
                all_desc.append(desc)

        total_desc_len = sum(len(d) for d in all_desc)
        if total_desc_len < 200:
            tips.append("[建议] 详细描述工作/项目中的具体职责和成果")

        # 检查是否有量化成果
        has_numbers = any(any(c.isdigit() for c in desc) for desc in all_desc)
        if not has_numbers:
            tips.append("[建议] 在经历描述中加入量化成果（如：提升效率30%）")

        # 根据JD给出建议
        required = job_req.get("hard_skills", [])
        if required:
            tips.append(f"[建议] 在经历描述中突出使用{required[:2]}等技能的场景")

        return tips[:5]

    def _suggest_keywords(self, resume_data: Dict, job_req: Dict, gaps: List) -> List:
        """生成关键词建议"""
        suggestions = []

        # 从差距中提取
        for gap in gaps[:5]:
            missing = gap.get("missing", "")
            if missing:
                suggestions.append({
                    "keyword": missing,
                    "reason": gap.get("suggestion", f"建议补充{missing}相关经验"),
                    "importance": gap.get("importance", "medium")
                })

        return suggestions

    def _generate_actionable_tips(self, gaps: List, job_req: Dict) -> List:
        """生成可执行的优化建议"""
        tips = []

        # 按重要性排序
        high_gaps = [g for g in gaps if g.get("importance") == "high"]
        medium_gaps = [g for g in gaps if g.get("importance") == "medium"]

        if high_gaps:
            tips.append({
                "priority": "high",
                "title": "优先补充核心技能",
                "actions": [f"学习并实践：{', '.join([g.get('missing', '') for g in high_gaps[:3]])}"]
            })

        # 技能提升建议
        required = job_req.get("hard_skills", [])
        if required:
            tips.append({
                "priority": "medium",
                "title": "技能提升路径",
                "actions": [
                    f"重点掌握：{', '.join(required[:3])}",
                    "通过项目实践验证技能水平"
                ]
            })

        # 简历优化建议
        tips.append({
            "priority": "low",
            "title": "简历呈现优化",
            "actions": [
                "使用STAR法则描述经历（情境-任务-行动-结果）",
                "量化工作成果（提升X%，完成Y项目）",
                "突出与岗位最相关的3-5个核心能力"
            ]
        })

        return tips
