"""
以 JD 为核心的匹配度分析引擎

设计理念：
- 不是评估候选人"优不优秀"
- 而是分析候选人"是否匹配岗位 JD"
- 逐项对照 JD 要求，给出明确判断

作者：Claude
创建日期：2026-06-01
"""

import json
import logging
import re
from typing import Dict, List, Optional, Any
from litellm import acompletion
import os

logger = logging.getLogger(__name__)


class JDCoreMatchEngine:
    """
    以 JD 为核心的匹配度分析引擎

    匹配逻辑：
    1. 解析 JD，提取所有要求（必须 + 加分）
    2. 逐项对照简历，标注匹配状态
    3. 计算匹配度 = (完全匹配 + 部分匹配×0.5) / 总要求数
    4. 输出结构化 JSON 报告
    """

    # 匹配状态标记
    MATCH_FULL = "✓"      # 完全匹配
    MATCH_PARTIAL = "~"   # 部分匹配
    MATCH_NONE = "✗"      # 不匹配
    MATCH_UNKNOWN = "?"   # 无法判断

    # 匹配度等级
    GRADE_MAP = {
        (80, 100): ("A", "A级 - 核心要求全部满足", "强烈推荐面试"),
        (60, 79): ("B", "B级 - 核心要求基本满足", "可以考虑面试"),
        (40, 59): ("C", "C级 - 多项核心要求不满足", "暂不推荐"),
        (0, 39): ("D", "D级 - 核心要求多数不满足", "不推荐"),
    }

    def __init__(self, model: str = "kimi"):
        """
        初始化引擎

        Args:
            model: 使用的 LLM 模型
        """
        self.model = model
        # 设置 Kimi API
        if model == "kimi":
            os.environ["OPENAI_API_KEY"] = os.getenv("KIMI_API_KEY", "")
            os.environ["OPENAI_API_BASE"] = "https://api.moonshot.cn/v1"

    async def calculate(self, resume_data: Dict, job_data: Dict) -> Dict[str, Any]:
        """
        执行匹配分析

        Args:
            resume_data: 简历数据
            job_data: JD 数据

        Returns:
            匹配分析结果
        """
        try:
            logger.info("开始 JD 核心匹配分析...")

            # 构造提示词
            prompt = self._build_analysis_prompt(resume_data, job_data)

            # 调用 LLM
            response = await acompletion(
                model="openai/kimi-k2.6",
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=1,  # K2.6 要求
                max_tokens=8192,  # 增加输出长度限制
                api_base="https://api.moonshot.cn/v1"
            )

            content = response.choices[0].message.content
            logger.info(f"LLM 返回内容长度: {len(content) if content else 0} 字符")

            if not content or not content.strip():
                logger.error("LLM 返回空内容")
                return self._get_fallback_result(resume_data, job_data)

            # 调试：打印原始内容
            logger.debug(f"LLM 原始返回:\n{content[:1000]}")

            # 解析 JSON
            result = self._parse_json_response(content)

            logger.info(f"JD 核心匹配分析完成，匹配度: {result.get('match_score', 0)}")

            return result

        except Exception as e:
            logger.error(f"JD 核心匹配分析失败: {e}")
            # 返回降级结果
            return self._get_fallback_result(resume_data, job_data)

    def _build_analysis_prompt(self, resume_data: Dict, job_data: Dict) -> str:
        """构造分析提示词"""
        # 格式化简历
        resume_text = self._format_resume(resume_data)
        # 格式化 JD
        jd_text = self._format_job(job_data)

        return f"""请分析以下简历与 JD 的匹配程度：

=== 岗位 JD ===
{jd_text}

=== 候选人简历 ===
{resume_text}

请按照要求输出 JSON 格式的匹配分析报告。"""

    def _format_resume(self, resume: Dict) -> str:
        """格式化简历为文本"""
        parts = []

        # 基本信息
        basic = resume.get("basic_info", {})
        if basic:
            parts.append(f"""【基本信息】
姓名: {basic.get('name', '')}
邮箱: {basic.get('email', '')}
电话: {basic.get('phone', '')}
院校: {basic.get('university', '') or basic.get('school', '')}
专业: {basic.get('major', '')}
学历: {basic.get('degree', '')}
毕业年份: {basic.get('graduation_year', '')}""")

        # 教育背景
        education = resume.get("education", {})
        if education and isinstance(education, dict):
            parts.append(f"""
【教育背景】
学校: {education.get('school', '')}
专业: {education.get('major', '')}
学历: {education.get('degree', '')}
毕业时间: {education.get('end_date', '')}
""")

        # 工作经历
        experience = resume.get("experience", [])
        if experience:
            parts.append("\n【工作/实习经历】")
            for exp in experience:
                parts.append(f"""
- {exp.get('company', '')} | {exp.get('position', '')}
  时间: {exp.get('start_date', '')} ~ {exp.get('end_date', '至今')}
  描述: {exp.get('description', '')}""")

        # 项目经历
        projects = resume.get("projects", [])
        if projects:
            parts.append("\n【项目经历】")
            for proj in projects:
                parts.append(f"""
- {proj.get('name', '')} | {proj.get('role', '')}
  时间: {proj.get('start_date', '')} ~ {proj.get('end_date', '')}
  描述: {proj.get('description', '')}
  技术栈: {', '.join(proj.get('tech_stack', []))}""")

        # 技能
        skills = resume.get("skills", [])
        if skills:
            parts.append(f"\n【技能】\n{', '.join(str(s) for s in skills)}")

        # 奖项
        awards = resume.get("awards", [])
        if awards:
            parts.append(f"\n【奖项荣誉】\n" + "\n".join(f"- {a}" for a in awards))

        return "\n".join(parts)

    def _format_job(self, job: Dict) -> str:
        """格式化 JD 为文本"""
        parts = []

        parts.append(f"""【岗位信息】
公司: {job.get('company', '')}
岗位: {job.get('position_name', '')}
类型: {job.get('job_type', '')}
地点: {job.get('location', '')}""")

        # 岗位描述
        description = job.get('description', '')
        if description:
            parts.append(f"\n【岗位描述】\n{description}")

        # 要求
        requirements = job.get('requirements', {})
        if requirements:
            # 学历要求
            edu = requirements.get('education', {})
            if edu:
                parts.append(f"""
【学历要求】
学历: {edu.get('degree', '')}
专业: {edu.get('major', '')}
院校: {edu.get('school', '')}""")

            # 技能要求
            skills = requirements.get('skills', [])
            if skills:
                parts.append(f"\n【技能要求】\n" + "\n".join(f"- {s}" for s in skills))

            # 经验要求
            exp = requirements.get('experience', '')
            if exp:
                parts.append(f"\n【经验要求】\n{exp}")

            # 加分项
            nice_to_have = requirements.get('nice_to_have', [])
            if nice_to_have:
                parts.append(f"\n【加分项】\n" + "\n".join(f"- {s}" for s in nice_to_have))

        return "\n".join(parts)

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一位专业的校招简历分析师。你的任务不是评估候选人"优不优秀"，而是分析候选人"是否匹配岗位JD"。

请仔细阅读岗位JD，提取其中的所有要求，然后对照简历逐项检查匹配程度。

【分析流程】

第一步：解析JD要求
- 目标院校要求
- 学历/专业要求
- 核心技能要求（必须具备）
- 加分技能要求（优先考虑）
- 项目/实习要求
- 其他明确要求

第二步：逐项匹配检查
对于每一项JD要求，对照简历进行匹配检查，标记状态：
- ✓ 完全匹配：简历中明确体现且满足要求
- ~ 部分匹配：有一定基础但未完全达到
- ✗ 不匹配：完全不符合要求
- ? 无法判断：简历中没有相关信息

第三步：计算匹配度
匹配度 = (完全匹配项数 + 部分匹配项数×0.5) / 总要求项数 × 100

第四步：输出匹配报告

【输出格式】
严格按照以下JSON格式输出，不要有任何额外文字：

{
  "match_score": 75,
  "match_level": "B级 - 可考虑",
  "executive_summary": "候选人满足3项必须要求、2项加分要求，有2项必须要求未满足。核心技能基本匹配，但缺少目标院校背景和相关实习经验。建议进一步沟通，考察学习能力。",
  "jd_analysis": {
    "must_requirements": [
      {"req": "本科及以上学历", "match": "✓", "evidence": "华中科技大学计算机硕士"},
      {"req": "计算机相关专业", "match": "✓", "evidence": "计算机科学与技术专业"},
      {"req": "熟练掌握Java", "match": "~", "evidence": "课程项目中使用，但熟练度未知"}
    ],
    "nice_to_have": [
      {"req": "985/211院校", "match": "✓", "evidence": "华中科技大学985"},
      {"req": "ACM/ICPC竞赛获奖", "match": "✗", "evidence": "无相关经历"}
    ]
  },
  "match_summary": {
    "total_requirements": 9,
    "fully_matched": 4,
    "partially_matched": 3,
    "not_matched": 1,
    "unknown": 1,
    "match_rate": "完全匹配44%，部分匹配33%，不匹配11%"
  },
  "strengths_vs_jd": [
    "满足院校要求（985）",
    "满足学历要求（硕士）",
    "满足专业要求（计算机）"
  ],
  "gaps_vs_jd": [
    "实习经历不够突出（非大厂，时间短）",
    "竞赛加分项缺失"
  ],
  "recommendation": {
    "should_interview": true,
    "reason": "核心要求基本满足，建议面试考察实际能力",
    "interview_focus": [
      "验证Java实际开发能力",
      "了解实习期间的具体工作",
      "考察学习能力和技术热情"
    ]
  }
}

【匹配度等级标准】
- 80-100分：A级 - 核心要求全部满足 - 强烈推荐面试
- 60-79分：B级 - 核心要求基本满足 - 可以考虑面试
- 40-59分：C级 - 多项核心要求不满足 - 暂不推荐
- 0-39分：D级 - 核心要求多数不满足 - 不推荐

【质量控制原则】
1. JD优先：所有分析以JD要求为基准，不是JD里写的不要作为扣分项
2. 逐项对照：每一项JD要求都要给出明确的匹配判断
3. 证据支撑：每个匹配判断都要说明简历中的证据
4. 客观标注：信息不足就标注"?"，不要猜测
5. 权重区分：区分"必须要求"和"加分要求"，不要混为一谈
6. 宽容对待：校招重在潜力，对部分缺失可以宽容

【重要】
- 必须只返回 JSON，不要有任何其他文字说明
- JD中没有提到的不作为扣分项
- 简历中没有明确说明的标注为 "?" 而不是假设其不存在"""

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """解析 JSON 响应，带容错处理"""
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}")
            # 尝试提取 JSON 部分（从第一个 { 到最后一个 }）
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                json_str = json_match.group()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e2:
                    logger.warning(f"提取的 JSON 仍然无效: {e2}")
                    logger.debug(f"问题 JSON: {json_str[:500]}")
                    # 尝试清理常见问题
                    cleaned = json_str.replace('\n', ' ').replace('\r', '')
                    # 移除注释（简单处理）
                    cleaned = re.sub(r'//.*?\n', '', cleaned)
                    try:
                        return json.loads(cleaned)
                    except:
                        pass

            # 最后尝试：手动构造最小可用结果
            logger.error("无法解析 JSON，使用降级结果")
            raise ValueError(f"无法从返回内容中提取有效的 JSON")

    def _get_fallback_result(self, resume: Dict, job: Dict) -> Dict[str, Any]:
        """降级结果"""
        return {
            "match_score": 50,
            "match_level": "B级 - 分析失败，使用默认值",
            "executive_summary": "匹配分析服务暂时不可用，请稍后重试。",
            "jd_analysis": {
                "must_requirements": [],
                "nice_to_have": []
            },
            "match_summary": {
                "total_requirements": 0,
                "fully_matched": 0,
                "partially_matched": 0,
                "not_matched": 0,
                "unknown": 0,
                "match_rate": "分析失败"
            },
            "strengths_vs_jd": [],
            "gaps_vs_jd": [],
            "recommendation": {
                "should_interview": False,
                "reason": "分析服务不可用",
                "interview_focus": []
            },
            "_error": "LLM 分析失败"
        }


# 全局实例
_jd_core_matcher_instance: Optional[JDCoreMatchEngine] = None


def get_jd_core_matcher() -> JDCoreMatchEngine:
    """获取 JD 核心匹配引擎实例"""
    global _jd_core_matcher_instance
    if _jd_core_matcher_instance is None:
        _jd_core_matcher_instance = JDCoreMatchEngine()
    return _jd_core_matcher_instance
