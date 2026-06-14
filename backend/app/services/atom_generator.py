"""
Offer 捕手 - 经历原子生成服务
"""
from typing import List, Dict, Optional
from app.ai.llm_client import get_llm_client


class AtomGenerator:
    """经历原子生成器 - 将简历拆解为可重用的原子单位"""

    def __init__(self, llm_client=None):
        """初始化生成器"""
        self.llm_client = llm_client or get_llm_client()

    def from_resume_data(self, resume_data: Dict) -> List[Dict]:
        """从简历数据生成经历原子

        Args:
            resume_data: 简历解析结果

        Returns:
            经历原子列表
        """
        atoms = []

        # 1. 从工作经历生成原子
        for exp in resume_data.get("experience", []):
            atom = {
                "type": "work",
                "title": exp.get("position", ""),
                "company": exp.get("company", ""),
                "position": exp.get("position", ""),
                "duration": exp.get("duration", ""),
                "description": exp.get("description", ""),
                "skills": self._extract_skills(exp.get("description", "")),
                "tags": self._generate_tags(exp),
                "keywords": self._extract_keywords(exp.get("description", "")),
                "weight": 1.0
            }
            atoms.append(atom)

        # 2. 从项目经历生成原子
        for project in resume_data.get("projects", []):
            atom = {
                "type": "project",
                "title": project.get("name", ""),
                "company": "",
                "position": project.get("role", ""),
                "duration": "",
                "description": project.get("description", ""),
                "skills": project.get("tech_stack", []),
                "tags": self._generate_tags(project),
                "keywords": self._extract_keywords(project.get("description", "")),
                "weight": 1.0
            }
            atoms.append(atom)

        # 3. 从教育背景生成原子
        education = resume_data.get("education")
        if education:
            atom = {
                "type": "education",
                "title": education.get("degree", ""),
                "company": education.get("school", ""),
                "position": education.get("major", ""),
                "duration": education.get("graduation_year", ""),
                "description": f"{education.get('school', '')} · {education.get('major', '')}",
                "skills": education.get("courses", []),
                "tags": ["教育", education.get("degree", "")],
                "keywords": [education.get("major", ""), education.get("school", "")],
                "weight": 1.0
            }
            atoms.append(atom)

        # 4. 技能列表生成原子
        skills = resume_data.get("skills", [])
        if skills:
            atom = {
                "type": "skills",
                "title": "技能概览",
                "company": "",
                "position": "",
                "duration": "",
                "description": ", ".join(skills),
                "skills": skills,
                "tags": ["技能"],
                "keywords": skills,
                "weight": 1.0
            }
            atoms.append(atom)

        return atoms

    def _extract_skills(self, text: str) -> List[str]:
        """从文本中提取技能关键词"""
        # 常见技能关键词
        common_skills = [
            "Python", "Java", "JavaScript", "React", "Vue", "Node.js",
            "SQL", "MySQL", "MongoDB", "Redis", "Docker", "Kubernetes",
            "TensorFlow", "PyTorch", "机器学习", "深度学习",
            "AI", "LLM", "Prompt Engineering", "数据分析", "产品经理",
            "Git", "Linux", "AWS", "Azure", "GCP"
        ]

        found = []
        text_lower = text.lower()
        for skill in common_skills:
            if skill.lower() in text_lower:
                found.append(skill)

        return found

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        # 简单版：分词后过滤常见词
        import re

        # 移除标点
        text = re.sub(r'[^\w\s一-鿿]', ' ', text)

        # 分词（简单按空格）
        words = text.split()

        # 过滤短词和常见词
        stop_words = {"的", "了", "和", "与", "或", "在", "是", "等", "及", "以"}
        keywords = [w for w in words if len(w) > 1 and w not in stop_words]

        # 限制数量
        return keywords[:10]

    def _generate_tags(self, item: Dict) -> List[str]:
        """为经历项生成标签"""
        tags = []

        # 根据类型添加标签
        if item.get("company"):
            tags.append(item["company"])
        if item.get("position"):
            tags.append(item["position"])

        return tags

    def enhance_with_llm(self, atom: Dict, target_jd: Optional[str] = None) -> Dict:
        """使用LLM增强经历原子描述

        Args:
            atom: 原始原子数据
            target_jd: 目标JD（可选，用于针对性优化）

        Returns:
            增强后的原子
        """
        if not target_jd:
            return atom

        # TODO: 实现LLM增强逻辑
        # 可以使用 LLM 根据 JD 重写描述，突出匹配的关键词
        return atom
