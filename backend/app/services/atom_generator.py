"""
Offer 捕手 - 经历原子生成服务

设计原则（与产品共识对齐）：
- 原子 = 一段「真实经历」（工作 / 项目 / 教育 / 获奖）。
- 经历分两层：
  - 事实层(fact)：公司、岗位、时间、做的是哪个项目 —— 锁定、不可改、不可编造。
  - 表达层(expression)：这段经历怎么描述、强调哪个侧面 —— 可针对不同 JD 合法改写。
- LLM 只负责「拆经历」和「改表达」，绝不允许编造没发生的事实。
"""
import json
import logging
import re
from typing import List, Dict, Optional

from app.ai.llm_client import get_llm_client

logger = logging.getLogger(__name__)


class AtomGenerator:
    """经历原子生成器 - 把简历拆成可重用、可针对 JD 重新表达的经历原子"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client or get_llm_client()

    # ========== 1. 从简历拆解经历原子 ==========

    def from_resume_data(self, resume_data: Dict) -> List[Dict]:
        """
        从结构化简历数据生成经历原子。

        只生成「经历类」原子：工作 / 实习 / 项目（教育、技能为纯事实/标签，不做成原子）。
        先用规则把事实层（公司/岗位/时间/项目名）稳定地切出来，
        再用 LLM 为每段经历补一句话亮点和技能标签（失败则降级到规则版）。
        """
        atoms: List[Dict] = []

        for exp in resume_data.get("experience", []) or []:
            position = exp.get("position", "") or ""
            # 实习与正职区分：岗位名含「实习」判为实习类
            atom_type = "intern" if "实习" in position else "work"
            atoms.append(self._build_atom(
                atom_type=atom_type,
                title=position or ("实习经历" if atom_type == "intern" else "工作经历"),
                company=exp.get("company", ""),
                role=position,
                duration=exp.get("duration", ""),
                description=exp.get("description", "")
            ))

        for project in resume_data.get("projects", []) or []:
            atoms.append(self._build_atom(
                atom_type="project",
                title=project.get("name", "") or "项目经历",
                company=project.get("company", ""),
                role=project.get("role", ""),
                duration=project.get("duration", ""),
                description=project.get("description", ""),
                skills=project.get("tech_stack", [])
            ))

        # 教育、技能不做成原子（纯事实/标签，没有可改写的表达层）

        # 用 LLM 批量为经历补亮点与技能（一次调用，省 token）
        try:
            self._enrich_atoms_with_llm(atoms)
        except Exception as e:
            logger.warning(f"LLM 经历增强失败，使用规则版降级: {e}")

        return atoms

    def _build_atom(
        self,
        atom_type: str,
        title: str,
        company: str = "",
        role: str = "",
        duration: str = "",
        description: str = "",
        skills: Optional[List[str]] = None
    ) -> Dict:
        """构造一个经历原子：事实层锁定，表达层默认用简历原文。"""
        skills = [str(s).strip() for s in (skills or []) if str(s).strip()]
        if not skills:
            skills = self._extract_skills(description)
        fact = {
            "company": company,
            "role": role,
            "duration": duration,
        }
        return {
            "type": atom_type,
            "title": title,
            "company": company,
            "description": description,  # 兼容旧字段：表达层基线
            "skills": skills,
            "meta": {
                "fact": fact,            # 事实层（锁定）
                "base_description": description,  # 表达层基线（简历原文）
                "highlight": "",         # 一句话亮点（LLM 补）
                "variants": []           # 针对不同 JD 的改写版本
            }
        }

    def _enrich_atoms_with_llm(self, atoms: List[Dict]) -> None:
        """用一次 LLM 调用，为所有经历补「一句话亮点」和「技能标签」。"""
        if not atoms:
            return
        payload = [
            {
                "index": i,
                "type": a["type"],
                "title": a["title"],
                "company": a.get("company", ""),
                "description": a["meta"]["base_description"]
            }
            for i, a in enumerate(atoms)
        ]
        prompt = (
            "你是资深简历顾问。下面是候选人简历里拆出的多段真实经历。\n"
            "请为每段经历输出：一句话亮点(highlight，<=30字，突出可量化成果或最有价值的点)、"
            "技能标签(skills，3-6个，从描述中真实出现的技术/方法/能力提取)。\n"
            "严禁编造经历中不存在的公司、项目、数字。只能基于给定描述提炼。\n"
            "只输出 JSON：{\"atoms\":[{\"index\":0,\"highlight\":\"...\",\"skills\":[\"...\"]}]}\n\n"
            f"经历列表：\n{json.dumps(payload, ensure_ascii=False)}"
        )
        result = self.llm_client.call_json([{"role": "user", "content": prompt}], model="kimi")
        for item in (result.get("atoms") or []):
            idx = item.get("index")
            if not isinstance(idx, int) or idx < 0 or idx >= len(atoms):
                continue
            highlight = str(item.get("highlight", "")).strip()
            skills = [str(s).strip() for s in (item.get("skills") or []) if str(s).strip()]
            if highlight:
                atoms[idx]["meta"]["highlight"] = highlight
            if skills:
                atoms[idx]["skills"] = skills

    # ========== 2. 针对 JD 改写表达层 ==========

    def rewrite_for_jd(self, atom: Dict, jd_text: str) -> Dict:
        """
        针对目标 JD 重写这段经历的「表达层」，返回一个 variant。

        守则：只改措辞/侧重/呈现，不改事实层；不得编造未发生的项目、职责、数字。
        """
        fact = (atom.get("meta") or {}).get("fact", {})
        base = (atom.get("meta") or {}).get("base_description") or atom.get("description", "")
        prompt = (
            "你是顶尖简历优化顾问。请把下面这段【真实经历】针对【目标JD】重新表达，"
            "让它更贴合岗位要求、更容易通过初筛。\n\n"
            "【硬性守则】\n"
            "1. 事实层锁定：公司、岗位、时间、做过的项目都不可更改、不可编造。\n"
            "2. 只允许：调整措辞、突出与JD相关的侧面、把已有成果更清晰/可量化地呈现、补充与描述一致的合理细节。\n"
            "3. 禁止：编造没发生的项目/职责/数字、夸大到与原描述矛盾。\n"
            "4. 输出 2-4 条 bullet，写成真实简历里的项目 bullet 风格：\n"
            "   - 以动词开头（负责/主导/搭建/优化/推动/落地…）。\n"
            "   - 句式用「做了什么 + 怎么做 + 量化结果」，结果优先用数字。\n"
            "   - 禁止用「展现了/体现了/具备…的能力」这类空话总结性结尾，简历里没人这样写。\n"
            "   - 每条尽量控制在 40 字以内，干练、可被追问。\n\n"
            f"事实层（锁定）：{json.dumps(fact, ensure_ascii=False)}\n"
            f"经历原始描述：{base}\n\n"
            f"目标JD：\n{jd_text[:1500]}\n\n"
            "只输出 JSON：{\"bullets\":[\"...\"],\"emphasis\":\"这次改写主要强调了什么(<=20字)\"}"
        )
        result = self.llm_client.call_json([{"role": "user", "content": prompt}], model="kimi")
        bullets = [str(b).strip() for b in (result.get("bullets") or []) if str(b).strip()][:4]
        emphasis = str(result.get("emphasis", "")).strip()
        return {
            "bullets": bullets,
            "emphasis": emphasis,
            "jd_excerpt": jd_text.strip()[:60]
        }

    def argue_user_fit(self, atom: Dict, jd_text: str) -> Dict:
        """
        兴趣类原子专用：论证「我是这个产品的目标用户」。

        与经历类 STAR 改写不同——这里产出的是「用户契合论证」：
        - 先判断兴趣与目标产品域是否真有重叠；不相关时明确提示不要硬蹭。
        - 相关时，把兴趣放大成「核心用户洞察 / 需求直觉」，体现 Product Sense by Empathy。
        """
        base = (atom.get("meta") or {}).get("base_description") or atom.get("description", "")
        title = atom.get("title", "")
        prompt = (
            "你是顶尖 C 端 AI 产品的招聘负责人。候选人有一项兴趣/用户身份，"
            "请判断它对【目标JD】所属产品是否构成「目标用户契合」信号，并据此输出。\n\n"
            "【判断与守则】\n"
            "1. 先判断 relevant：这个兴趣是否和 JD 的产品域/目标用户群真有重叠"
            "（如：乙游爱好者 × 乙女向陪伴AI = 强契合；乙游 × 企业B端数据平台 = 不契合）。\n"
            "2. 若 relevant=false：bullets 返回空数组，note 写明「此岗位无需突出该兴趣，硬写反而显得不专业」。\n"
            "3. 若 relevant=true：把兴趣放大成「我是核心目标用户」的论证，体现需求直觉与场景理解，"
            "可写成 1-2 条简历可用句（如：作为该品类重度用户，对XX体验痛点有第一手洞察）。\n"
            "4. 禁止编造没说过的经历或数据，只基于这项兴趣本身合理引申。\n\n"
            f"兴趣/用户身份：{title}　详情：{base}\n\n"
            f"目标JD：\n{jd_text[:1500]}\n\n"
            "只输出 JSON：{\"relevant\":true,\"bullets\":[\"...\"],\"emphasis\":\"契合点(<=20字)\",\"note\":\"\"}"
        )
        result = self.llm_client.call_json([{"role": "user", "content": prompt}], model="kimi")
        relevant = bool(result.get("relevant", False))
        bullets = [str(b).strip() for b in (result.get("bullets") or []) if str(b).strip()][:3]
        return {
            "relevant": relevant,
            "bullets": bullets if relevant else [],
            "emphasis": str(result.get("emphasis", "")).strip(),
            "note": str(result.get("note", "")).strip(),
            "jd_excerpt": jd_text.strip()[:60]
        }

    # ========== 工具方法 ==========

    def _extract_skills(self, text: str) -> List[str]:
        """从文本中提取技能关键词（LLM 不可用时的降级）"""
        common_skills = [
            "Python", "Java", "JavaScript", "React", "Vue", "Node.js",
            "SQL", "MySQL", "MongoDB", "Redis", "Docker", "Kubernetes",
            "TensorFlow", "PyTorch", "机器学习", "深度学习",
            "AI", "LLM", "RAG", "Agent", "Prompt", "数据分析", "A/B",
            "Git", "Linux", "AWS", "Azure", "GCP", "Milvus", "Embedding"
        ]
        found = []
        text_lower = (text or "").lower()
        for skill in common_skills:
            if skill.lower() in text_lower:
                found.append(skill)
        return found[:6]


_atom_generator_instance: Optional["AtomGenerator"] = None


def get_atom_generator() -> "AtomGenerator":
    global _atom_generator_instance
    if _atom_generator_instance is None:
        _atom_generator_instance = AtomGenerator()
    return _atom_generator_instance
