"""
Offer 捕手 - 简历生成服务
"""
from typing import Dict, List, Optional
from app.ai.llm_client import get_llm_client


class ResumeGenerator:
    """简历生成器 - 基于匹配结果和经历原子生成优化简历"""

    def __init__(self, llm_client=None):
        """初始化生成器"""
        self.llm_client = llm_client or get_llm_client()

    def generate(
        self,
        resume_data: Dict,
        job_data: Dict,
        match_result: Dict,
        atoms: Optional[List[Dict]] = None,
        missing_keywords: Optional[List[str]] = None
    ) -> Dict:
        """生成针对该JD优化的简历

        Args:
            resume_data: 原始简历数据
            job_data: 岗位数据
            match_result: 匹配结果
            atoms: 经历原子列表
            missing_keywords: 缺失的关键词

        Returns:
            优化后的简历数据
        """
        # 1. 生成个人简介（突出匹配的部分）
        summary = self._generate_summary(resume_data, job_data, match_result)

        # 2. 重新组织技能列表（优先展示匹配的技能）
        organized_skills = self._organize_skills(resume_data, job_data)

        # 3. 优化工作/项目经历描述
        enhanced_experience = self._enhance_experience(
            resume_data, job_data, atoms or []
        )

        # 4. 组装完整简历
        generated = {
            "basic_info": resume_data.get("basic_info", {}),
            "summary": summary,
            "skills": organized_skills,
            "experience": enhanced_experience.get("work", []),
            "projects": enhanced_experience.get("projects", []),
            "education": resume_data.get("education"),
            "target_keywords": job_data.get("requirements", {}).get("hard_skills", []),
            "optimization_notes": self._generate_optimization_notes(
                match_result, missing_keywords or []
            )
        }

        return generated

    def _generate_summary(
        self,
        resume_data: Dict,
        job_data: Dict,
        match_result: Dict
    ) -> str:
        """生成个人简介"""
        basic = resume_data.get("basic_info", {})
        job_req = job_data.get("requirements", {})

        # 提取匹配的技能
        matched_skills = []
        gaps = match_result.get("gaps", [])

        # 简单版生成简介
        summary_parts = [
            f"{basic.get('name', '')}，{basic.get('university', '')}{basic.get('major', '')}专业在读。"
        ]

        # 添加技能描述
        skills = resume_data.get("skills", [])[:3]
        if skills:
            summary_parts.append(f"熟练掌握{', '.join(skills)}等技术栈。")

        # 添加经验描述
        exp = resume_data.get("experience", [])
        if exp:
            summary_parts.append(f"曾在{exp[0].get('company', '')}等公司实习。")

        return " ".join(summary_parts)

    def _organize_skills(self, resume_data: Dict, job_data: Dict) -> List[str]:
        """重新组织技能列表"""
        resume_skills = resume_data.get("skills", [])
        job_skills = job_data.get("requirements", {}).get("hard_skills", [])

        # 分为匹配技能和其他技能
        matched = []
        others = []

        for skill in resume_skills:
            if any(job_skill.lower() in skill.lower() or skill.lower() in job_skill.lower()
                   for job_skill in job_skills):
                matched.append(skill)
            else:
                others.append(skill)

        # 匹配的技能放前面
        return matched + others

    def _enhance_experience(
        self,
        resume_data: Dict,
        job_data: Dict,
        atoms: List[Dict]
    ) -> Dict:
        """优化经历描述"""
        job_keywords = [kw.lower() for kw in job_data.get("requirements", {}).get("hard_skills", [])]

        result = {"work": [], "projects": []}

        # 优化工作经历
        for exp in resume_data.get("experience", []):
            enhanced = self._enhance_single_experience(
                exp, job_keywords, "work"
            )
            result["work"].append(enhanced)

        # 优化项目经历
        for proj in resume_data.get("projects", []):
            enhanced = self._enhance_single_experience(
                proj, job_keywords, "project"
            )
            result["projects"].append(enhanced)

        return result

    def _enhance_single_experience(
        self,
        experience: Dict,
        job_keywords: List[str],
        exp_type: str
    ) -> Dict:
        """优化单个经历描述"""
        enhanced = experience.copy()

        # 获取原始描述
        description = experience.get("description", "")
        tech_stack = experience.get("tech_stack", [])

        # 标记匹配的关键词
        highlighted_keywords = []
        for kw in job_keywords:
            if kw in description.lower() or \
               any(kw in ts.lower() for ts in tech_stack):
                highlighted_keywords.append(kw)

        # 添加高亮标记
        if highlighted_keywords:
            enhanced["highlighted_keywords"] = highlighted_keywords

        return enhanced

    def _generate_optimization_notes(
        self,
        match_result: Dict,
        missing_keywords: List[str]
    ) -> List[str]:
        """生成优化说明"""
        notes = []

        score = match_result.get("total_score", 0)
        if score >= 80:
            notes.append("[高度匹配] 你的背景与该职位高度匹配")
        elif score >= 60:
            notes.append("[基本匹配] 你的背景基本匹配，建议补充以下关键词")
        else:
            notes.append("[需加强] 匹配度较低，强烈建议补充以下内容")

        if missing_keywords:
            notes.extend([f"  - {kw}" for kw in missing_keywords[:5]])

        # 添加具体建议
        gaps = match_result.get("gaps", [])
        for gap in gaps[:3]:
            notes.append(f"[建议] {gap.get('suggestion', '')}")

        return notes

    def generate_with_llm(
        self,
        resume_data: Dict,
        job_data: Dict,
        match_result: Dict
    ) -> Dict:
        """使用LLM生成更优化的简历（调用API）

        Args:
            resume_data: 原始简历
            job_data: 岗位信息
            match_result: 匹配结果

        Returns:
            LLM生成的优化简历
        """
        # TODO: 实现LLM调用
        # 构建prompt，让LLM根据JD重写简历描述
        prompt = f"""
请根据以下岗位要求，优化简历描述：

【岗位要求】
职位：{job_data.get('position_name', '')}
公司：{job_data.get('company', '')}
硬技能：{', '.join(job_data.get('requirements', {}).get('hard_skills', []))}

【原始简历】
{resume_data}

【匹配分析】
匹配度：{match_result.get('total_score', 0)}分
差距：{match_result.get('gaps', [])}

请重写简历中的工作经历和项目描述，突出与岗位要求相关的技能和经验。
"""

        # 调用LLM
        # result = self.llm_client.call_json([{"role": "user", "content": prompt}])

        # 暂时返回基础生成结果
        return self.generate(resume_data, job_data, match_result)
