"""内容安全护栏回归测试。

不调用外部 API，覆盖字段提取误抓、原子改写事实漂移等高风险问题。
"""
import os

os.environ.setdefault("LOG_DIR", "/tmp")
os.environ.setdefault("DB_PATH", "/tmp/offer-catcher-main-test.db")

from app.main import _extract_interests_from_text, _sanitize_resume_bullet
from app.services.atom_generator import AtomGenerator


def test_interest_parser_ignores_inline_mentions() -> None:
    resume = """项目经历：Offer 捕手
推动导出 PDF 优化，关注长简历分页、中文显示、英文技术词、教育经历和兴趣爱好是否完整。

兴趣爱好
喜欢体验 AI 工具、效率产品和教育类应用，也喜欢摄影和羽毛球。
"""
    assert _extract_interests_from_text(resume) == "喜欢体验 AI 工具、效率产品和教育类应用，也喜欢摄影和羽毛球"


def test_interest_parser_does_not_capture_random_sentence() -> None:
    resume = "项目复盘：检查教育经历和兴趣爱好是否完整，避免导出遗漏。"
    assert _extract_interests_from_text(resume) == ""


def test_resume_bullet_sanitizer_keeps_result_packaging() -> None:
    raw = "使用Redis缓存部分高频统计结果，降低重复查询对数据库的压力，提升系统性能"
    assert _sanitize_resume_bullet(raw) == raw


def test_atom_rewrite_guard_allows_result_packaging_but_rewrites_new_entities() -> None:
    atom = {
        "title": "AI 产品经理实习项目负责人",
        "description": "某课程项目模拟企业内部知识管理场景，员工需要在制度文档、产品手册和项目复盘中快速查找答案。",
        "meta": {
            "base_description": "某课程项目模拟企业内部知识管理场景，员工需要在制度文档、产品手册和项目复盘中快速查找答案。"
        },
    }
    bullet = "负责设计并实施AI助手项目，优化知识检索效率，提升员工查询响应速度30%。"
    assert AtomGenerator(llm_client=None)._sanitize_rewrite_bullet(bullet, atom) == "负责参与设计智能助手项目，优化知识检索效率，提升员工查询响应速度30%"


def test_atom_rewrite_guard_removes_jd_injected_facts() -> None:
    atom = {
        "title": "AI 产品经理实习项目负责人",
        "description": "某课程项目模拟企业内部知识管理场景，员工需要在制度文档、产品手册和项目复盘中快速查找答案。",
        "meta": {
            "base_description": "某课程项目模拟企业内部知识管理场景，员工需要在制度文档、产品手册和项目复盘中快速查找答案。"
        },
    }
    guard = AtomGenerator(llm_client=None)
    assert guard._sanitize_rewrite_bullet(
        "与算法团队紧密合作，推动基于大模型的知识库问答功能开发，增强信息检索准确性。",
        atom,
    ) == "推动知识库问答方案设计，增强信息检索准确性"
    assert guard._sanitize_rewrite_bullet(
        "基于用户行为数据，分析产品功能效果，提出并实施迭代优化方案，提升用户满意度。",
        atom,
    ) == "基于用户反馈，分析产品功能效果，提出迭代优化方案，提升用户满意度"
    assert guard._sanitize_rewrite_bullet(
        "基于用户反馈，提出知识库问答系统迭代建议，优化搜索算法。",
        atom,
    ) == "基于用户反馈，提出知识库问答系统迭代建议"


def test_old_atom_variant_is_sanitized_before_customize_reference() -> None:
    atom = {
        "title": "字节跳动 数据产品运营实习生",
        "description": "参与内部数据看板日常运营，负责整理业务方提出的指标口径、筛选条件和展示维度需求。使用 SQL 查询基础数据，协助验证看板中 PV、UV、转化率、留存率等指标是否与业务口径一致。",
        "meta": {
            "base_description": "参与内部数据看板日常运营，负责整理业务方提出的指标口径、筛选条件和展示维度需求。使用 SQL 查询基础数据，协助验证看板中 PV、UV、转化率、留存率等指标是否与业务口径一致。"
        },
    }
    clean = AtomGenerator(llm_client=None)._sanitize_rewrite_bullet(
        "负责整理业务方提出的AI产品指标口径需求，使用SQL验证数据一致性，确保数据准确性。",
        atom,
    )
    assert "AI产品" not in clean
    assert clean == "负责整理业务方提出的产品指标口径需求，使用SQL验证数据一致性，确保数据准确性"


def test_source_resume_id_is_primary_atom_scope() -> None:
    current_resume_id = "resume-a"
    resume_text = "产品负责人 校园活动管理与报名平台"

    def belongs(atom):
        meta = atom.get("meta") or {}
        source_resume_id = str(meta.get("source_resume_id") or "").strip()
        if current_resume_id and source_resume_id:
            return source_resume_id == current_resume_id
        title = str(atom.get("title") or "").strip()
        return len(title) >= 3 and title.replace(" ", "").lower() in resume_text.replace(" ", "").lower()

    assert belongs({"title": "产品负责人", "meta": {"source_resume_id": "resume-a"}}) is True
    assert belongs({"title": "产品负责人", "meta": {"source_resume_id": "resume-b"}}) is False
    assert belongs({"title": "校园活动管理与报名平台", "meta": {}}) is True


def test_atom_generator_falls_back_to_raw_text_sections() -> None:
    resume_data = {
        "raw_text": """
项目经历一：校园二手交易平台
项目时间：2023.09 - 2024.01
项目角色：后端开发
工作内容：
1. 使用 Spring Boot 和 MyBatis 完成商品发布、订单创建等接口。

实习经历一：北京云启科技有限公司 后端开发实习生
实习时间：2024.06 - 2024.09
工作内容：
1. 参与企业内部数据看板系统开发，负责用户权限和报表导出相关接口。
"""
    }

    atoms = AtomGenerator(llm_client=None)._build_atoms_from_raw_text(resume_data["raw_text"])
    titles = [atom["title"] for atom in atoms]
    companies = [atom.get("company") for atom in atoms]
    assert "校园二手交易平台" in titles
    assert "后端开发实习生" in titles
    assert "北京云启科技有限公司" in companies
    assert all("数据分析项目" not in str(atom) for atom in atoms)


if __name__ == "__main__":
    test_interest_parser_ignores_inline_mentions()
    test_interest_parser_does_not_capture_random_sentence()
    test_resume_bullet_sanitizer_keeps_result_packaging()
    test_atom_rewrite_guard_allows_result_packaging_but_rewrites_new_entities()
    test_atom_rewrite_guard_removes_jd_injected_facts()
    test_old_atom_variant_is_sanitized_before_customize_reference()
    test_source_resume_id_is_primary_atom_scope()
    test_atom_generator_falls_back_to_raw_text_sections()
    print("Content guard tests passed")
