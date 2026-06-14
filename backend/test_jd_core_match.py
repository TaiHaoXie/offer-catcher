"""
测试 JD 核心匹配引擎

验证新的匹配分析逻辑是否正常工作

作者：Claude
创建日期：2026-06-01
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# 设置 Kimi API 环境变量（重要！）
os.environ["OPENAI_API_KEY"] = os.getenv("KIMI_API_KEY", "")
os.environ["OPENAI_API_BASE"] = "https://api.moonshot.cn/v1"

# 检查 API Key
api_key = os.getenv("KIMI_API_KEY")
if not api_key:
    print("❌ 错误：未找到 KIMI_API_KEY 环境变量")
    exit(1)

print(f"✅ Kimi API Key 已配置")
print()


async def test_jd_core_match():
    """测试 JD 核心匹配引擎"""
    from app.services.jd_core_match_engine import get_jd_core_matcher

    engine = get_jd_core_matcher()

    # 测试简历
    test_resume = {
        "basic_info": {
            "name": "徐琳迪",
            "email": "xulindi@example.com",
            "phone": "13800138000",
            "university": "河南牧业经济学院",
            "major": "国际中文教育",
            "degree": "硕士",
            "graduation_year": "2027"
        },
        "education": {
            "school": "河南牧业经济学院",
            "major": "国际中文教育",
            "degree": "硕士",
            "end_date": "2027-06"
        },
        "experience": [
            {
                "company": "北京瞬歌智能科技",
                "position": "产品实习生",
                "start_date": "2024-06",
                "end_date": "2024-09",
                "description": "参与产品需求分析，协助完成竞品分析报告，支持产品迭代优化"
            },
            {
                "company": "字节跳动",
                "position": "AI产品实习生",
                "start_date": "2025-06",
                "end_date": "2025-09",
                "description": "负责AI产品需求文档撰写，参与用户调研，协助产品经理完成功能设计"
            }
        ],
        "projects": [
            {
                "name": "Offer 捕手",
                "role": "产品负责人",
                "start_date": "2025-03",
                "end_date": "2025-06",
                "description": "开发求职匹配分析工具，帮助学生分析简历与岗位的匹配度，提供简历优化建议",
                "tech_stack": ["Python", "FastAPI", "Vue"]
            }
        ],
        "skills": [
            "产品设计", "需求分析", "竞品分析", "用户调研", "Python", "SQL", "数据分析", "A/B测试"
        ],
        "awards": ["校级优秀学生干部"]
    }

    # 测试 JD
    test_job = {
        "company": "字节跳动",
        "position_name": "AI产品经理实习生",
        "job_type": "实习",
        "location": "北京",
        "description": "负责AI产品的需求分析和功能设计，参与用户调研和数据分析",
        "requirements": {
            "education": {
                "degree": "本科及以上",
                "major": "专业不限，计算机/心理学优先",
                "school": "985/211院校优先"
            },
            "skills": [
                "熟练掌握产品设计方法",
                "具备数据分析能力（SQL/Excel）",
                "了解AI/大模型基础知识"
            ],
            "experience": "有互联网产品实习经验优先",
            "nice_to_have": [
                "985/211院校",
                "有大厂实习经历",
                "有AI产品相关经验"
            ]
        }
    }

    print("📊 测试 JD 核心匹配引擎...")
    print(f"👤 候选人: {test_resume['basic_info']['name']}")
    print(f"💼 岗位: {test_job['company']} - {test_job['position_name']}")
    print()

    try:
        result = await engine.calculate(test_resume, test_job)

        print("✅ 匹配分析完成!")
        print()
        print("=" * 60)
        print(f"🎯 匹配度: {result.get('match_score', 0)}/100")
        print(f"📊 等级: {result.get('match_level', '未知')}")
        print()
        print(f"📝 总结: {result.get('executive_summary', '')}")
        print("=" * 60)
        print()

        # 详细匹配结果
        jd_analysis = result.get('jd_analysis', {})
        must_req = jd_analysis.get('must_requirements', [])
        nice_to_have = jd_analysis.get('nice_to_have', [])

        if must_req:
            print("📋 必须要求匹配:")
            for req in must_req[:5]:
                print(f"  {req.get('match', '?')} {req.get('req', '')} - {req.get('evidence', '')[:50]}")
            print()

        if nice_to_have:
            print("⭐ 加分项匹配:")
            for req in nice_to_have[:3]:
                print(f"  {req.get('match', '?')} {req.get('req', '')} - {req.get('evidence', '')[:50]}")
            print()

        # 优势与差距
        strengths = result.get('strengths_vs_jd', [])
        gaps = result.get('gaps_vs_jd', [])

        if strengths:
            print("✅ 优势:")
            for s in strengths:
                print(f"  • {s}")
            print()

        if gaps:
            print("⚠️ 差距:")
            for g in gaps:
                print(f"  • {g}")
            print()

        # 建议
        recommendation = result.get('recommendation', {})
        if recommendation:
            print("💡 建议:")
            print(f"  是否面试: {'是' if recommendation.get('should_interview') else '否'}")
            print(f"  理由: {recommendation.get('reason', '')}")
            focus = recommendation.get('interview_focus', [])
            if focus:
                print(f"  面试重点:")
                for f in focus:
                    print(f"    - {f}")

        print()
        print("🎉 JD 核心匹配引擎测试完成!")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_jd_core_match())
