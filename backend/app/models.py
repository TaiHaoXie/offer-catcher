"""
Offer 捕手 - 数据模型定义
"""
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime


# ========== 基础信息模型 ==========

class BasicInfo(BaseModel):
    """基本信息"""
    name: str = Field(description="姓名")
    email: str = Field(description="邮箱")
    phone: Optional[str] = Field(default="", description="手机号")
    university: str = Field(description="学校")
    major: str = Field(description="专业")
    degree: str = Field(description="学历")
    graduation_year: str = Field(description="毕业年份")


class Education(BaseModel):
    """教育背景"""
    school: str = Field(description="学校名称")
    major: str = Field(description="专业")
    degree: str = Field(description="学历")
    gpa: Optional[str] = Field(default="", description="GPA")
    courses: List[str] = Field(default_factory=list, description="核心课程")


class WorkExperience(BaseModel):
    """工作/实习经历"""
    company: str = Field(description="公司名称")
    position: str = Field(description="职位")
    duration: str = Field(description="起止时间")
    description: str = Field(description="工作描述")


class Project(BaseModel):
    """项目经历"""
    name: str = Field(description="项目名称")
    role: str = Field(description="角色")
    tech_stack: List[str] = Field(default_factory=list, description="技术栈")
    description: str = Field(description="项目描述")


# ========== 简历模型 ==========

class ResumeData(BaseModel):
    """简历解析结果"""
    basic_info: BasicInfo
    skills: List[str] = Field(default_factory=list, description="技能列表")
    experience: List[WorkExperience] = Field(default_factory=list, description="工作经历")
    projects: List[Project] = Field(default_factory=list, description="项目经历")
    education: Optional[Education] = Field(default=None, description="教育背景")


class ResumeUploadResponse(BaseModel):
    """简历上传响应"""
    success: bool
    resume_id: str
    data: ResumeData
    message: str = ""


# ========== 岗位模型 ==========

class JobRequirements(BaseModel):
    """岗位要求"""
    hard_skills: List[str] = Field(default_factory=list, description="硬技能")
    soft_skills: List[str] = Field(default_factory=list, description="软技能")
    education: str = Field(default="", description="学历要求")
    experience: str = Field(default="", description="经验要求")
    preferred: List[str] = Field(default_factory=list, description="加分项")


class JobData(BaseModel):
    """岗位解析结果"""
    position_name: str = Field(description="岗位名称")
    company: str = Field(default="", description="公司名称")
    location: str = Field(default="", description="地点")
    requirements: JobRequirements
    responsibilities: List[str] = Field(default_factory=list, description="岗位职责")


class JobParseResponse(BaseModel):
    """岗位解析响应"""
    success: bool
    job_id: str
    data: JobData
    message: str = ""


# ========== 匹配结果模型 ==========

class MatchBreakdown(BaseModel):
    """匹配度细分"""
    hard_skills: float = Field(description="硬技能匹配度")
    soft_skills: float = Field(description="软技能匹配度")
    education: float = Field(description="教育背景匹配度")
    experience: float = Field(description="经验匹配度")
    projects: float = Field(description="项目相关性")


class GapItem(BaseModel):
    """差距项"""
    type: str = Field(description="类型: hard_skill/soft_skill/experience/project")
    missing: str = Field(description="缺失内容")
    importance: str = Field(description="重要性: high/medium/low")
    suggestion: str = Field(description="建议")


class MatchResult(BaseModel):
    """匹配结果"""
    total_score: float = Field(description="总分")
    breakdown: MatchBreakdown = Field(description="细分得分")
    gaps: List[GapItem] = Field(default_factory=list, description="差距分析")


class MatchResponse(BaseModel):
    """匹配计算响应"""
    success: bool
    match_id: str
    data: MatchResult
    message: str = ""


# ========== 优化建议模型 ==========

class SuggestionItem(BaseModel):
    """优化建议项"""
    type: str = Field(description="类型: 技能补充/项目优化/关键词补充")
    priority: str = Field(description="优先级: high/medium/low")
    content: str = Field(description="具体建议内容")
    example: Optional[str] = Field(default="", description="优化示例")


class OptimizationSuggestions(BaseModel):
    """优化建议"""
    suggestions: List[SuggestionItem] = Field(default_factory=list, description="建议列表")


class OptimizationResponse(BaseModel):
    """优化建议响应"""
    success: bool
    data: OptimizationSuggestions
    message: str = ""


# ========== 完整匹配响应（含建议）==========

class FullMatchResponse(BaseModel):
    """完整匹配响应（匹配结果+优化建议）"""
    success: bool
    match_id: str
    data: MatchResult
    suggestions: OptimizationSuggestions
    message: str = ""


# ========== 历史记录模型 ==========

class MatchHistoryItem(BaseModel):
    """匹配历史记录"""
    id: Optional[str] = None
    match_id: Optional[str] = None
    resume_id: Optional[str] = None
    job_id: Optional[str] = None
    position_name: str = ""
    company: str = ""
    total_score: float = 0
    created_at: Optional[str] = None  # 改为 str 类型接收 ISO 格式
    match_result: Optional[Dict] = None  # 改为 Dict 避免 MatchResult 验证问题
    suggestions: Optional[Dict] = None  # 改为 Dict 避免 OptimizationSuggestions 验证问题

    class Config:
        # 允许从 match_result 中提取 total_score
        extra = "ignore"

    @classmethod
    def from_db_record(cls, record: Dict) -> "MatchHistoryItem":
        """从数据库记录创建历史项"""
        match_result = record.get("match_result", {})
        return cls(
            id=record.get("id"),
            match_id=record.get("id"),  # 使用 id 作为 match_id
            resume_id=record.get("resume_id"),
            job_id=record.get("job_id"),
            position_name=record.get("position_name", ""),
            company=record.get("company", ""),
            total_score=match_result.get("total_score", 0) if isinstance(match_result, dict) else 0,
            created_at=record.get("created_at"),
            match_result=match_result,
            suggestions=record.get("suggestions")
        )


class HistoryResponse(BaseModel):
    """历史记录响应"""
    success: bool
    data: List[MatchHistoryItem]
    message: str = ""


# ========== 经历原子库模型 ==========

class ExperienceAtom(BaseModel):
    """经历原子"""
    id: Optional[str] = None
    type: str = Field(description="类型: work/project/education/award")
    title: str = Field(description="标题")
    company: Optional[str] = Field(default="", description="公司/组织")
    position: Optional[str] = Field(default="", description="职位")
    duration: Optional[str] = Field(default="", description="时间")
    description: str = Field(description="详细描述")
    skills: List[str] = Field(default_factory=list, description="相关技能")
    tags: List[str] = Field(default_factory=list, description="标签")
    keywords: List[str] = Field(default_factory=list, description="关键词")
    created_at: Optional[str] = None
    weight: float = Field(default=1.0, description="权重（基于反馈更新）")


class AtomLibraryResponse(BaseModel):
    """原子库响应"""
    success: bool
    data: List[ExperienceAtom]
    message: str = ""


class GeneratedResume(BaseModel):
    """生成的简历"""
    basic_info: Dict
    summary: str = Field(description="个人简介")
    skills: List[str] = Field(default_factory=list)
    experience: List[Dict] = Field(default_factory=list)
    projects: List[Dict] = Field(default_factory=list)
    education: Optional[Dict] = None
    target_keywords: List[str] = Field(default_factory=list, description="针对该JD的关键词")
    # 增强版字段
    original_skills: List[str] = Field(default_factory=list, description="原始技能")
    skills_optimization: Optional[Dict] = Field(default=None, description="技能优化建议")
    experience_tips: List[str] = Field(default_factory=list, description="经历优化建议")
    keyword_suggestions: List[Dict] = Field(default_factory=list, description="关键词建议")
    match_score: int = Field(default=0, description="匹配分数")
    actionable_tips: List[Dict] = Field(default_factory=list, description="可执行的优化建议")


class GeneratedResumeResponse(BaseModel):
    """生成简历响应"""
    success: bool
    data: GeneratedResume
    message: str = ""


# ========== 投递追踪模型 ==========

class ApplicationRecord(BaseModel):
    """投递记录"""
    id: Optional[str] = None
    company: str = Field(description="公司")
    position: str = Field(description="岗位")
    status: str = Field(description="状态: pending/interview/rejected/offered")
    applied_date: Optional[str] = None
    interview_date: Optional[str] = None
    notes: str = Field(default="", description="备注")
    keywords_used: List[str] = Field(default_factory=list, description="使用的关键词")


class ApplicationResponse(BaseModel):
    """投递记录响应"""
    success: bool
    data: List[ApplicationRecord]
    message: str = ""


class ApplicationUpdateRequest(BaseModel):
    """更新投递状态请求"""
    application_id: str
    status: str
    interview_date: Optional[str] = None
    notes: str = ""


class JDKeyword(BaseModel):
    """JD关键词"""
    keyword: str = Field(description="关键词")
    weight: float = Field(default=1.0, description="权重")
    category: str = Field(default="", description="类别: skill/experience/other")


class JDAnalysis(BaseModel):
    """JD分析结果"""
    position_name: str
    company: str
    keywords: List[JDKeyword] = Field(default_factory=list)
    core_requirements: List[str] = Field(default_factory=list)
    preferred: List[str] = Field(default_factory=list)


class KeywordCoverage(BaseModel):
    """关键词覆盖分析"""
    keyword: str
    weight: float
    covered: bool
    source: str = Field(description="来源: 哪个经历包含此关键词")


class EnhancedMatchResult(BaseModel):
    """增强匹配结果"""
    total_score: float
    keyword_coverage: float = Field(description="关键词覆盖率")
    covered_keywords: List[KeywordCoverage]
    missing_keywords: List[JDKeyword]
    vector_similarity: Optional[float] = Field(default=None, description="向量相似度")
    suggestions: List[str] = Field(default_factory=list)
