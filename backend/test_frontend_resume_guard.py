"""前端定制简历展示回归测试。

不启动浏览器、不调用外部 API，只检查最终交付页不要把分析报告话术混进简历区。
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "frontend" / "index.html"


def test_customized_resume_workspace_has_no_strategy_report_copy() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    forbidden = [
        "JD 对齐情况",
        "优化提醒",
        "定制策略",
        "排序策略",
        "建议经历排布",
        "本轮定制策略",
    ]
    for phrase in forbidden:
        assert phrase not in html, f"前端仍残留分析报告话术：{phrase}"


def test_customized_resume_view_uses_plain_lines_not_list_bullets() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    forbidden = [
        "resume-paper-bullets",
        "block.bullets.map(b => `<li>",
        "ul { margin: 3px 0 0 17px; }",
        "prefix = \"- \"",
    ]
    for phrase in forbidden:
        assert phrase not in html, f"简历展示仍使用列表/短杠 bullet：{phrase}"


def test_customized_resume_view_has_experience_font_hierarchy() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert ".resume-paper-h2" in html and "font-size: 14px" in html, "一级标题字号应更大"
    assert ".resume-paper-exp-title { font-size: 12px" in html, "经历标题应为中等字号"
    assert ".resume-paper-line" in html and "font-size: 10.5px" in html, "经历内容应小一号"


def test_auth_restores_atoms_for_customize_flow() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "renderAuthState();\n                loadAtoms();" in html, "登录成功后应重新加载原子库"
    assert "renderAuthState();\n                    loadAtoms();" in html, "恢复登录态后应重新加载原子库"


def test_print_fallback_keeps_resume_headline() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "${resume.headline ? `<div class=\"headline\">${esc(resume.headline)}</div>` : ''}" in html


if __name__ == "__main__":
    test_customized_resume_workspace_has_no_strategy_report_copy()
    test_customized_resume_view_uses_plain_lines_not_list_bullets()
    test_customized_resume_view_has_experience_font_hierarchy()
    test_auth_restores_atoms_for_customize_flow()
    test_print_fallback_keeps_resume_headline()
    print("Frontend resume guard tests passed")
