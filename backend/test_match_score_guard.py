"""匹配分数防虚高护栏。

不调用外部 LLM，只验证：即使模型误给垃圾简历高分，本地证据制动器也会压分。
"""
import os

os.environ.setdefault("LOG_DIR", "/tmp")
os.environ.setdefault("DB_PATH", "/tmp/offer-catcher-main-test.db")

from app.services.one_shot_match_engine import OneShotMatchEngine


JD_TEXT = """
后端开发实习生
要求：熟悉 Java、Spring Boot、MySQL、Redis，理解 RESTful API 设计。
有后端项目经验，能完成接口开发、数据库设计和缓存优化。
"""


def make_high_score_model_result() -> dict:
    return {
        "executive_summary": {
            "match_score": 92,
            "match_level": "A级",
            "hiring_recommendation": "建议推进面试",
            "one_sentence_verdict": "模型误判为高度匹配",
        },
        "jd_interpretation": {"role_title": "后端开发实习生", "overall_goal": "", "notes": []},
        "jd_decomposition": {
            "hard_requirements": ["熟悉 Java、Spring Boot、MySQL、Redis"],
            "core_competencies": ["后端项目经验", "接口开发"],
            "plus_items": [],
            "pseudo_requirements": [],
        },
        "requirement_checks": [
            {
                "requirement": "熟悉 Java、Spring Boot、MySQL、Redis",
                "original_text": "熟悉 Java、Spring Boot、MySQL、Redis",
                "plain_text": "能做基础后端开发",
                "requirement_type": "tool_experience",
                "dimension": "skill",
                "weight_tier": "knockout",
                "required_level": 2,
                "demonstrated_level": 3,
                "evidence_strength": 4,
                "status": "matched",
                "resume_evidence": "模型误判证据",
            },
            {
                "requirement": "有后端项目经验",
                "original_text": "有后端项目经验",
                "plain_text": "做过后端项目",
                "requirement_type": "execution",
                "dimension": "project",
                "weight_tier": "core",
                "required_level": 2,
                "demonstrated_level": 3,
                "evidence_strength": 4,
                "status": "matched",
                "resume_evidence": "模型误判证据",
            },
        ],
        "strengths": [{"point": "模型误判优势", "evidence": "空", "why_it_matters": "", "interview_probe": ""}],
        "gaps": [],
        "rewrite_priorities": [],
        "action_plan": {"within_24_hours": [], "within_7_days": [], "longer_term": []},
        "interview_prediction": {"必考题预测": [], "终局鼓励": ""},
        "recommendation": {"should_interview": True, "reason": "模型误判建议推进"},
    }


def test_garbage_resume_high_score_is_capped() -> None:
    engine = OneShotMatchEngine()
    garbage_resume = "本人性格开朗，吃苦耐劳，服从安排，热爱学习，希望贵公司给我一个机会。"
    result = engine._normalize_recruiter_report(
        make_high_score_model_result(),
        resume_text=garbage_resume,
        jd_text=JD_TEXT,
    )
    assert result["match_score"] <= 50
    assert result["match_level"] == "D级"
    assert result["recommendation"]["should_interview"] is False
    guard = result["sections"]["score_breakdown"]["local_evidence_guardrail"]
    assert guard["applied"] is True
    assert guard["overlap"] == []


def test_relevant_resume_not_capped_by_local_guard() -> None:
    engine = OneShotMatchEngine()
    relevant_resume = """
    校园二手交易平台：使用 Java、Spring Boot 和 MyBatis 开发商品发布、订单查询等 RESTful API。
    设计 MySQL 商品表和订单表，使用 Redis 缓存热门商品列表，降低重复查询压力。
    """
    result = engine._normalize_recruiter_report(
        make_high_score_model_result(),
        resume_text=relevant_resume,
        jd_text=JD_TEXT,
    )
    guard = result["sections"]["score_breakdown"].get("local_evidence_guardrail")
    assert not guard
    assert result["match_score"] >= 85


if __name__ == "__main__":
    test_garbage_resume_high_score_is_capped()
    test_relevant_resume_not_capped_by_local_guard()
    print("Match score guard tests passed")
