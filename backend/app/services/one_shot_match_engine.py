"""
Offer 捕手 - 单 prompt 简历匹配分析引擎
"""

import io
import json
import logging
import os
import re
import asyncio
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv
from litellm import acompletion

from app.utils.pdf_parser import get_pdf_parser

logger = logging.getLogger(__name__)

load_dotenv()


class OneShotMatchEngine:
    """最小可用版本：单 prompt 输出招聘官报告，再规范化给前端使用"""

    def __init__(self):
        self.api_key = os.getenv("KIMI_API_KEY", "")
        self.api_base = os.getenv("KIMI_API_BASE", "https://api.moonshot.cn/v1")
        self.pdf_parser = get_pdf_parser()
        # 结果缓存：同一份简历 + 同一个 JD，返回完全一致的分析结果。
        # 目的：消除"连点两次结果跳级"的体验问题（同样输入本就该给同样输出）。
        self._result_cache: Dict[str, Dict[str, Any]] = {}

        # litellm 在使用 openai/* 兼容模型时，会优先读取 OPENAI_API_KEY。
        # 这里把 Kimi 密钥显式映射过去，避免流式匹配接口启动后拿不到凭证。
        if self.api_key:
            os.environ["OPENAI_API_KEY"] = self.api_key

    # 算分逻辑版本号：每次改动评分/锚定逻辑就 +1，让历史旧缓存自动失效，
    # 避免"改了算法但还命中旧结果"（专业对口修复后必须 bump）。
    SCORING_LOGIC_VERSION = "v8-buffer-tuned"

    @staticmethod
    def _make_cache_key(resume_text: str, jd_text: str) -> str:
        import hashlib
        raw = (
            OneShotMatchEngine.SCORING_LOGIC_VERSION + "\x00"
            + (resume_text or "").strip() + "\x00"
            + (jd_text or "").strip()
        )
        return hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()

    def _extract_resume_text(self, file_bytes: bytes, filename: str) -> str:
        """提取简历文本"""
        try:
            if filename.lower().endswith(".pdf"):
                text = self.pdf_parser.extract_text(file_bytes, filename)
                if text and len(text) > 100:
                    logger.info(f"PyMuPDF 提取成功: {len(text)} 字符")
                    return text
            elif filename.lower().endswith(".docx"):
                from docx import Document
                doc = Document(io.BytesIO(file_bytes))
                return "\n".join([p.text for p in doc.paragraphs])
            return file_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"提取简历文本失败: {e}")
            raise

    def _extract_json_object(self, text: str) -> Dict[str, Any]:
        """尽量稳健地从模型输出中提取 JSON"""
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
            stripped = re.sub(r"```$", "", stripped).strip()

        try:
            return json.loads(stripped)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", stripped)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
            # 输出被截断（max_tokens 触顶）时，尝试补全闭合后再解析，尽量抢救已生成的内容
            return self._loads_truncated_json(stripped)

    def _loads_truncated_json(self, text: str) -> Dict[str, Any]:
        """抢救被截断的 JSON：去掉最后一段不完整内容，并补齐括号/引号后再解析。"""
        start = text.find("{")
        if start == -1:
            raise ValueError("未找到 JSON 起始")
        s = text[start:]

        # 逐字符扫描，记录最后一个“完整键值对结束”的位置（栈回到对象内、且在引号外）
        in_str = False
        escape = False
        stack: List[str] = []
        last_safe = -1
        for i, ch in enumerate(s):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if stack:
                    stack.pop()
            elif ch == "," and len(stack) >= 1:
                last_safe = i  # 一个元素/键值对刚结束的位置

        if last_safe == -1:
            raise ValueError("无法定位可抢救的 JSON 片段")

        # 截到最后一个安全逗号前，再按当时栈深度补齐闭合符号
        head = s[:last_safe]
        # 重新计算 head 结束时还未闭合的括号
        in_str = False
        escape = False
        stack = []
        for ch in head:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if stack:
                    stack.pop()
        closing = "".join("}" if c == "{" else "]" for c in reversed(stack))
        return json.loads(head + closing)

    def _extract_jd_requirements(self, jd_text: str, limit: int = 8) -> List[str]:
        """从 JD 中抽取 5-8 条较像硬要求的内容"""
        lines: List[str] = []
        for raw_line in jd_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line = re.sub(r"^[\-\d\.\)\(、\s]+", "", line)
            if len(line) < 4:
                continue
            lines.append(line)

        priority_markers = ["要求", "熟悉", "掌握", "负责", "能力", "经验", "技能", "数据", "AI", "产品"]
        ranked = sorted(
            lines,
            key=lambda line: (
                -sum(marker in line for marker in priority_markers),
                -len(line)
            )
        )

        unique: List[str] = []
        seen = set()
        for line in ranked:
            if line not in seen:
                unique.append(line)
                seen.add(line)
            if len(unique) >= limit:
                break
        return unique

    def _smart_truncate_resume_text(
        self,
        resume_text: str,
        jd_requirements: List[str],
        max_chars: int = 2600
    ) -> str:
        """智能截取：保留开头概览 + 与 JD 相关的关键片段"""
        if len(resume_text) <= max_chars:
            return resume_text

        head = resume_text[:1200]
        snippets: List[str] = []

        for req in jd_requirements:
            keywords = re.findall(r"[A-Za-z0-9\+\#\.]+|[\u4e00-\u9fff]{2,}", req)
            for keyword in keywords[:4]:
                idx = resume_text.lower().find(keyword.lower())
                if idx == -1:
                    continue
                start = max(0, idx - 80)
                end = min(len(resume_text), idx + 180)
                snippet = resume_text[start:end].strip()
                if snippet and snippet not in snippets:
                    snippets.append(snippet)
            if len("\n".join(snippets)) > 1200:
                break

        tail = resume_text[-300:] if len(resume_text) > 2200 else ""
        combined = head
        if snippets:
            combined += "\n\n[与JD相关的简历片段]\n" + "\n---\n".join(snippets[:6])
        if tail:
            combined += "\n\n[简历尾部补充]\n" + tail
        return combined[:max_chars]

    def _format_atoms_for_prompt(self, atoms: Optional[List[Dict[str, Any]]], limit: int = 8) -> str:
        """将经历原子库压缩为可供模型引用的结构化证据"""
        if not atoms:
            return "无可用经历原子。"

        selected = atoms[:limit]
        lines: List[str] = []
        for atom in selected:
            atom_type = atom.get("type", "")
            title = atom.get("title", "")
            company = atom.get("company", "")
            description = atom.get("description", "")
            skills = ", ".join((atom.get("skills") or [])[:5])
            lines.append(
                f"- [{atom_type}] {title} | {company} | 技能: {skills} | 描述: {description[:120]}"
            )
        return "\n".join(lines)

    def _infer_match_level(self, score: int) -> str:
        if score >= 85:
            return "A级"
        if score >= 70:
            return "B级"
        if score >= 55:
            return "C级"
        return "D级"

    def _sharpen_verdict(self, verdict: str, score: int, gaps: List[Any], knockout_blocked: bool = False) -> str:
        """把一句话判断收得更像自然的招聘官评语"""
        text = str(verdict or "").strip()

        # 硬门槛受限（如专业不对口/学历不够）优先：明确告诉用户"不是简历不行，是岗位卡硬门槛"，
        # 保留诊断温度，避免一句冷冰冰的"背景有明显距离"。
        if knockout_blocked and score < 70:
            return "简历本身有亮点，分数偏低主要是这个岗位卡了硬门槛（专业/学历/必备技能不完全匹配）；这份经历投到更对口的方向会更有竞争力。"

        lowered = text.replace("，", "").replace("。", "")
        if any(marker in lowered for marker in ["面试中大概率会被追问", "不足以支撑高分", "呈现得不够直接", "不够完整"]):
            return text

        gap_text = " ".join(
            str((item.get("gap") or item.get("title") or "")) if isinstance(item, dict) else str(item)
            for item in (gaps or [])
        )

        if any(keyword in gap_text for keyword in ["跨团队", "协作", "沟通"]):
            return "经历相关，但简历里对协作能力的体现还不够具体，面试中大概率会被追问跨团队细节。"
        if any(keyword in gap_text for keyword in ["B端", "toB", "商业化", "业务"]):
            return "项目背景不错，但 B 端视角还不够清楚，招聘方未必能快速看出你对业务场景的理解。"
        if any(keyword in gap_text for keyword in ["0到1", "从0到1", "闭环", "落地"]):
            return "项目经历有亮点，但从 0 到 1 的证据还不够扎实，当前写法不足以把这部分优势讲清楚。"
        if score >= 70:
            return "经历本身有竞争力，但简历还没把关键价值写得足够直接，面试中大概率会围绕核心 gap 深挖。"
        if score >= 55:
            return "不是背景不行，而是当前写法还不够完整；建议先补强最关键的证据，再去投递。"
        return "当前简历和岗位要求还有明显距离，直接投递通过初筛的概率不高，建议先补强经历或重写表述。"

    def _normalize_gap_priorities(self, gaps: List[str]) -> List[str]:
        normalized: List[str] = []
        for idx, gap in enumerate(gaps or []):
            text = str(gap).strip()
            if text.startswith(("P0:", "P1:", "P2:")):
                normalized.append(text)
                continue
            if idx == 0:
                normalized.append(f"P1: {text}")
            else:
                normalized.append(f"P2: {text}")
        return normalized[:3]

    def _normalize_action_plan(self, actions: List[str]) -> List[str]:
        normalized: List[str] = []
        for action in actions or []:
            text = str(action).strip()
            if not text:
                continue
            if all(marker in text for marker in ["动作：", "修改对象：", "预期效果："]):
                normalized.append(text)
            else:
                normalized.append(
                    f"动作：{text}；修改对象：简历对应经历描述；预期效果：让招聘方更清楚看到匹配证据"
                )
        return normalized[:3]

    def _refine_plain_requirement(self, original_text: str, plain_text: str, requirement_type: str) -> str:
        """把过于空泛的 JD 翻译收紧成更像招聘官真实考点的表述"""
        original = str(original_text or "").strip()
        plain = str(plain_text or "").strip()
        rtype = str(requirement_type or "").strip().lower()
        source = f"{original} {plain}"
        lower_source = source.lower()

        if ("b端" in lower_source or "to b" in lower_source or "tob" in lower_source) and ("产品" in source or rtype == "product_judgment"):
            return "能从业务流程、角色权限、协作链路和交付价值的角度理解并设计 B 端产品"
        if "owner" in lower_source or "推动" in source or "落地" in source:
            return "能对一个模块或项目承担结果责任，并把事情推进到真正交付"
        if "0-1" in source or "从0到1" in source:
            return "参与过一个模块从需求定义、方案设计到上线落地的完整过程"
        if "表达" in source or "阐述" in source or rtype == "communication":
            return "能把项目背景、你的职责、方案取舍和结果讲清楚，方便招聘方快速判断"
        if "agent" in lower_source or "dify" in lower_source or "coze" in lower_source or "扣子" in source:
            return "至少实际接触过 Agent / 工作流平台，并能说明你用它做过什么"
        return plain or original

    def _split_requirement_concepts(self, original_text: str) -> List[str]:
        """把一条 JD 要求拆成更细的短语，便于做“逐条思考”"""
        source = str(original_text or "").strip()
        if not source:
            return []

        special_terms: List[str] = []
        if "B端产品意识" in source:
            special_terms.append("B端产品意识")
        if "古典产品经理" in source:
            special_terms.append("古典产品经理能力")
        if "知识体系" in source:
            special_terms.append("知识体系")
        if special_terms:
            return special_terms[:4]

        normalized = re.sub(r"[（(].*?[)）]", "", source)
        normalized = re.sub(r"[：:]", "，", normalized)
        parts = re.split(r"[，,；;/、]|以及|并且|并|和", normalized)

        concepts: List[str] = []
        seen = set()
        for raw in parts:
            part = str(raw).strip()
            part = re.sub(r"^[需能熟悉掌握具备负责有对并且]+", "", part)
            if len(part) < 2:
                continue
            if part not in seen:
                concepts.append(part)
                seen.add(part)
            if len(concepts) >= 4:
                break

        return concepts[:4] if concepts else [source[:24]]

    def _explain_requirement_concept(self, concept: str, original_text: str, requirement_type: str) -> str:
        """给每个短语一个招聘官视角解释"""
        text = str(concept or "").strip()
        source = str(original_text or "").strip()
        lower = f"{text} {source}".lower()
        rtype = str(requirement_type or "").strip().lower()

        if "b端" in lower or "to b" in lower or "tob" in lower:
            return "重点看你是否理解企业业务流程、角色分工、权限和交付效率，而不是只会做表层体验。"
        if "古典产品经理" in text or ("古典" in text and "产品" in source):
            return "指扎实的后台产品基本功，比如流程设计、权限模型、PRD、复杂逻辑梳理，不是只会讲概念。"
        if "知识体系" in text:
            return "不是零散知道几个词，而是做需求、拆流程、定方案时有一套稳定的方法。"
        if "0-1" in lower or "从0到1" in lower:
            return "想确认你不是只接后半段，而是真的参与过定义、设计、推进到上线的完整过程。"
        if "表达" in text or "阐述" in text or rtype == "communication":
            return "重点看你能不能把背景、职责、方案取舍和结果讲清楚，而不是泛泛说参与过。"
        if "owner" in lower or "推动" in text or "落地" in text:
            return "重点看你是否对结果负责，能把事情从讨论推进到真正交付。"
        if "agent" in lower or "coze" in lower or "dify" in lower or "扣子" in lower:
            return "不是只听说过平台，而是最好能拿出你实际搭过什么流程、解决了什么问题。"
        if "权限" in text or "rbac" in lower:
            return "看你是否真的做过角色划分、权限边界和操作约束，而不是停留在页面层。"
        if "流程" in text or "工作流" in text:
            return "看你能不能把业务步骤、异常分支和协作链路理顺。"
        return "这条不是看你会不会背术语，而是看你能不能拿真实项目证明自己做过这一块。"

    def _normalize_requirement_concept_breakdown(
        self,
        raw_breakdown: Any,
        original_text: str,
        requirement_type: str
    ) -> List[Dict[str, str]]:
        """统一 requirement 的短语拆解结构"""
        normalized: List[Dict[str, str]] = []

        if isinstance(raw_breakdown, list):
            for item in raw_breakdown:
                if isinstance(item, dict):
                    term = str(item.get("term") or item.get("concept") or item.get("短语") or "").strip()
                    meaning = str(
                        item.get("meaning")
                        or item.get("explanation")
                        or item.get("interpretation")
                        or item.get("说明")
                        or ""
                    ).strip()
                else:
                    term = str(item).strip()
                    meaning = ""

                if not term:
                    continue
                normalized.append({
                    "term": term,
                    "meaning": meaning or self._explain_requirement_concept(term, original_text, requirement_type)
                })

        if not normalized:
            for term in self._split_requirement_concepts(original_text):
                normalized.append({
                    "term": term,
                    "meaning": self._explain_requirement_concept(term, original_text, requirement_type)
                })

        return normalized[:4]

    def _make_requirement_human_translation(self, original_text: str, plain_text: str, requirement_type: str) -> str:
        """把 JD 黑话翻成更接地气的一句话"""
        source = str(original_text or "").strip()
        plain = str(plain_text or "").strip()
        lower = f"{source} {plain}".lower()
        rtype = str(requirement_type or "").strip().lower()

        if ("b端" in lower or "to b" in lower or "tob" in lower) and ("古典" in source or "产品" in source):
            return "懂企业业务，逻辑扎实，能把复杂流程、角色权限和后台系统理顺，不是只会做花哨界面。"
        if "0-1" in lower or "从0到1" in lower:
            return "不是只打辅助，而是真的参与过一个模块从定义、设计到上线的完整过程。"
        if "表达" in source or "阐述" in source or rtype == "communication":
            return "得能把你做过什么、为什么这么做、结果怎样讲明白，让面试官快速判断。"
        if "owner" in lower or "推动" in source or "落地" in source:
            return "不只是参与，而是要能扛事、推人、控节奏，把事情真的做成。"
        if "agent" in lower or "coze" in lower or "dify" in lower or "扣子" in lower:
            return "最好不是停留在听说过，而是实际搭过 Agent / 工作流，并能说清楚用途和产出。"
        return plain or source

    def _make_requirement_interviewer_intent(
        self,
        original_text: str,
        requirement_type: str,
        observable_signals: List[str]
    ) -> str:
        """招聘官真正想确认的点"""
        source = str(original_text or "").strip()
        lower = source.lower()
        signals = [str(item).strip() for item in (observable_signals or []) if str(item).strip()]

        if "b端" in lower or "to b" in lower or "tob" in lower:
            return "招聘官想确认你是否真的做过企业场景，而不是把 C 端项目硬翻成 B 端。"
        if "0-1" in lower or "从0到1" in lower:
            return "招聘官想确认你是否参与过需求定义、方案判断、推进落地，而不是只接执行尾巴。"
        if "表达" in source or "阐述" in source:
            return "招聘官想确认你是否能把项目讲清楚，避免面试里一追问就散。"
        if "agent" in lower or "coze" in lower or "dify" in lower or "扣子" in source:
            return "招聘官想确认你是否真的上手过平台，而不是只把工具名挂在简历上。"
        if signals:
            return f"招聘官真正会追问这些可观察信号：{'；'.join(signals[:3])}。"
        return "招聘官想确认这条要求背后有没有真实项目、真实职责和真实结果支撑。"

    def _make_requirement_interview_tell_hint(
        self,
        original_text: str,
        requirement_type: str,
        observable_signals: List[str]
    ) -> str:
        """告诉用户面试里应该怎么讲这一条"""
        source = str(original_text or "").strip()
        lower = source.lower()
        signals = [str(item).strip() for item in (observable_signals or []) if str(item).strip()]

        if "b端" in lower or "to b" in lower or "tob" in lower:
            return "准备一个企业场景案例，按“业务目标-角色-流程-权限-结果”讲，不要只讲页面功能。"
        if "0-1" in lower or "从0到1" in lower:
            return "面试里按“为什么做-怎么定义-如何推进-上线结果”顺着讲，重点讲你的判断。"
        if "表达" in source or "阐述" in source or requirement_type == "communication":
            return "先讲背景，再讲你的职责、关键决策和结果，控制在 1-2 分钟内讲完整。"
        if "agent" in lower or "coze" in lower or "dify" in lower or "扣子" in source:
            return "准备一段平台实操案例：你搭了什么流程、为什么这样搭、效果如何。"
        if signals:
            return f"面试准备时优先围绕这几个信号举例：{'；'.join(signals[:2])}。"
        return "面试里别空讲概念，准备一个真实项目，把背景、动作和结果说清楚。"

    def _make_requirement_fix_strategy(
        self,
        original_text: str,
        gap_type: str,
        requirement_type: str,
        resume_evidence: str,
        raw_fix_strategy: str
    ) -> str:
        """把泛泛的补位建议改写成能直接用于改简历的动作建议"""
        raw = str(raw_fix_strategy or "").strip()
        if raw and all(keyword not in raw for keyword in ["补充", "增加", "写清", "明确", "改写", "写出"]):
            return raw

        original = str(original_text or "").strip()
        evidence = str(resume_evidence or "").strip()
        rtype = str(requirement_type or "").strip().lower()
        gap = str(gap_type or "").strip().lower()

        if gap == "expression_gap":
            if "b端" in original.lower() or "B端" in original:
                return "把相关项目改写成 B 端语境：补上业务场景、服务对象、核心流程、你负责的产品判断和最终价值。"
            return "不要只写参与过什么，改成“场景-问题-你的动作-结果”的写法，让招聘方一眼看出你和岗位要求的对应关系。"
        if gap == "evidence_gap":
            if "dify" in original.lower() or "coze" in original.lower() or "扣子" in original:
                return "既然简历里已经提到相关工具，就补上你用它做过什么：项目场景、搭建内容、你的具体动作和最终产出。"
            if evidence:
                return f"围绕现有证据“{evidence[:24]}”往下补：写清你负责的部分、怎么推进、结果如何，而不是只写参与。"
            return "补充一个具体案例：写清项目场景、你的职责、关键动作和结果，让这条要求有可验证证据。"
        if gap == "capability_gap":
            return "这条不要硬改写成“已经会了”，只能补真实实践；简历里可以先弱化无关表述，同时补一个最接近的学习或项目经历。"
        if gap == "experience_gap":
            return "这不是单靠润色能补齐的缺口，简历里应明确写相近场景经验；如果没有，建议降低表述强度并准备替代案例。"
        if rtype == "product_judgment":
            return "把项目写成产品判断过程：为什么做、服务谁、你怎么判断方案、最后带来了什么结果。"
        return raw or "修改这一条时不要只换词，要补上场景、职责、动作和结果，让招聘方能直接看到证据。"

    def _infer_is_abstract_requirement(self, original_text: str, requirement_type: str, current_value: bool) -> bool:
        """收紧“抽象 requirement”边界，避免把明确要求误判成抽象表述"""
        if current_value is True:
            source = str(original_text or "").strip()
            lower_source = source.lower()
            explicit_markers = [
                "0-1", "从0到1", "方案", "阐述", "逻辑", "coze", "dify", "扣子",
                "agent", "平台", "低代码", "工作流", "项目经验", "模块"
            ]
            if any(marker in lower_source or marker in source for marker in explicit_markers):
                return False
        return current_value

    def _normalize_strengths_section(self, strengths: List[Any]) -> List[Dict[str, str]]:
        """统一核心匹配项结构，供前端稳定渲染"""
        normalized: List[Dict[str, str]] = []
        for item in strengths or []:
            if isinstance(item, dict):
                title = str(item.get("point") or item.get("匹配点") or item.get("title") or "").strip()
                evidence = str(item.get("evidence") or item.get("证据锚点") or item.get("resume_quote") or "").strip()
                why_it_matters = str(item.get("why_it_matters") or item.get("为什么匹配") or item.get("why") or "").strip()
                interview_probe = str(item.get("interview_probe") or item.get("面试放大点") or item.get("interview_tip") or "").strip()
            else:
                title = str(item).strip()
                evidence = ""
                why_it_matters = ""
                interview_probe = ""

            if not title:
                continue
            normalized.append({
                "title": title,
                "evidence": evidence,
                "why_it_matters": why_it_matters,
                "interview_probe": interview_probe
            })
        return normalized[:3]

    def _normalize_gaps_section(self, gaps: List[Any]) -> List[Dict[str, str]]:
        """统一关键缺失项结构"""
        normalized: List[Dict[str, str]] = []
        for item in gaps or []:
            if isinstance(item, dict):
                title = str(item.get("gap") or item.get("Gap") or item.get("title") or "").strip()
                severity = str(item.get("severity") or item.get("risk_level") or "medium").strip().lower()
                why_it_blocks = str(item.get("why_it_blocks") or item.get("影响原因") or "").strip()
                fix_now = str(item.get("emergency_fix") or item.get("fix_now") or "").strip()
                fix_transfer = str(item.get("transfer_fix") or item.get("fix_transfer") or "").strip()
            else:
                raw_text = str(item).strip()
                if raw_text.startswith(("P0:", "P1:", "P2:")):
                    prefix, title = raw_text.split(":", 1)
                    severity = {"P0": "high", "P1": "medium", "P2": "low"}.get(prefix.strip(), "medium")
                    title = title.strip()
                else:
                    severity = "medium"
                    title = raw_text
                why_it_blocks = ""
                fix_now = ""
                fix_transfer = ""

            if severity not in {"high", "medium", "low"}:
                severity = "medium"
            if not title:
                continue
            normalized.append({
                "title": title,
                "severity": severity,
                "why_it_blocks": why_it_blocks,
                "fix_now": fix_now,
                "fix_transfer": fix_transfer
            })
        return normalized[:3]

    def _normalize_rewrite_actions(self, rewrite_priorities: List[Any], action_plan: List[str]) -> List[Dict[str, str]]:
        """统一简历重构指令结构"""
        normalized: List[Dict[str, str]] = []
        for idx, item in enumerate(rewrite_priorities or []):
            if isinstance(item, dict):
                priority = str(item.get("priority") or idx + 1)
                target = str(item.get("target_section") or item.get("section") or "简历对应模块").strip()
                problem = str(item.get("problem") or "").strip()
                goal = str(item.get("rewrite_goal") or "").strip()
                action = str(item.get("rewrite_method") or "").strip()
                example = str(item.get("example_direction") or "").strip()
                side_door_fix = str(item.get("side_door_fix") or item.get("旁路补位技巧") or item.get("邪修小技巧") or "").strip()
            else:
                priority = str(idx + 1)
                target = "简历对应模块"
                problem = ""
                goal = ""
                action = str(item).strip()
                example = ""
                side_door_fix = ""

            if not any([target, action, goal, problem]):
                continue
            normalized.append({
                "priority": priority,
                "target": target or "简历对应模块",
                "problem": problem,
                "goal": goal,
                "action": action,
                "example": example,
                "side_door_fix": side_door_fix
            })

        if normalized:
            return normalized[:3]

        for idx, item in enumerate(action_plan or []):
            text = str(item).strip()
            if not text:
                continue
            normalized.append({
                "priority": str(idx + 1),
                "target": "简历对应模块",
                "problem": "",
                "goal": "",
                "action": text,
                "example": "",
                "side_door_fix": ""
            })
        return normalized[:3]

    def _normalize_interview_questions(self, interview_predictions: List[Any]) -> List[Dict[str, str]]:
        """统一面试预判问题结构"""
        normalized: List[Dict[str, str]] = []
        for item in interview_predictions or []:
            if isinstance(item, dict):
                question = str(item.get("问题") or item.get("question") or "").strip()
                answer_hint = str(item.get("参考回答思路") or item.get("answer") or item.get("answer_hint") or "").strip()
            else:
                question = str(item).strip()
                answer_hint = ""

            if not question:
                continue
            normalized.append({
                "question": question,
                "answer_hint": answer_hint
            })
        return normalized[:3]

    def _build_evidence_lines(self, requirement_checks: List[Dict[str, Any]]) -> List[str]:
        """把逐条 requirement check 压成前端可直接展示的证据行"""
        evidence_lines: List[str] = []
        for item in requirement_checks or []:
            requirement = str(item.get("requirement", "")).strip()
            status = str(item.get("status", "insufficient_evidence")).strip()
            evidence = str(item.get("resume_evidence", "") or "空").strip()
            reason = str(item.get("reason", "") or item.get("judgement_reason", "")).strip()
            if not requirement:
                continue
            status_text = {
                "matched": "匹配",
                "partially_matched": "部分匹配",
                "not_matched": "不匹配",
                "insufficient_evidence": "证据不足"
            }.get(status, status)
            line = f"要求：{requirement}\n判断：{status_text}\n证据：{evidence}"
            if reason:
                line += f"\n说明：{reason}"
            evidence_lines.append(line)
        return evidence_lines[:8]

    def _normalize_requirement_checks_section(
        self,
        requirement_checks: List[Dict[str, Any]],
        jd_decomposition: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """统一逐条 requirement check 结构，兼容新旧字段并补齐 JD 人话翻译层"""
        normalized: List[Dict[str, Any]] = []
        hard_requirements = set(str(item).strip() for item in (jd_decomposition.get("hard_requirements") or []) if str(item).strip())
        plus_items = set(str(item).strip() for item in (jd_decomposition.get("plus_items") or []) if str(item).strip())

        for item in requirement_checks or []:
            if not isinstance(item, dict):
                continue

            original_text = str(
                item.get("original_text")
                or item.get("requirement")
                or item.get("title")
                or ""
            ).strip()
            if not original_text:
                continue

            plain_text = str(
                item.get("plain_text")
                or item.get("plain_requirement")
                or item.get("interpreted_requirement")
                or ""
            ).strip()
            requirement_type = str(
                item.get("requirement_type")
                or item.get("category")
                or "general"
            ).strip()
            status = str(item.get("status") or "insufficient_evidence").strip()
            jd_evidence = str(item.get("jd_evidence") or original_text).strip()
            resume_evidence = str(item.get("resume_evidence") or "").strip()
            why = str(
                item.get("why")
                or item.get("reason")
                or item.get("judge_reason")
                or item.get("judgement_reason")
                or ""
            ).strip()
            gap_type = str(item.get("gap_type") or "").strip().lower()
            fix_strategy = str(
                item.get("fix_strategy")
                or item.get("emergency_fix")
                or item.get("transfer_fix")
                or ""
            ).strip()
            observable_signals = item.get("observable_signals") or []
            if not isinstance(observable_signals, list):
                observable_signals = []
            concept_breakdown = self._normalize_requirement_concept_breakdown(
                item.get("concept_breakdown") or item.get("core_concepts") or [],
                original_text,
                requirement_type
            )
            human_translation = str(
                item.get("human_translation")
                or item.get("human_readable_translation")
                or item.get("一句话翻译")
                or ""
            ).strip()
            interviewer_intent = str(
                item.get("interviewer_intent")
                or item.get("what_they_really_mean")
                or item.get("招聘官到底想看什么")
                or ""
            ).strip()
            interview_tell_hint = str(
                item.get("interview_tell_hint")
                or item.get("interview_hint")
                or item.get("面试怎么讲")
                or ""
            ).strip()
            resume_rewrite_hint = str(
                item.get("resume_rewrite_hint")
                or item.get("resume_hint")
                or item.get("简历怎么写")
                or ""
            ).strip()

            category = str(item.get("category") or "").strip()
            is_hard_gate = bool(item.get("is_hard_gate", original_text in hard_requirements))
            is_bonus = bool(item.get("is_bonus", original_text in plus_items))
            is_abstract = bool(item.get("is_abstract", False))
            is_abstract = self._infer_is_abstract_requirement(original_text, requirement_type, is_abstract)

            if not category:
                if is_hard_gate:
                    category = "hard_requirement"
                elif is_bonus:
                    category = "plus_item"
                else:
                    category = "core_competency"

            if not gap_type and status in {"partially_matched", "insufficient_evidence"}:
                gap_type = "evidence_gap"
            elif not gap_type and status == "not_matched":
                gap_type = "capability_gap"

            plain_text = self._refine_plain_requirement(original_text, plain_text, requirement_type)
            fix_strategy = self._make_requirement_fix_strategy(
                original_text,
                gap_type,
                requirement_type,
                resume_evidence,
                fix_strategy
            )
            human_translation = human_translation or self._make_requirement_human_translation(
                original_text,
                plain_text,
                requirement_type
            )
            interviewer_intent = interviewer_intent or self._make_requirement_interviewer_intent(
                original_text,
                requirement_type,
                observable_signals
            )
            interview_tell_hint = interview_tell_hint or self._make_requirement_interview_tell_hint(
                original_text,
                requirement_type,
                observable_signals
            )
            resume_rewrite_hint = resume_rewrite_hint or fix_strategy

            # ===== 结构化评估字段（KSAO / Demands-Abilities Fit / STAR）=====
            ksao_type = str(item.get("ksao_type", "")).strip().upper()[:1]
            if ksao_type not in {"K", "S", "A", "O"}:
                ksao_type = self._infer_ksao_type(original_text, requirement_type)
            ksao_label = str(item.get("ksao_label", "")).strip() or {
                "K": "知识", "S": "技能", "A": "能力", "O": "特质"
            }.get(ksao_type, "")
            weight_tier = str(item.get("weight_tier", "")).strip().lower()
            if weight_tier not in {"knockout", "core", "nice"}:
                weight_tier = "knockout" if is_hard_gate else ("nice" if is_bonus else "core")
            required_level = self._clamp_int(item.get("required_level", 2), 1, 3, 2)
            # demonstrated_level / evidence_strength：模型给了就用，否则按 status 兜底推断
            status_level_default = {
                "matched": 3, "partially_matched": 2,
                "insufficient_evidence": 1, "not_matched": 0
            }.get(status, 1)
            status_evidence_default = {
                "matched": 3, "partially_matched": 2,
                "insufficient_evidence": 1, "not_matched": 0
            }.get(status, 1)
            demonstrated_level = self._clamp_int(
                item.get("demonstrated_level", status_level_default), 0, 3, status_level_default
            )
            evidence_strength = self._clamp_int(
                item.get("evidence_strength", status_evidence_default), 0, 4, status_evidence_default
            )

            normalized.append({
                "requirement": original_text,
                "original_text": original_text,
                "plain_text": plain_text,
                "concept_breakdown": concept_breakdown,
                "human_translation": human_translation,
                "interviewer_intent": interviewer_intent,
                "resume_rewrite_hint": resume_rewrite_hint,
                "interview_tell_hint": interview_tell_hint,
                "requirement_type": requirement_type,
                "category": category,
                "importance": str(item.get("importance") or "medium").strip(),
                "is_hard_gate": is_hard_gate,
                "is_bonus": is_bonus,
                "is_abstract": is_abstract,
                "ksao_type": ksao_type,
                "ksao_label": ksao_label,
                "weight_tier": weight_tier,
                "required_level": required_level,
                "demonstrated_level": demonstrated_level,
                "evidence_strength": evidence_strength,
                "observable_signals": observable_signals[:4],
                "status": status,
                "gap_type": gap_type,
                "jd_evidence": jd_evidence,
                "resume_evidence": resume_evidence,
                "reason": why,
                "judge_reason": why,
                "why": why,
                "fix_strategy": fix_strategy,
                "can_be_fixed_by_rewrite": bool(item.get("can_be_fixed_by_rewrite", gap_type in {"evidence_gap", "expression_gap"}))
            })

        return normalized[:8]

    @staticmethod
    def _infer_ksao_type(text: str, requirement_type: str = "") -> str:
        """缺省时按关键词把要求归到 KSAO 四类（工作分析口径）"""
        t = f"{text} {requirement_type}".lower()
        if any(k in t for k in ["学历", "本科", "硕士", "博士", "年经验", "年以上", "经验者", "应届", "0-1", "从0到1", "落地经验"]):
            return "O"
        if any(k in t for k in ["原理", "理解", "了解", "概念", "知识", "机制", "架构"]):
            return "K"
        if any(k in t for k in ["熟练", "掌握", "会用", "使用", "工具", "编程", "sql", "python", "prompt", "agent", "rag", "操作"]):
            return "S"
        if any(k in t for k in ["能力", "思维", "拆解", "设计", "分析", "推动", "沟通", "协作", "判断", "解决"]):
            return "A"
        return "S"

    @staticmethod
    def _clamp_int(value: Any, lo: int, hi: int, default: int = 0) -> int:
        try:
            v = int(round(float(value)))
        except (TypeError, ValueError):
            return default
        return max(lo, min(hi, v))

    def _compute_ksao_score(self, requirement_checks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        结构化简历评估打分模型（工业组织心理学口径，可复算）：
        - KSAO 工作分析：每条要求带 ksao_type
        - Demands-Abilities Fit：用 demonstrated_level / required_level 衡量层级达成度
        - STAR 证据强度：evidence_strength(0-4) 折算证据可信度
        - 非补偿性(knockout) + 补偿性(core) 混合模型

        返回 None 表示数据不足以复算（缺少结构化字段），此时回退到 LLM 自评分。
        """
        if not requirement_checks:
            return None

        knockout_items: List[Dict[str, Any]] = []
        core_items: List[Dict[str, Any]] = []
        nice_items: List[Dict[str, Any]] = []
        structured_count = 0

        for raw in requirement_checks:
            if not isinstance(raw, dict):
                continue
            tier = str(raw.get("weight_tier", "")).strip().lower()
            has_levels = ("required_level" in raw) or ("demonstrated_level" in raw)
            if has_levels:
                structured_count += 1
            required = self._clamp_int(raw.get("required_level", 2), 1, 3, 2)
            demonstrated = self._clamp_int(raw.get("demonstrated_level", 0), 0, 3, 0)
            evidence = self._clamp_int(raw.get("evidence_strength", 0), 0, 4, 0)

            # 单条达成度：层级达成 × 证据可信度，均归一到 0-1
            level_fit = min(1.0, demonstrated / required) if required else 0.0
            evidence_factor = evidence / 4.0
            # 证据是"折扣"：层级再高、没证据也要打折（STAR 行为事件法精神）。
            # 证据权重收窄到 0.55~1.0，避免模型某次把证据从4判成2时分数剧烈摆动（降方差）。
            item_fit = level_fit * (0.55 + 0.45 * evidence_factor)

            entry = {
                "requirement": raw.get("requirement") or raw.get("original_text", ""),
                "ksao_type": str(raw.get("ksao_type", "")).strip().upper()[:1],
                "ksao_label": raw.get("ksao_label", ""),
                "required_level": required,
                "demonstrated_level": demonstrated,
                "evidence_strength": evidence,
                "fit": round(item_fit, 3),
            }

            if tier == "knockout":
                knockout_items.append(entry)
            elif tier == "nice":
                nice_items.append(entry)
            else:
                core_items.append(entry)

        # 没有任何结构化字段，说明模型没按新 schema 输出，回退到 LLM 自评分
        if structured_count == 0:
            return None

        # ===== 非补偿性：knockout 达成率作为整体上限 =====
        if knockout_items:
            knockout_fit = sum(i["fit"] for i in knockout_items) / len(knockout_items)
        else:
            knockout_fit = 1.0  # 无硬门槛则不设额外上限

        # ===== 补偿性：core 加权平均（按要求层级加权，层级越高越重要）=====
        if core_items:
            weight_sum = sum(i["required_level"] for i in core_items) or len(core_items)
            core_fit = sum(i["fit"] * i["required_level"] for i in core_items) / weight_sum
        elif knockout_items:
            core_fit = knockout_fit
        else:
            core_fit = sum(i["fit"] for i in nice_items) / len(nice_items) if nice_items else 0.0

        # ===== 加分项：达标才加分，缺失不扣分 =====
        nice_bonus = 0.0
        if nice_items:
            nice_fit = sum(i["fit"] for i in nice_items) / len(nice_items)
            nice_bonus = nice_fit * 5.0  # 最多 +5

        # 基础分：knockout 占 45%，core 占 55%（硬门槛是前提，核心能力是主体）
        base = (0.45 * knockout_fit + 0.55 * core_fit) * 100.0
        raw_score = base + nice_bonus

        # 非补偿性封顶：硬门槛没过，整体不可能高分。
        # 但给"硬门槛受限、却有真实亮点(core)"的候选人留缓冲——不一刀压到谷底，
        # 让这类落在 D 高位 / 低 C，而不是冷冰冰的 30。
        if knockout_items:
            if knockout_fit < 0.34:
                raw_score = min(raw_score, 58)
            elif knockout_fit < 0.6:
                raw_score = min(raw_score, 68)
            elif knockout_fit < 0.8:
                raw_score = min(raw_score, 80)
            # 硬门槛受限但简历仍有一定亮点(core)时，给一点托底，避免"简历其实不错却被打成谷底分"。
            # 托底到 D 高位附近，既体现"硬门槛卡住"，又不冷冰冰砸到谷底。
            if knockout_fit < 0.34 and core_fit >= 0.35:
                raw_score = max(raw_score, 50)
            elif knockout_fit < 0.34 and core_fit >= 0.2:
                raw_score = max(raw_score, 44)

        score = int(max(30, min(96, round(raw_score))))

        return {
            "score": score,
            "level": self._infer_match_level(score),
            "knockout_fit": round(knockout_fit, 3),
            "core_fit": round(core_fit, 3),
            "nice_bonus": round(nice_bonus, 2),
            "tiers": {
                "knockout": knockout_items,
                "core": core_items,
                "nice": nice_items,
            },
            "method": "KSAO 工作分析 + Demands-Abilities Fit + STAR 证据强度 + 非补偿性/补偿性混合模型",
        }

    def _compute_five_dimensions(self, requirement_checks: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """本地算法：按五维（学历/经验/技能/项目/潜力）聚合每条要求的达成度，得到五维评分。

        维度分 = 该维度下各条 fit 的加权平均(按 required_level 加权) × 100。
        没有任一条命中某维度时，给该维度一个中性占位，避免前端展示空白。
        """
        if not requirement_checks:
            return None

        dim_meta = [
            ("education", "学历背景"),
            ("experience", "经验匹配"),
            ("skill", "技能匹配"),
            ("project", "项目深度"),
            ("potential", "成长潜力"),
        ]
        # 关键词兜底：模型没给 dimension 时按文本推断
        def infer_dim(text: str) -> str:
            t = str(text or "")
            if any(k in t for k in ["学历", "本科", "硕士", "博士", "专业", "毕业", "GPA", "学位"]):
                return "education"
            if any(k in t for k in ["实习", "经验", "年以上", "工作经历", "履历"]):
                return "experience"
            if any(k in t for k in ["项目", "从0到1", "0-1", "落地", "成果", "复杂"]):
                return "project"
            if any(k in t for k in ["学习", "潜力", "探索", "主动", "沟通", "协作", "owner", "态度"]):
                return "potential"
            return "skill"

        buckets: Dict[str, List[Dict[str, float]]] = {k: [] for k, _ in dim_meta}
        has_any = False
        for raw in requirement_checks:
            if not isinstance(raw, dict):
                continue
            required = self._clamp_int(raw.get("required_level", 2), 1, 3, 2)
            demonstrated = self._clamp_int(raw.get("demonstrated_level", 0), 0, 3, 0)
            evidence = self._clamp_int(raw.get("evidence_strength", 0), 0, 4, 0)
            level_fit = min(1.0, demonstrated / required) if required else 0.0
            item_fit = level_fit * (0.55 + 0.45 * (evidence / 4.0))

            dim = str(raw.get("dimension", "")).strip().lower()
            if dim not in buckets:
                dim = infer_dim(raw.get("original_text") or raw.get("requirement") or raw.get("plain_text", ""))
            buckets[dim].append({"fit": item_fit, "w": float(required)})
            has_any = True

        if not has_any:
            return None

        dimensions = []
        for key, label in dim_meta:
            items = buckets[key]
            if items:
                wsum = sum(i["w"] for i in items) or len(items)
                fit = sum(i["fit"] * i["w"] for i in items) / wsum
                score = int(max(30, min(98, round(fit * 100))))
                count = len(items)
            else:
                # 该维度 JD 没有明确要求 → 给中性分，不拉低也不虚高
                score = 70
                count = 0
            dimensions.append({
                "key": key,
                "label": label,
                "score": score,
                "requirement_count": count,
            })
        return dimensions

    # ===== 学历本地锚定：把"学历是否达标"这类铁事实交给本地判定，不随模型每次波动 =====
    @staticmethod
    def _detect_degree_rank(text: str) -> int:
        """从文本里识别最高学历层级：博士=4 硕士=3 本科=2 大专=1 未知=0。"""
        t = str(text or "")
        if any(k in t for k in ["博士", "PhD", "Ph.D", "Doctor"]):
            return 4
        if any(k in t for k in ["硕士", "研究生", "Master", "MSc", "MBA", "MS "]):
            return 3
        if any(k in t for k in ["本科", "学士", "Bachelor", "BSc", "BS ", "BE "]):
            return 2
        if any(k in t for k in ["大专", "专科", "高职", "Diploma", "Associate"]):
            return 1
        return 0

    def _anchor_education_requirement(
        self,
        requirement_checks: List[Dict[str, Any]],
        resume_text: str,
        jd_text: str,
    ) -> List[Dict[str, Any]]:
        """对"学历维度"做最小化的确定性修正。

        设计原则（模型给判断、本地兜铁事实）：
        - 只在"学历层级客观不达标"时，本地拉低该条达成度（这是模型偶尔会漏的硬事实）；
        - 学历层级达标时，完全不覆盖模型判断——专业是否对口等语义交给模型，
          避免用关键词猜专业带来的误判（如把"AI产品经理"误当成 AI 专业）。
        """
        if not requirement_checks:
            return requirement_checks

        resume_rank = self._detect_degree_rank(resume_text)
        if resume_rank == 0:
            # 简历里没读到明确学历，不强行锚定，保持模型判断
            return requirement_checks

        edu_keywords = ["学历", "本科", "硕士", "研究生", "博士", "学位", "毕业", "GPA", "院校", "学校"]

        for raw in requirement_checks:
            if not isinstance(raw, dict):
                continue
            dim = str(raw.get("dimension", "")).strip().lower()
            text_for_match = " ".join(str(raw.get(k, "")) for k in ("original_text", "requirement", "plain_text"))
            is_edu = dim == "education" or any(k in text_for_match for k in edu_keywords)
            if not is_edu:
                continue

            # JD 对学历的最低层级要求（读不到默认本科=2）
            jd_required_rank = self._detect_degree_rank(text_for_match) or self._detect_degree_rank(jd_text) or 2

            # 只兜"学历层级不达标"这一铁事实；达标则不动模型判断（专业对口由模型决定）
            if resume_rank < jd_required_rank:
                raw["dimension"] = "education"
                raw["required_level"] = self._clamp_int(raw.get("required_level", 2), 1, 3, 2)
                raw["demonstrated_level"] = 1
                raw["evidence_strength"] = 4  # 学历层级是硬事实
                raw["_anchored"] = "education_underqualified"

        return requirement_checks

    def _apply_score_guardrails(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """高分制动器：避免轻易出现虚高的 A级/90分"""
        score = int(result.get("match_score", 60))

        # 如果已用结构化 KSAO 模型复算出分数，则该分数本身已含非补偿性封顶，
        # 不再叠加启发式扣分，只统一生成与分数一致的推荐语，保证“分数可复算”。
        score_breakdown = (result.get("sections") or {}).get("score_breakdown")
        if score_breakdown:
            adjusted_score = max(0, min(100, score))
            result["match_score"] = adjusted_score
            result["match_level"] = self._infer_match_level(adjusted_score)
            requirement_checks_sb = result.get("report_requirement_checks") or result.get("requirement_checks") or []
            high_block = any(
                str(c.get("weight_tier", "")).lower() == "knockout"
                and str(c.get("status", "")) in {"not_matched", "insufficient_evidence"}
                for c in requirement_checks_sb if isinstance(c, dict)
            )
            should_interview = adjusted_score >= 70 and not high_block
            if adjusted_score >= 85:
                recommendation_reason = "硬门槛全部达标、核心能力证据充分，已具备推进面试的说服力。"
            elif adjusted_score >= 70:
                recommendation_reason = "硬门槛达标且核心能力基本匹配，但仍有证据/层级缺口，建议补强后投递。"
            elif adjusted_score >= 55:
                recommendation_reason = "核心能力证据普遍不足或有硬门槛接近未达标，建议先补关键证据再投递。"
            else:
                recommendation_reason = "硬门槛存在明显未达标或核心能力大面积缺失，当前版本难以通过初筛。"
            result["recommendation"] = {
                "should_interview": should_interview,
                "reason": recommendation_reason
            }
            if isinstance(result.get("report_executive_summary"), dict):
                result["report_executive_summary"]["match_score"] = adjusted_score
                result["report_executive_summary"]["match_level"] = result["match_level"]
                result["report_executive_summary"]["hiring_recommendation"] = recommendation_reason
            if isinstance(result.get("summary"), dict):
                result["summary"]["score"] = adjusted_score
                result["summary"]["level"] = result["match_level"]
                result["summary"]["recommendation"] = recommendation_reason
                result["summary"]["should_interview"] = should_interview
            return result

        strengths = result.get("strengths_vs_jd") or result.get("strengths") or []
        gaps = result.get("gaps_vs_jd") or result.get("gaps") or []
        requirement_checks = result.get("report_requirement_checks") or result.get("requirement_checks") or []
        jd_decomposition = result.get("report_jd_decomposition") or result.get("jd_decomposition") or {}
        hard_requirements = jd_decomposition.get("hard_requirements", []) if isinstance(jd_decomposition, dict) else []
        action_plan_raw = result.get("action_plan") or []
        recommendation = result.get("recommendation") or {}
        reason = recommendation.get("reason", "")

        if isinstance(action_plan_raw, dict):
            action_plan = (
                list(action_plan_raw.get("within_24_hours", []) or []) +
                list(action_plan_raw.get("within_7_days", []) or []) +
                list(action_plan_raw.get("longer_term", []) or [])
            )
        else:
            action_plan = action_plan_raw or []

        medium_or_above_gaps = 0
        high_gaps = 0
        for item in gaps:
            if isinstance(item, dict):
                severity = str(item.get("severity", "medium")).lower()
            else:
                text = str(item)
                severity = "high" if text.startswith("P0:") else "medium" if text.startswith("P1:") else "low"
            if severity in {"medium", "high"}:
                medium_or_above_gaps += 1
            if severity == "high":
                high_gaps += 1

        matched_count = 0
        partial_count = 0
        insufficient_count = 0
        not_matched_count = 0
        for item in requirement_checks:
            status = str(item.get("status", "insufficient_evidence")).strip()
            if status == "matched":
                matched_count += 1
            elif status == "partially_matched":
                partial_count += 1
            elif status == "not_matched":
                not_matched_count += 1
            else:
                insufficient_count += 1

        penalties = 0
        if len(strengths) < 2:
            penalties += 8
        if len(strengths) < 3:
            penalties += 4
        if len(gaps) >= 1:
            penalties += 8
        if len(gaps) >= 2:
            penalties += 6
        if medium_or_above_gaps >= 1:
            penalties += 5
        if medium_or_above_gaps >= 2:
            penalties += 5
        if high_gaps >= 1:
            penalties += 10
        if len(action_plan) < 2:
            penalties += 6
        if partial_count >= 2:
            penalties += 5
        if insufficient_count >= 2:
            penalties += 6
        if insufficient_count >= 4:
            penalties += 6
        if not_matched_count >= 1:
            penalties += 12
        if not_matched_count >= 2:
            penalties += 10

        generic_markers = ["建议面试", "建议进一步沟通", "整体不错", "背景较强", "匹配度较高"]
        if any(marker in reason for marker in generic_markers):
            penalties += 5

        adjusted_score = max(35, min(95, score - penalties))

        hard_requirement_count = len(hard_requirements or [])
        hard_requirement_hit_count = 0
        if hard_requirement_count and requirement_checks:
            hard_requirement_texts = [str(item).strip() for item in hard_requirements if str(item).strip()]
            for check in requirement_checks:
                requirement = str(check.get("requirement", "")).strip()
                status = str(check.get("status", "insufficient_evidence")).strip()
                if requirement in hard_requirement_texts and status == "matched":
                    hard_requirement_hit_count += 1

        # 更严格的真实招聘口径：硬门槛命中不足时，不允许高分
        if hard_requirement_count >= 2 and hard_requirement_hit_count == 0 and adjusted_score > 55:
            adjusted_score = 55
        if hard_requirement_count >= 2 and hard_requirement_hit_count == 1 and adjusted_score > 62:
            adjusted_score = 62
        if matched_count == 0 and partial_count <= 1 and adjusted_score > 58:
            adjusted_score = 58
        if insufficient_count >= max(3, hard_requirement_count) and adjusted_score > 60:
            adjusted_score = 60
        if len(strengths) == 0 and medium_or_above_gaps >= 1 and adjusted_score > 55:
            adjusted_score = 55

        can_be_a = (
            adjusted_score >= 85 and
            len(strengths) >= 3 and
            medium_or_above_gaps == 0 and
            len(action_plan) >= 2
        )

        if not can_be_a and adjusted_score >= 85:
            adjusted_score = 82
        if medium_or_above_gaps >= 1 and adjusted_score > 82:
            adjusted_score = 82
        if high_gaps >= 1 and adjusted_score > 68:
            adjusted_score = 68
        if not_matched_count >= 1 and adjusted_score > 62:
            adjusted_score = 62
        if not_matched_count >= 2 and adjusted_score > 55:
            adjusted_score = 55
        if insufficient_count >= 3 and adjusted_score > 72:
            adjusted_score = 72

        result["match_score"] = adjusted_score
        result["match_level"] = self._infer_match_level(adjusted_score)

        should_interview = (
            adjusted_score >= 70 and
            high_gaps == 0 and
            not_matched_count == 0
        )

        if adjusted_score >= 85:
            recommendation_reason = "这版简历已经具备推进面试的说服力，重点准备面试表达即可。"
        elif adjusted_score >= 70:
            recommendation_reason = "简历有明确面试价值，但仍有几个关键点需要补强，否则面试中会被重点追问。"
        elif adjusted_score >= 55:
            recommendation_reason = "不是完全不能投，而是当前写法还不够稳妥；建议先补强最关键的证据，再去投递。"
        else:
            recommendation_reason = "当前简历和岗位要求还有明显距离，建议先补证据、补写法，再考虑投递效率。"

        result["recommendation"] = {
            "should_interview": should_interview,
            "reason": recommendation_reason
        }

        if isinstance(result.get("report_executive_summary"), dict):
            result["report_executive_summary"]["match_score"] = adjusted_score
            result["report_executive_summary"]["match_level"] = result["match_level"]
            result["report_executive_summary"]["hiring_recommendation"] = recommendation_reason

        if isinstance(result.get("summary"), dict):
            result["summary"]["score"] = adjusted_score
            result["summary"]["level"] = result["match_level"]
            result["summary"]["recommendation"] = recommendation_reason
            result["summary"]["should_interview"] = should_interview

        return result

    def _normalize_recruiter_report(self, result: Dict[str, Any], raw_text: str = "", resume_text: str = "", jd_text: str = "") -> Dict[str, Any]:
        """把招聘官风格完整报告压成前端稳定可用的字段"""
        diagnosis_section = result.get("🎯 一、 总体诊断", {})
        strengths_section = result.get("✅ 二、 核心匹配项 —— 放大优势", [])
        gaps_section = result.get("⚠️ 三、 关键缺失项 —— 直击痛点", [])
        rewrite_section = result.get("🛠️ 四、 简历重构指令", [])
        interview_section_cn = result.get("💡 五、 面试预判与终局建议", {})

        executive_summary = result.get("executive_summary", {})
        if isinstance(executive_summary, str):
            executive_summary = {
                "match_score": result.get("match_score", 60),
                "match_level": result.get("match_level", "C级"),
                "hiring_recommendation": result.get("recommendation", {}).get("reason", ""),
                "one_sentence_verdict": executive_summary
            }
        elif not executive_summary and diagnosis_section:
            raw_score = diagnosis_section.get("匹配度评分", "")
            score_match = re.search(r"([1-9]\d?|100)", str(raw_score))
            executive_summary = {
                "match_score": int(score_match.group(1)) if score_match else result.get("match_score", 60),
                "match_level": self._infer_match_level(int(score_match.group(1))) if score_match else result.get("match_level", "C级"),
                "hiring_recommendation": diagnosis_section.get("匹配度评分", ""),
                "one_sentence_verdict": diagnosis_section.get("一句话定调", "分析完成")
            }

        recommendation = result.get("recommendation", {})
        requirement_checks = result.get("requirement_checks", [])
        strengths = result.get("strengths", []) or strengths_section
        gaps = result.get("gaps", []) or gaps_section
        rewrite_priorities = result.get("rewrite_priorities", []) or rewrite_section
        action_plan_obj = result.get("action_plan", {})

        # 单一事实来源：分数和等级只认 executive_summary
        match_score = int(executive_summary.get("match_score", 60))
        match_level = executive_summary.get("match_level", self._infer_match_level(match_score))
        one_sentence_verdict = executive_summary.get("one_sentence_verdict", result.get("executive_summary", "分析完成"))

        strengths_vs_jd = result.get("strengths_vs_jd")
        if not strengths_vs_jd:
            strengths_vs_jd = []
            for item in strengths:
                if isinstance(item, dict):
                    point = item.get("point") or item.get("匹配点")
                    if point:
                        strengths_vs_jd.append(point)
                elif isinstance(item, str):
                    strengths_vs_jd.append(item)

        gaps_vs_jd = result.get("gaps_vs_jd")
        if not gaps_vs_jd:
            gap_lines = []
            for item in gaps:
                if isinstance(item, dict):
                    gap = item.get("gap") or item.get("Gap", "")
                    severity = item.get("severity", "medium")
                else:
                    gap = str(item)
                    severity = "medium"
                prefix = {"high": "P0", "medium": "P1", "low": "P2"}.get(severity, "P1")
                if gap:
                    gap_lines.append(f"{prefix}: {gap}")
            gaps_vs_jd = gap_lines

        # 检测"硬门槛受限"信号：是否存在未达标的 knockout 项（如专业不对口/学历不够/必备硬技能缺失）。
        # 用于让低分 verdict 更准确：区分"硬门槛卡住"和"简历本身写得差"。
        knockout_blocked = any(
            isinstance(c, dict)
            and str(c.get("weight_tier", "")).lower() == "knockout"
            and str(c.get("status", "")) in {"not_matched", "insufficient_evidence"}
            for c in requirement_checks
        )
        one_sentence_verdict = self._sharpen_verdict(one_sentence_verdict, match_score, gaps, knockout_blocked)

        action_plan = result.get("action_plan")
        if not action_plan:
            action_plan = []
            if isinstance(action_plan_obj, dict):
                for section in ("within_24_hours", "within_7_days", "longer_term"):
                    for item in action_plan_obj.get(section, [])[:2]:
                        action_plan.append(item)
            elif rewrite_priorities:
                for item in rewrite_priorities[:3]:
                    if isinstance(item, str):
                        action_plan.append(item)
            if not action_plan:
                for item in rewrite_priorities[:3]:
                    if isinstance(item, dict):
                        method = item.get("rewrite_method", "")
                        target = item.get("target_section", "简历对应模块")
                        goal = item.get("rewrite_goal", "提高岗位匹配证据清晰度")
                        if method:
                            action_plan.append(f"动作：{method}；修改对象：{target}；预期效果：{goal}")

        jd_alignment = result.get("jd_alignment")
        if not jd_alignment:
            jd_alignment = []
            for item in requirement_checks:
                status = item.get("status", "insufficient_evidence")
                gap_level = {
                    "matched": "OK",
                    "partially_matched": "P2",
                    "not_matched": "P0",
                    "insufficient_evidence": "P1"
                }.get(status, "P1")
                jd_alignment.append({
                    "requirement": item.get("requirement", ""),
                    "has_evidence": status in {"matched", "partially_matched"},
                    "evidence": item.get("resume_evidence", "") or "空",
                    "gap_level": gap_level
                })

        interview_section = result.get("interview_prediction", {})
        if not interview_section:
            interview_section = result.get("面试预判与终局建议", {})
        if not interview_section:
            interview_section = interview_section_cn

        interview_predictions = interview_section.get("必考题预测", []) if isinstance(interview_section, dict) else []
        encouragement = interview_section.get("终局鼓励", "") if isinstance(interview_section, dict) else ""

        jd_interpretation = result.get("jd_interpretation", {}) or {}
        jd_decomposition = result.get("jd_decomposition", {}) or {}
        requirement_checks = self._normalize_requirement_checks_section(requirement_checks, jd_decomposition)
        # 学历本地锚定：在算分前用简历+JD事实修正"学历维度"，让主分数和学历维度不随模型波动
        requirement_checks = self._anchor_education_requirement(requirement_checks, resume_text, jd_text)
        jd_core = jd_decomposition.get("hard_requirements", [])[:8]
        jd_competencies = jd_decomposition.get("core_competencies", [])[:6]
        jd_plus_items = jd_decomposition.get("plus_items", [])[:6]
        jd_pseudo_requirements = jd_decomposition.get("pseudo_requirements", [])[:6]
        strengths_structured = self._normalize_strengths_section(strengths)
        gaps_structured = self._normalize_gaps_section(gaps)
        rewrite_actions = self._normalize_rewrite_actions(rewrite_priorities, action_plan)
        interview_questions = self._normalize_interview_questions(interview_predictions)
        evidence_lines = self._build_evidence_lines(requirement_checks)

        # ===== 结构化复算分数（KSAO + Demands-Abilities Fit + STAR 加权模型）=====
        # 优先用可复算的结构化分数；拿不到结构化字段时回退到 LLM 自评分。
        ksao_breakdown = self._compute_ksao_score(requirement_checks)
        if ksao_breakdown:
            match_score = ksao_breakdown["score"]
            match_level = ksao_breakdown["level"]

        # 本地算法叠加五维评分（学历/经验/技能/项目/潜力），挂到 score_breakdown 供前端展示
        five_dimensions = self._compute_five_dimensions(requirement_checks)
        if five_dimensions:
            if ksao_breakdown:
                ksao_breakdown["dimensions"] = five_dimensions
            else:
                ksao_breakdown = {"dimensions": five_dimensions}

        normalized = {
            "ok": True,
            "schema_version": "match_analysis_v2",
            "summary": {
                "score": max(0, min(100, match_score)),
                "level": match_level if match_level in {"A级", "B级", "C级", "D级"} else self._infer_match_level(match_score),
                "verdict": one_sentence_verdict,
                "recommendation": recommendation.get("reason", executive_summary.get("hiring_recommendation", one_sentence_verdict)),
                "should_interview": recommendation.get("should_interview", match_score >= 60)
            },
            "sections": {
                "jd_interpretation": {
                    "role_title": jd_interpretation.get("role_title", ""),
                    "overall_goal": jd_interpretation.get("overall_goal", ""),
                    "notes": (jd_interpretation.get("notes") or [])[:3]
                },
                "jd_core": jd_core,
                "jd_competencies": jd_competencies,
                "jd_plus_items": jd_plus_items,
                "jd_pseudo_requirements": jd_pseudo_requirements,
                "requirement_checks": requirement_checks,
                "strengths": strengths_structured,
                "matched_skills": strengths_structured,
                "gaps": gaps_structured,
                "missing_skills": gaps_structured,
                "rewrite_actions": rewrite_actions,
                "optimization_suggestions": rewrite_actions,
                "interview_questions": interview_questions,
                "encouragement": encouragement,
                "evidence_lines": evidence_lines,
                "score_breakdown": ksao_breakdown
            },
            "meta": {
                "raw_text": raw_text or result.get("full_analysis", ""),
                "engine": "one_shot_match_engine"
            },
            "match_score": max(0, min(100, match_score)),
            "match_level": match_level if match_level in {"A级", "B级", "C级", "D级"} else self._infer_match_level(match_score),
            "executive_summary": one_sentence_verdict,
            "jd_analysis": result.get("jd_analysis", {"must_requirements": []}),
            "jd_alignment": jd_alignment[:8],
            "strengths_vs_jd": (strengths_vs_jd or [])[:3],
            "matched_skills": strengths_structured,
            "gaps_vs_jd": self._normalize_gap_priorities(gaps_vs_jd or []),
            "missing_skills": gaps_structured,
            "action_plan": self._normalize_action_plan(action_plan or []),
            "optimization_suggestions": rewrite_actions,
            "report_executive_summary": executive_summary,
            "report_jd_interpretation": jd_interpretation,
            "report_jd_decomposition": result.get("jd_decomposition", {}),
            "report_requirement_checks": requirement_checks,
            "report_strengths": strengths,
            "report_gaps": gaps,
            "report_resume_diagnosis": result.get("resume_diagnosis", {}),
            "report_rewrite_priorities": rewrite_priorities,
            "report_action_plan_sections": action_plan_obj if isinstance(action_plan_obj, dict) else {},
            "report_interview_predictions": interview_predictions,
            "report_encouragement": encouragement,
            "recommendation": {
                "should_interview": recommendation.get("should_interview", match_score >= 60),
                "reason": recommendation.get("reason", executive_summary.get("hiring_recommendation", one_sentence_verdict))
            },
            "full_analysis": raw_text or result.get("full_analysis", "")
        }

        return self._apply_score_guardrails(normalized)

    async def _acompletion_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 3,
    ):
        """带退避重试的 LLM 调用：缓解 Kimi 429 限流导致的偶发失败"""
        last_error: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                return await acompletion(
                    model="openai/moonshot-v1-32k",
                    messages=messages,
                    temperature=0,
                    max_tokens=6000,
                    api_key=self.api_key,
                    api_base=self.api_base,
                    timeout=90,
                    num_retries=0,
                )
            except Exception as e:
                last_error = e
                message = str(e).lower()
                is_rate_limit = "429" in message or "rate" in message or "overloaded" in message
                if attempt >= max_retries or not is_rate_limit:
                    raise
                wait_seconds = 2 * (2 ** attempt)  # 2s, 4s, 8s
                logger.warning(f"LLM 限流（第{attempt + 1}次），{wait_seconds}s 后重试: {e}")
                await asyncio.sleep(wait_seconds)
        raise last_error or Exception("LLM 调用失败")

    async def analyze_stream(
        self,
        resume_input: Union[str, bytes],
        jd_text: str,
        filename: str = "resume",
        atoms: Optional[List[Dict[str, Any]]] = None
    ):
        """单 prompt 主版本：输出完整报告，再压成前端稳定结构"""
        try:
            yield ("progress", {"stage": "start", "message": "🔍 分析中..."})

            if isinstance(resume_input, bytes):
                resume_text = self._extract_resume_text(resume_input, filename)
            else:
                resume_text = resume_input

            # 命中缓存：同一简历 + 同一 JD 直接返回一致结果，避免连点跳级
            cache_key = self._make_cache_key(resume_text, jd_text)
            cached = self._result_cache.get(cache_key)
            if cached is not None:
                yield ("result", cached)
                yield ("done", {"message": "✓ 分析完成"})
                return

            jd_requirements = self._extract_jd_requirements(jd_text)
            resume_text = self._smart_truncate_resume_text(resume_text, jd_requirements)
            atoms_text = self._format_atoms_for_prompt(atoms)

            prompt = f"""你现在扮演一名有大厂一线经验的招聘官 + 业务面试官，专长是 AI 产品 / 数据产品 / B 端产品 / LLM 应用岗位筛选。

你的任务不是安慰候选人，也不是泛泛地“优化简历”，而是像真实招聘场景那样回答三件事：
1. 这份简历与当前 JD 是否真的匹配；
2. 哪些地方只是表面沾边，但证据不足；
3. 候选人当前最大的 gap 在哪，应该怎么低成本补位。

【角色要求】
1. 先像招聘官一样判断“过不过初筛”，再判断“值不值得推进”。
2. 你可以犀利，但不能刻薄；可以直接，但必须给解法。
3. 你不是职业规划师，不写鸡汤，不写正确但没用的话。

【分析原则】
1. 先拆 JD：区分必须具备、强相关加分、可培养项，并识别隐性门槛。
2. 再看证据：任何判断都尽量绑定到 JD 要求或简历证据，禁止脑补。
3. 不要只看关键词命中，要看是否真的证明了候选人做过什么、本人负责什么、难度如何、结果如何、是否经得起追问。
4. gap 要区分：能力缺失、证据缺失、表达缺失。不要把三者混在一起。
5. 如果候选人背景还行但表达不够，要明确指出是“证据颗粒度不足”或“呈现方式不够直接”，不要一味否定人。
6. 如果明显不匹配，也要直接指出，不要为了好听而虚高打分。
7. 每个关键 gap 都优先给“低成本补表达/补证据”的方案，再给“中成本补经历”的方案。
8. 允许给 side_door_fix / 旁路补位技巧，但必须真实、可执行、不能造假、不能伪造经历、不能编不存在的项目。

【你最该避免的错误】
1. 用空话代替判断，例如“沟通能力强”“综合素质不错”“建议继续提升”。
2. 用关键词重合代替真实匹配。
3. 在证据不足时替候选人补经历、补结果、补指标。
4. 只会挑刺，不给具体补法。

【评分方法论：结构化简历评估（HR / 工业组织心理学标准）】
你必须按下面这套有学科依据的结构化方法评估，而不是凭感觉打分：
1. KSAO 工作分析（O*NET / SIOP 标准）：把每条 JD 要求归类为
   - K 知识(Knowledge)：领域概念、原理（如"理解 LLM/RAG 原理"）
   - S 技能(Skill)：可操作的熟练度（如"熟练 SQL / Prompt 设计"）
   - A 能力(Ability)：稳定的认知/解决问题能力（如"逻辑拆解、方案设计"）
   - O 其他特质(Other)：经验年限、学历、性格倾向等（如"0-1 落地经验、本科以上"）
2. Demands-Abilities Fit（Edwards 1991 / Kristof-Brown 2005）：匹配 = 岗位"要求层级(required_level 1-3)"与候选人"展现层级(demonstrated_level 0-3)"的差，而不是关键词重合。
   - required_level：1=了解/接触即可，2=熟悉/能独立做，3=精通/能主导
   - demonstrated_level：0=简历无体现，1=提及但无证据，2=有项目证据，3=有主导且有结果
3. STAR 证据强度（McClelland 行为事件法）：evidence_strength 0-4
   - 0=无；1=只有名词/技能词；2=有 Situation+Task；3=有 Action；4=有明确 Result/量化结果
4. 权重分层（补偿性 + 非补偿性混合模型，Schmidt & Hunter 1998）：
   - knockout：硬门槛/一票否决项（学历、必备硬技能、必需经验），未达标直接压低总分
   - core：岗位核心胜任力，按层级差与证据强度补偿性加权
   - nice：加分项，达标加分、缺失不扣分

【评分要求】
- 输出 0-100 分。分数应当与上面 KSAO 各条的层级差和证据强度一致，可被复算。
- 85-100：knockout 全部达标 + core 高度匹配且证据强(STAR≥3) + 关键风险极少。
- 70-84：knockout 达标，core 多数匹配，但有 1-2 个证据/层级缺口。
- 55-69：有相关性，但 core 证据普遍不足(STAR≤2)或有 knockout 接近未达标。
- 0-54：knockout 明显未达标，或 core 大面积缺失。
- 除非"knockout 全达标 + core 证据充分"，否则不要轻易给 85 分以上。

【输出约束】
只能输出合法 JSON 对象，不允许输出 Markdown、解释文字、代码块。
字段必须齐全；没有内容时用空字符串、空数组或合理默认值，不要省略字段。

JSON Schema:
{{
  "executive_summary": {{
    "match_score": 0,
    "match_level": "A级|B级|C级|D级",
    "hiring_recommendation": "一句话建议，说明是否值得推进，口吻像大厂招聘官",
    "one_sentence_verdict": "一句话定调，像大厂招聘官在看完简历后的第一反应，要求锋利、专业、像箴言"
  }},
  "jd_interpretation": {{
    "role_title": "岗位名称的人话理解",
    "overall_goal": "这个岗位真正想要的人在做什么",
    "notes": ["这份JD里最需要注意的点1", "点2"]
  }},
  "jd_decomposition": {{
    "hard_requirements": ["3-8条JD硬要求"],
    "core_competencies": ["2-4条关键能力"],
    "plus_items": ["0-4条加分项"],
    "pseudo_requirements": ["0-4条看起来像要求、但不应过度扣分的表述"]
  }},
  "requirement_checks": [
    {{
      "requirement": "某条JD要求",
      "original_text": "JD原话",
      "concept_breakdown": [
        {{
          "term": "原句里的一个关键短语",
          "meaning": "这个短语在招聘官语境下到底是什么意思"
        }}
      ],
      "plain_text": "翻译成人话后的真实要求",
      "human_translation": "一句更接地气、更像人说话的翻译",
      "interviewer_intent": "招聘官真正想确认什么",
      "resume_rewrite_hint": "如果候选人真做过，简历里这一条应该怎么写",
      "interview_tell_hint": "面试里应该怎么讲这条",
      "requirement_type": "tool_experience/product_judgment/execution/communication/business_understanding/other",
      "ksao_type": "K|S|A|O",
      "ksao_label": "知识|技能|能力|特质",
      "dimension": "education|experience|skill|project|potential",
      "weight_tier": "knockout|core|nice",
      "required_level": 1,
      "demonstrated_level": 0,
      "evidence_strength": 0,
      "status": "matched|partially_matched|not_matched|insufficient_evidence",
      "gap_type": "capability_gap/evidence_gap/experience_gap/expression_gap/none",
      "is_hard_gate": true,
      "is_bonus": false,
      "is_abstract": false,
      "observable_signals": ["可观察信号1", "可观察信号2"],
      "jd_evidence": "对应JD证据",
      "resume_evidence": "对应简历证据，没有则写空",
      "reason": "为什么这么判断",
      "fix_strategy": "如果有gap，优先怎么补"
    }}
  ],
  "strengths": [
    {{
      "point": "一个真正有含金量的匹配点",
      "evidence": "简历中的证据",
      "why_it_matters": "为什么这点对JD重要",
      "interview_probe": "面试时可以怎么放大"
    }}
  ],
  "gaps": [
    {{
      "gap": "关键缺失项",
      "severity": "high|medium|low",
      "why_it_blocks": "为什么它会影响初筛/面试",
      "emergency_fix": "短期怎么补表达",
      "transfer_fix": "如果没有直接经历，如何迁移已有经历去补"
    }}
  ],
  "rewrite_priorities": [
    {{
      "priority": 1,
      "target_section": "应该修改的简历模块",
      "problem": "当前写法的问题",
      "rewrite_goal": "希望改成什么效果",
      "rewrite_method": "具体怎么改",
      "example_direction": "一句改写方向提示",
      "side_door_fix": "一个真实可执行的旁路补位技巧，前提是不造假"
    }}
  ],
  "action_plan": {{
    "within_24_hours": ["1-3条"],
    "within_7_days": ["1-3条"],
    "longer_term": ["0-3条"]
  }},
  "interview_prediction": {{
    "必考题预测": [
      {{
        "问题": "高概率面试题",
        "参考回答思路": "一句很短的答题方向"
      }}
    ],
    "终局鼓励": "一句简短提醒"
  }},
  "recommendation": {{
    "should_interview": true,
    "reason": "是否建议推进到面试，以及核心理由"
  }}
}}

【输出内容要求】
- jd_decomposition 里必须区分：
  - hard_requirements：不满足会明显影响初筛的硬门槛
  - core_competencies：岗位真正要看的能力
  - plus_items：有更好、没有也不必一票否决
  - pseudo_requirements：JD里常见的包装性措辞/软性表述，不要当成硬门槛
- jd_interpretation 必须先把 JD 翻译成人话，明确这个岗位真正想考什么；如果 JD 写得抽象，要主动翻译成可验证能力。
- strengths 最多 3 条，只保留最有杀伤力的点。
- gaps 最多 3 条，必须按严重程度排序。
- rewrite_priorities 最多 3 条，必须足够可执行。
- gaps 的写法要像真实招聘官指出阻塞点，而不是泛泛列短板。
- rewrite_priorities 必须写成“简历编辑指令”而不是泛泛建议：优先使用“补充 / 删除 / 替换 / 前置 / 量化 / 显性化”这类动作词。
- rewrite_priorities 中至少 2 条要给出“side_door_fix”，即低成本补位技巧，例如如何重排已有经历、如何换说法、如何借已有项目侧写目标能力，但严禁造假。
- 如果判断为 Gap，但候选人可能有可迁移经历，必须在 transfer_fix 中说清楚“从什么经历迁移成什么表述”。
- requirement_checks 至少覆盖最重要的 5 条 JD 要求，但应以 hard_requirements 和 core_competencies 为主，不要把 pseudo_requirements 当成硬扣分项。
- requirement_checks 中每一条都必须同时给出：JD原话(original_text)、人话翻译(plain_text)、gap 类型(gap_type) 和可观察信号(observable_signals)。
- requirement_checks 中每一条都必须填写结构化评估字段，且要彼此自洽：
  - ksao_type / ksao_label：按 KSAO 分类（K知识 / S技能 / A能力 / O特质）。
  - dimension：把这条要求归到五个评估维度之一——education(学历背景) / experience(经验匹配) / skill(技能匹配) / project(项目深度) / potential(成长潜力)。学历相关填 education，实习工作年限/相关度填 experience，硬技能工具填 skill，项目复杂度成果填 project，学习力/探索欲/软素质填 potential。
  - weight_tier：knockout（硬门槛/一票否决）/ core（核心胜任力）/ nice（加分项）。学历、必备硬技能、必需经验设为 knockout。
  - required_level(1-3)：这条 JD 要求到什么程度。
  - demonstrated_level(0-3)：候选人在简历里展现到什么程度，必须与 resume_evidence 一致；无证据填 0。
  - evidence_strength(0-4)：按 STAR 完整度打分（有量化结果才给 4）。
  - status 必须与上面数值一致：demonstrated_level≥required_level 且 evidence_strength≥3 才算 matched；有证据但层级或强度不够算 partially_matched；提及无证据算 insufficient_evidence；完全没有算 not_matched。
- 【硬门槛严格判定】对于"专业相关 / 学历要求 / 必备硬技能"这类 knockout 要求，必须严格：
  - 如果 JD 点名了专业方向（如"计算机/软件/人工智能相关专业"），而候选人专业明显不属于该方向（如"国际中文教育""汉语言文学""市场营销"投技术岗），这条专业要求的 demonstrated_level 必须填 0 或 1，status 填 not_matched 或 insufficient_evidence，绝不能因为候选人有相关兴趣/求职意向就给 2 以上。
  - 跨专业但学历层级达标时，也只在该专业要求上据实给低分，不要为了"鼓励"而抬高 knockout 项。
- 如果一条 JD 要求写得抽象，比如“owner意识”“业务sense”“推动力”，必须翻译成招聘官真正会看的行为信号，不能直接照抄就开始判断。
- requirement_checks 里的每一条，都先像人一样“拆短语再判断”：
  - concept_breakdown：把原句拆成 2-4 个关键短语，并分别解释这些短语到底在说什么。
  - human_translation：用接地气的大白话把整句重写一遍，避免用黑话解释黑话。
  - interviewer_intent：明确招聘官真正想确认什么，不要只停留在表层词义。
  - resume_rewrite_hint：告诉候选人如果真做过，这条应该怎样写回简历。
  - interview_tell_hint：告诉候选人面试里这条应该怎么讲，优先讲什么例子。
- 对抽象 JD，先做“短语拆解 -> 说人话 -> 招聘官意图 -> 再判断是否匹配”这四步；不要一看到黑话就直接判 matched / gap。
- 像“有B端产品意识，具备B端古典产品经理能力和知识体系”这类句子，不能只翻成“懂B端产品”，而要拆出：企业业务流程 / 角色权限 / 复杂逻辑 / PRD与流程设计 / 系统思维 这些真正考点。
- 解释要像一个懂业务的一线面试官在说人话：专业，但别装腔作势；允许直白，禁止继续堆黑话。
- recommendation.reason 要和分数逻辑一致，不能自相矛盾。
- 如果简历证据不足，就写 insufficient_evidence，不要瞎编。
- one_sentence_verdict 不要温吞。要像招聘官的第一判断，专业、锋利、克制、像真实面评里的第一句结论。
- hiring_recommendation 要兼顾判断与帮助：既告诉用户值不值得投，也要指出优先补哪一刀最有效。
- why_it_blocks 要像招聘官解释“为什么会卡简历”那样写，优先使用“初筛阶段不容易判断 / 不足以支撑高分 / 面试中大概率会被追问 / 关键价值没有被清楚呈现 / 还不足以让人放心推进”这类真实表达，不要写成学术说明。
- emergency_fix 要优先给 7 天内能完成的补表达/补证据动作。
- transfer_fix 要说明：如果没有直接经历，应该从哪段已有经历迁移、重排、补充或换说法。
- 整体语气要像真实大厂招聘官：判断明确，但始终基于证据；指出问题，但对候选人真的有帮助。
- 所有字段尽量短，单条优先控制在 50 字以内；不要写长段解释，避免 JSON 过长。
- interview_prediction 最多 2 题；参考回答思路必须很短。
- action_plan 每个阶段最多 2 条，优先保留最高价值动作。

【输入材料】
JD硬要求列表：
{json.dumps(jd_requirements, ensure_ascii=False)}

JD原文：
{jd_text[:2500]}

简历正文：
{resume_text[:2600]}

经历原子库：
{atoms_text}
"""

            response = await self._acompletion_with_retry(
                messages=[
                    {"role": "system", "content": "你是首席简历匹配架构师，只能输出合法JSON对象，不允许输出任何JSON之外的内容。"},
                    {"role": "user", "content": prompt}
                ],
            )

            if not response.choices:
                raise Exception("AI未返回结果")

            result_text = response.choices[0].message.content or ""
            if not result_text.strip():
                raise Exception("AI返回空内容")

            try:
                result = self._extract_json_object(result_text)
            except Exception:
                result = {
                    "executive_summary": {
                        "match_score": 60,
                        "match_level": "C级",
                        "hiring_recommendation": "可作为备选",
                        "one_sentence_verdict": result_text[:120]
                    },
                    "jd_decomposition": {
                        "hard_requirements": jd_requirements[:3],
                        "core_competencies": [],
                        "plus_items": []
                    },
                    "requirement_checks": [],
                    "strengths": [],
                    "gaps": [],
                    "resume_diagnosis": {},
                    "rewrite_priorities": [],
                    "action_plan": {"within_24_hours": [], "within_7_days": [], "longer_term": []},
                    "application_strategy": {"should_apply_now": True, "best_fit_roles": [], "roles_to_avoid_for_now": [], "strategy_note": ""},
                    "recommendation": {"should_interview": True, "reason": "请查看详细分析"}
                }

            final_result = self._normalize_recruiter_report(result, raw_text=result_text, resume_text=resume_text, jd_text=jd_text)
            # 写入缓存（用未截断前算好的 key），保证后续同输入结果完全一致
            try:
                self._result_cache[cache_key] = final_result
            except Exception:
                pass
            yield ("result", final_result)
            yield ("done", {"message": "✓ 分析完成"})

        except Exception as e:
            logger.error(f"分析失败，返回降级兜底结果: {e}")
            # 降级兜底：LLM 重试仍失败时，仍返回一份可渲染的基础结果，避免前端白屏
            try:
                safe_requirements = self._extract_jd_requirements(jd_text)
            except Exception:
                safe_requirements = []
            fallback_raw = {
                "executive_summary": {
                    "match_score": 60,
                    "match_level": "C级",
                    "hiring_recommendation": "AI 智能分析暂时不可用（接口繁忙），以下为基础匹配视图，建议稍后重试以获得完整的招聘官视角分析。",
                    "one_sentence_verdict": "AI 服务当前繁忙，已为你生成基础匹配视图，稍后重试可获得更深入的逐条分析。"
                },
                "jd_decomposition": {
                    "hard_requirements": safe_requirements[:5],
                    "core_competencies": [],
                    "plus_items": [],
                    "pseudo_requirements": []
                },
                "requirement_checks": [
                    {
                        "requirement": req,
                        "original_text": req,
                        "status": "insufficient_evidence",
                        "reason": "AI 分析暂不可用，未能逐条比对，建议稍后重试。"
                    }
                    for req in safe_requirements[:5]
                ],
                "strengths": [],
                "gaps": [],
                "rewrite_priorities": [],
                "action_plan": {"within_24_hours": ["稍后重试一次完整的 AI 匹配分析"], "within_7_days": [], "longer_term": []},
                "recommendation": {"should_interview": False, "reason": "请稍后重试以获得完整分析结果"}
            }
            fallback_result_payload = self._normalize_recruiter_report(fallback_raw, raw_text="")
            fallback_result_payload["degraded"] = True
            yield ("result", fallback_result_payload)
            yield ("done", {"message": "已返回基础结果（AI 服务繁忙）"})

    async def analyze(
        self,
        resume_input: Union[str, bytes],
        filename: str,
        jd_text: str,
        atoms: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        final_result: Optional[Dict[str, Any]] = None
        async for event_type, event_data in self.analyze_stream(
            resume_input=resume_input,
            jd_text=jd_text,
            filename=filename,
            atoms=atoms
        ):
            if event_type == "result":
                final_result = event_data
            elif event_type == "error":
                raise Exception(event_data.get("message", "分析失败"))

        if final_result is None:
            raise Exception("分析未返回结果")
        return final_result


def fallback_result():
    """当 AI 分析失败时返回兜底结果"""
    yield ("progress", {"stage": "fallback", "message": "AI响应异常，使用基础分析..."})
    yield ("result", {
        "match_score": 50,
        "match_level": "C级",
        "executive_summary": "AI分析暂时不可用，建议稍后重试或人工审核",
        "jd_analysis": {"must_requirements": []},
        "strengths_vs_jd": ["简历已提交", "JD已解析"],
        "gaps_vs_jd": ["AI分析服务异常"],
        "action_plan": ["动作：稍后重试；修改对象：当前匹配分析；预期效果：获得可用结果"],
        "recommendation": {
            "should_interview": False,
            "reason": "建议人工审核简历内容"
        }
    })
    yield ("done", {"message": "✓ 基础分析完成"})


_one_shot_matcher_instance: Optional[OneShotMatchEngine] = None


def get_one_shot_matcher() -> OneShotMatchEngine:
    global _one_shot_matcher_instance
    if _one_shot_matcher_instance is None:
        _one_shot_matcher_instance = OneShotMatchEngine()
    return _one_shot_matcher_instance
