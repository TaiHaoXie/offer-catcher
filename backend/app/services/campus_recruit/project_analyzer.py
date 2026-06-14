"""项目质量分析 - 真实大厂HR筛选逻辑.

项目质量评分维度：
- 技术深度：核心项目 > 课程作业
- 业务价值：真实业务 > Demo
- 规模：大规模 > 小规模
- 复杂度：高并发/分布式 > 简单CRUD
- 完整性：全栈/端到端 > 单模块
"""

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ProjectComplexity(Enum):
    """项目复杂度."""
    HIGH = "高并发/分布式/系统级"
    MEDIUM = "业务应用/全栈"
    LOW = "课程作业/Demo"


@dataclass
class ProjectQuality:
    """项目质量评分."""
    name: str
    complexity: ProjectComplexity
    tech_depth_score: int  # 技术深度 0-100
    business_value_score: int  # 业务价值 0-100
    scale_score: int  # 规模分数 0-100
    overall_score: int  # 综合分数
    highlights: List[str]  # 亮点


class ProjectAnalyzer:
    """项目质量分析器."""

    # 高复杂度关键词
    HIGH_COMPLEXITY_KEYWORDS = [
        "高并发", "分布式", "微服务", "微服务架构",
        "消息队列", "kafka", "rabbitmq", "rocketmq",
        "缓存", "redis", "memcached", "缓存集群",
        "分库分表", "数据库集群", "mysql集群",
        "负载均衡", "nginx", "lvs", "slb",
        "容器化", "docker", "kubernetes", "k8s",
        "服务治理", "dubbo", "spring cloud", "istio",
        "监控", "prometheus", "grafana", "elk",
        "链路追踪", "skywalking", "zipkin", "jaeger",
        "cdn", "加速", "oss",
        "搜索", "elasticsearch", "solr", "lucene",
        "大数据", "spark", "flink", "hadoop", "hive",
        "实时计算", "storm", "samza",
        "数据仓库", "数仓", "olap", "clickhouse",
        "推荐算法", "个性化", "协同过滤", "召回",
        "机器学习", "模型训练", "模型部署",
        "深度学习", "tensorflow", "pytorch",
    ]

    # 中复杂度关键词
    MEDIUM_COMPLEXITY_KEYWORDS = [
        "restful", "api", "接口",
        "数据库", "mysql", "postgresql", "mongodb",
        "前后端分离", "前端", "vue", "react",
        "后端", "spring", "django", "flask",
        "登录", "认证", "jwt", "oauth",
        "支付", "微信支付", "支付宝",
        "文件上传", "oss", "s3",
        "定时任务", "cron", "scheduler",
        "日志", "log", "logging",
        "单元测试", "测试", "junit",
        "敏捷", "scrum", "kanban",
    ]

    # 低复杂度关键词（课程作业特征）
    LOW_COMPLEXITY_KEYWORDS = [
        "课程设计", "课程作业", "实验",
        "大作业", "期末", "作业",
        "学生", "校园", "班级",
        "简单", "demo", "演示",
        "crud", "增删改查",
        "管理系统", "信息管理", "图书管理",
        "学习", "练习", "实践",
    ]

    # 业务价值关键词
    BUSINESS_VALUE_KEYWORDS = {
        "high": [
            "上线", "投产", "生产环境", "用户量",
            "日活", "月活", "DAU", "MAU",
            "营收", "交易额", "GMV",
            "降低成本", "提升效率", "优化",
            "核心", "关键", "重要",
            "团队", "项目组", "部门",
        ],
        "medium": [
            "原型", "demo", "mvp",
            "计划", "设计", "方案",
        ],
        "low": [
            "学习", "练习", "课程", "作业",
            "模拟", "仿真", "虚拟",
        ],
    }

    def analyze(self, project: Dict) -> ProjectQuality:
        """分析项目质量.

        Args:
            project: 项目信息，包含 title, description, tech_stack 等

        Returns:
            ProjectQuality
        """
        title = project.get("title", "")
        description = project.get("description", "")
        tech_stack = project.get("tech_stack", [])

        # 合并所有文本进行分析
        all_text = f"{title} {description} {' '.join(tech_stack)}"

        # 1. 计算复杂度
        complexity = self._calculate_complexity(all_text)

        # 2. 计算技术深度
        tech_depth_score = self._calculate_tech_depth(all_text)

        # 3. 计算业务价值
        business_value_score = self._calculate_business_value(all_text)

        # 4. 计算规模分数
        scale_score = self._calculate_scale(all_text)

        # 5. 综合分数
        overall_score = int(
            tech_depth_score * 0.4 +
            business_value_score * 0.3 +
            scale_score * 0.3
        )

        # 6. 提取亮点
        highlights = self._extract_highlights(all_text)

        return ProjectQuality(
            name=title,
            complexity=complexity,
            tech_depth_score=tech_depth_score,
            business_value_score=business_value_score,
            scale_score=scale_score,
            overall_score=overall_score,
            highlights=highlights,
        )

    def _calculate_complexity(self, text: str) -> ProjectComplexity:
        """计算项目复杂度."""
        text_lower = text.lower()

        # 检查高复杂度关键词
        high_count = sum(1 for kw in self.HIGH_COMPLEXITY_KEYWORDS
                        if kw.lower() in text_lower)
        if high_count >= 2:
            return ProjectComplexity.HIGH

        # 检查低复杂度关键词
        low_count = sum(1 for kw in self.LOW_COMPLEXITY_KEYWORDS
                       if kw.lower() in text_lower)
        if low_count >= 2:
            return ProjectComplexity.LOW

        return ProjectComplexity.MEDIUM

    def _calculate_tech_depth(self, text: str) -> int:
        """计算技术深度分数（0-100）。"""
        text_lower = text.lower()
        score = 30  # 基础分

        # 高复杂度技术加分
        for kw in self.HIGH_COMPLEXITY_KEYWORDS:
            if kw.lower() in text_lower:
                score += 5

        # 中复杂度技术加分
        for kw in self.MEDIUM_COMPLEXITY_KEYWORDS:
            if kw.lower() in text_lower:
                score += 2

        # 低复杂度减分
        for kw in self.LOW_COMPLEXITY_KEYWORDS:
            if kw.lower() in text_lower:
                score -= 5

        return max(0, min(100, score))

    def _calculate_business_value(self, text: str) -> int:
        """计算业务价值分数（0-100）。"""
        text_lower = text.lower()
        score = 30  # 基础分

        # 高价值关键词
        for kw in self.BUSINESS_VALUE_KEYWORDS["high"]:
            if kw.lower() in text_lower:
                score += 10

        # 低价值关键词
        for kw in self.BUSINESS_VALUE_KEYWORDS["low"]:
            if kw.lower() in text_lower:
                score -= 10

        # 检查数值指标
        if re.search(r'日活?\s*[用户量]?\s*[:：]?\s*\d+', text):
            score += 15
        if re.search(r'月活?\s*[用户量]?\s*[:：]?\s*\d+', text):
            score += 10
        if re.search(r'营收?\s*[:：]?\s*\d+', text):
            score += 15

        return max(0, min(100, score))

    def _calculate_scale(self, text: str) -> int:
        """计算规模分数（0-100）。"""
        score = 30

        # 高并发相关
        high_concurrency = ["qps", "tps", "并发", "pv", "uv", "吞吐"]
        for kw in high_concurrency:
            if kw.lower() in text.lower():
                score += 10

        # 数据量相关
        data_scale = ["万级", "百万", "千万", "亿级", "大数据", "海量"]
        for kw in data_scale:
            if kw in text:
                score += 10

        # 团队规模
        if re.search(r'团队\s*[:：]?\s*\d+\s*人', text):
            match = re.search(r'团队\s*[:：]?\s*(\d+)\s*人', text)
            if match:
                team_size = int(match.group(1))
                if team_size >= 10:
                    score += 20
                elif team_size >= 5:
                    score += 10

        return max(0, min(100, score))

    def _extract_highlights(self, text: str) -> List[str]:
        """提取项目亮点."""
        highlights = []
        text_lower = text.lower()

        # 提取技术亮点
        for kw in self.HIGH_COMPLEXITY_KEYWORDS[:10]:  # 只取前10个
            if kw.lower() in text_lower:
                highlights.append(f"使用{kw}")

        # 提取业务亮点
        if "上线" in text or "投产" in text:
            highlights.append("已上线")
        if "用户" in text:
            highlights.append("有用户")

        return highlights[:5]  # 最多5个亮点


# 单例
_project_analyzer: Optional[ProjectAnalyzer] = None


def get_project_analyzer() -> ProjectAnalyzer:
    """获取项目分析器单例。"""
    global _project_analyzer
    if _project_analyzer is None:
        _project_analyzer = ProjectAnalyzer()
    return _project_analyzer
