"""
Offer 捕手 - 专业级简历优化服务
基于匹配分析结果，生成针对性的简历优化方案
目标：显著提升用户简历投递通过率
"""
from typing import Dict, List, Optional
from datetime import datetime


class ProfessionalResumeOptimizer:
    """专业级简历优化器"""

    # 动词强度提升映射
    VERB_UPGRADE_MAP = {
        # 低级 -> 高级
        "协助": "负责", "assist": "responsible for",
        "参与": "执行", "participate": "execute",
        "学习": "掌握", "learn": "master",
        "帮忙": "支持", "help": "support",
        "负责": "主导", "responsible": "lead",
        "执行": "构建", "execute": "build",
    }

    # 量化成果模板
    QUANTIFICATION_TEMPLATES = {
        "效率提升": [
            "将{流程}时间从{X}缩短至{Y}（-{Z}%）",
            "优化{流程}，效率提升{X}%",
            "通过{方法}，处理速度提升{X}倍"
        ],
        "成本节约": [
            "优化资源配置，节约成本{X}%",
            "通过{方法}，降低{Y}%成本",
            "实现{目标}的同时，节约{X}万元"
        ],
        "用户增长": [
            "推动{功能}上线，用户数增长{X}%",
            "优化{流程}，用户留存率提升{X}%",
            "实现{目标}，DAU增长{X}%"
        ],
        "质量提升": [
            "优化{流程}，准确率提升{X}%",
            "建立{机制}，问题率降低{X}%",
            "重构{模块}，性能提升{X}%"
        ]
    }

    # 前1/3优化策略
    FIRST_THIRD_OPTIMIZATION = {
        "技能前置": "将JD核心技能放在前1/3，突出匹配度",
        "成果前置": "将最显著的量化成果放在开头",
        "大厂经历前置": "如果有大厂/知名公司经历，放在前1/3",
        "最新经历前置": "最近的相关经历优先展示"
    }

    def __init__(self, llm_client=None):
        """初始化优化器"""
        self.llm_client = llm_client

    def optimize_resume(
        self,
        resume_data: Dict,
        job_data: Dict,
        match_result: Dict
    ) -> Dict:
        """
        基于匹配分析结果优化简历

        Args:
            resume_data: 原始简历数据
            job_data: 目标岗位数据
            match_result: 匹配分析结果

        Returns:
            优化方案和优化后的简历
        """
        # 1. 分析优化点
        optimization_points = self._analyze_optimization_points(
            resume_data, job_data, match_result
        )

        # 2. 生成优化方案
        optimization_plan = self._generate_optimization_plan(
            optimization_points, job_data
        )

        # 3. 执行简历优化
        optimized_resume = self._execute_optimization(
            resume_data, optimization_plan
        )

        # 4. 生成对比说明
        comparison = self._generate_comparison(
            resume_data, optimized_resume, optimization_plan
        )

        return {
            "optimization_points": optimization_points,
            "optimization_plan": optimization_plan,
            "optimized_resume": optimized_resume,
            "comparison": comparison,
            "expected_improvement": self._estimate_improvement(
                match_result, optimization_plan
            ),
            "generated_at": datetime.now().isoformat()
        }

    def _analyze_optimization_points(
        self,
        resume: Dict,
        job: Dict,
        match_result: Dict
    ) -> List[Dict]:
        """分析简历需要优化的点"""
        points = []

        # 1. 技能匹配分析
        skill_match = match_result.get("skill_match", {})
        missing_skills = skill_match.get("missing_skills", [])
        if missing_skills:
            points.append({
                "type": "skill_addition",
                "priority": "high",
                "description": f"缺少核心技能: {', '.join(missing_skills)}",
                "action": "在技能部分补充这些技能，或从项目/经历中提取相关证据"
            })

        # 2. 前1/3分析
        first_third = match_result.get("first_third_analysis", {})
        if first_third.get("status") in ["fair", "poor"]:
            missing_in_first = first_third.get("missing_skills", [])
            points.append({
                "type": "first_third_optimization",
                "priority": "high",
                "description": f"前1/3核心技能覆盖率不足: {first_third.get('coverage_rate', 0)}%",
                "action": f"将以下技能前置到前1/3: {', '.join(missing_in_first[:3])}"
            })

        # 3. 经验动词强度分析
        exp_match = match_result.get("experience_match", {})
        avg_verb = exp_match.get("avg_verb_strength", 0)
        if avg_verb < 7:
            experiences = resume.get("experience", [])
            for i, exp in enumerate(experiences):
                desc = exp.get("description", "")
                weak_verbs = self._find_weak_verbs(desc)
                if weak_verbs:
                    points.append({
                        "type": "verb_upgrade",
                        "priority": "medium",
                        "description": f"第{i+1}段经历动词强度偏低",
                        "action": f"将{weak_verbs}替换为更强有力的动词",
                        "target": f"experience[{i}]",
                        "suggestions": self._suggest_verb_upgrades(weak_verbs)
                    })

        # 4. 量化成果分析
        has_quantifications = any(
            e.get("achievements")
            for e in exp_match.get("experiences", [])
        )
        if not has_quantifications:
            experiences = resume.get("experience", [])
            for i, exp in enumerate(experiences):
                desc = exp.get("description", "")
                if desc and not self._has_quantification(desc):
                    points.append({
                        "type": "quantification_addition",
                        "priority": "high",
                        "description": f"第{i+1}段经历缺少量化成果",
                        "action": "添加具体的量化数据（如：提升X%、服务Y用户）",
                        "target": f"experience[{i}]",
                        "templates": self._suggest_quantification_templates(
                            exp, job
                        )
                    })

        # 5. 项目相关性分析
        proj_match = match_result.get("project_match", {})
        if proj_match.get("avg_relevance", 0) < 60:
            points.append({
                "type": "project_relevance",
                "priority": "medium",
                "description": "项目与JD相关性不足",
                "action": "调整项目描述，突出与目标岗位相关的技术栈和业务场景"
            })

        return points

    def _find_weak_verbs(self, text: str) -> List[str]:
        """找出文本中的弱动词"""
        weak_verbs = []
        weak_verb_list = ["协助", "参与", "帮忙", "学习", "协助", "assist", "participate", "help", "learn"]

        text_lower = text.lower()
        for verb in weak_verb_list:
            if verb in text_lower:
                weak_verbs.append(verb)

        return weak_verbs

    def _suggest_verb_upgrades(self, weak_verbs: List[str]) -> List[str]:
        """建议动词升级"""
        suggestions = []
        for verb in weak_verbs:
            if verb in self.VERB_UPGRADE_MAP:
                suggestions.append(f"'{verb}' → '{self.VERB_UPGRADE_MAP[verb]}'")
        return suggestions

    def _has_quantification(self, text: str) -> bool:
        """检查文本是否有量化表达"""
        import re
        # 匹配数字+单位或百分比
        patterns = [
            r'\d+%',
            r'\d+\s*(万|千|百)?',
            r'\d+\.?\d*\s*(倍|增长|降低|减少|提升|优化|节约)'
        ]
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False

    def _suggest_quantification_templates(
        self, experience: Dict, job: Dict
    ) -> List[str]:
        """建议量化成果模板"""
        desc = experience.get("description", "")
        company = experience.get("company", "")

        # 根据描述内容推测可能的量化方向
        templates = []

        if "效率" in desc or "速度" in desc or "时间" in desc:
            templates.append("效率提升: 将处理时间从X缩短至Y（-Z%）")

        if "用户" in desc or "客户" in desc:
            templates.append("用户增长: 推动功能上线，用户数增长X%")

        if "成本" in desc or "预算" in desc:
            templates.append("成本节约: 优化资源配置，节约成本X%")

        if "准确率" in desc or "质量" in desc or "错误" in desc:
            templates.append("质量提升: 优化流程，准确率提升X%")

        if not templates:
            templates.append("量化成果: 具体说明你做的事情带来了什么可度量的结果")

        return templates[:3]

    def _generate_optimization_plan(
        self, points: List[Dict], job: Dict
    ) -> Dict:
        """生成优化方案"""
        plan = {
            "priority_high": [],
            "priority_medium": [],
            "priority_low": [],
            "quick_wins": [],
            "estimated_time": ""
        }

        high_count = 0
        medium_count = 0

        for point in points:
            item = {
                "type": point["type"],
                "description": point["description"],
                "action": point["action"]
            }

            if point["priority"] == "high":
                plan["priority_high"].append(item)
                high_count += 1
            elif point["priority"] == "medium":
                plan["priority_medium"].append(item)
                medium_count += 1
            else:
                plan["priority_low"].append(item)

            # 快速见效的优化
            if point["type"] in ["first_third_optimization", "verb_upgrade"]:
                plan["quick_wins"].append(item)

        # 估算时间
        total = high_count + medium_count
        if total <= 2:
            plan["estimated_time"] = "10-15分钟"
        elif total <= 4:
            plan["estimated_time"] = "20-30分钟"
        else:
            plan["estimated_time"] = "30-45分钟"

        return plan

    def _execute_optimization(
        self, resume: Dict, plan: Dict
    ) -> Dict:
        """执行简历优化"""
        optimized = resume.copy()

        # 1. 优化经历描述（动词升级）
        if "experience" in optimized:
            for i, exp in enumerate(optimized["experience"]):
                if "description" in exp:
                    optimized["experience"][i]["description"] = self._upgrade_verbs_in_text(
                        exp["description"]
                    )

        # 2. 添加量化成果建议
        # （这里只提供建议，不自动添加具体数值）
        if "experience" in optimized:
            for i, exp in enumerate(optimized["experience"]):
                if not self._has_quantification(exp.get("description", "")):
                    optimized["experience"][i]["quantification_hint"] = (
                        "[建议] 添加量化成果，例如：提升X%、服务Y用户、节约Z成本"
                    )

        # 3. 优化前1/3（技能排序）
        if "skills" in optimized and plan.get("priority_high"):
            # 将技能按重要性排序（这里简单处理，实际应根据JD）
            optimized["skills_priority_note"] = (
                "[建议] 将JD核心技能放在技能列表前面"
            )

        return optimized

    def _upgrade_verbs_in_text(self, text: str) -> str:
        """升级文本中的动词"""
        result = text
        for weak, strong in self.VERB_UPGRADE_MAP.items():
            if weak in result:
                result = result.replace(weak, strong)
        return result

    def _generate_comparison(
        self, original: Dict, optimized: Dict, plan: Dict
    ) -> Dict:
        """生成优化前后对比"""
        return {
            "summary": f"共{len(plan['priority_high'])}个高优先级优化点",
            "key_changes": [
                f"优化了{len(plan['priority_high'])}个关键问题",
                f"调整了{len(plan.get('quick_wins', []))}个快速见效项"
            ],
            "next_steps": [
                "1. 检查优化后的简历内容",
                "2. 根据量化建议添加具体数据",
                "3. 调整前1/3技能顺序",
                "4. 导出并投递"
            ]
        }

    def _estimate_improvement(
        self, match_result: Dict, plan: Dict
    ) -> Dict:
        """估算优化后的提升"""
        current_score = match_result.get("total_score", 0)

        # 估算优化后分数
        high_priority_count = len(plan.get("priority_high", []))
        estimated_gain = high_priority_count * 5  # 每个高优先级约提升5分

        new_score = min(95, current_score + estimated_gain)

        # 估算通过率提升
        current_rate = self._score_to_pass_rate(current_score)
        new_rate = self._score_to_pass_rate(new_score)

        return {
            "current_score": current_score,
            "estimated_new_score": new_score,
            "score_improvement": new_score - current_score,
            "current_pass_rate": current_rate,
            "estimated_pass_rate": new_rate,
            "pass_rate_improvement": new_rate - current_rate,
            "note": "优化后简历匹配度显著提升，投递通过率预计增加"
        }

    def _score_to_pass_rate(self, score: float) -> int:
        """将匹配分数转换为预估通过率"""
        if score >= 85:
            return 75  # 75%通过率
        elif score >= 75:
            return 50
        elif score >= 65:
            return 30
        elif score >= 55:
            return 15
        else:
            return 5


# 便捷函数
def optimize_resume_for_job(
    resume: Dict, job: Dict, match_result: Dict
) -> Dict:
    """优化简历（便捷接口）"""
    optimizer = ProfessionalResumeOptimizer()
    return optimizer.optimize_resume(resume, job, match_result)
