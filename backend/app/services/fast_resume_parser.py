"""
Offer 捕手 - 快速简历解析器
使用正则表达式进行秒级解析，失败时回退到LLM
"""
import re
from typing import Dict, Optional
from pathlib import Path


class FastResumeParser:
    """快速简历解析器 - 正则表达式解析"""

    def __init__(self, llm_client=None):
        """初始化解析器"""
        self.llm_client = llm_client

    def parse(self, file_path: str) -> Dict:
        """解析简历文件并返回结构化数据"""
        # 1. 提取文本
        text = self.extract_text(file_path)

        if not text or len(text) < 50:
            raise ValueError("文件内容为空或过少，请检查文件格式")

        # 2. 快速解析
        return self.parse_from_text(text)

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
        """提取PDF文本"""
        try:
            import PyPDF2
            text = ""
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        except ImportError:
            try:
                import pdfplumber
                text = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() + "\n"
                return text.strip()
            except ImportError:
                raise ImportError("请安装 PyPDF2 或 pdfplumber")

    def _extract_docx_text(self, file_path: Path) -> str:
        """提取Word文本"""
        try:
            from docx import Document
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except ImportError:
            raise ImportError("请安装 python-docx")

    def _extract_txt_text(self, file_path: Path) -> str:
        """提取TXT文本"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def parse_from_text(self, text: str) -> Dict:
        """从文本解析简历 - 快速模式"""
        if not text or len(text) < 50:
            raise ValueError("文本内容过少，无法解析")

        # 尝试快速解析
        result = self._fast_parse(text)
        if result and result.get("basic_info", {}).get("name"):
            return result

        # 快速解析失败，使用LLM
        if self.llm_client:
            return self.llm_client.resume_parse(text)

        raise ValueError("简历格式无法识别，请使用标准格式")

    def _fast_parse(self, text: str) -> Optional[Dict]:
        """使用正则表达式快速解析"""
        try:
            result = {
                "basic_info": self._parse_basic_info(text),
                "skills": self._parse_skills(text),
                "experience": self._parse_experience(text),
                "projects": self._parse_projects(text),
                "education": self._parse_education(text)
            }
            return result
        except Exception as e:
            print(f"快速解析失败: {e}")
            return None

    def _parse_basic_info(self, text: str) -> Dict:
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

        # 姓名 - 优先级从高到低
        name_patterns = [
            r"姓名[：:]\s*([^\n\r]{2,10})",
            r"姓\s*名[：:]\s*([^\n\r]{2,10})",
            r"求\s*职\s*人[：:]\s*([^\n\r]{2,10})",
            r"^([^\n\r]{2,4})\s*\n",  # 文档开头的名字（单独一行）
            r"^\s*([一-龥]{2,4})\s+[^\n\r]{5,}",  # 开头的中文名字后跟其他内容
        ]

        for pattern in name_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                name = match.group(1).strip()
                # 过滤掉明显不是名字的内容
                invalid_keywords = ["学校", "专业", "学历", "邮箱", "电话", "大学", "学院", "公司", "职位", "部门", "经验",
                                   "简历", "Summary", "Skills", "工作", "项目", "教育", "证书", "奖项", "语言"]
                if name and not any(x in name for x in invalid_keywords):
                    # 确保是中文名（2-4个汉字）
                    if re.match(r'^[一-龥]{2,4}$', name):
                        info["name"] = name
                        break

        # 学校
        uni_patterns = [
            r"学校[：:]\s*([^\n\r]+)",
            r"就读?于[：:]\s*([^\n\r]+)",
            r"毕业院校[：:]\s*([^\n\r]+)",
            r"([^\n\r]*[大学学院学院校][^\n\r]*)\s*\n",  # 包含"大学"或"学院"的行
        ]
        for pattern in uni_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                uni = match.group(1).strip()
                # 过滤掉明显不是学校的内容
                if uni and len(uni) < 30 and any(x in uni for x in ["大学", "学院", "学校"]):
                    info["university"] = uni
                    break
            if info["university"]:
                break

        # 专业
        major_patterns = [
            r"专业[：:]\s*([^\n\r]+)",
            r"所在专业[：:]\s*([^\n\r]+)"
        ]
        for pattern in major_patterns:
            match = re.search(pattern, text)
            if match:
                info["major"] = match.group(1).strip()
                break

        # 学历
        degree_patterns = [
            r"学历[：:]\s*([^\n\r]+)",
            r"学位[：:]\s*([^\n\r]+)"
        ]
        for pattern in degree_patterns:
            match = re.search(pattern, text)
            if match:
                info["degree"] = match.group(1).strip()
                break

        # 邮箱 - 支持带空格的格式
        email_patterns = [
            r'[\w\.-]+@[\w\.-]+\.\w+',  # 标准格式
            r'[\w\.-]+\s*@[\w\.-]+\.\w+',  # 带空格格式
        ]
        for pattern in email_patterns:
            email_match = re.search(pattern, text)
            if email_match:
                info["email"] = email_match.group().replace(' ', '')
                break

        # 电话
        phone_match = re.search(r'1[3-9]\d{9}', text)
        if phone_match:
            info["phone"] = phone_match.group()

        return info

    def _parse_skills(self, text: str) -> list:
        """解析技能列表 - 更智能的识别"""
        skills = []

        # 常见技能关键词库（精确匹配）
        tech_keywords = {
            'programming': ['Python', 'Java', 'JavaScript', 'C++', 'Go', 'Rust', 'Swift', 'Kotlin', 'TypeScript', 'PHP', 'Ruby', 'MATLAB', 'R', 'SQL', 'HTML', 'CSS', 'Playwright', 'GitHub', 'API'],
            'frameworks': ['React', 'Vue', 'Angular', 'Django', 'Flask', 'Spring', 'Express', 'Next.js', 'Nuxt.js', 'Laravel', 'Rails', 'TensorFlow', 'PyTorch', 'Keras', 'Scikit-learn', 'Pandas', 'NumPy', 'LangChain'],
            'databases': ['MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch', 'Oracle', 'SQLite', 'DynamoDB', 'Milvus'],
            'tools': ['Git', 'Docker', 'Kubernetes', 'Jenkins', 'Linux', 'Nginx', 'AWS', 'Azure', 'GCP', 'Jira', 'Confluence', 'Figma', 'Axure', 'XMind', 'SSE'],
            'ai_concepts': ['RAG', 'LLM', 'Prompt', 'Engineering', 'Agent', 'Embedding', 'Coze', 'Dify', 'LangChain', 'CLIP', 'OCR'],
            'concepts': ['机器学习', '深度学习', '自然语言处理', 'NLP', '计算机视觉', '数据分析', '产品经理', '项目管理', '敏捷开发', 'DevOps', 'CI/CD', 'Cohort', 'TEM8', 'Web3']
        }

        # 将所有关键词放入一个集合
        all_keywords = set()
        for category_keywords in tech_keywords.values():
            all_keywords.update(category_keywords)

        # 无效词黑名单
        invalid_skills = {
            '硕士', '211', '985', '本科', '博士', '上海', '北京', '深圳', '邮箱', '电话', '手机',
            '基于', '面向', '驱动', '相关', '其他', '包括', '等', '与', '和', '以及', '或者', '例如',
            '全', '精排', '召回', '向量', '检索', '精排）', '（', '）', '•', '：', '｜', '|',
            'UV', 'LTV', 'MVP', 'A/', 'B/', 'Dify/', 'Python/', 'Playwright/', '自动化'
        }

        # 方法1：从标题行（如"211硕⼠ | 提⽰词⼯程 ｜ RAG..."）提取技能
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            # 检查是否包含 | 或 ｜ 分隔符
            if '|' in line or '｜' in line:
                # 用 | 或 ｜ 分割
                parts = re.split(r'[｜|]+', line)
                for part in parts:
                    part = part.strip()
                    if part and len(part) > 1 and len(part) < 30:
                        # 检查是否是已知技能的精确或部分匹配
                        for keyword in all_keywords:
                            if keyword == part or (keyword in part and len(part) <= len(keyword) + 3):
                                if part not in skills and part not in invalid_skills:
                                    skills.append(part)
                                    break

        # 方法2：查找"Skills"后的技能列表（最准确）
        skills_section_pattern = r'Skills\s*\n([\s\S]+?)(?=\n\n\S+|\Z)'
        skills_match = re.search(skills_section_pattern, text, re.IGNORECASE)
        if skills_match:
            section_text = skills_match.group(1)
            # 提取每一行的技能（格式：• 技能1、技能2）
            bullet_items = re.findall(r'•\s*([^\n]+)', section_text)
            for item in bullet_items:
                # 分割（逗号、顿号、/、：）
                item_skills = re.split(r'[,，、/：:]+', item)
                for skill in item_skills:
                    skill = skill.strip()
                    if skill and len(skill) > 1 and len(skill) < 50:
                        # 去掉前面的标签
                        skill = re.sub(r'^[编程技术AI产品工具语言其他]+[：:：\s]+', '', skill)
                        skill = skill.strip()
                        if skill and skill not in skills and skill not in invalid_skills:
                            # 只添加看起来像技能的词
                            if any(kw in skill or skill in kw for kw in all_keywords):
                                skills.append(skill)

        # 方法3：直接搜索已知技能关键词
        for keyword in all_keywords:
            if keyword in text and keyword not in skills:
                skills.append(keyword)

        # 去重并保持顺序
        seen = set()
        result = []
        for skill in skills:
            clean_skill = skill.strip()
            # 清理技能名称
            clean_skill = re.sub(r'[｜|、，,.\s]+$', '', clean_skill)
            if clean_skill and clean_skill not in seen and clean_skill not in invalid_skills:
                seen.add(clean_skill)
                result.append(clean_skill)

        return result[:30]  # 最多返回30个技能

    def _parse_experience(self, text: str) -> list:
        """解析工作经历"""
        experiences = []

        # 大厂公司名单（用于智能识别）
        known_companies = {
            '字节跳动', '腾讯', '阿里巴巴', '阿里', '百度', '美团', '京东', '华为', '小米', '网易', '滴滴',
            'Microsoft', 'Google', 'Amazon', 'Meta', 'Apple', 'Netflix', 'Adobe', 'Oracle',
            '快手', '哔哩哔哩', 'B站', '小红书', '拼多多', '携程', '顺丰', '大疆',
            '北京瞬歌智能科技', '瞬歌智能', 'TikTok'
        }

        # 关键词黑名单（不是公司的词）
        not_company = {'教育', '学历', '技能', '项目', '负责', '参与', '设计', '开发', '实现', '构建',
                      '优化', '提升', 'Python', 'Java', 'JavaScript', 'React', 'Vue', 'Django', 'Flask',
                      'MySQL', 'Redis', 'Docker', 'Kubernetes', 'TensorFlow', 'PyTorch'}

        # 方法1：查找"Professional Experience"后的工作经历（英文格式）
        # 格式：
        # Professional Experience
        # 公司名 日期范围（可能在同一行）
        # • 职位描述...
        prof_exp_pattern = r'Professional Experience\s*\n([\s\S]+?)(?=\n\n\S+|\Z)'
        prof_match = re.search(prof_exp_pattern, text, re.IGNORECASE)
        if prof_match:
            section_text = prof_match.group(1)
            lines = section_text.split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('•') or line.startswith('-'):
                    continue

                # 尝试匹配：公司名 + 日期范围（在同一行）
                # 格式：北京瞬歌智能科技 02/2026 – 03/2026
                exp_pattern = r'([^\d]+?)\s+(\d{2}/\d{4})\s*[–—-]\s*(\d{2}/\d{4}|至今|Present)'
                exp_match = re.search(exp_pattern, line)
                if exp_match:
                    company = exp_match.group(1).strip()
                    duration = exp_match.group(2) + ' – ' + exp_match.group(3)

                    # 检查是否是已知公司或看起来像公司名
                    if (company in known_companies or
                        any(c in company for c in known_companies) or
                        (len(company) >= 2 and len(company) <= 20 and company not in not_company and
                         any(kw in company for kw in ['科技', '公司', '有限', '智能', 'TikTok', 'ByteDance']))):

                        experiences.append({
                            "company": company,
                            "position": "",
                            "duration": duration,
                            "description": ""
                        })

        if experiences:
            # 去重
            seen_companies = set()
            result = []
            for exp in experiences:
                company = exp.get('company', '')
                if company and company not in seen_companies:
                    seen_companies.add(company)
                    result.append(exp)
            if len(result) >= 1:
                return result[:5]

        # 方法2：解析日期+公司+职位格式（中文格式）
        # 匹配：2023.07-2023.12 字节跳动 后端开发实习生
        lines = text.split('\n')
        for line in lines:
            # 日期范围开头的行
            date_match = re.match(r'^(\d{4})\.(\d{1,2})\s*[-–—至]\s*(\d{4})\.(\d{1,2}|至今)', line)
            if date_match:
                start_year, start_month, end_year, end_month = date_match.groups()
                # 提取日期后的内容
                rest = line[date_match.end():].strip()
                # 按空格分割
                parts = rest.split()
                if parts:
                    # 第一部分可能是公司名
                    company = parts[0]
                    # 检查是否是已知公司或合理公司名
                    if (company in known_companies or
                        (len(company) >= 2 and len(company) <= 6 and company not in not_company)):
                        position = ' '.join(parts[1:]) if len(parts) > 1 else ''
                        experiences.append({
                            "company": company,
                            "position": position,
                            "duration": f"{start_year}.{start_month}-{end_year}.{end_month}",
                            "description": ""
                        })

        # 方法3：在工作/实习经历段落中查找
        # 查找"实习经历"、"工作经历"等标题后的内容
        exp_section_pattern = r'(?:实习|工作)(?:经历|经验)[：:\s]*\n([\s\S]+?)(?=\n\n|\n[一二三四]、|\n项目|\n技能|$)'
        exp_match = re.search(exp_section_pattern, text, re.DOTALL)
        if exp_match:
            section_text = exp_match.group(1)
            # 在这个段落里找已知公司
            for company in known_companies:
                if company in section_text:
                    # 查找公司附近的职位信息
                    company_pos = section_text.find(company)
                    context = section_text[company_pos:company_pos + 100]
                    # 查找职位关键词
                    for pos_keyword in ['实习生', '工程师', '开发', '产品经理', '运营', '设计师', '经理']:
                        if pos_keyword in context:
                            experiences.append({
                                "company": company,
                                "position": pos_keyword,
                                "duration": "",
                                "description": ""
                            })
                            break
                    else:
                        # 没找到具体职位，只添加公司
                        experiences.append({
                            "company": company,
                            "position": "",
                            "duration": "",
                            "description": ""
                        })

        # 去重：优先保留有duration和position的记录
        seen_companies = set()
        result = []
        # 先排序：有duration的优先
        experiences.sort(key=lambda x: (bool(x.get('duration')), bool(x.get('position'))), reverse=True)
        for exp in experiences:
            company = exp['company']
            if company not in seen_companies:
                seen_companies.add(company)
                result.append(exp)

        return result[:5]

    def _parse_projects(self, text: str) -> list:
        """解析项目经历"""
        projects = []

        # 优先方法1：查找"Projects"后的项目列表（英简历格式）
        # 格式：
        # Projects
        # 项目名（通常包含Agent/平台/系统/引擎/助手等关键词）
        # 产品负责人 | 独立开发（角色行，包含|）
        # • 描述内容...
        projects_section_pattern = r'Projects\s*\n([\s\S]+?)(?=\n\n\S+|\Z)'
        projects_match = re.search(projects_section_pattern, text, re.IGNORECASE)
        if projects_match:
            section_text = projects_match.group(1)
            lines = section_text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()

                if not line:
                    i += 1
                    continue

                # 跳过以 • 开头的描述行
                if line.startswith('•') or line.startswith('-'):
                    i += 1
                    continue

                # 跳过空行
                if not line or len(line) < 3:
                    i += 1
                    continue

                # 检查是否是有效的项目名（包含项目特征关键词）
                project_keywords = ['Agent', '平台', '系统', '引擎', '助手', '工具', 'SaaS', 'AI', 'RAG', '多模态', '自适应', '教师', '电商', '搜索', '导购', '备课']
                # 检查下一行是否是角色信息行（包含 | 或 ｜）
                role = ""
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if ('|' in next_line or '｜' in next_line) and not any(next_line.startswith(v) for v in ['•', '-']):
                        # 这是角色行，提取角色
                        role_parts = re.split(r'[｜|]', next_line)
                        if role_parts:
                            role = role_parts[0].strip()

                # 当前行作为项目名
                potential_name = line

                # 检查是否是有效的项目名
                is_valid_project = (
                    len(potential_name) > 5 and len(potential_name) < 100 and
                    any(kw in potential_name for kw in project_keywords) and
                    # 过滤掉明显不是项目名的词和句子
                    not any(x in potential_name for x in ['方案设计', '指标成效', '产品定位', '负责', '参与', '协助', '设计', '开发', '实现', '构建', '搭建', '优化', '改进', '维护', '管理', '协调', '主导', '推进', '提升', '降低', '建立', '解决']) and
                    # 过滤掉包含句子的行（通常是描述）
                    not any(punct in potential_name for punct in ['：', '；', '。', '；']) and
                    # 不以数字开头
                    not potential_name[0].isdigit()
                )

                if is_valid_project:
                    projects.append({
                        "name": potential_name,
                        "role": role,
                        "duration": "",
                        "tech_stack": [],
                        "description": ""
                    })
                    # 如果下一行是角色行，跳过它
                    if role and i + 1 < len(lines):
                        i += 2
                        continue
                i += 1

        if projects:
            # 去重
            seen = set()
            result = []
            for p in projects:
                name = p.get('name', '')
                if name and name not in seen:
                    seen.add(name)
                    result.append(p)
            if len(result) >= 1:
                return result[:5]

        # 备用方法：原有的解析逻辑
        # 项目关键词
        project_keywords = {'平台', '系统', '网站', '应用', 'APP', '小程序', '管理', '分析', '推荐',
                           '搜索', '商城', '后台', '中台', '工具', '服务', '模块', '组件'}

        # 方法2：解析"项目一/二/三："或"项目1/2/3："格式
        project_num_pattern = r'项目[一二三四五六七八九十\d]+[：:]\s*([^\n]+)'
        matches = re.finditer(project_num_pattern, text)
        for match in matches:
            content = match.group(1).strip()
            lines = content.split('\n')
            project_name = lines[0].strip('、，。-')
            if project_name and len(project_name) > 2:
                projects.append({
                    "name": project_name,
                    "role": "",
                    "duration": "",
                    "tech_stack": [],
                    "description": ""
                })

        # 方法3：查找"项目名称："或"项目名："格式
        name_patterns = [
            r'项目名称[：:]\s*([^\n，。]+)',
            r'项目名[：:]\s*([^\n，。]+)'
        ]
        for pattern in name_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                name = match.group(1).strip()
                if name and len(name) > 2:
                    projects.append({
                        "name": name,
                        "role": "",
                        "duration": "",
                        "tech_stack": [],
                        "description": ""
                    })

        # 去重
        seen = set()
        result = []
        for proj in projects:
            name = proj.get('name', '').strip()
            name = re.sub(r'^项目[一二三四\d]+[：:]', '', name)
            name = re.sub(r'^项目名称[：:]', '', name)
            name = name.strip()
            if name and len(name) > 2 and name not in seen:
                seen.add(name)
                proj['name'] = name
                result.append(proj)

        return result[:5]

    def _parse_education(self, text: str) -> Dict:
        """解析教育背景"""
        edu = {
            "school": "",
            "major": "",
            "degree": "",
            "gpa": "",
            "courses": []
        }

        # 大学后缀关键词
        university_keywords = ['大学', '学院', '学校', '理工', '师范', '科技', '工业', '交通', '财经']

        # 方法1：查找"Education"后的教育信息（英文格式）
        # 格式：
        # Education
        # 学校名
        # 日期范围
        # 专业
        # • 其他信息...
        edu_pattern = r'Education\s*\n([\s\S]+?)(?=\n\n\S+|\Z)'
        edu_match = re.search(edu_pattern, text, re.IGNORECASE)
        if edu_match:
            section_text = edu_match.group(1)
            lines = section_text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue

                # 跳过描述行
                if line.startswith('•') or line.startswith('-'):
                    i += 1
                    continue

                # 检查是否是学校名（非日期行，非描述行）
                if (not re.match(r'\d{2}/\d{4}', line) and
                    len(line) > 2 and len(line) < 30):
                    # 检查是否包含大学关键词
                    if any(kw in line for kw in university_keywords):
                        edu["school"] = line

                        # 查找日期后的专业信息
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            # 如果下一行是日期，再下一行可能是专业
                            if re.match(r'\d{2}/\d{4}', next_line) and i + 2 < len(lines):
                                major_line = lines[i + 2].strip()
                                if not major_line.startswith('•') and len(major_line) > 2:
                                    edu["major"] = major_line
                        break
                i += 1

        # 方法2：解析"教育背景"标题下的内容（中文格式）
        if not edu["school"]:
            cn_edu_pattern = r'教育背景[：:\s]*\n([\s\S]+?)(?=\n\n|\n技能|\n实习|\n项目|\n工作|$)'
            cn_edu_match = re.search(cn_edu_pattern, text, re.DOTALL)
            if cn_edu_match:
                section = cn_edu_match.group(1)
                lines = section.strip().split('\n')
                if lines:
                    first_line = lines[0].strip()
                    # 尝试解析：学校 专业 学位 年份
                    parts = first_line.split()
                    if len(parts) >= 3:
                        # 找包含大学关键词的部分
                        for i, part in enumerate(parts):
                            if any(kw in part for kw in university_keywords):
                                edu["school"] = part
                                # 专业通常在前面
                                if i > 0:
                                    edu["major"] = parts[i-1]
                                break

                        # 找学历关键词
                        degree_keywords = ['本科', '硕士', '博士', '专科']
                        for part in parts:
                            if any(kw in part for kw in degree_keywords):
                                edu["degree"] = part
                                break

        # 方法3：如果没有找到，尝试特定格式
        if not edu["school"]:
            # 格式：XX大学 XX专业 本科 2020-2024
            line_pattern = r'([^\s]{2,10}(?:大学|学院))\s+([^\s]{2,15}(?:专业|系))?\s*([^0-9]{2,10})?\s*(\d{4})?'
            for line in text.split('\n'):
                match = re.search(line_pattern, line)
                if match:
                    school, major, degree, year = match.groups()
                    if school:
                        edu["school"] = school
                    if major:
                        edu["major"] = major
                    if degree:
                        edu["degree"] = degree
                    break

        # 方法4：查找单独的字段
        if not edu["school"]:
            for pattern in [r"学校[：:]\s*([^\n\r]+)", r"毕业院校[：:]\s*([^\n\r]+)", r"就读[于于]?[：:]\s*([^\n\r]+)"]:
                match = re.search(pattern, text)
                if match:
                    edu["school"] = match.group(1).strip()
                    break

        if not edu["major"]:
            for pattern in [r"专业[：:]\s*([^\n\r]+)", r"所在专业[：:]\s*([^\n\r]+)"]:
                match = re.search(pattern, text)
                if match:
                    edu["major"] = match.group(1).strip()
                    break

        if not edu["degree"]:
            for pattern in [r"学历[：:]\s*([^\n\r]+)", r"学位[：:]\s*([^\n\r]+)", r"[本硕博]士?[：:\s]*([^\n\r]+)"]:
                match = re.search(pattern, text)
                if match:
                    edu["degree"] = match.group(1).strip()
                    break

        return edu
