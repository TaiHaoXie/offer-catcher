"""
Offer 捕手 - 快速JD解析服务
使用正则表达式快速解析JD，目标 < 100ms
"""
import re
from typing import Dict, List, Tuple


class FastJDParser:
    """快速JD解析器 - 正则表达式解析，无需LLM"""

    # 技能关键词库
    SKILL_PATTERNS = {
        # 编程语言
        "python": r"python|pytorch|tensorflow|pandas|numpy",
        "java": r"java|spring|mybatis|jvm",
        "javascript": r"javascript|js|typescript|ts|node\.js|react|vue|angular",
        "c++": r"c\+\+|cpp|qt|mfc",
        "go": r"\bgolang\b|\bgo\b",
        "rust": r"\brust\b",

        # AI/ML
        "机器学习": r"机器学习|machine learning|ml",
        "深度学习": r"深度学习|deep learning|神经网络|neural",
        "nlp": r"nlp|自然语言|文本处理|bert|gpt|transformer",
        "推荐算法": r"推荐|recommend|搜索|召回|排序|ctr",
        "数据挖掘": r"数据挖掘|data mining|大数据|spark|flink|hive",

        # 产品相关
        "产品经理": r"产品经理|product manager|pm",
        "需求分析": r"需求|requirement|用户调研|user research",
        "原型设计": r"原型|prototype|axure|figma|sketch",
        "数据分析": r"数据分析|data analysis|sql|excel",
        "用户研究": r"用户研究|user study|用户测试|可用性",

        # 通用技能
        "沟通能力": r"沟通|communication|协作|协调",
        "团队管理": r"团队|team|管理|manage|lead",
        "项目管理": r"项目管理|project management|pmp|敏捷|agile|scrum",
    }

    # 学历关键词
    EDUCATION_PATTERNS = {
        "博士": r"博士|phd|\bph\.d\b",
        "硕士": r"硕士|master|研究生",
        "本科": r"本科|bachelor|学士",
    }

    # 经验关键词
    EXPERIENCE_PATTERNS = {
        "实习经验": r"实习|intern",
        "3年以上": r"3\s*年|三年|three\+? years?",
        "2年以上": r"2\s*年|两年|two\+? years?",
        "1年以上": r"1\s*年|一年|one\+? years?",
    }

    def __init__(self):
        """初始化解析器"""
        # 预编译正则表达式
        self._compile_patterns()

    def _compile_patterns(self):
        """预编译所有正则表达式"""
        self.compiled_skills = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.SKILL_PATTERNS.items()
        }
        self.compiled_education = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.EDUCATION_PATTERNS.items()
        }
        self.compiled_experience = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.EXPERIENCE_PATTERNS.items()
        }

    def parse(self, jd_text: str) -> Dict:
        """解析JD文本

        Args:
            jd_text: JD文本内容

        Returns:
            结构化的岗位数据
        """
        if not jd_text or len(jd_text) < 20:
            return self._empty_result()

        # 提取职位名称
        position = self._extract_position(jd_text)

        # 提取公司名称
        company = self._extract_company(jd_text)

        # 提取技能要求
        hard_skills, soft_skills = self._extract_skills(jd_text)

        # 提取学历要求
        education = self._extract_education(jd_text)

        # 提取经验要求
        experience = self._extract_experience(jd_text)

        # 提取职责描述
        responsibilities = self._extract_responsibilities(jd_text)

        return {
            "position_name": position,
            "company": company,
            "requirements": {
                "hard_skills": hard_skills,
                "soft_skills": soft_skills,
                "education": education,
                "experience": experience,
            },
            "responsibilities": responsibilities,
            "raw_text": jd_text[:500],  # 保存前500字符
        }

    def _extract_position(self, text: str) -> str:
        """提取职位名称"""
        # 常见职位模式
        patterns = [
            r"职位[：:]\s*([^\n]+)",
            r"岗位[：:]\s*([^\n]+)",
            r"position[：:]\s*([^\n]+)",
            r"job[：:]\s*([^\n]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                position = match.group(1).strip()
                # 清理多余文字
                position = re.sub(r"（.*?）", "", position)
                position = re.sub(r"\(.*?\)", "", position)
                return position[:30]  # 限制长度

        # 尝试从第一行提取
        lines = text.split("\n")
        if lines:
            first_line = lines[0].strip()
            if len(first_line) < 30:
                return first_line

        return "未知职位"

    def _extract_company(self, text: str) -> str:
        """提取公司名称"""
        patterns = [
            r"公司[：:]\s*([^\n]+)",
            r"company[：:]\s*([^\n]+)",
            r"单位[：:]\s*([^\n]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:30]

        return ""

    def _extract_skills(self, text: str) -> Tuple[List[str], List[str]]:
        """提取技能要求，区分硬技能和软技能"""
        hard_skills = []
        soft_skills = []

        # 硬技能检测 - 扩展覆盖AI产品经理相关技能
        hard_skill_keywords = [
            # 编程语言
            "python", "java", "javascript", "c++", "go", "rust",
            # AI/ML
            "机器学习", "深度学习", "nlp", "推荐算法", "数据挖掘",
            "llm", "大模型", "rag", "embedding", "向量检索", "prompt engineering",
            "transformer", "gpt", "bert", "claude",
            # Web框架
            "react", "vue", "angular", "node", "spring",
            # 数据
            "sql", "mysql", "redis", "mongodb", "postgresql", "数据分析",
            # 产品技能
            "产品设计", "需求分析", "用户调研", "原型设计", "竞品分析",
        ]

        # 软技能检测
        soft_skill_keywords = [
            "沟通", "协作", "团队", "管理", "领导",
            "产品思维", "用户研究", "项目管理", "敏捷", "scrum",
            "用户洞察", "数据分析", "ab实验", "增长分析",
        ]

        text_lower = text.lower()

        # 检测硬技能
        for skill in hard_skill_keywords:
            if skill.lower() in text_lower:
                hard_skills.append(skill)

        # 检测软技能
        for skill in soft_skill_keywords:
            if skill.lower() in text_lower:
                soft_skills.append(skill)

        return list(set(hard_skills)), list(set(soft_skills))

    def _extract_education(self, text: str) -> str:
        """提取学历要求"""
        # 按优先级检测
        for level in ["博士", "硕士", "本科"]:
            pattern = self.compiled_education.get(level)
            if pattern and pattern.search(text):
                return f"{level}及以上学历"

        # 默认本科
        return "本科及以上学历"

    def _extract_experience(self, text: str) -> str:
        """提取经验要求"""
        # 按优先级检测
        for exp in ["3年以上", "2年以上", "1年以上", "实习经验"]:
            pattern = self.compiled_experience.get(exp)
            if pattern and pattern.search(text):
                if "实习" in exp:
                    return "有实习经验优先"
                return exp

        return "有相关经验优先"

    def _extract_responsibilities(self, text: str) -> List[str]:
        """提取职责描述"""
        responsibilities = []

        # 尝试匹配职责部分
        patterns = [
            r"职责[：:]\\s*\\n((?:[^\\n]+\\n){1,10})",
            r"responsibilities[：:]\\s*\\n((?:[^\\n]+\\n){1,10})",
            r"工作内容[：:]\\s*\\n((?:[^\\n]+\\n){1,10})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                section = match.group(1)
                # 按行分割并清理
                lines = [
                    line.strip()
                    for line in section.split("\n")
                    if line.strip() and len(line.strip()) > 3
                ]
                responsibilities.extend(lines[:5])  # 最多取5条
                break

        return responsibilities[:5]

    def _empty_result(self) -> Dict:
        """返回空结果"""
        return {
            "position_name": "未知职位",
            "company": "",
            "requirements": {
                "hard_skills": [],
                "soft_skills": [],
                "education": "本科及以上学历",
                "experience": "有相关经验优先",
            },
            "responsibilities": [],
            "raw_text": "",
        }
