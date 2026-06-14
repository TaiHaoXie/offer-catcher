"""
Offer 捕手 - 优化建议生成服务
"""
from typing import Dict
from app.models import OptimizationSuggestions, SuggestionItem


class Optimizer:
    """优化建议生成器"""

    def __init__(self, llm_client):
        """初始化优化器"""
        self.llm_client = llm_client

    def generate(
        self,
        match_result: Dict,
        resume_data: Dict,
        job_data: Dict
    ) -> OptimizationSuggestions:
        """生成优化建议"""

        # 构建差距分析文本
        gaps_analysis = self._build_gaps_analysis(match_result)

        # 构建简历摘要
        resume_snippet = self._build_resume_snippet(resume_data)

        # 构建JD摘要
        jd_snippet = self._build_jd_snippet(job_data)

        # 调用LLM生成建议
        try:
            result = self.llm_client.generate_optimization(
                gaps_analysis=gaps_analysis,
                resume_snippet=resume_snippet,
                jd_snippet=jd_snippet
            )

            suggestions = []
            for s in result.get("suggestions", []):
                suggestions.append(SuggestionItem(**s))

            return OptimizationSuggestions(suggestions=suggestions)

        except Exception as e:
            # 如果LLM调用失败，使用规则生成建议
            return self._generate_rule_based_suggestions(match_result, resume_data, job_data)

    def _build_gaps_analysis(self, match_result: Dict) -> str:
        """构建差距分析文本"""
        lines = ["=== 差距分析 ==="]

        # 总分
        total_score = match_result.get("total_score", 0)
        lines.append(f"总匹配度: {total_score}分")

        # 细分
        breakdown = match_result.get("breakdown", {})
        lines.append("\n各维度得分:")
        lines.append(f"- 硬技能: {breakdown.get('hard_skills', 0)}%")
        lines.append(f"- 软技能: {breakdown.get('soft_skills', 0)}%")
        lines.append(f"- 教育背景: {breakdown.get('education', 0)}%")
        lines.append(f"- 经验匹配: {breakdown.get('experience', 0)}%")
        lines.append(f"- 项目相关: {breakdown.get('projects', 0)}%")

        # 差距项
        gaps = match_result.get("gaps", [])
        if gaps:
            lines.append("\n主要差距:")
            for gap in gaps:
                lines.append(f"- [{gap.get('importance', 'medium')}] {gap.get('type', '')}: {gap.get('missing', '')}")
                lines.append(f"  建议: {gap.get('suggestion', '')}")

        return "\n".join(lines)

    def _build_resume_snippet(self, resume_data: Dict) -> str:
        """构建简历摘要"""
        lines = ["=== 简历摘要 ==="]

        # 基本信息
        basic = resume_data.get("basic_info", {})
        lines.append(f"姓名: {basic.get('name', '')}")
        lines.append(f"学校: {basic.get('university', '')} | 专业: {basic.get('major', '')} | 学历: {basic.get('degree', '')}")

        # 技能
        skills = resume_data.get("skills", [])
        if skills:
            lines.append(f"\n技能: {', '.join(skills[:10])}")

        # 经历
        exp = resume_data.get("experience", [])
        if exp:
            lines.append("\n实习经历:")
            for e in exp[:2]:
                lines.append(f"- {e.get('company', '')} | {e.get('position', '')} | {e.get('duration', '')}")

        # 项目
        projects = resume_data.get("projects", [])
        if projects:
            lines.append("\n项目经历:")
            for p in projects[:2]:
                lines.append(f"- {p.get('name', '')} | {p.get('role', '')}")
                lines.append(f"  技术栈: {', '.join(p.get('tech_stack', []))}")

        return "\n".join(lines)

    def _build_jd_snippet(self, job_data: Dict) -> str:
        """构建JD摘要"""
        lines = ["=== 岗位摘要 ==="]

        lines.append(f"岗位: {job_data.get('position_name', '')}")
        lines.append(f"公司: {job_data.get('company', '')} | 地点: {job_data.get('location', '')}")

        # 要求
        req = job_data.get("requirements", {})
        lines.append(f"\n学历要求: {req.get('education', '')}")
        lines.append(f"经验要求: {req.get('experience', '')}")

        hard_skills = req.get("hard_skills", [])
        if hard_skills:
            lines.append(f"\n硬技能: {', '.join(hard_skills)}")

        soft_skills = req.get("soft_skills", [])
        if soft_skills:
            lines.append(f"软技能: {', '.join(soft_skills)}")

        preferred = req.get("preferred", [])
        if preferred:
            lines.append(f"\n加分项: {', '.join(preferred)}")

        return "\n".join(lines)

    def _generate_rule_based_suggestions(
        self,
        match_result: Dict,
        resume_data: Dict,
        job_data: Dict
    ) -> OptimizationSuggestions:
        """基于规则生成建议（LLM失败时的备用方案）"""
        suggestions = []

        gaps = match_result.get("gaps", [])
        breakdown = match_result.get("breakdown", {})

        # 根据差距生成建议
        for gap in gaps:
            gap_type = gap.get("type", "")
            missing = gap.get("missing", "")
            importance = gap.get("importance", "medium")

            if gap_type == "hard_skill":
                suggestions.append(SuggestionItem(
                    type="技能补充",
                    priority=importance,
                    content=f"缺失技能: {missing}。建议在简历中补充相关学习或项目经验。",
                    example=f"技能：...{missing}...\n描述：使用{missing}完成XX项目，实现XX功能"
                ))
            elif gap_type == "soft_skill":
                suggestions.append(SuggestionItem(
                    type="软技能补充",
                    priority=importance,
                    content=f"建议在项目描述中体现{missing}，使用具体事例证明。",
                    example=f"在团队中负责XX协作，通过XX方式提升团队效率"
                ))
            elif gap_type == "experience":
                suggestions.append(SuggestionItem(
                    type="经验补充",
                    priority=importance,
                    content=f"建议补充相关实习经验。如果没有实习，可通过项目弥补。",
                    example="在校期间独立完成XX项目，使用XX技术栈，实现XX功能"
                ))
            elif gap_type == "project":
                suggestions.append(SuggestionItem(
                    type="项目优化",
                    priority=importance,
                    content=f"建议补充与岗位要求技术栈相关的项目经验。",
                    example=f"使用{missing}技术栈完成XX项目"
                ))

        # 根据低分维度生成建议
        if breakdown.get("hard_skills", 0) < 60:
            suggestions.append(SuggestionItem(
                type="技能补充",
                priority="high",
                content="硬技能匹配度较低，建议针对岗位要求学习核心技能。",
                example="制定学习计划，每天投入2小时学习XX技能，完成至少1个实战项目"
            ))

        if breakdown.get("projects", 0) < 60:
            suggestions.append(SuggestionItem(
                type="项目优化",
                priority="high",
                content="项目相关性较低，建议优化项目描述，突出与岗位相关的技能。",
                example="使用STAR法则重写项目：情境(S)→任务(T)→行动(A)→结果(R)"
            ))

        return OptimizationSuggestions(suggestions=suggestions)
