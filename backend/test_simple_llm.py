"""
简单 LLM 测试 - 验证 K2.6 长文本处理能力

作者：Claude
创建日期：2026-06-01
"""

import asyncio
import os
from dotenv import load_dotenv
from litellm import acompletion

load_dotenv()

api_key = os.getenv("KIMI_API_KEY")
if not api_key:
    print("❌ 错误：未找到 KIMI_API_KEY 环境变量")
    exit(1)

print(f"✅ Kimi API Key 已配置")
print()


async def test_long_prompt():
    """测试长提示词处理"""

    # 构造一个较长的提示词（模拟 JD 匹配分析的场景）
    long_prompt = """请分析以下候选人是否匹配岗位要求：

【岗位JD】
公司: 字节跳动
岗位: AI产品经理实习生
要求:
- 本科及以上学历
- 熟练掌握产品设计方法
- 具备数据分析能力
- 有互联网产品实习经验优先

【候选人简历】
姓名: 张三
学历: 硕士 - 清华大学计算机专业
经历:
- 腾讯产品实习生（2024.06-2024.09）
- 负责用户调研和需求分析
技能: 产品设计, Python, SQL

请按以下 JSON 格式输出:
{
  "match_score": 85,
  "match_level": "A级",
  "executive_summary": "候选人满足核心要求"
}"""

    print("📊 测试 K2.6 长文本处理...")
    print(f"提示词长度: {len(long_prompt)} 字符")
    print()

    try:
        response = await acompletion(
            model="openai/kimi-k2.6",
            messages=[
                {"role": "system", "content": "你是一个专业的简历分析师。只返回JSON格式。"},
                {"role": "user", "content": long_prompt}
            ],
            temperature=1,
            max_tokens=2000,
            api_base="https://api.moonshot.cn/v1"
        )

        content = response.choices[0].message.content
        print(f"✅ API 调用成功!")
        print(f"📝 返回内容长度: {len(content) if content else 0} 字符")
        print()
        print("📄 返回内容:")
        print("-" * 60)
        print(content[:500] if content else "(空)")
        print("-" * 60)

    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_long_prompt())
