"""
Offer 捕手 - 深度分析服务
提供JD逐句拆解质询、双栏diff可视化、动词强度映射功能
"""
import re
from typing import Dict, List, Tuple
from itertools import product


class DeepAnalysisService:
    """深度分析服务 - JD逐句拆解与证据质询"""

    # 动词强度层级（从高到低）
    VERB_HIERARCHY = {
        # 最高级 - 完全负责/主导
        "主导": 9, "负责": 9, "独立完成": 9, "全面负责": 9,
        "own": 9, "lead": 9, "head": 9, "drive": 9,

        # 高级 - 建设性/创造性工作
        "构建": 8, "搭建": 8, "设计": 8, "开发": 8, "实现": 8,
        "build": 8, "design": 8, "develop": 8, "implement": 8,

        # 中高级 - 推进/执行
        "推进": 7, "执行": 7, "实施": 7, "落地": 7, "优化": 7,
        "execute": 7, "implement": 7, "optimize": 7,

        # 中级 - 深度参与
        "参与": 6, "协助": 5, "配合": 5, "支持": 5,
        "assist": 5, "support": 5, "help": 4, "help": 4,

        # 低级 - 边缘参与
        "学习": 3, "了解": 2, "熟悉": 2,
        "learn": 3, "study": 3, "understand": 2, "know": 2
    }

    def __init__(self, llm_client=None):
        """初始化分析服务"""
        self.llm_client = llm_client

    def analyze(self, resume_data: Dict, job_data: Dict) -> Dict:
        """执行完整深度分析"""
        # 获取JD文本（支持多种格式）
        jd_text = self._extract_jd_text(job_data)

        # 1. JD逐句拆解质询
        sentence_analysis = self._analyze_jd_sentences(
            jd_text,
            resume_data
        )

        # 2. 双栏diff可视化
        diff_table = self._generate_diff_table(
            sentence_analysis,
            job_data,
            resume_data
        )

        # 3. 动词强度映射
        verb_analysis = self._analyze_verbs(
            jd_text,
            resume_data
        )

        return {
            "sentence_analysis": sentence_analysis,
            "diff_table": diff_table,
            "verb_analysis": verb_analysis
        }

    def _extract_jd_text(self, job_data: Dict) -> str:
        """从job_data中提取文本"""
        # 尝试多种可能的字段
        if isinstance(job_data, dict):
            # 直接的requirements字段
            req = job_data.get("requirements", "")
            if isinstance(req, str):
                return req

            # 尝试组合多个字段
            parts = []
            for field in ["description", "responsibilities", "requirements"]:
                value = job_data.get(field, "")
                if value:
                    if isinstance(value, str):
                        parts.append(value)
                    elif isinstance(value, list):
                        parts.extend(value)

            return "\n".join(parts) if parts else str(job_data)

        return str(job_data)

    def _split_jd_sentences(self, jd_text: str) -> List[str]:
        """将JD按句子拆分"""
        if not jd_text:
            return []

        # 按句号、分号、换行拆分
        separators = ['。', '；', '\n', '.', ';']
        sentences = [jd_text]

        for sep in separators:
            new_sentences = []
            for s in sentences:
                parts = s.split(sep)
                new_sentences.extend([p.strip() for p in parts if p.strip()])
            sentences = new_sentences

        # 过滤掉太短的句子
        return [s for s in sentences if len(s) > 5]

    def _analyze_jd_sentences(
        self,
        jd_requirements: str,
        resume_data: Dict
    ) -> List[Dict]:
        """分析每个JD句子，查找简历中的证据"""
        jd_sentences = self._split_jd_sentences(jd_requirements)

        results = []
        for sentence in jd_sentences:
            # 提取关键词
            keywords = self._extract_keywords(sentence)

            # 查找证据
            evidence = self._find_evidence(keywords, resume_data)

            # 判断证据强度
            strength = self._judge_evidence_strength(evidence, keywords)

            results.append({
                "jd_sentence": sentence,
                "keywords": keywords,
                "evidence": evidence,
                "strength": strength,  # "direct", "indirect", "missing"
                "suggestion": self._generate_sentence_suggestion(sentence, evidence, strength)
            })

        return results

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        # 简单的关键词提取：取名词性词汇
        # 这里简化处理，提取看起来像关键词的词
        keywords = []

        # 常见技能词模式
        skill_patterns = [
            r'(Python|Java|JavaScript|C\+\+|Go|Rust)',
            r'(机器学习|深度学习|NLP|推荐系统|算法)',
            r'(数据分析|数据挖掘|大数据)',
            r'(产品经理|项目管理|需求分析)',
            r'(React|Vue|Angular|Node\.js)',
        ]

        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            keywords.extend(matches)

        # 去重
        return list(set(keywords))

    def _find_evidence(self, keywords: List[str], resume_data: Dict) -> List[Dict]:
        """在简历中查找关键词的证据"""
        evidence = []

        # 搜索区域：技能、经历、项目
        search_areas = [
            ("skills", resume_data.get("skills", [])),
            ("experience", resume_data.get("experience", [])),
            ("projects", resume_data.get("projects", []))
        ]

        for area_name, area_data in search_areas:
            if not area_data:
                continue

            for keyword in keywords:
                keyword_lower = keyword.lower()

                if area_name == "skills":
                    # 技能列表直接匹配
                    for skill in area_data:
                        if keyword_lower in skill.lower():
                            evidence.append({
                                "type": "skill",
                                "keyword": keyword,
                                "content": skill,
                                "match_type": "direct"
                            })
                else:
                    # 经历/项目需要搜索描述
                    for item in area_data:
                        desc = item.get("description", "")
                        title = item.get("name", item.get("title", ""))

                        if keyword_lower in desc.lower() or keyword_lower in title.lower():
                            evidence.append({
                                "type": area_name[:-1],  # experience -> experienc, projects -> project
                                "keyword": keyword,
                                "content": title or desc[:50],
                                "match_type": "direct" if keyword_lower in desc.lower() else "indirect"
                            })

        return evidence

    def _judge_evidence_strength(self, evidence: List[Dict], keywords: List[str]) -> str:
        """判断证据强度"""
        if not evidence:
            return "missing"

        # 检查是否有直接提及
        has_direct = any(e.get("match_type") == "direct" for e in evidence)

        # 检查关键词覆盖率
        covered_keywords = set(e.get("keyword", "") for e in evidence)
        coverage = len(covered_keywords) / max(len(keywords), 1)

        if has_direct and coverage >= 0.5:
            return "direct"
        elif coverage > 0:
            return "indirect"
        else:
            return "missing"

    def _generate_sentence_suggestion(
        self,
        jd_sentence: str,
        evidence: List[Dict],
        strength: str
    ) -> str:
        """生成句子级别的建议"""
        if strength == "direct":
            return "[已证实] 已有直接证据，保持现有表述"
        elif strength == "indirect":
            return f"[需强化] 有间接提及，建议在经历描述中明确使用：{jd_sentence[:20]}..."
        else:
            return f"[需补充] 完全缺失，建议补充相关经历或项目"

    def _generate_diff_table(
        self,
        sentence_analysis: List[Dict],
        job_data: Dict,
        resume_data: Dict
    ) -> List[Dict]:
        """生成双栏diff对照表"""
        table = []

        for analysis in sentence_analysis:
            strength = analysis["strength"]
            # 状态标记
            if strength == "direct":
                status = "[匹配]"
            elif strength == "indirect":
                status = "[弱匹配]"
            else:
                status = "[缺失]"

            # 证据内容
            if analysis["evidence"]:
                evidence_text = "; ".join([
                    e.get("content", "")[:30] for e in analysis["evidence"][:2]
                ])
            else:
                evidence_text = "(空)"

            table.append({
                "jd_requirement": analysis["jd_sentence"][:50],
                "evidence": evidence_text,
                "status": status,
                "suggestion": analysis["suggestion"]
            })

        return table

    def _analyze_verbs(self, jd_requirements: str, resume_data: Dict) -> Dict:
        """分析动词强度差异"""
        # 提取JD中的动词
        jd_verbs = self._extract_verbs(jd_requirements)

        # 提取简历中的动词
        resume_verbs = []
        for exp in resume_data.get("experience", []):
            desc = exp.get("description", "")
            resume_verbs.extend(self._extract_verbs(desc))

        for proj in resume_data.get("projects", []):
            desc = proj.get("description", "")
            resume_verbs.extend(self._extract_verbs(desc))

        # 对比动词强度
        verb_gaps = []
        for jd_verb in jd_verbs:
            jd_strength = self.VERB_HIERARCHY.get(jd_verb, 5)

            # 查找简历中对应领域的动词
            # 简化处理：直接对比动词强度
            max_resume_strength = 0
            matching_resume_verb = None

            for resume_verb in resume_verbs:
                resume_strength = self.VERB_HIERARCHY.get(resume_verb, 5)
                if resume_strength > max_resume_strength:
                    max_resume_strength = resume_strength
                    matching_resume_verb = resume_verb

            gap = jd_strength - max_resume_strength

            if gap > 0:
                # 找到更强的候选词
                suggestions = self._get_stronger_verbs(matching_resume_verb, gap)

                verb_gaps.append({
                    "jd_verb": jd_verb,
                    "jd_strength": jd_strength,
                    "resume_verb": matching_resume_verb or "未找到",
                    "resume_strength": max_resume_strength,
                    "gap": gap,
                    "suggestions": suggestions
                })

        return {
            "jd_verbs": jd_verbs,
            "resume_verbs": list(set(resume_verbs)),
            "gaps": verb_gaps
        }

    def _extract_verbs(self, text: str) -> List[str]:
        """从文本中提取动词"""
        verbs = []

        # 查找层级词典中的动词
        for verb in self.VERB_HIERARCHY.keys():
            if verb in text:
                verbs.append(verb)

        return verbs

    def _get_stronger_verbs(self, current_verb: str, gap: int) -> List[str]:
        """获取更强的动词建议"""
        if not current_verb:
            return ["主导", "负责", "构建", "设计"]

        current_strength = self.VERB_HIERARCHY.get(current_verb, 5)
        target_strength = current_strength + gap

        suggestions = []
        for verb, strength in self.VERB_HIERARCHY.items():
            if strength >= target_strength and strength > current_strength:
                suggestions.append(verb)

        return list(set(suggestions))[:5]
