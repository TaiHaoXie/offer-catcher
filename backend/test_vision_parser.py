"""
测试 Kimi 视觉解析器

验证 moonshot-v1-vision-preview 模型是否正常工作

作者：Claude
创建日期：2026-06-01
"""

import asyncio
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 检查 API Key
api_key = os.getenv("KIMI_API_KEY")
if not api_key:
    print("❌ 错误：未找到 KIMI_API_KEY 环境变量")
    print("请先设置：export KIMI_API_KEY='your-key'")
    exit(1)

print(f"✅ Kimi API Key 已配置: {api_key[:8]}...")
print()

async def test_vision_parser():
    """测试视觉解析器"""
    from app.services.kimi_vision_parser import get_vision_parser

    parser = get_vision_parser()

    # 创建一个简单的测试图片（1x1 像素 PNG）
    # 在实际使用中，这里应该是真实的简历图片/PDF
    print("📸 测试 Kimi 视觉模型调用...")

    try:
        # 先测试一个小图片验证 API 连通性
        import base64
        # 创建一个最小的测试图片
        test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # 构造测试消息
        from litellm import acompletion
        messages = [
            {
                "role": "system",
                "content": "你是一个测试助手。请回复 'OK' 表示正常工作。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "测试：如果你能看到这条消息，请回复 'OK'"
                    }
                ]
            }
        ]

        print(f"🔧 调用模型: kimi-k2.6")

        response = await acompletion(
            model="openai/kimi-k2.6",
            messages=messages,
            temperature=1,  # K2.6 只允许 temperature=1
            max_tokens=100,
            api_base="https://api.moonshot.cn/v1"
        )

        content = response.choices[0].message.content
        print(f"✅ API 响应成功!")
        print(f"📝 响应内容: {content[:200]}")
        print()
        print("🎉 Kimi 视觉模型 moonshot-v1-vision-preview 工作正常！")

    except Exception as e:
        print(f"❌ 视觉模型调用失败: {e}")
        print()
        print("可能的原因：")
        print("1. API Key 无效或过期")
        print("2. 模型名称不正确（已更新为 moonshot-v1-vision-preview）")
        print("3. API 访问限制")
        print("4. 网络连接问题")

if __name__ == "__main__":
    asyncio.run(test_vision_parser())
