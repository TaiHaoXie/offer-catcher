"""
Offer 捕手 - 增强匹配引擎
深化前3名功能：
1. 加权分区关键词匹配
2. LLM提取真实需求
3. 前1/3黄金法则
"""
from typing import Dict, List, Optional, Tuple
from app.services.match_engine import MatchEngine


class EnhancedMatchEngine(MatchEngine):
    """增强匹配引擎 - 深化分析"""

    # 动态权重配置
    DYNAMIC_WEIGHTS = {
        "startup": {  # 初创公司
            "hard_skills": 0.25,
            "soft_skills": 0.20,
            "education": 0.10,
            "experience": 0.20,
            "projects": 0.25,  # 更看重项目
        },
        "big_company": {  # 大厂
            "hard_skills": 0.30,
            "soft_skills": 0.25,
            "education": 0.20,  # 更看重背景
            "experience": 0.15,
            "projects": 0.10,
        },
        "default": {
            "hard_skills": 0.40,
            "soft_skills": 0.20,
            "education": 0.15,
            "experience": 0.15,
            "projects": 0.10,
        }
    }

    # 稀缺技能列表（市场罕见技能给更高权重）
    SCARCE_SKILLS = {
        "大模型": 2.0,
        "llm": 2.0,
        "transformer": 2.0,
        "推荐算法": 1.8,
        "风控": 1.8,
        "高并发": 1.5,
        "分布式": 1.5,
    }

    def __init__(self, llm_client=None):
        """初始化引擎"""
        super().__init__()
        self.llm_client = llm_client

    def calculate_enhanced(
        self,
        resume_data: Dict,
        job_data: Dict
    ) -> Dict:
        """增强匹配计算

        Returns:
            包含基础匹配、深度分析、优化建议的完整结果
        """
        # 1. 判断公司类型，选择动态权重
        company_type = self._detect_company_type(job_data)
        weights = self.DYNAMIC_WEIGHTS.get(
            company_type,
            self.DYNAMIC_WEIGHTS["default"]
        )

        # 2. 基础匹配（使用动态权重）
        base_result = self._calculate_with_weights(
            resume_data, job_data, weights
        )

        # 3. LLM提取真实需求
        real_requirements = self._extract_real_requirements(job_data)

        # 4. 基于真实需求重新计算
        priority_score = self._calculate_priority_match(
            resume_data, real_requirements
        )

        # 5. 前1/3黄金法则分析
        first_third_analysis = self._analyze_first_third(
            resume_data, job_data
        )

        return {
            "base_match": base_result,
            "company_type": company_type,
            "real_requirements": real_requirements,
            "priority_score": priority_score,
            "first_third_analysis": first_third_analysis,
            "optimization_tips": self._generate_optimization_tips(
                base_result, real_requirements, first_third_analysis
            ),
        }

    def _detect_company_type(self, job_data: Dict) -> str:
        """检测公司类型"""
        company = job_data.get("company", "")

        # 检查是否是大厂
        for big_co in self.big_companies:
            if big_co.lower() in company.lower():
                return "big_company"

        # 检查是否是初创公司（关键词）
        startup_keywords = ["创业", "初创", "start-up", "startup", "A轮", "B轮"]
        text = (company + " " + job_data.get("raw_text", "")).lower()
        if any(kw in text for kw in startup_keywords):
            return "startup"

        return "default"

    def _calculate_with_weights(
        self,
        resume: Dict,
        job: Dict,
        weights: Dict
    ) -> Dict:
        """使用指定权重计算匹配度"""
        # 调用父类方法获取各部分分数
        hard_score, _ = self._calculate_hard_skill_match(resume, job)
        soft_score, _ = self._calculate_soft_skill_match(resume, job)
        edu_score, _ = self._calculate_education_match(resume, job)
        exp_score, _ = self._calculate_experience_match(resume, job)
        proj_score, _ = self._calculate_project_match(resume, job)

        # 应用动态权重
        total = (
            hard_score * weights["hard_skills"] +
            soft_score * weights["soft_skills"] +
            edu_score * weights["education"] +
            exp_score * weights["experience"] +
            proj_score * weights["projects"]
        )

        return {
            "total_score": round(total, 1),
            "breakdown": {
                "hard_skills": round(hard_score, 1),
                "soft_skills": round(soft_score, 1),
                "education": round(edu_score, 1),
                "experience": round(exp_score, 1),
                "projects": round(proj_score, 1),
            },
            "weights_used": weights,
        }

    def _extract_real_requirements(self, job_data: Dict) -> Dict:
        """LLM提取JD真实需求

        将JD要求分为三类：
        - must: 必备要求（没有就不面试）
        - nice: 加分项（有了更好）
        - noise: 噪音（可以忽略）
        """
        if not self.llm_client:
            return self._fallback_requirement_extraction(job_data)

        jd_text = job_data.get("raw_text", "")
        if not jd_text:
            return self._fallback_requirement_extraction(job_data)

        try:
            # 构建prompt
            prompt = f"""分析以下JD，提取真实需求等级：

JD内容：
{jd_text[:1000]}

请按以下格式返回JSON：
{{
    "must": ["必备技能1", "必备技能2", ...],  // 没有0-3个
    "nice": ["加分项1", "加分项2", ...],   // 有1-5个更好
    "noise": ["噪音项1", ...]               // 其他要求
}}

规则：
- must: 没有这个基本不会面试
- nice: 有明显优势
- noise: 写了但不是关键

只返回JSON，不要其他内容。"""

            response = self.llm_client.chat(prompt)
            return self._parse_llm_requirements(response)

        except Exception as e:
            print(f"LLM提取需求失败: {e}")
            return self._fallback_requirement_extraction(job_data)

    def _fallback_requirement_extraction(self, job_data: Dict) -> Dict:
        """备用需求提取（基于规则）"""
        requirements = job_data.get("requirements", {})
        hard_skills = requirements.get("hard_skills", [])

        # 简单分类：前2个是must，后面是nice
        return {
            "must": hard_skills[:2] if len(hard_skills) >= 2 else hard_skills,
            "nice": hard_skills[2:5] if len(hard_skills) > 2 else [],
            "noise": [],
            "method": "rule_based"
        }

    def _parse_llm_requirements(self, response: str) -> Dict:
        """解析LLM返回的需求"""
        import json
        import re

        # 尝试提取JSON
        json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                data["method"] = "llm_extracted"
                return data
            except:
                pass

        return self._fallback_requirement_extraction({})

    def _calculate_priority_match(
        self,
        resume: Dict,
        real_requirements: Dict
    ) -> Dict:
        """只基于must+nice计算优先级分数"""
        must_skills = real_requirements.get("must", [])
        nice_skills = real_requirements.get("nice", [])

        resume_skills = set([
            s.lower().strip() for s in resume.get("skills", [])
        ])
        resume_text = self._get_resume_text(resume).lower()

        # must技能权重更高
        must_matched = sum(
            2 for skill in must_skills
            if skill.lower() in resume_text
        )
        must_total = len(must_skills) * 2 if must_skills else 1

        # nice技能权重较低
        nice_matched = sum(
            1 for skill in nice_skills
            if skill.lower() in resume_text
        )
        nice_total = len(nice_skills) if nice_skills else 1

        priority_score = (
            must_matched / must_total * 60 +  # must占60%
            nice_matched / nice_total * 40      # nice占40%
        )

        return {
            "priority_score": round(priority_score, 1),
            "must_coverage": f"{must_matched}/{len(must_skills)}",
            "nice_coverage": f"{nice_matched}/{len(nice_skills)}",
            "must_skills": must_skills,
            "nice_skills": nice_skills,
        }

    def _analyze_first_third(
        self,
        resume: Dict,
        job: Dict
    ) -> Dict:
        """分析简历前1/3是否符合JD黄金法则

        黄金法则：
        1. JD的top5关键词在简历前1/3出现
        2. 前1/3按JD需求顺序排列
        """
        # 获取简历前1/3内容
        resume_text = self._get_resume_text(resume)
        words = resume_text.split()
        first_third_words = words[:len(words) // 3]
        first_third_text = " ".join(first_third_words)

        # 获取JD top5关键词
        job_skills = job.get("requirements", {}).get("hard_skills", [])[:5]

        # 检查top5关键词是否在前1/3出现
        coverage = []
        for skill in job_skills:
            found = skill.lower() in first_third_text.lower()
            coverage.append({
                "keyword": skill,
                "in_first_third": found,
            })

        covered_count = sum(1 for c in coverage if c["in_first_third"])
        coverage_rate = covered_count / len(coverage) * 100 if coverage else 0

        # 分析前1/3质量
        quality_issues = []
        if coverage_rate < 60:
            quality_issues.append("前1/3缺少JD核心关键词")

        # 检查是否有量化成果
        has_numbers = any(c.isdigit() for c in first_third_text)
        if not has_numbers:
            quality_issues.append("前1/3缺少量化成果")

        return {
            "coverage_rate": round(coverage_rate, 1),
            "keyword_coverage": coverage,
            "quality_issues": quality_issues,
            "suggestion": self._generate_first_third_suggestion(
                coverage_rate, quality_issues, job_skills
            )
        }

    def _generate_first_third_suggestion(
        self,
        coverage_rate: float,
        issues: List[str],
        top_keywords: List[str]
    ) -> str:
        """生成前1/3优化建议"""
        if coverage_rate >= 80:
            return "前1/3关键词覆盖良好，保持现有结构"

        suggestions = []
        missing = [
            f"'{kw}'" for i, kw in enumerate(top_keywords)
            if not any(c["keyword"] == kw and c["in_first_third"]
                      for c in [
                          {"keyword": k, "in_first_third": False}
                          for k in top_keywords
                      ])
        ][:3]

        if missing:
            suggestions.append(
                f"将{', '.join(missing)}放在简历前1/3"
            )

        if "量化成果" in " ".join(issues):
            suggestions.append(
                "在前1/3添加量化成果（如：提升X%，完成Y项目）"
            )

        return "；".join(suggestions) if suggestions else "前1/3结构基本合理"

    def _generate_optimization_tips(
        self,
        base_result: Dict,
        real_requirements: Dict,
        first_third: Dict
    ) -> List[Dict]:
        """生成综合优化建议"""
        tips = []

        # 1. 基于真实需求的建议
        must_coverage = real_requirements.get("must", [])
        if must_coverage:
            tips.append({
                "priority": "high",
                "type": "必备技能",
                "content": f"重点突出以下必备技能：{', '.join(must_coverage[:3])}",
                "action": "在项目/经历中明确使用这些技能的场景"
            })

        # 2. 基于前1/3的建议
        if first_third["coverage_rate"] < 70:
            tips.append({
                "priority": "high",
                "type": "简历结构",
                "content": first_third["suggestion"],
                "action": "调整简历前1/3内容，突出JD核心关键词"
            })

        # 3. 基于匹配分数的建议
        total_score = base_result.get("total_score", 0)
        if total_score < 60:
            tips.append({
                "priority": "high",
                "type": "整体提升",
                "content": f"当前匹配度{total_score}分，需重点补充经验",
                "action": "增加相关项目或实习经历"
            })

        return tips
