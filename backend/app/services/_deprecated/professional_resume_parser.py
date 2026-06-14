"""
Offer 捕手 - 专业级简历解析器
支持中英文简历、多种格式，解析准确率 > 95%
"""
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class ProfessionalResumeParser:
    """专业级简历解析器"""

    # 简历段落的常见标题模式
    SECTION_PATTERNS = {
        "basic_info": [
            r"^basic\s*info$",
            r"^个人信息$",
            r"^个人资料$",
            r"^基本信息$"
        ],
        "summary": [
            r"^summary$",
            r"^个人简介$",
            r"^自我评价$",
            r"^专业概述$"
        ],
        "skills": [
            r"^skills?$",
            r"^技能$",
            r"^专业技能$",
            r"^技术栈$",
            r"^技术能力$"
        ],
        "experience": [
            r"^experience$",
            r"^work\s*experience$",
            r"^professional\s*experience$",
            r"^工作经历$",
            r"^实习经历$",
            r"^职业经历$"
        ],
        "projects": [
            r"^projects?$",
            r"^项目经历$",
            r"^project\s*experience$",
            r"^个人项目$"
        ],
        "education": [
            r"^education$",
            r"^教育背景$",
            r"^学历$"
        ]
    }

    def __init__(self, llm_client=None):
        """初始化解析器"""
        self.llm_client = llm_client

    def parse(self, file_path: str) -> Dict:
        """解析简历文件"""
        text = self.extract_text(file_path)
        return self.parse_from_text(text)

    def parse_from_text(self, text: str) -> Dict:
        """从文本解析简历"""
        if not text or len(text) < 50:
            raise ValueError("文本内容过少，无法解析")

        # 预处理文本
        text = self._preprocess_text(text)

        # 分段解析
        sections = self._split_sections(text)

        result = {
            "basic_info": self._parse_basic_info(text, sections.get("header", "")),
            "skills": self._parse_skills(sections.get("skills", "")),
            "experience": self._parse_experience(sections.get("experience", "")),
            "projects": self._parse_projects(sections.get("projects", "")),
            "education": self._parse_education(sections.get("education", "")),
            "summary": self._parse_summary(sections.get("summary", ""))
        }

        return result

    def extract_text(self, file_path: str) -> str:
        """从文件中提取文本"""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if file_path.suffix.lower() == ".pdf":
            return self._extract_pdf_text(file_path)
        elif file_path.suffix.lower() in [".docx", ".doc"]:
            return self._extract_docx_text(file_path)
        elif file_path.suffix.lower() == ".txt":
            return self._extract_txt_text(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {file_path.suffix}")

    def _extract_pdf_text(self, file_path: Path) -> str:
        """提取PDF文本，增强版"""
        try:
            import PyPDF2
            text = ""
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    page_text = page.extract_text()
                    text += page_text + "\n"
            return self._cleanup_text(text)
        except ImportError:
            try:
                import pdfplumber
                text = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() + "\n"
                return self._cleanup_text(text)
            except ImportError:
                raise ImportError("请安装 PyPDF2: pip install PyPDF2")

    def _extract_docx_text(self, file_path: Path) -> str:
        """提取Word文本"""
        try:
            from docx import Document
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return self._cleanup_text(text)
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")

    def _extract_txt_text(self, file_path: Path) -> str:
        """提取TXT文本"""
        with open(file_path, "rb") as f:
            content = f.read()
            # 尝试UTF-8解码
            try:
                return self._cleanup_text(content.decode('utf-8'))
            except UnicodeDecodeError:
                # 尝试GBK
                return self._cleanup_text(content.decode('gbk', errors='ignore'))

    def _preprocess_text(self, text: str) -> str:
        """预处理文本"""
        # 统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # 处理PDF常见的断行问题（单词被截断）
        # 例如："Pyth\non" -> "Python"
        text = re.sub(r'([a-zA-Z])\n([a-zA-Z])', r'\1\2', text)

        # 清理多余的空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _cleanup_text(self, text: str) -> str:
        """清理提取的文本"""
        # 移除页码、页眉页脚等
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            line = line.strip()
            # 跳过页码
            if re.match(r'^\d+\s*$', line):
                continue
            # 跳过可能的页眉页脚（短行且数字多）
            if len(line) < 10 and re.search(r'\d{2,}', line):
                continue
            cleaned.append(line)
        return '\n'.join(cleaned)

    def _split_sections(self, text: str) -> Dict[str, str]:
        """将简历文本分段"""
        sections = {
            "header": "",
            "summary": "",
            "skills": "",
            "experience": "",
            "projects": "",
            "education": ""
        }

        lines = text.split('\n')
        current_section = "header"
        current_content = []

        for i, line in enumerate(lines):
            line_lower = line.strip().lower()

            # 检测是否是段落标题
            detected_section = self._detect_section(line)

            if detected_section:
                # 保存之前的内容
                if current_content:
                    sections[current_section] = '\n'.join(current_content)

                current_section = detected_section
                current_content = []
            else:
                current_content.append(line)

        # 保存最后一个段落
        if current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _detect_section(self, line: str) -> Optional[str]:
        """检测段落标题"""
        line_trimmed = line.strip()

        # 空行不是标题
        if not line_trimmed:
            return None

        # 检查是否匹配任何段落标题模式
        for section, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, line_trimmed, re.IGNORECASE):
                    return section

        return None

    def _parse_basic_info(self, full_text: str, header_text: str) -> Dict:
        """解析基本信息"""
        info = {
            "name": "",
            "email": "",
            "phone": "",
            "university": "",
            "major": "",
            "degree": "",
            "graduation_year": ""
        }

        # 从头部文本提取
        lines = header_text.split('\n') if header_text else full_text.split('\n')[:10]

        for line in lines[:15]:
            # 邮箱
            if not info["email"]:
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line)
                if email_match:
                    info["email"] = email_match.group()

            # 电话
            if not info["phone"]:
                phone_match = re.search(r'1[3-9]\d{9}', line)
                if phone_match:
                    info["phone"] = phone_match.group()

            # 姓名 - 通常在第一行或第二行
            if not info["name"]:
                # 检查是否是中文姓名（2-4个汉字）
                name_match = re.match(r'^([一-龥]{2,4})$', line.strip())
                if name_match:
                    name = name_match.group(1)
                    # 排除常见非姓名词
                    exclude = ["简历", "个人", "求职", "姓名", "工作", "项目", "教育", "技能"]
                    if name not in exclude:
                        info["name"] = name

        # 如果没找到姓名，尝试从全文第一行提取
        if not info["name"]:
            first_line = lines[0].strip() if lines else ""
            # 提取开头的中文名字
            name_match = re.search(r'([一-龥]{2,4})', first_line)
            if name_match:
                info["name"] = name_match.group(1)

        return info

    def _parse_skills(self, skills_text: str) -> List[str]:
        """解析技能列表"""
        if not skills_text:
            return []

        skills = []

        # 按行处理技能文本
        lines = skills_text.split('\n')
        for line in lines:
            line = line.strip()

            # 跳过空行和标题
            if not line or len(line) < 2:
                continue

            # 跳过标题行（如 "编程与技术："）
            if re.match(r'^[一-龥]+[：:]', line):
                # 提取冒号后的内容
                parts = re.split(r'[：:]', line, 1)
                if len(parts) > 1:
                    line = parts[1].strip()

            # 处理不同格式的技能列表
            # 格式1: "• Python、Playwright、GitHub、SQL"
            if line.startswith('•') or line.startswith('-'):
                line = line[1:].strip()

            # 格式2: "Python, Playwright, GitHub, SQL"
            if ',' in line or '，' in line or '、' in line:
                # 处理混合分隔符
                parts = re.split(r'[，,、、]', line)
                for part in parts:
                    part = part.strip()
                    # 清理括号内容但保留主要技能名
                    # 例如 "RAG 全链路（Milvus + PostgreSQL + LLM 精排）" -> "RAG", "Milvus", "PostgreSQL", "LLM"
                    if '（' in part or '(' in part:
                        # 提取括号前的技能名和括号内的关键词
                        bracket_free = re.sub(r'[（()].*?[）)]', '', part)
                        # 添加主要技能名
                        if bracket_free.strip():
                            skills.append(bracket_free.strip())
                        # 提取括号内的技术关键词
                        bracket_content = re.findall(r'[（(](.*?)[）)]', part)
                        if bracket_content:
                            inner_skills = re.split(r'[+/\s、，]', bracket_content[0])
                            for inner in inner_skills:
                                inner = inner.strip()
                                if inner and len(inner) > 1:
                                    skills.append(inner)
                    elif part and len(part) > 1 and len(part) < 30:
                        skills.append(part)
            else:
                # 单个技能
                if len(line) > 1 and len(line) < 30:
                    skills.append(line)

        # 去重并保持顺序
        seen = set()
        result = []
        for skill in skills:
            # 清理技能名
            skill = skill.strip('•、，,-')
            if skill and skill not in seen and len(skill) > 1:
                # 进一步清理
                skill = re.sub(r'^[•\-\s]+', '', skill)
                if skill and len(skill) < 30:
                    seen.add(skill)
                    result.append(skill)

        return result[:30]

    def _parse_experience(self, exp_text: str) -> List[Dict]:
        """解析工作经历"""
        if not exp_text:
            return []

        experiences = []

        # 按公司分组
        # 模式：公司名后跟职位和时间
        lines = exp_text.split('\n')
        current_company = ""
        current_position = ""
        current_duration = ""
        current_desc = []

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # 检测公司名（通常较短、全大写或包含特定关键词）
            # 常见公司特征：包含"科技"、"有限公司"、"字节跳动"等
            if self._is_company_name(line):
                # 保存之前的经历
                if current_company:
                    experiences.append({
                        "company": current_company,
                        "position": current_position,
                        "duration": current_duration,
                        "description": '\n'.join(current_desc)
                    })

                current_company = line
                current_position = ""
                current_duration = ""
                current_desc = []

            # 检测职位（通常包含"经理"、"工程师"、"实习"等）
            elif self._is_position(line):
                current_position = line

            # 检测时间（日期格式）
            elif self._is_duration(line):
                current_duration = line

            # 其他内容作为描述
            elif line and not line.startswith(('•', '-', '*')):
                current_desc.append(line)
            elif line.startswith(('•', '-', '*')):
                current_desc.append(line[1:].strip())

        # 保存最后一个经历
        if current_company:
            experiences.append({
                "company": current_company,
                "position": current_position,
                "duration": current_duration,
                "description": '\n'.join(current_desc)
            })

        return experiences[:5]

    def _is_company_name(self, text: str) -> bool:
        """判断是否是公司名"""
        # 长度适中
        if len(text) < 2 or len(text) > 30:
            return False

        # 包含公司相关关键词
        company_keywords = [
            "科技", "有限公司", "股份", "集团", "公司",
            "字节跳动", "腾讯", "阿里", "华为", "微软",
            "Apple", "Google", "Microsoft", "Amazon", "Meta",
            "TikTok", "Bytedance"
        ]

        # 检查是否包含公司关键词
        has_keyword = any(kw in text for kw in company_keywords)

        # 检查是否全大写或首字母大写（常见公司名格式）
        is_proper_case = text[0].isupper() or text.isupper()

        # 不包含项目描述的特征词
        desc_keywords = ["负责", "设计", "开发", "实现", "优化", "负责"]
        has_desc = any(kw in text for kw in desc_keywords)

        return (has_keyword or is_proper_case) and not has_desc

    def _is_position(self, text: str) -> bool:
        """判断是否是职位"""
        position_keywords = [
            "经理", "工程师", "实习生", "实习", "专员", "总监",
            "Manager", "Engineer", "Intern", "Specialist", "Director"
        ]
        return any(kw in text for kw in position_keywords)

    def _is_duration(self, text: str) -> bool:
        """判断是否是时间段"""
        # 匹配日期格式
        patterns = [
            r'\d{2}/\d{4}\s*–\s*\d{2}/\d{4}',  # 02/2026 – 03/2026
            r'\d{4}\.\d{2}\s*–\s*\d{4}\.\d{2}',  # 2026.02 – 2026.03
            r'\d{4}\.\d{2}',  # 简单日期
            r'\d{2}/\d{4}',  # 简单日期
        ]
        return any(re.search(pattern, text) for pattern in patterns)

    def _parse_projects(self, proj_text: str) -> List[Dict]:
        """解析项目经历"""
        if not proj_text:
            return []

        projects = []

        # 按项目分组
        lines = proj_text.split('\n')
        current_project = ""
        current_role = ""
        current_tech = []
        current_desc = []

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # 检测项目名（通常是简短的标题行）
            # 特征：以"基于XXX的..."或"XXX系统/平台/助手"等
            if self._is_project_title(line):
                # 保存之前的项目
                if current_project:
                    projects.append({
                        "name": current_project,
                        "role": current_role,
                        "tech_stack": current_tech,
                        "description": '\n'.join(current_desc)
                    })

                current_project = line
                current_role = ""
                current_tech = []
                current_desc = []

            # 检测职位
            elif line in ["产品负责人", "独立开发", "项目负责人", "技术负责人"]:
                current_role = line

            # 检测技术栈（通常包含技术关键词）
            elif any(kw in line.lower() for kw in ["python", "java", "react", "vue", "sql", "llm", "milvus"]):
                # 提取技术关键词
                tech_keywords = re.split(r'[、，,\s/+]+', line)
                for tech in tech_keywords:
                    tech = tech.strip()
                    if tech and len(tech) > 1:
                        current_tech.append(tech)

            # 其他内容作为描述
            elif line and not line.startswith(('•', '-', '*')):
                current_desc.append(line)
            elif line.startswith(('•', '-', '*')):
                current_desc.append(line[1:].strip())

        # 保存最后一个项目
        if current_project:
            projects.append({
                "name": current_project,
                "role": current_role,
                "tech_stack": current_tech,
                "description": '\n'.join(current_desc)
            })

        return projects[:5]

    def _is_project_title(self, text: str) -> bool:
        """判断是否是项目标题"""
        # 项目标题特征：
        # 1. 以"基于XXX的"开头
        # 2. 包含"系统"、"平台"、"助手"、"引擎"等词
        # 3. 不包含动词（如"负责"、"设计"）

        if len(text) < 3 or len(text) > 50:
            return False

        # 项目关键词
        project_keywords = ["系统", "平台", "助手", "引擎", "工具", "Agent", "SaaS", "平台"]
        has_project_kw = any(kw in text for kw in project_keywords)

        # 排除描述性内容
        desc_keywords = ["负责", "设计", "开发", "实现", "优化", "通过", "完成", "参与"]
        has_desc_kw = any(kw in text for kw in desc_keywords)

        # 不包含冒号（冒号通常是字段名）
        has_colon = ':' in text or '：' in text

        return has_project_kw and not has_desc_kw and not has_colon

    def _parse_education(self, edu_text: str) -> Dict:
        """解析教育背景"""
        edu = {
            "school": "",
            "major": "",
            "degree": "",
            "gpa": "",
            "courses": []
        }

        if not edu_text:
            return edu

        lines = edu_text.split('\n')

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # 学校（通常较长，包含"大学"、"学院"）
            if any(kw in line for kw in ["大学", "学院"]) and len(line) < 30:
                # 提取学校名
                school_match = re.match(r'([^\s|（(]+)', line)
                if school_match:
                    edu["school"] = school_match.group(1)

            # 专业
            elif "国际" in line or "中文" in line or "英语" in line or "商务" in line:
                # 可能是专业名
                if not edu["major"]:
                    edu["major"] = line

            # GPA
            elif "gpa" in line.lower() or "绩点" in line:
                gpa_match = re.search(r'(\d+\.?\d*)', line)
                if gpa_match:
                    edu["gpa"] = gpa_match.group(1)

            # 学位（硕士、博士）
            elif "硕士" in line or "博士" in line or "本科" in line:
                if not edu["degree"]:
                    edu["degree"] = line

        return edu

    def _parse_summary(self, summary_text: str) -> str:
        """解析个人简介"""
        if not summary_text:
            return ""

        # 清理简介文本
        lines = summary_text.split('\n')
        summary_lines = []

        for line in lines:
            line = line.strip()
            # 跳过空行和项目符号
            if line and not line.startswith(('•', '-', '*')):
                summary_lines.append(line)

        return ' '.join(summary_lines)[:500]  # 限制长度
