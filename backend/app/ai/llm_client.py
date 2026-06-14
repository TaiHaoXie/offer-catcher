"""
Offer 捕手 - LLM客户端（LiteLLM多模型支持）
"""
import os
import json
from typing import Dict, List, Optional, Any
from litellm import completion
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class LLMClient:
    """LLM客户端（支持多模型）"""

    def __init__(self):
        """初始化客户端"""
        # 默认模型（豆包）
        self.default_model = os.getenv("LLM_MODEL", "doubao")
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.api_base = os.getenv("LLM_API_BASE", "")

    def _get_model_config(self, model: Optional[str] = None) -> Dict:
        """获取模型配置"""
        model = model or self.default_model

        configs = {
            # 豆包API
            "doubao": {
                "model": "openai/doubao-pro-32k",
                "api_base": os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3"),
                "api_key": os.getenv("DOUBAO_API_KEY", "")
            },
            # 通义千问
            "qwen": {
                "model": "openai/qwen-plus",
                "api_base": os.getenv("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                "api_key": os.getenv("QWEN_API_KEY", "")
            },
            # Kimi (月之暗面)
            "kimi": {
                "model": "openai/moonshot-v1-8k",
                "api_base": os.getenv("KIMI_API_BASE", "https://api.moonshot.cn/v1"),
                "api_key": os.getenv("KIMI_API_KEY", "")
            },
            # OpenAI
            "openai": {
                "model": "gpt-4o-mini",
                "api_base": "https://api.openai.com/v1",
                "api_key": os.getenv("OPENAI_API_KEY", "")
            },
            # Ollama本地
            "ollama": {
                "model": "ollama/llama3",
                "api_base": os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1"),
                "api_key": "ollama"  # Ollama不需要真实key
            }
        }

        return configs.get(model, configs["doubao"])

    def call(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        response_format: Optional[Dict] = None,
        temperature: float = 0.3
    ) -> str:
        """调用LLM"""

        config = self._get_model_config(model)

        try:
            response = completion(
                model=config["model"],
                messages=messages,
                api_base=config["api_base"],
                api_key=config["api_key"],
                response_format=response_format,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM调用失败: {e}")
            # 尝试使用备用模型
            if model != "doubao":
                return self.call(messages, model="doubao", response_format=response_format)
            raise

    def call_json(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None
    ) -> Dict:
        """调用LLM并返回JSON结果"""
        response_text = self.call(
            messages=messages,
            model=model,
            response_format={"type": "json_object"}
        )
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            print(f"JSON解析失败: {response_text}")
            return {}

    def resume_parse(self, resume_text: str) -> Dict:
        """解析简历"""
        from .prompts import RESUME_PARSE_PROMPT

        messages = [
            {"role": "user", "content": RESUME_PARSE_PROMPT.format(resume_text=resume_text)}
        ]
        return self.call_json(messages)

    def jd_parse(self, jd_text: str) -> Dict:
        """解析岗位JD"""
        from .prompts import JD_PARSE_PROMPT

        messages = [
            {"role": "user", "content": JD_PARSE_PROMPT.format(jd_text=jd_text)}
        ]
        return self.call_json(messages)

    def generate_optimization(
        self,
        gaps_analysis: str,
        resume_snippet: str,
        jd_snippet: str
    ) -> Dict:
        """生成优化建议"""
        from .prompts import OPTIMIZATION_PROMPT

        messages = [
            {"role": "user", "content": OPTIMIZATION_PROMPT.format(
                gaps_analysis=gaps_analysis,
                resume_snippet=resume_snippet,
                jd_snippet=jd_snippet
            )}
        ]
        return self.call_json(messages)


# 全局客户端实例
_client_instance: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取LLM客户端实例（单例模式）"""
    global _client_instance
    if _client_instance is None:
        _client_instance = LLMClient()
    return _client_instance
