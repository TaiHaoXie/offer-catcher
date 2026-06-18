"""本地 PDF 导出回归测试。

不调用外部 LLM/API，只验证后端直出 PDF 是否有效、可抽取中文文本、长简历不截断。
"""
import os

os.environ.setdefault("LOG_DIR", "/tmp")
os.environ.setdefault("DB_PATH", "/tmp/offer-catcher-main-test.db")

import fitz

from app.main import _build_resume_pdf_bytes


def make_resume(name: str, repeat: int = 1) -> dict:
    base_bullets = [
        "使用 Java、Spring Boot 和 MyBatis 完成核心业务接口开发，支持简历解析、匹配分析和导出流程。",
        "负责用户调研、竞品分析和需求拆解，输出 PRD 与版本排期，推动研发按里程碑交付。",
        "使用 SQL 和 Excel 搭建岗位投放数据看板，跟踪转化率、留存率和关键漏斗指标。",
        "参与 AI 简历匹配产品的策略设计，梳理解析、匹配、优化建议和历史记录闭环。",
        "协调设计、前端、后端完成投递流程优化，减少用户重复填写和信息遗漏问题。",
    ]
    blocks = []
    for i in range(repeat):
        blocks.append({
            "title": f"Offer 捕手求职匹配系统 第{i + 1}阶段",
            "company": "校园项目",
            "type": "project" if i % 2 == 0 else "intern",
            "bullets": base_bullets,
        })
    return {
        "basic_info": {
            "name": name,
            "phone": "13800138000",
            "email": "candidate@example.com",
            "job_intention": "AI 产品经理实习生",
            "location": "北京",
        },
        "profile_summary": "具备产品设计、数据分析和 AI 应用落地经验，关注学生求职场景中的解析准确性、匹配解释和简历优化闭环。",
        "skills_line": ["Java", "Spring Boot", "MyBatis", "SQL", "Python", "FastAPI", "数据分析", "用户调研"],
        "selected_atoms": blocks,
        "education_list": [
            {"school": "华南理工大学", "major": "信息管理与信息系统", "degree": "本科", "date_range": "2019 - 2023"},
            {"school": "北京大学", "major": "软件工程", "degree": "硕士", "date_range": "2023 - 2026"},
        ],
        "interests": "长期关注 AI 工具、职业发展与效率产品，喜欢阅读商业案例和整理求职方法论。",
    }


def assert_pdf_contains(pdf_bytes: bytes, expected: list[str], min_pages: int, max_pages: int) -> None:
    assert pdf_bytes.startswith(b"%PDF-"), "导出内容不是 PDF"
    assert len(pdf_bytes) > 5000, "PDF 内容过小，可能为空文件"
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        text = "\n".join(page.get_text() for page in doc)
        normalized_text = "".join(text.split())
        assert min_pages <= doc.page_count <= max_pages, f"页数异常：{doc.page_count}"
        for item in expected:
            assert "".join(item.split()) in normalized_text, f"缺少文本：{item}"
        for bad in ["J a v a", "S p r i n g", "M y B a t i s", "燧"]:
            assert bad not in text, f"PDF 字体渲染异常：{bad}"
        for good in ["Java", "SQL"]:
            assert good in text, f"英文技术词被拆散：{good}"
    finally:
        doc.close()


def test_short_resume_pdf() -> None:
    pdf_bytes = _build_resume_pdf_bytes(make_resume("李明", repeat=1))
    assert_pdf_contains(
        pdf_bytes,
        ["李明", "个人介绍", "核心技能", "Offer 捕手", "华南理工大学", "兴趣爱好"],
        min_pages=1,
        max_pages=2,
    )


def test_pdf_filters_degree_only_education_and_plain_bullets() -> None:
    resume = make_resume("李明", repeat=1)
    resume["education_list"] = [
        {"school": "华南师范大学", "major": "信息管理与信息系统", "degree": "本科", "date_range": "2021 - 2025"},
        {"school": "", "major": "", "degree": "本科", "date_range": ""},
    ]
    pdf_bytes = _build_resume_pdf_bytes(resume)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        text = "\n".join(page.get_text() for page in doc)
        normalized_text = "".join(text.split())
        for item in ["华南师范大学", "信息管理与信息系统", "本科", "2021-2025"]:
            assert item in normalized_text
        assert "\n本科\n" not in text, "不应单独输出只有学位的空教育记录"
        for line in text.splitlines():
            assert not line.strip().startswith("- "), f"PDF bullet 不应带短杠：{line}"
    finally:
        doc.close()


def test_pdf_experience_typography_has_clear_hierarchy() -> None:
    pdf_bytes = _build_resume_pdf_bytes(make_resume("李明", repeat=1))
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        lines = []
        for page in doc:
            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    line_text = "".join(span.get("text", "") for span in spans)
                    line_size = max((round(float(span.get("size", 0)), 1) for span in spans), default=0)
                    lines.append((line_text, line_size))

        section_sizes = [
            size
            for text, size in lines
            if text.strip().startswith("项目") or text.strip().startswith("实习 / 工作经历")
        ]
        exp_title_sizes = [size for text, size in lines if "Offer 捕手求职匹配系统" in text]
        body_sizes = [size for text, size in lines if "使用 Java、Spring Boot" in text]

        assert section_sizes and exp_title_sizes and body_sizes
        assert max(section_sizes) >= 12.0, "一级标题应明显更大"
        assert max(exp_title_sizes) >= 10.8, "经历标题应保持中等字号"
        assert max(body_sizes) <= 10.6, "经历内容应与个人介绍同级，低于经历标题"
        assert max(section_sizes) > max(exp_title_sizes) > max(body_sizes)
        # 一级标题旁允许恢复英文副标题，但必须是正常英文，不允许出现字母散开的渲染问题。
        for page_text in ("\n".join(page.get_text() for page in doc),):
            for label in ["Profile", "Summary", "Skills", "Projects", "Education", "Interests"]:
                assert label in page_text, f"应保留一级标题英文副标题：{label}"
            for broken in ["P r o f i l e", "S k i l l s", "P r o j e c t s", "E d u c a t i o n"]:
                assert broken not in page_text, f"英文副标题不应被渲染成散字：{broken}"
    finally:
        doc.close()


def test_long_resume_pdf() -> None:
    pdf_bytes = _build_resume_pdf_bytes(make_resume("赵振华", repeat=16))
    assert_pdf_contains(
        pdf_bytes,
        ["赵振华", "项目", "实习", "工作经历", "北京大学", "兴趣爱好"],
        min_pages=2,
        max_pages=8,
    )


if __name__ == "__main__":
    test_short_resume_pdf()
    test_pdf_filters_degree_only_education_and_plain_bullets()
    test_pdf_experience_typography_has_clear_hierarchy()
    test_long_resume_pdf()
    print("PDF export tests passed")
