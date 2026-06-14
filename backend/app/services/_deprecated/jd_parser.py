"""
Offer 捕手 - 岗位JD解析服务
"""
from typing import Dict


class JDParser:
    """岗位JD解析器"""

    def __init__(self, llm_client):
        """初始化解析器"""
        self.llm_client = llm_client

    def parse(self, jd_text: str) -> Dict:
        """解析岗位JD并返回结构化数据"""
        if not jd_text or len(jd_text) < 20:
            raise ValueError("JD内容过少，无法解析")

        return self.llm_client.jd_parse(jd_text)

    def parse_from_url(self, url: str) -> Dict:
        """从URL解析JD（预留接口）"""
        # TODO: 实现网页抓取功能
        # 目前先返回提示
        raise NotImplementedError("URL解析功能暂未开放，请直接粘贴JD文本")
