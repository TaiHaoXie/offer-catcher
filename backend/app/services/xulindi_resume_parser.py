"""
针对徐琳迪简历格式的专用解析器
基于实际 PDF 格式定制
"""
import re
from typing import Dict, Optional


def normalize_pdf_text(text: str) -> str:
    """标准化 PDF 文本，处理特殊字符"""
    # 康熙部首 → 常用汉字
    char_map = {
        '⼤': '大',  # ⼤ → 大
        '⼉': '学',  # ⼥ → 学 (如果有)
        '⼾': '工',  # ⼯ → 工 (如果有)
    }
    for old, new in char_map.items():
        text = text.replace(old, new)
    return text


class XulindiResumeParser:
    """针对特定格式的简历解析器"""

    def parse(self, text: str) -> Dict:
        """从文本解析简历"""
        # 标准化 PDF 文本（处理特殊字符）
        text = normalize_pdf_text(text)

        result = {
            "basic_info": self._parse_basic_info(text),
            "skills": self._parse_skills(text),
            "experience": self._parse_experience(text),
            "projects": self._parse_projects(text),
            "education": self._parse_education(text)
        }
        return result

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

        lines = text.split('\n')

        # 第一行是姓名
        if lines and lines[0].strip():
            name = lines[0].strip()
            if len(name) >= 2 and len(name) <= 5:
                info["name"] = name

        # 从第二行提取标签（211硕⼠ | 提⽰词⼯程 等）
        for i, line in enumerate(lines[:10]):
            line = line.strip()
            # 邮箱 - 支持空格
            email_match = re.search(r'[\w\.-]+\s*@\s*[\w\.-]+\.\w+', line)
            if email_match:
                info["email"] = email_match.group().replace(' ', '').replace(' ', '')

            # 电话 - 11位数字
            phone_match = re.search(r'1[3-9]\d{9}', line)
            if phone_match:
                info["phone"] = phone_match.group()

        return info

    def _parse_skills(self, text: str) -> list:
        """解析技能"""
        skills = []

        # 从 header 行提取: 211硕⼠ | 提⽰词⼯程 ｜ RAG | Dify | Coze | Python
        lines = text.split('\n')
        for i, line in enumerate(lines[:5]):
            if '|' in line or '｜' in line:
                # 分割技能
                parts = re.split(r'[｜|]+', line)
                for part in parts:
                    part = part.strip()
                    # 过滤掉学位信息和地点
                    if part and not any(x in part for x in ['硕', '博', '本', '211', '985', '上海', '北京', '邮箱', '电话', '手机', '@', '163.com']):
                        if len(part) > 1 and len(part) < 30:
                            skills.append(part)

        # 从 Skills 部分提取
        skills_pattern = r'Skills\s*\n([\s\S]+?)(?=\n\n\S+|\Z)'
        skills_match = re.search(skills_pattern, text, re.IGNORECASE)
        if skills_match:
            section = skills_match.group(1)
            # 提取每一行，包括带标签的
            section_lines = section.split('\n')
            for line in section_lines:
                line = line.strip()
                if not line or line == '•':
                    continue

                # 移除开头的 •
                line = re.sub(r'^•\s*', '', line)

                # 移除标签（编程与技术：、AI 技术栈：等）- 使用更宽泛的匹配
                line = re.sub(r'^[^：:]+[：:：]\s*', '', line)

                # 分割（顿号、斜杠、逗号、空格、括号）
                # 先替换括号为空格
                line = re.sub(r'[（()].*?[）)]', ' ', line)
                item_skills = re.split(r'[、/／,，\s（）()]+', line)
                for skill in item_skills:
                    skill = skill.strip()
                    # 过滤掉无效词和过短的词
                    invalid_prefix = ['技术栈', '框架', '编程', '自动化', '语言', '产品', '其他', '实习', '工作']
                    invalid_words = ['实习经验', '摄像摄影', '非遗纪录⽚', '商拍拍摄', '资格证书', '教师资格证', '俄语基础', '⾼中', '英语', '等', '与', '和', '全链路', '精排', '召回']

                    # 检查是否以无效前缀开头
                    if any(skill.startswith(p) for p in invalid_prefix):
                        # 尝试提取有效部分
                        for p in invalid_prefix:
                            if skill.startswith(p):
                                skill = skill[len(p):].strip('：:：、')
                                break

                    if skill and len(skill) > 1 and not any(x in skill for x in invalid_words):
                        skills.append(skill)

        # 去重并清理
        seen = set()
        result = []
        for skill in skills:
            skill = skill.strip()
            if skill and skill not in seen:
                # 移除所有空格
                skill = re.sub(r'\s+', '', skill)
                if skill and len(skill) > 1 and len(skill) < 30:
                    seen.add(skill)
                    result.append(skill)

        return result[:20]

    def _parse_experience(self, text: str) -> list:
        """解析工作经历"""
        experiences = []

        # 查找 Professional Experience 部分，排除 Education
        exp_pattern = r'Professional Experience\s*\n([\s\S]+?)(?=\n\nEducation|\nEducation|\n\n\S+|\Z)'
        exp_match = re.search(exp_pattern, text, re.IGNORECASE)
        if exp_match:
            section = exp_match.group(1)
            lines = section.split('\n')

            for i, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith('•'):
                    continue

                # 匹配：公司名 + 日期范围
                # 格式：北京瞬歌智能科技 02/2026 – 03/2026
                match = re.search(r'([^\d]+?)\s+(\d{2}/\d{4})\s*[–—-]\s*(\d{2}/\d{4}|至今|Present)', line)
                if match:
                    company = match.group(1).strip()
                    duration = f"{match.group(2)} – {match.group(3)}"

                    # 检查是否是大学（排除教育背景）
                    if '大学' in company or '学院' in company:
                        continue

                    # 检查是否包含职位关键词
                    position = ""
                    for pos_kw in ['产品经理', '经理', '实习生', '实习', '工程师', '开发', '运营', '设计师']:
                        if pos_kw in line:
                            position = pos_kw
                            break

                    experiences.append({
                        "company": company,
                        "position": position,
                        "duration": duration,
                        "description": ""
                    })

        return experiences[:5]

    def _parse_projects(self, text: str) -> list:
        """解析项目经历"""
        projects = []

        # 查找 Projects 部分，排除 Professional Experience
        proj_pattern = r'Projects\s*\n([\s\S]+?)(?=\n\nProfessional Experience|\nProfessional Experience|\n\n\S+|\Z)'
        proj_match = re.search(proj_pattern, text, re.IGNORECASE)
        if proj_match:
            section = proj_match.group(1)
            lines = section.split('\n')

            for i, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith('•'):
                    continue

                # 检查是否是项目名（包含项目关键词）
                project_keywords = ['Agent', '平台', '系统', '引擎', '助手', '工具', 'SaaS', 'AI', 'RAG', '多模态', '自适应', '教师', '电商', '搜索', '导购', '备课']

                if any(kw in line for kw in project_keywords):
                    # 检查下一行是否是角色行（包含 | ）
                    role = ""
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if '|' in next_line or '｜' in next_line:
                            role = next_line.split('|')[0].split('｜')[0].strip()

                    # 过滤掉描述性句子和包含实习/工作相关的
                    if not any(x in line for x in ['：', '；', '。', '；', '•', '提升', '降低', '建立', '解决', '支持', '通过', '实习', '产品经理', '标注']):
                        if len(line) > 5 and len(line) < 100:
                            projects.append({
                                "name": line,
                                "role": role,
                                "duration": "",
                                "tech_stack": [],
                                "description": ""
                            })

        return projects[:5]

    def _parse_education(self, text: str) -> Dict:
        """解析教育背景"""
        edu = {
            "school": "",
            "major": "",
            "degree": "",
            "gpa": "",
            "courses": []
        }

        # 查找 Education 部分
        edu_pattern = r'Education\s*\n([\s\S]+?)(?=\n\nSkills|\nSkills|\Z)'
        edu_match = re.search(edu_pattern, text, re.IGNORECASE)
        if edu_match:
            section = edu_match.group(1)
            lines = section.split('\n')

            # 找到第一个学校（通常是最高学历/当前学历）
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # 格式：学校名 日期范围（在同一行）
                # 例如：郑州⼤学 09/2024 – 06/2027
                school_date_match = re.match(r'([^\d]+大学[^\d]*)\s+(\d{2}/\d{4})', line)
                if not school_date_match:
                    school_date_match = re.match(r'([^\d]+学院[^\d]*)\s+(\d{2}/\d{4})', line)

                if school_date_match and not edu["school"]:
                    school = school_date_match.group(1).strip()
                    date_part = school_date_match.group(2)

                    # 查找专业（下一行）
                    major = ""
                    if i + 1 < len(lines):
                        major_line = lines[i + 1].strip()
                        # 如果不是 • 开头且不是另一条学校记录，则认为是专业
                        if not major_line.startswith('•') and not re.match(r'.*\d{2}/\d{4}', major_line):
                            major = major_line

                    edu["school"] = school
                    edu["major"] = major
                    # 根据年份判断学历（2024-2027 是硕士）
                    if "2024" in date_part or "2025" in date_part or "2026" in date_part or "2027" in date_part:
                        edu["degree"] = "硕士"
                    else:
                        edu["degree"] = "本科"
                    break  # 只取第一个学校

        return edu
