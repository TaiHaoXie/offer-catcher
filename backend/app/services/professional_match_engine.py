"""
Offer 捕手 - 专业级匹配引擎
对标大厂HR系统，实现多维度深度匹配分析
"""
import re
import json
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
from datetime import datetime


class ProfessionalMatchEngine:
    """专业级匹配引擎 - 大厂标准"""

    # 技能层次树 - 用于技能匹配和层级分析
    SKILL_TAXONOMY = {
        # AI/ML 层次
        "llm": {
            "level": 9,
            "keywords": ["llm", "大模型", "gpt", "claude", "bert", "transformer"],
            "related": ["rag", "prompt engineering", "fine-tuning", "agent"]
        },
        "rag": {
            "level": 8,
            "keywords": ["rag", "检索增强", "vector", "embedding"],
            "related": ["向量检索", "milvus", "pinecone", "chroma", "faiss"]
        },
        "machine_learning": {
            "level": 8,
            "keywords": ["机器学习", "machine learning", "ml", "深度学习", "deep learning"],
            "related": ["神经网络", "neural", "tensorflow", "pytorch", "模型训练"]
        },
        "nlp": {
            "level": 8,
            "keywords": ["nlp", "自然语言处理", "text mining"],
            "related": ["文本分类", "命名实体识别", "情感分析", "分词"]
        },

        # 产品技能
        "product_management": {
            "level": 7,
            "keywords": ["产品经理", "product manager", "pm", "产品设计"],
            "related": ["需求分析", "用户调研", "原型设计", "prd", "竞品分析"]
        },
        "data_analysis": {
            "level": 7,
            "keywords": ["数据分析", "data analysis", "sql", "tableau"],
            "related": ["ab实验", "a/b测试", "漏斗分析", "cohort分析", "增长分析"]
        },
        "user_research": {
            "level": 6,
            "keywords": ["用户研究", "user research", "用户画像", "persona"],
            "related": ["可用性测试", "用户访谈", "问卷设计"]
        },

        # 编程技能
        "python": {
            "level": 7,
            "keywords": ["python", "py"],
            "related": ["pandas", "numpy", "flask", "fastapi", "django"]
        },
        "javascript": {
            "level": 6,
            "keywords": ["javascript", "js", "typescript", "ts"],
            "related": ["react", "vue", "node", "angular", "前端"]
        },

        # 云/DevOps
        "cloud": {
            "level": 5,
            "keywords": ["aws", "azure", "gcp", "云服务", "cloud"],
            "related": ["docker", "kubernetes", "k8s", "部署"]
        },
    }

    # 动词强度层级 - 用于分析经验深度
    VERB_HIERARCHY = {
        # L9 - 主导级
        "主导": 9, "lead": 9, "带领": 9, "负责": 8, "owner": 9, "owned": 9,
        "head": 9, "founder": 9, "创立": 9, "发起": 9,
        # L8 - 构建级
        "构建": 8, "build": 8, "搭建": 8, "建立": 8, "创建": 8, "create": 8,
        "设计": 8, "design": 8, "架构": 8, "implement": 8, "实现": 8,
        # L7 - 执行级
        "开发": 7, "develop": 7, "完成": 7, "deliver": 7, "执行": 7, "execute": 7,
        "produce": 7, "制作": 7, "optimize": 7, "优化": 7, "改进": 7, "improve": 7,
        # L6 - 参与级
        "参与": 6, "participate": 6, "协助": 5, "assist": 5, "support": 5,
        "collaborate": 6, "合作": 6, "配合": 5,
        # L5 - 学习级
        "学习": 5, "learn": 5, "研究": 5, "research": 5, "探索": 5,
    }

    # 公司类型特征词
    BIG_COMPANY_KEYWORDS = [
        "字节跳动", "bytedance", "tiktok", "腾讯", "tencent",
        "阿里", "alibaba", "淘宝", "支付宝", "华为", "huawei",
        "美团", "meituan", "京东", "jd", "百度", "baidu",
        "网易", "netease", "小米", "xiaomi", "滴滴", "didi",
        "apple", "google", "microsoft", "amazon", "meta", "facebook"
    ]

    STARTUP_KEYWORDS = [
        "创业", "初创", "start-up", "startup", "a轮", "b轮", "c轮",
        "天使轮", "seed", "series a", "series b"
    ]

    def __init__(self, llm_client=None):
        """初始化引擎"""
        self.llm_client = llm_client

    def calculate(self, resume_data: Dict, job_data: Dict) -> Dict:
        """
        专业级匹配计算

        返回完整的多维度匹配分析
        """
        # 1. 基础信息匹配
        basic_match = self._analyze_basic_match(resume_data, job_data)

        # 2. 技能匹配（含语义分析）
        skill_match = self._analyze_skill_match(resume_data, job_data)

        # 3. 经验深度匹配
        experience_match = self._analyze_experience_match(resume_data, job_data)

        # 4. 项目相关性匹配
        project_match = self._analyze_project_match(resume_data, job_data)

        # 5. 简历前1/3黄金法则分析
        first_third_analysis = self._analyze_first_third_rule(resume_data, job_data)

        # 6. 综合评分
        total_score = self._calculate_total_score(
            basic_match, skill_match, experience_match, project_match
        )

        # 7. 生成优化建议
        suggestions = self._generate_professional_suggestions(
            skill_match, experience_match, project_match, job_data, first_third_analysis
        )

        return {
            "total_score": total_score,
            "match_level": self._get_match_level(total_score),
            "basic_match": basic_match,
            "skill_match": skill_match,
            "experience_match": experience_match,
            "project_match": project_match,
            "first_third_analysis": first_third_analysis,
            "suggestions": suggestions,
            "analysis_timestamp": datetime.now().isoformat()
        }

    def _analyze_basic_match(self, resume: Dict, job: Dict) -> Dict:
        """分析基础信息匹配度"""
        result = {
            "education_match": {"score": 0, "details": ""},
            "experience_match": {"score": 0, "details": ""},
            "overall_score": 0
        }

        # 学历匹配
        edu_requirements = job.get("requirements", {}).get("education", "")
        resume_edu = resume.get("education", {})

        edu_score = self._calculate_education_match(edu_requirements, resume_edu)
        result["education_match"] = edu_score

        # 经验年限匹配
        exp_requirements = job.get("requirements", {}).get("experience", "")
        resume_exp = resume.get("experience", [])

        exp_score = self._calculate_experience_duration_match(exp_requirements, resume_exp)
        result["experience_match"] = exp_score

        result["overall_score"] = (edu_score["score"] + exp_score["score"]) / 2
        return result

    def _calculate_education_match(self, requirement: str, resume_edu: Dict) -> Dict:
        """计算学历匹配度"""
        if not requirement:
            return {"score": 100, "details": "无学历要求"}

        # 解析要求学历
        req_level = self._parse_education_level(requirement)

        # 解析简历学历 - 从多个字段尝试
        edu_text = " ".join([
            resume_edu.get("degree", ""),
            resume_edu.get("school", ""),
            resume_edu.get("major", "")
        ])
        resume_level = self._parse_education_level(edu_text)

        # 计算匹配度
        if resume_level >= req_level:
            return {"score": 100, "details": f"学历符合要求"}
        elif resume_level >= req_level - 1:
            return {"score": 70, "details": f"学历略低于要求但可接受"}
        else:
            return {"score": 30, "details": f"学历不符合要求"}

    def _parse_education_level(self, text: str) -> int:
        """解析学历等级（数字越大越高）"""
        text = text.lower()
        if "博士" in text or "phd" in text or "ph.d" in text:
            return 4
        elif "硕士" in text or "master" in text or "研究生" in text:
            return 3
        elif "本科" in text or "bachelor" in text or "学士" in text:
            return 2
        elif "大学" in text or "学院" in text:
            # 检查是否有日期格式表示在读（09/2024 – 06/2027）
            if re.search(r'\d{2}/\d{4}\s*[–-—]\s*\d{2}/\d{4}', text):
                return 2  # 本科在读
            return 2  # 有学院名称，默认本科
        elif "大专" in text or "专科" in text:
            return 1
        else:
            return 0

    def _calculate_experience_duration_match(self, requirement: str, resume_exp: List) -> Dict:
        """计算经验年限匹配度"""
        if not requirement or not resume_exp:
            return {"score": 50, "details": "无法判断经验匹配"}

        # 从经历中提取总工作时长
        total_months = self._extract_total_experience_months(resume_exp)
        total_years = total_months / 12

        # 解析要求年限
        req_years = self._parse_experience_years(requirement)

        if total_years >= req_years:
            return {
                "score": 100,
                "details": f"经验充足（{total_years:.1f}年 >= {req_years}年）"
            }
        elif total_years >= req_years * 0.7:
            return {
                "score": 70,
                "details": f"经验略少于要求（{total_years:.1f}年 vs {req_years}年）"
            }
        else:
            return {
                "score": 30,
                "details": f"经验不足（{total_years:.1f}年 < {req_years}年）"
            }

    def _extract_total_experience_months(self, experiences: List[Dict]) -> int:
        """从经历中提取总工作时长（月数）"""
        total = 0
        for exp in experiences:
            # 尝试从多个字段获取duration
            duration = exp.get("duration", "")
            if not duration:
                # 如果duration字段为空，尝试从position中提取
                duration = exp.get("position", "")
            if duration:
                months = self._parse_duration_to_months(duration)
                if months > 0:
                    total += months
        return total

    def _parse_duration_to_months(self, duration: str) -> int:
        """解析时长字符串为月数"""
        # 匹配 02/2026 – 03/2026 格式
        pattern = r'(\d{2})/(\d{4})\s*[–-—]\s*(\d{2})/(\d{4})'
        match = re.search(pattern, duration)
        if match:
            start_month, start_year, end_month, end_year = match.groups()
            # 计算月数差
            months = (int(end_year) - int(start_year)) * 12 + (int(end_month) - int(start_month))
            return max(0, months)
        return 0

    def _parse_experience_years(self, requirement: str) -> float:
        """解析经验要求为年数"""
        match = re.search(r'(\d+)\s*年', requirement)
        if match:
            return float(match.group(1))
        match = re.search(r'(\d+)\s*\+', requirement)
        if match:
            return float(match.group(1))
        return 1.0  # 默认1年

    def _analyze_skill_match(self, resume: Dict, job: Dict) -> Dict:
        """深度技能匹配分析"""
        # 获取技能列表
        job_skills = job.get("requirements", {}).get("hard_skills", [])
        resume_skills = resume.get("skills", [])

        # 构建技能匹配矩阵
        matched_skills = []
        missing_skills = []
        related_skills = []

        # 将简历文本用于语义匹配
        resume_text = self._get_resume_text(resume)

        for skill_req in job_skills:
            skill_req_lower = skill_req.lower()

            # 直接匹配
            if any(skill_req_lower in s.lower() for s in resume_skills):
                matched_skills.append({
                    "skill": skill_req,
                    "match_type": "direct",
                    "confidence": 100
                })
            # 语义匹配（技能层次树）
            elif self._semantic_skill_match(skill_req, resume_text):
                matched_skills.append({
                    "skill": skill_req,
                    "match_type": "semantic",
                    "confidence": 75
                })
                related = self._get_related_skills(skill_req)
                if related:
                    related_skills.extend(related)
            else:
                missing_skills.append(skill_req)

        # 计算技能覆盖率
        coverage_rate = len(matched_skills) / len(job_skills) * 100 if job_skills else 0

        # 技能深度评分（基于技能层次）
        depth_score = self._calculate_skill_depth_score(matched_skills, resume_text)

        return {
            "coverage_rate": round(coverage_rate, 1),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "related_skills": list(set(related_skills)),
            "depth_score": depth_score,
            "overall_score": round((coverage_rate * 0.6 + depth_score * 0.4), 1)
        }

    def _semantic_skill_match(self, skill: str, resume_text: str) -> bool:
        """语义技能匹配"""
        skill_lower = skill.lower()

        # 检查技能层次树
        for category, data in self.SKILL_TAXONOMY.items():
            if skill_lower in data["keywords"] or skill_lower in category:
                # 检查相关技能
                for related in data.get("related", []):
                    if related.lower() in resume_text.lower():
                        return True
        return False

    def _get_related_skills(self, skill: str) -> List[str]:
        """获取相关技能"""
        skill_lower = skill.lower()
        for category, data in self.SKILL_TAXONOMY.items():
            if skill_lower in data["keywords"] or skill_lower in category:
                return data.get("related", [])
        return []

    def _calculate_skill_depth_score(self, matched_skills: List, resume_text: str) -> float:
        """计算技能深度分数"""
        if not matched_skills:
            return 0

        total_depth = 0
        for skill_info in matched_skills:
            skill = skill_info["skill"]
            # 找到技能等级
            for category, data in self.SKILL_TAXONOMY.items():
                if skill.lower() in data["keywords"] or skill.lower() in category:
                    total_depth += data["level"]
                    break
            else:
                total_depth += 5  # 默认等级

        # 归一化到0-100
        avg_depth = total_depth / len(matched_skills)
        return min(100, (avg_depth / 9) * 100)

    def _analyze_experience_match(self, resume: Dict, job: Dict) -> Dict:
        """经验深度匹配分析"""
        experiences = resume.get("experience", [])
        job_requirements = job.get("responsibilities", [])

        # 分析每段经历的动词强度
        experience_analysis = []
        for exp in experiences:
            analysis = self._analyze_single_experience(exp, job_requirements)
            experience_analysis.append(analysis)

        # 计算整体经验匹配度
        avg_verb_strength = sum(e["verb_strength"] for e in experience_analysis) / len(experience_analysis) if experience_analysis else 0
        avg_relevance = sum(e["relevance_score"] for e in experience_analysis) / len(experience_analysis) if experience_analysis else 0

        return {
            "experiences": experience_analysis,
            "avg_verb_strength": round(avg_verb_strength, 1),
            "avg_relevance": round(avg_relevance, 1),
            "overall_score": round((avg_verb_strength * 10 + avg_relevance * 0.9) / 2, 1)
        }

    def _analyze_single_experience(self, exp: Dict, job_requirements: List) -> Dict:
        """分析单个经历的深度"""
        description = exp.get("description", "")
        company = exp.get("company", "")
        position = exp.get("position", "")

        # 1. 动词强度分析
        verb_strength = self._calculate_verb_strength(description)

        # 2. 相关性分析（与JD职责匹配）
        relevance_score = self._calculate_experience_relevance(description, job_requirements)

        # 3. 量化成果分析
        achievements = self._extract_achievements(description)

        # 4. 公司层级评分
        company_tier = self._get_company_tier(company)

        return {
            "company": company,
            "position": position,
            "verb_strength": verb_strength,
            "relevance_score": relevance_score,
            "achievements": achievements,
            "company_tier": company_tier
        }

    def _calculate_verb_strength(self, text: str) -> float:
        """计算文本中的动词强度"""
        if not text:
            return 0

        max_strength = 0
        text_lower = text.lower()

        for verb, strength in self.VERB_HIERARCHY.items():
            if verb in text_lower:
                max_strength = max(max_strength, strength)

        return max_strength

    def _calculate_experience_relevance(self, exp_text: str, job_requirements: List) -> float:
        """计算经历与JD的相关性"""
        if not exp_text or not job_requirements:
            return 50

        # 提取经历中的关键词
        exp_keywords = self._extract_keywords(exp_text)

        # 计算与JD职责的重叠
        relevant_count = 0
        for req in job_requirements:
            req_keywords = self._extract_keywords(req)
            overlap = len(set(exp_keywords) & set(req_keywords))
            if overlap > 0:
                relevant_count += 1

        return (relevant_count / len(job_requirements)) * 100 if job_requirements else 50

    def _extract_achievements(self, text: str) -> List[str]:
        """提取量化成果"""
        achievements = []

        # 匹配数字+单位模式
        patterns = [
            r'(\d+%|\d+\s*%)',  # 百分比
            r'(\d+\s*(万|千|百)?)',  # 数字
            r'(\d+\.?\d*)\s*(倍|增长|降低|减少|提升|优化)',  # 增长类
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    achievements.append(''.join(match))
                else:
                    achievements.append(match)

        return achievements[:5]  # 最多返回5个

    def _get_company_tier(self, company: str) -> str:
        """判断公司层级"""
        company_lower = company.lower()

        # 大厂
        for big_co in self.BIG_COMPANY_KEYWORDS:
            if big_co in company_lower:
                return "tier1_big_company"

        # 初创
        for startup_kw in self.STARTUP_KEYWORDS:
            if startup_kw in company_lower:
                return "tier2_startup"

        return "tier3_other"

    def _analyze_project_match(self, resume: Dict, job: Dict) -> Dict:
        """项目相关性匹配分析"""
        projects = resume.get("projects", [])
        job_skills = job.get("requirements", {}).get("hard_skills", [])

        # 构建完整简历文本用于语义匹配
        resume_text = self._get_resume_text(resume)

        project_analysis = []
        for proj in projects:
            analysis = self._analyze_single_project(proj, job_skills, resume_text)
            project_analysis.append(analysis)

        # 计算整体项目匹配度
        avg_relevance = sum(p["relevance_score"] for p in project_analysis) / len(project_analysis) if project_analysis else 0
        avg_tech_match = sum(p["tech_match_score"] for p in project_analysis) / len(project_analysis) if project_analysis else 0

        return {
            "projects": project_analysis,
            "avg_relevance": round(avg_relevance, 1),
            "avg_tech_match": round(avg_tech_match, 1),
            "overall_score": round((avg_relevance + avg_tech_match) / 2, 1)
        }

    def _analyze_single_project(self, proj: Dict, job_skills: List, resume_text: str = "") -> Dict:
        """分析单个项目的相关性"""
        name = proj.get("name", "")
        description = proj.get("description", "")
        tech_stack = proj.get("tech_stack", [])

        # 技术栈匹配度
        tech_match = self._calculate_tech_stack_match(tech_stack, job_skills)

        # 项目描述与JD相关性（使用语义匹配）
        relevance_score = self._calculate_project_relevance(description, job_skills, resume_text)

        # 项目规模（基于描述长度和复杂度）
        project_scale = self._estimate_project_scale(description)

        return {
            "name": name,
            "relevance_score": relevance_score,
            "tech_match_score": tech_match,
            "project_scale": project_scale
        }

    def _calculate_tech_stack_match(self, tech_stack: List, job_skills: List) -> float:
        """计算技术栈匹配度"""
        if not tech_stack or not job_skills:
            return 0

        matched = 0
        for skill in job_skills:
            skill_lower = skill.lower()
            for tech in tech_stack:
                if skill_lower in tech.lower() or tech.lower() in skill_lower:
                    matched += 1
                    break

        return (matched / len(job_skills)) * 100

    def _calculate_project_relevance(self, description: str, job_skills: List, resume_text: str = "") -> float:
        """计算项目与JD的相关性"""
        if not description and not resume_text:
            return 0

        # 使用描述+全文进行匹配
        combined_text = (description + " " + resume_text).lower()
        matched_keywords = 0

        for skill in job_skills:
            skill_lower = skill.lower()
            # 直接匹配
            if skill_lower in combined_text:
                matched_keywords += 1
            # 语义匹配（技能层次树）
            elif self._semantic_skill_match(skill, combined_text):
                matched_keywords += 0.7  # 语义匹配给70%权重

        return (matched_keywords / len(job_skills)) * 100 if job_skills else 50

    def _estimate_project_scale(self, description: str) -> str:
        """估算项目规模"""
        if not description:
            return "unknown"

        # 基于关键词判断
        if any(kw in description for kw in ["从0到1", "独立开发", "全栈", "完整"]):
            return "large"
        elif any(kw in description for kw in ["参与", "协助", "部分"]):
            return "small"
        else:
            return "medium"

    def _calculate_total_score(
        self,
        basic_match: Dict,
        skill_match: Dict,
        experience_match: Dict,
        project_match: Dict
    ) -> float:
        """计算总分"""
        # 权重分配（对标大厂标准）
        weights = {
            "basic": 0.15,      # 基础门槛
            "skill": 0.35,      # 技能最重要
            "experience": 0.30, # 经验深度
            "project": 0.20     # 项目相关性
        }

        total = (
            basic_match["overall_score"] * weights["basic"] +
            skill_match["overall_score"] * weights["skill"] +
            experience_match["overall_score"] * weights["experience"] +
            project_match["overall_score"] * weights["project"]
        )

        return round(total, 1)

    def _get_match_level(self, score: float) -> str:
        """获取匹配等级"""
        if score >= 85:
            return "excellent"  # 优秀
        elif score >= 70:
            return "good"       # 良好
        elif score >= 55:
            return "fair"       # 一般
        else:
            return "poor"        # 较差

    def _generate_professional_suggestions(
        self,
        skill_match: Dict,
        experience_match: Dict,
        project_match: Dict,
        job_data: Dict,
        first_third_analysis: Dict
    ) -> List[Dict]:
        """生成专业级优化建议"""
        suggestions = []

        # 1. 技能缺失建议
        missing_skills = skill_match.get("missing_skills", [])
        if missing_skills:
            suggestions.append({
                "priority": "high",
                "category": "技能补充",
                "issue": f"缺少核心技能: {', '.join(missing_skills[:3])}",
                "action": f"建议重点学习{'、'.join(missing_skills[:2])}，可通过在线课程或项目实践补充"
            })

        # 2. 技能深度建议
        depth_score = skill_match.get("depth_score", 0)
        if depth_score < 60:
            suggestions.append({
                "priority": "medium",
                "category": "技能深化",
                "issue": f"技能深度不足（当前{depth_score}分）",
                "action": "建议在项目中深入应用核心技能，积累复杂场景经验，而非浅层使用"
            })

        # 3. 经验动词强度建议
        avg_verb = experience_match.get("avg_verb_strength", 0)
        if avg_verb < 7:
            suggestions.append({
                "priority": "high",
                "category": "经历表达",
                "issue": f"经历描述动词强度偏低（当前{avg_verb}/9）",
                "action": "将'协助''参与'等词汇改为'负责''构建''主导'等主动词，强调个人贡献"
            })

        # 4. 量化成果建议
        has_achievements = any(
            e.get("achievements")
            for e in experience_match.get("experiences", [])
        )
        if not has_achievements:
            suggestions.append({
                "priority": "high",
                "category": "量化成果",
                "issue": "经历描述缺少量化成果",
                "action": "为每段经历添加具体数据：提升X%、完成Y项目、服务Z用户、节约N成本"
            })

        # 5. 项目相关性建议
        avg_proj_relevance = project_match.get("avg_relevance", 0)
        if avg_proj_relevance < 50:
            suggestions.append({
                "priority": "medium",
                "category": "项目匹配",
                "issue": f"项目与JD相关性偏低（当前{avg_proj_relevance}%）",
                "action": "调整项目描述，突出与目标岗位相关的技术栈和业务场景"
            })

        # 6. 技能覆盖建议
        coverage = skill_match.get("coverage_rate", 0)
        if coverage < 50:
            suggestions.append({
                "priority": "critical",
                "category": "整体匹配",
                "issue": f"技能覆盖率严重不足（仅{coverage}%）",
                "action": "当前岗位匹配度较低，建议：1）补充核心技能 2）寻找匹配度更高的岗位 3）通过实习积累相关经验"
            })

        # 7. 前1/3黄金法则建议
        first_third_status = first_third_analysis.get("status", "")
        first_third_coverage = first_third_analysis.get("coverage_rate", 0)
        missing_in_first = first_third_analysis.get("missing_skills", [])

        if first_third_status in ["fair", "poor"]:
            suggestions.append({
                "priority": "high",
                "category": "简历结构",
                "issue": f"前1/3核心技能覆盖率不足（{first_third_coverage}%）",
                "action": f"将以下核心技能前置到简历前1/3：{', '.join(missing_in_first[:3])}。HR前6秒只看前1/3，必须让核心关键词第一时间被看到"
            })

        return suggestions

    def _analyze_first_third_rule(self, resume: Dict, job: Dict) -> Dict:
        """
        分析简历前1/3是否符合黄金法则

        黄金法则：HR在前6秒只看前1/3，核心关键词必须出现
        """
        # 获取简历全文
        resume_text = self._get_resume_text(resume)

        # 获取JD核心技能（前5个）
        job_skills = job.get("requirements", {}).get("hard_skills", [])[:5]

        # 计算前1/3位置
        words = resume_text.split()
        if len(words) < 10:
            return {"coverage_rate": 0, "status": "简历内容过少"}

        first_third_end = len(words) // 3
        first_third_text = " ".join(words[:first_third_end]).lower()

        # 检查核心技能是否在前1/3出现
        coverage = []
        for skill in job_skills:
            skill_lower = skill.lower()
            found = skill_lower in first_third_text
            coverage.append({
                "skill": skill,
                "in_first_third": found
            })

        covered_count = sum(1 for c in coverage if c["in_first_third"])
        coverage_rate = (covered_count / len(coverage) * 100) if coverage else 0

        # 分析前1/3质量
        quality_issues = []

        # 1. 关键词覆盖率
        if coverage_rate < 60:
            quality_issues.append("前1/3核心关键词覆盖率不足60%")

        # 2. 量化成果
        has_numbers = any(c.isdigit() for c in first_third_text)
        if not has_numbers:
            quality_issues.append("前1/3缺少量化成果")

        # 3. 动词强度
        verb_strength = self._calculate_verb_strength(first_third_text)
        if verb_strength < 7:
            quality_issues.append(f"前1/3动词强度偏低（当前{verb_strength}/9）")

        # 生成状态和建议
        if coverage_rate >= 80 and len(quality_issues) == 0:
            status = "excellent"
            suggestion = "前1/3结构优秀，保持现有布局"
        elif coverage_rate >= 60 and len(quality_issues) <= 1:
            status = "good"
            suggestion = "前1/3结构良好，可微调提升"
        elif coverage_rate >= 40:
            status = "fair"
            suggestion = "前1/3需要优化，建议调整核心技能位置"
        else:
            status = "poor"
            suggestion = "前1/3结构需重构，建议将JD核心技能前置"

        # 找出缺失的核心技能
        missing_skills = [c["skill"] for c in coverage if not c["in_first_third"]]

        return {
            "status": status,
            "coverage_rate": round(coverage_rate, 1),
            "keyword_coverage": coverage,
            "missing_skills": missing_skills,
            "quality_issues": quality_issues,
            "verb_strength": verb_strength,
            "suggestion": suggestion
        }

    def _get_resume_text(self, resume: Dict) -> str:
        """获取简历全文文本"""
        parts = []

        # 基本信息
        basic = resume.get("basic_info", {})
        parts.extend([basic.get(k, "") for k in ["name", "university", "major"]])

        # 技能
        parts.extend(resume.get("skills", []))

        # 经历描述
        for exp in resume.get("experience", []):
            parts.append(exp.get("description", ""))

        # 项目描述
        for proj in resume.get("projects", []):
            parts.append(proj.get("description", ""))

        return " ".join(parts)

    def _extract_keywords(self, text: str) -> List[str]:
        """提取文本中的关键词"""
        # 简单关键词提取（可以升级为NLP）
        keywords = []

        # 中文关键词（2-4个字）
        chinese_words = re.findall(r'[一-龥]{2,4}', text)
        keywords.extend(chinese_words)

        # 英文关键词
        english_words = re.findall(r'[a-zA-Z]{3,10}', text)
        keywords.extend(english_words)

        return list(set(keywords))


# 便捷函数
def calculate_match(resume: Dict, job: Dict) -> Dict:
    """计算匹配度（便捷接口）"""
    engine = ProfessionalMatchEngine()
    return engine.calculate(resume, job)
