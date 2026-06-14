"""
Kimi 视觉模型解析器

流程：上传文件 → 转成图片 → Kimi 视觉模型分析 → 返回结果

优势：
- AI 直接看原始格式，不会丢失排版信息
- 支持多页 PDF
- 更准确地识别复杂布局

作者：Claude
创建日期：2026-06-01
"""

import json
import logging
import os
import base64
import io
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from litellm import acompletion
from PIL import Image
import fitz  # PyMuPDF

load_dotenv()

logger = logging.getLogger(__name__)


class KimiVisionParser:
    """Kimi 视觉模型简历解析器"""

    def __init__(self):
        """初始化 Kimi 视觉解析器"""
        # 设置 Kimi API
        os.environ["OPENAI_API_KEY"] = os.getenv("KIMI_API_KEY", "")
        os.environ["OPENAI_API_BASE"] = "https://api.moonshot.cn/v1"

    async def parse_pdf_async(self, pdf_bytes: bytes, filename: str = "") -> Dict[str, Any]:
        """
        解析 PDF 文件（转换为图片后调用视觉模型）

        Args:
            pdf_bytes: PDF 文件二进制内容
            filename: 文件名

        Returns:
            解析结果字典
        """
        try:
            logger.info(f"使用 Kimi 视觉模型解析 PDF: {filename}")

            # 将 PDF 转为图片列表
            images = self._pdf_to_images(pdf_bytes, max_pages=5)
            logger.info(f"PDF 转换完成，共 {len(images)} 页")

            # 调用 Kimi 视觉模型
            result = await self._call_vision_model(images, filename)
            logger.info(f"Kimi 视觉解析完成")

            return result

        except Exception as e:
            logger.error(f"Kimi 视觉解析失败: {e}")
            # 降级到文本解析
            logger.info("降级到文本解析...")
            return await self._fallback_to_text(pdf_bytes)

    async def parse_image_async(self, image_bytes: bytes, filename: str = "") -> Dict[str, Any]:
        """
        解析图片文件（JPG、PNG 等）

        Args:
            image_bytes: 图片文件二进制内容
            filename: 文件名

        Returns:
            解析结果字典
        """
        try:
            logger.info(f"使用 Kimi 视觉模型解析图片: {filename}")

            # 将图片转为 base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            images = [image_base64]

            result = await self._call_vision_model(images, filename)
            return result

        except Exception as e:
            logger.error(f"图片解析失败: {e}")
            raise

    def _pdf_to_images(self, pdf_bytes: bytes, max_pages: int = 5) -> List[str]:
        """
        将 PDF 转为 base64 图片列表

        Args:
            pdf_bytes: PDF 二进制内容
            max_pages: 最大转换页数

        Returns:
            base64 编码的图片列表
        """
        images = []

        try:
            doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")

            for page_num in range(min(len(doc), max_pages)):
                page = doc[page_num]

                # 渲染为图片（高分辨率）
                mat = fitz.Matrix(2, 2)  # 2x 缩放，提高清晰度
                pix = page.get_pixmap(matrix=mat, alpha=False)

                # 转为 PNG 格式
                img_data = pix.tobytes("png")

                # 转为 base64
                img_base64 = base64.b64encode(img_data).decode('utf-8')
                images.append(img_base64)

            doc.close()

            return images

        except Exception as e:
            logger.error(f"PDF 转图片失败: {e}")
            raise

    async def _call_vision_model(self, images: List[str], filename: str) -> Dict[str, Any]:
        """
        调用 Kimi 视觉模型

        Args:
            images: base64 编码的图片列表
            filename: 文件名（用于日志）

        Returns:
            解析结果字典
        """
        # 构造消息
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt()
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请解析这份简历，提取所有信息。这是简历的图片："
                    }
                ]
            }
        ]

        # 添加图片
        for i, img_base64 in enumerate(images):
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_base64}"
                }
            })

        try:
            response = await acompletion(
                model="openai/kimi-k2.6",  # Kimi 最新多模态模型，支持视觉理解
                messages=messages,
                temperature=1,  # K2.6 只允许 temperature=1
                max_tokens=4000,
                api_base="https://api.moonshot.cn/v1"
            )

            content = response.choices[0].message.content

            # 解析 JSON（容错处理）
            result = self._parse_json_response(content)

            return result

        except Exception as e:
            logger.error(f"Kimi 视觉模型调用失败: {e}")
            raise

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的简历解析助手。请将简历图片内容解析为 JSON 格式，要求：

【重要】必须只返回 JSON，不要有任何其他文字说明。

JSON 格式如下：
{
  "basic_info": {
    "name": "姓名",
    "phone": "手机号",
    "email": "邮箱",
    "location": "城市",
    "birth_date": "生日（如果有）"
  },
  "education": [
    {
      "school": "学校名称",
      "major": "专业",
      "degree": "学位（本科/硕士/博士等）",
      "start_date": "开始时间",
      "end_date": "结束时间",
      "gpa": "GPA（如果有）",
      "courses": ["课程列表"],
      "achievements": ["荣誉奖项"]
    }
  ],
  "experience": [
    {
      "company": "公司名称",
      "position": "职位",
      "start_date": "开始时间",
      "end_date": "结束时间",
      "description": "工作内容描述（保留完整原文）"
    }
  ],
  "projects": [
    {
      "name": "项目名称",
      "role": "角色",
      "start_date": "开始时间",
      "end_date": "结束时间",
      "description": "项目描述（保留完整原文）",
      "tech_stack": ["技术栈"],
      "achievements": ["成果/指标"]
    }
  ],
  "skills": {
    "technical": ["编程与技术技能"],
    "ai": ["AI 技术栈"],
    "product": ["产品工具"],
    "languages": ["语言能力"],
    "other": ["其他技能"]
  },
  "awards": ["奖项荣誉"],
  "publications": ["论文专利"],
  "summary": ["个人总结/优势"]
}

注意：
- 如果某个字段没有信息，用空字符串或空数组，不要省略
- 日期格式统一为 MM/YYYY 或 YYYY-MM
- 描述性内容保留原文，不要缩写
- 技能按类别分组
"""

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """解析 JSON 响应，带容错处理"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 JSON 部分
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            else:
                raise ValueError(f"无法从返回内容中提取 JSON: {content[:500]}")

    async def extract_text_via_vision(self, file_bytes: bytes, filename: str = "") -> str:
        """
        视觉 OCR 兜底：把 PDF/图片渲染/读成图片后，让视觉模型逐字读出原始文本。

        用于常规文本层解析失败的场景（扫描版 PDF、图片型简历、字体编码异常导致乱码）。
        只返回纯文本，不做结构化，尽量保留原文顺序与换行。

        Args:
            file_bytes: 文件二进制
            filename: 文件名（用于判断类型）

        Returns:
            str: OCR 提取的纯文本（失败时返回空字符串）
        """
        try:
            lower = (filename or "").lower()
            if lower.endswith(".pdf"):
                images = self._pdf_to_images(file_bytes, max_pages=3)
            else:
                # 图片文件：直接 base64
                images = [base64.b64encode(file_bytes).decode("utf-8")]

            if not images:
                return ""

            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是一个 OCR 文字识别助手。请逐字识别图片中的所有文字，"
                        "按从上到下、从左到右的阅读顺序输出纯文本，保留自然换行。"
                        "只输出识别到的文字本身，不要添加任何解释、标题或 Markdown 标记。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请识别下面图片中的全部文字："}
                    ],
                },
            ]
            for img_base64 in images:
                messages[1]["content"].append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                })

            response = await acompletion(
                model="openai/kimi-k2.6",
                messages=messages,
                temperature=1,
                max_tokens=4000,
                api_base="https://api.moonshot.cn/v1",
            )
            text = response.choices[0].message.content or ""
            return text.strip()
        except Exception as e:
            logger.error(f"视觉 OCR 取文本失败: {e}")
            return ""

    async def _fallback_to_text(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """降级方案：使用文本解析"""
        from app.services.llm_resume_parser import get_llm_parser
        from app.utils.pdf_parser import get_pdf_parser

        # 提取文本
        pdf_parser = get_pdf_parser()
        text = pdf_parser.extract_text(pdf_bytes, "fallback")

        # 用 LLM 解析文本
        llm_parser = get_llm_parser()
        return await llm_parser.parse_async(text)


# 全局实例
_vision_parser_instance: Optional[KimiVisionParser] = None


def get_vision_parser() -> KimiVisionParser:
    """获取视觉解析器实例"""
    global _vision_parser_instance
    if _vision_parser_instance is None:
        _vision_parser_instance = KimiVisionParser()
    return _vision_parser_instance
