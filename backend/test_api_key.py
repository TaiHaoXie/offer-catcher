"""测试不同 Kimi 模型的可用性"""
import asyncio
import os
from dotenv import load_dotenv
from litellm import acompletion

load_dotenv()

api_key = os.getenv("KIMI_API_KEY")
print(f"API Key: {api_key[:12]}...")

async def test_model(model_name):
    """测试单个模型"""
    print(f"\n测试模型: {model_name}")
    try:
        response = await acompletion(
            model=model_name,
            messages=[{"role": "user", "content": "Hi"}],
            temperature=1,
            max_tokens=50,
            api_base="https://api.moonshot.cn/v1"
        )
        content = response.choices[0].message.content
        print(f"  ✅ 成功: {content[:50]}")
        return True
    except Exception as e:
        print(f"  ❌ 失败: {str(e)[:80]}")
        return False


async def main():
    models = [
        "openai/moonshot-v1-8k",
        "openai/kimi-k2.6",
    ]

    for m in models:
        await test_model(m)

asyncio.run(main())
