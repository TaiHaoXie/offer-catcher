"""简化版 JD 核心匹配测试"""
import asyncio
import os
from dotenv import load_dotenv
from litellm import acompletion

load_dotenv()

# 设置 Kimi API 环境变量（重要！）
os.environ["OPENAI_API_KEY"] = os.getenv("KIMI_API_KEY", "")
os.environ["OPENAI_API_BASE"] = "https://api.moonshot.cn/v1"

async def test_simple_match():
    """测试简化版匹配分析"""

    prompt = """分析候选人是否匹配岗位JD，只返回JSON格式：

JD: 本科及以上，熟练掌握产品设计，有实习经验优先
简历: 硕士学历，腾讯产品实习经历，擅长产品设计

返回JSON格式:
{
  "match_score": 85,
  "match_level": "A级",
  "summary": "候选人满足核心要求"
}"""

    print("📊 测试简化版匹配分析...")

    try:
        response = await acompletion(
            model="openai/kimi-k2.6",
            messages=[
                {"role": "system", "content": "只返回JSON，不要其他文字"},
                {"role": "user", "content": prompt}
            ],
            temperature=1,
            max_tokens=500,
            api_base="https://api.moonshot.cn/v1"
        )

        content = response.choices[0].message.content
        print(f"✅ 成功!")
        print(f"📝 返回: {content}")

    except Exception as e:
        print(f"❌ 失败: {e}")

asyncio.run(test_simple_match())
