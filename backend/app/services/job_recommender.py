"""
Offer 捕手 - 岗位推荐服务

直接命中赛题痛点1：从内置岗位池中，基于简历做匹配打分并返回 Top-N 推荐岗位。
采用轻量级的关键词/技能重合度打分（规则实现，不依赖 LLM），保证演示稳定可解释。
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

JOB_POOL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "job_pool.json",
)

# 中文常见无意义词，避免污染匹配
_STOPWORDS = {
    "负责", "参与", "能够", "以及", "进行", "相关", "经验", "能力", "岗位",
    "要求", "加分", "我们", "提供", "熟练", "掌握", "具备", "了解", "优先",
    "公司", "职责", "学历", "本科", "硕士", "及以上", "专业",
}


def _tokenize(text: str) -> List[str]:
    """把文本切成可比对的 token：英文/数字串 + 2-8 字中文词。"""
    raw = re.findall(r"[A-Za-z0-9\+\#\.]+|[\u4e00-\u9fff]{2,8}", str(text or "").lower())
    tokens: List[str] = []
    for tok in raw:
        tok = tok.strip()
        if len(tok) < 2 or tok in _STOPWORDS:
            continue
        tokens.append(tok)
    return tokens


def _resume_text(resume: Dict[str, Any]) -> str:
    """把简历结构拼成一段可分词的文本。"""
    parts: List[str] = []
    basic = resume.get("basic_info", {}) or {}
    parts.append(basic.get("major", ""))

    skills = resume.get("skills", []) or []
    for s in skills:
        parts.append(s if isinstance(s, str) else str(s.get("name", "")))

    for exp in resume.get("experience", []) or []:
        parts.append(exp.get("position", ""))
        parts.append(exp.get("company", ""))
        parts.append(exp.get("description", ""))

    for proj in resume.get("projects", []) or []:
        parts.append(proj.get("name", ""))
        parts.append(proj.get("description", ""))
        for t in proj.get("tech_stack", []) or []:
            parts.append(t)

    return " ".join([p for p in parts if p])


class JobRecommender:
    """基于岗位池的简历-岗位匹配推荐器。"""

    def __init__(self, job_pool_path: str = JOB_POOL_PATH):
        self.job_pool_path = job_pool_path
        self._jobs: Optional[List[Dict[str, Any]]] = None

    def _load_jobs(self) -> List[Dict[str, Any]]:
        if self._jobs is None:
            try:
                with open(self.job_pool_path, "r", encoding="utf-8") as f:
                    self._jobs = json.load(f)
            except Exception:
                self._jobs = []
        return self._jobs

    def _score_job(self, resume_tokens: set, resume_token_text: str, job: Dict[str, Any]) -> Dict[str, Any]:
        """对单个岗位打分，返回匹配度(0-100)、命中技能、缺失技能。"""
        job_skills = job.get("skills", []) or []
        matched_skills: List[str] = []
        missing_skills: List[str] = []

        for skill in job_skills:
            skill_tokens = _tokenize(skill)
            # 技能命中：技能的任一 token 出现在简历文本里
            hit = any(tok in resume_token_text for tok in skill_tokens) or (skill.lower() in resume_token_text)
            if hit:
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)

        # JD 全文 token 重合度（补充信号）
        jd_tokens = set(_tokenize(job.get("jd_text", "")))
        overlap = resume_tokens & jd_tokens

        skill_ratio = len(matched_skills) / max(1, len(job_skills))
        overlap_ratio = len(overlap) / max(1, len(jd_tokens))

        # 加权：技能命中为主(70%)，JD 全文重合为辅(30%)
        raw = skill_ratio * 0.7 + overlap_ratio * 0.3
        # 映射到更可读的 40-95 区间，避免出现 0 分或满分的极端观感
        score = round(40 + raw * 55)
        score = max(0, min(100, score))

        if matched_skills:
            reason = f"命中 {len(matched_skills)}/{len(job_skills)} 项关键技能：{('、'.join(matched_skills[:4]))}"
        else:
            reason = "与该岗位的技能重合较低，可作为拓展方向参考"

        return {
            "id": job.get("id", ""),
            "position_name": job.get("position_name", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "tags": job.get("tags", []),
            "jd_text": job.get("jd_text", ""),
            "match_score": score,
            "matched_skills": matched_skills[:6],
            "missing_skills": missing_skills[:6],
            "reason": reason,
        }

    def recommend(self, resume: Dict[str, Any], top_n: int = 5) -> List[Dict[str, Any]]:
        """返回按匹配度降序的 Top-N 岗位推荐。"""
        jobs = self._load_jobs()
        if not jobs:
            return []

        # 支持两种输入：结构化简历 dict，或带 raw_text 的纯文本
        if resume.get("raw_text"):
            resume_token_text = str(resume.get("raw_text", "")).lower()
        else:
            resume_token_text = _resume_text(resume).lower()
        resume_tokens = set(_tokenize(resume_token_text))

        scored = [self._score_job(resume_tokens, resume_token_text, job) for job in jobs]
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return scored[:top_n]


_recommender_instance: Optional[JobRecommender] = None


def get_job_recommender() -> JobRecommender:
    global _recommender_instance
    if _recommender_instance is None:
        _recommender_instance = JobRecommender()
    return _recommender_instance
