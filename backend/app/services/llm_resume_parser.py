"""
LLM 驱动的简历解析器

优势：
- 完整提取信息，不遗漏
- 智能识别各种简历格式
- 处理非标准格式

支持模型：OpenAI (gpt-4o)、Kimi (moonshot-v1-8k)、通义千问 (qwen) 等

作者：Claude
创建日期：2026-06-01
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from litellm import acompletion

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)


class LLMResumeParser:
    """LLM 驱动的简历解析器"""

    # 支持的模型配置
    MODELS = {
        "gpt-4o": {"model": "gpt-4o"},
        "gpt-4": {"model": "gpt-4-turbo"},
        "kimi": {"model": "openai/moonshot-v1-8k"},  # litellm 格式
        "qwen": {"model": "openai/qwen-plus"},
    }

    def __init__(self, model: str = "kimi"):
        """
        Args:
            model: 使用的模型，支持 kimi、gpt-4o、qwen 等
        """
        self.model_name = model
        self.config = self.MODELS.get(model, self.MODELS["kimi"])

        # 设置 API key 和 base
        if model == "kimi":
            os.environ["OPENAI_API_KEY"] = os.getenv("KIMI_API_KEY", "")
            os.environ["OPENAI_API_BASE"] = "https://api.moonshot.cn/v1"
        elif model == "qwen":
            os.environ["OPENAI_API_KEY"] = os.getenv("QWEN_API_KEY", "")
            os.environ["OPENAI_API_BASE"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        else:
            os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")

    async def parse_async(self, text: str) -> Dict[str, Any]:
        """异步解析简历文本"""
        try:
            logger.info(f"使用 LLM 解析简历 (模型: {self.model_name})...")

            # 构造参数
            params = {
                "model": self.config["model"],
                "messages": [
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": f"请解析以下简历内容，提取所有信息：\n\n{text}"
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 4000
            }

            # 添加 API base（如果需要）
            if "api_base" in self.config:
                params["api_base"] = self.config["api_base"]

            # Kimi 不支持 response_format，去掉
            # 通过 prompt 要求返回 JSON
            response = await acompletion(**params)

            content = response.choices[0].message.content
            logger.info(f"LLM 返回内容长度: {len(content)} 字符")

            # 尝试解析 JSON，如果失败则提取 JSON 部分
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # 尝试提取 JSON 部分（Kimi 可能在 JSON 前后加了文字）
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise ValueError(f"无法从返回内容中提取 JSON: {content[:200]}")

            logger.info(f"LLM 解析成功，提取到姓名: {result.get('basic_info', {}).get('name', '未知')}")

            return self._normalize_result(result)

        except Exception as e:
            logger.error(f"LLM 解析失败: {e}")
            raise

    def parse(self, text: str) -> Dict[str, Any]:
        """同步解析简历文本（兼容接口）"""
        import asyncio
        try:
            # 获取或创建事件循环
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                asyncio.set_event_loop(asyncio.new_event_loop())
                loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.parse_async(text))
        except RuntimeError:
            # 没有事件循环，创建新的
            return asyncio.run(self.parse_async(text))

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的简历解析助手。请将简历内容解析为 JSON 格式，要求：

【重要】必须只返回 JSON，不要有任何其他文字说明。

JSON 格式如下：

1. 完整提取：不要遗漏任何信息，包括姓名、联系方式、教育背景、工作经历、项目经历、技能等
2. 准确分类：将信息正确归类到对应字段
3. 保留原文：对于描述性内容，保留原始表述

返回 JSON 格式：
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

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """标准化结果格式，兼容现有数据结构"""
        normalized = {
            "id": result.get("id"),
            "basic_info": result.get("basic_info", {}),
        }

        # 教育背景
        education = result.get("education", [])
        if education and isinstance(education, list) and len(education) > 0:
            # 按学位高低挑「最高学历」填进 basic_info（供匹配/抬头用），
            # 不能简单取最后一条 —— 数组顺序不固定，最后一条常是较早的本科。
            degree_rank = {"博士": 4, "phd": 4, "硕士": 3, "研究生": 3, "master": 3,
                           "本科": 2, "学士": 2, "bachelor": 2, "大专": 1, "专科": 1}
            def _rank(e):
                d = str(e.get("degree", "")).lower()
                for k, v in degree_rank.items():
                    if k in d:
                        return v
                return 0
            top_edu = max(education, key=_rank)
            normalized["basic_info"].update({
                "university": top_edu.get("school", ""),
                "major": top_edu.get("major", ""),
                "degree": top_edu.get("degree", ""),
                "graduation_year": top_edu.get("end_date", "")[-4:] if top_edu.get("end_date") else ""
            })
            # 关键：保留「完整教育数组」，不要压成一条，否则导出会丢掉其他学历（如硕士）。
            normalized["education"] = top_edu          # 兼容旧逻辑：单条=最高学历
            normalized["education_list"] = education   # 新增：完整多段教育，供导出展示
        else:
            normalized["education"] = {"school": "", "major": "", "degree": "", "gpa": "", "courses": []}
            normalized["education_list"] = []

        # 工作经历
        normalized["experience"] = result.get("experience", [])

        # 项目经历
        normalized["projects"] = result.get("projects", [])

        # 技能（展开为一维数组，兼容现有结构）
        skills = result.get("skills", {})
        all_skills = []
        if isinstance(skills, dict):
            for category, skill_list in skills.items():
                if isinstance(skill_list, list):
                    all_skills.extend(skill_list)
        elif isinstance(skills, list):
            all_skills = skills
        normalized["skills"] = all_skills

        # 其他信息
        normalized["awards"] = result.get("awards", [])
        normalized["publications"] = result.get("publications", [])

        return normalized


# 全局实例
_llm_parser_instance: Optional[LLMResumeParser] = None


def get_llm_parser() -> LLMResumeParser:
    """获取 LLM 解析器实例"""
    global _llm_parser_instance
    if _llm_parser_instance is None:
        # 从环境变量读取模型
        import os
        model = os.getenv("LLM_MODEL", "gpt-4o")
        _llm_parser_instance = LLMResumeParser(model=model)
    return _llm_parser_instance
