"""
Offer 捕手 - 学生求职匹配智能体 API
大厂专业级匹配分析 + 流式输出 + 简历优化

版本：1.2.0 (生产优化版)
- 使用 SQLite 替代 TinyDB，支持并发
- 添加 Redis 缓存层，提升性能
- 添加 API Key 认证
- 改进错误处理和日志
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import os
import io
import logging
import uvicorn
import re

# 导入服务模块
from app.services.fast_jd_parser import FastJDParser
from app.services.fast_resume_parser import FastResumeParser
from app.services.xulindi_resume_parser import XulindiResumeParser
from app.services.llm_resume_parser import get_llm_parser
from app.services.kimi_vision_parser import get_vision_parser
from app.services.gemini_style_matcher import GeminiStyleMatcher
from app.services.professional_match_engine import ProfessionalMatchEngine
from app.services.professional_resume_optimizer import ProfessionalResumeOptimizer
# 使用 SQLite 数据库
from app.db.sqlite_db import get_db
# 使用 Redis 缓存
from app.cache.redis_cache import get_cache, CacheConfig
# Celery 任务
from app.tasks.celery_app import celery_app
from app.tasks.resume_tasks import parse_resume_text_task, parse_resume_file_task
from app.tasks.job_tasks import parse_job_task
from app.tasks.match_tasks import match_analysis_task, optimize_resume_task
# 监控和告警
from app.monitoring.metrics import get_metrics, MetricsMiddleware
# 快速 PDF 解析
from app.utils.pdf_parser import get_pdf_parser
from app.services.campus_recruit.campus_scorer import CampusRecruitScorer, CampusScore
# 一次性匹配分析引擎
from app.services.one_shot_match_engine import get_one_shot_matcher
# 深度分析与经历原子生成
from app.services.deep_analysis import DeepAnalysisService
from app.services.atom_generator import AtomGenerator
# 岗位推荐
from app.services.job_recommender import get_job_recommender
# 账号鉴权与用量额度
from app.services.auth_service import get_auth_service, get_current_user
from app.services.quota_service import get_quota_service
from fastapi import Depends

# ========== 日志配置 ==========

# 确保日志目录存在（使用绝对路径）
import os
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, 'app.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ========== API Key 认证 ==========

API_KEYS = os.getenv("API_KEYS", "demo-key-123").split(",")

def verify_api_key(request: Request) -> bool:
    """验证 API Key（演示版简单实现）"""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        api_key = request.query_params.get("api_key")
    # 演示版本：如果没有 API Key，允许通过
    # 生产环境应该强制验证
    return True

# ========== 应用初始化 ==========

app = FastAPI(
    title="Offer 捕手 API",
    description="学生求职匹配智能体 - 生产优化版 v1.2.0",
    version="1.2.0"
)

# CORS 配置（仅允许本地开发）
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3005",
    "http://127.0.0.1:3005",
    "http://localhost:8888",
    "http://127.0.0.1:8888",
    "http://localhost:8890",
    "http://127.0.0.1:8890",
    "file://"  # 允许本地文件访问（仅演示用）
]

# 在容器/远程预览场景下，前端访问域名可能是一个局域网 IP（例如 192.168.x.x）。
# 这里提供一个可配置的正则白名单，默认允许 localhost / 127.0.0.1 / 任意 IPv4 + 任意端口。
# 如需更严格限制，可通过环境变量覆盖：CORS_ALLOW_ORIGIN_REGEX
CORS_ALLOW_ORIGIN_REGEX = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1|\d+\.\d+\.\d+\.\d+)(:\d+)?$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# 添加 Prometheus 监控中间件
# 注意：需要在 uvicorn.run 中包装，不在模块级别包装
# app = MetricsMiddleware(app)  # 移到启动块中

# 初始化服务
jd_parser = FastJDParser()
resume_parser = FastResumeParser()
xulindi_parser = XulindiResumeParser()
llm_parser = get_llm_parser()  # LLM 文本解析器
vision_parser = get_vision_parser()  # Kimi 视觉解析器
gemini_matcher = GeminiStyleMatcher()
match_engine = ProfessionalMatchEngine()
resume_optimizer = ProfessionalResumeOptimizer()
campus_scorer = CampusRecruitScorer()
deep_analysis_service = DeepAnalysisService()
atom_generator = AtomGenerator()
# 初始化缓存
cache = get_cache()

# ========== 数据模型 ==========

class ParseJDRequest(BaseModel):
    """JD解析请求"""
    jd_text: str

class MatchRequest(BaseModel):
    """匹配分析请求"""
    resume_id: str
    job_id: str

class OptimizeResumeRequest(BaseModel):
    """简历优化请求"""
    resume_id: str
    job_id: str

class CustomizeResumeRequest(BaseModel):
    """定制简历生成请求"""
    resume_id: Optional[str] = None
    resume_text: Optional[str] = None
    jd_text: str
    match_result: Dict[str, Any]
    atoms: List[Dict[str, Any]] = []

# ========== 根路径 ==========

@app.get("/api/health")
async def root():
    """API 状态检查"""
    try:
        db = get_db()
        stats = db.get_stats()
        cache_stats = cache.get_stats()
        return {
            "service": "Offer 捕手 API",
            "version": "1.2.0",
            "status": "running",
            "database": "SQLite (WAL mode)",
            "cache": "Redis",
            "database_stats": stats,
            "cache_stats": cache_stats
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "service": "Offer 捕手 API",
            "version": "1.2.0",
            "status": "degraded",
            "error": str(e)
        }

# ========== 账号鉴权 / 用量额度 / 邀请码接口 ==========

class PhoneLoginRequest(BaseModel):
    phone: str
    code: str


class RedeemInviteRequest(BaseModel):
    code: str


@app.post("/api/v1/auth/login")
async def auth_login(req: PhoneLoginRequest):
    """手机号 + 验证码登录/注册，返回 JWT。

    - 站长本人手机号无限次；其他手机号凭通用验证码可使用一次完整流程。
    - 首次登录自动创建账号（无需单独注册）。
    """
    try:
        return {"success": True, **get_auth_service().login_with_phone(req.phone, req.code)}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.get("/api/v1/auth/me")
async def auth_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """返回当前登录用户信息（手机号、剩余次数、是否无限、是否看过引导）。"""
    return {"success": True, "user": current_user}


@app.post("/api/v1/auth/onboarding-done")
async def auth_onboarding_done(current_user: Dict[str, Any] = Depends(get_current_user)):
    """标记当前用户已完成首次引导。"""
    get_db().mark_onboarding_done(current_user["id"])
    return {"success": True}


@app.post("/api/v1/invite/redeem")
async def invite_redeem(req: RedeemInviteRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """兑换邀请码，增加免费体验次数。"""
    try:
        result = get_quota_service().redeem_invite(current_user["id"], req.code)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/share/claim")
async def share_claim(current_user: Dict[str, Any] = Depends(get_current_user)):
    """分享给微信好友奖励：每个账号仅可领取一次 +1 次。"""
    try:
        result = get_quota_service().claim_share_reward(current_user["id"])
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== 简历解析接口 ==========

@app.post("/api/v1/resume/parse")
async def parse_resume(file: UploadFile = File(...)):
    """
    解析上传的简历文件

    支持格式：
    - PDF: 使用 Kimi 视觉模型直接分析图片
    - 图片: 使用 Kimi 视觉模型分析
    - DOCX: 提取文本后用 LLM 分析
    - TXT: 直接用 LLM 分析

    错误处理：
    - 文件过大: 前端限制，后端验证
    - 格式不支持: 返回友好提示
    - AI 调用失败: 降级到文本解析
    """
    db = get_db()
    pdf_parser = get_pdf_parser()

    # 文件大小限制 (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    try:
        logger.info(f"Parsing resume file: {file.filename}")

        # 读取文件内容
        content = await file.read()
        filename = file.filename or ""

        # 检查文件大小
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"文件过大，请上传小于 10MB 的文件")

        resume_data = None

        # 根据文件类型选择解析方式
        if filename.lower().endswith('.pdf'):
            # 优先走「文本提取 + LLM」快路径：绝大多数简历是数字版 PDF，可直接取文本，
            # 比把每页渲染成 2x 图片再喂视觉模型快很多。只有文本为空/疑似乱码（扫描件）
            # 才回退到 Kimi 视觉模型。
            text = ""
            try:
                text = pdf_parser.extract_text(content, filename)
            except Exception as e:
                logger.warning(f"PDF 文本提取失败，转视觉解析: {e}")

            if text.strip() and not pdf_parser._looks_garbled(text):
                logger.info("PDF 文本提取成功，使用 LLM 文本解析（快路径）")
                resume_data = await llm_parser.parse_async(text)
            else:
                # 扫描件 / 取不到文本：用 Kimi 视觉模型兜底
                try:
                    logger.info("PDF 无可用文本，使用 Kimi 视觉模型解析...")
                    resume_data = await vision_parser.parse_pdf_async(content, filename)
                    logger.info(f"视觉解析成功: {resume_data.get('basic_info', {}).get('name', '未知')}")
                except Exception as e:
                    logger.warning(f"视觉解析失败: {e}")
                    if not text.strip():
                        raise ValueError("无法从 PDF 中提取文本内容")
                    resume_data = await llm_parser.parse_async(text)

        elif filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            # 图片文件，使用视觉模型
            logger.info("使用 Kimi 视觉模型解析图片...")
            resume_data = await vision_parser.parse_image_async(content, filename)

        elif filename.lower().endswith('.docx'):
            # DOCX 文件，提取文本后用 LLM 解析
            try:
                from docx import Document
                doc = Document(io.BytesIO(content))
                text = "\n".join([p.text for p in doc.paragraphs])
            except ImportError:
                text = content.decode('utf-8', errors='ignore')

            if text.strip():
                resume_data = await llm_parser.parse_async(text)
            else:
                raise ValueError("无法从 DOCX 中提取文本内容")

        else:
            # 纯文本文件
            text = content.decode('utf-8', errors='ignore')
            resume_data = await llm_parser.parse_async(text)

        # 验证解析结果
        if not resume_data or not resume_data.get("basic_info", {}).get("name"):
            raise ValueError("解析失败：无法识别简历中的姓名信息")

        # 保存到数据库
        resume_id = db.save_resume(resume_data)
        logger.info(f"Resume parsed successfully: {resume_id}")

        return {
            "success": True,
            "resume_id": resume_id,
            "data": {**resume_data, "id": resume_id},
            "message": "简历解析成功"
        }

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Resume parsing failed: {e}")
        raise HTTPException(status_code=500, detail=f"简历解析失败: {str(e)}")


class ParseResumeTextRequest(BaseModel):
    """简历文本解析请求"""
    text: str


@app.post("/api/v1/resume/parse-text")
async def parse_resume_text(request: ParseResumeTextRequest):
    """解析粘贴的简历文本"""
    db = get_db()
    try:
        logger.info("Parsing resume from text")

        # 先检查缓存
        cached_result = cache.get_cached_resume_parse(request.text)
        if cached_result:
            logger.info("Resume parse cache hit")
            # 缓存命中，保存新的记录并返回
            resume_id = db.save_resume(cached_result)
            return {
                "success": True,
                "resume_id": resume_id,
                "data": {**cached_result, "id": resume_id},
                "message": "简历解析成功（缓存）",
                "cached": True
            }

        # 优先使用 LLM 解析器（完整提取，不丢信息）
        try:
            resume_data = await llm_parser.parse_async(request.text)
            if resume_data.get("basic_info", {}).get("name"):
                logger.info(f"LLM 解析成功: {resume_data['basic_info'].get('name')}")
            else:
                raise ValueError("LLM 解析未能识别姓名")
        except Exception as e:
            logger.warning(f"LLM 解析失败，回退到传统解析器: {e}")
            # 回退到传统解析器
            try:
                resume_data = xulindi_parser.parse(request.text)
                if not resume_data.get("basic_info", {}).get("name"):
                    resume_data = resume_parser.parse_from_text(request.text)
            except Exception as e2:
                raise ValueError(f"所有解析器都失败了: {e2}")

        # 保存到数据库
        resume_id = db.save_resume(resume_data)

        # 缓存解析结果
        cache.cache_resume_parse(request.text, resume_data)

        return {
            "success": True,
            "resume_id": resume_id,
            "data": {**resume_data, "id": resume_id},
            "message": "简历解析成功"
        }

    except Exception as e:
        logger.error(f"Resume text parsing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== JD解析接口 ==========

@app.post("/api/v1/job/parse")
async def parse_job(request: ParseJDRequest):
    """解析JD文本"""
    db = get_db()
    try:
        logger.info("Parsing job description")

        # 先检查缓存
        cached_result = cache.get_cached_job_parse(request.jd_text)
        if cached_result:
            logger.info("Job parse cache hit")
            job_id = db.save_job(cached_result)
            return {
                "success": True,
                "data": {**cached_result, "id": job_id},
                "message": "JD解析成功（缓存）",
                "cached": True
            }

        # 使用快速JD解析器
        job_data = jd_parser.parse(request.jd_text)

        # 保存到数据库
        job_id = db.save_job(job_data)

        # 缓存解析结果
        cache.cache_job_parse(request.jd_text, job_data)

        return {
            "success": True,
            "data": {**job_data, "id": job_id},
            "message": "JD解析成功"
        }

    except Exception as e:
        logger.error(f"Job parsing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== 匹配分析接口 ==========

@app.post("/api/v1/match")
async def match_analysis(request: MatchRequest):
    """执行专业级匹配分析"""
    db = get_db()
    try:
        logger.info(f"Starting match analysis: resume={request.resume_id}, job={request.job_id}")

        # 先检查缓存
        cached_match = cache.get_cached_match_result(request.resume_id, request.job_id)
        if cached_match:
            logger.info("Match result cache hit")
            # 保存新的匹配记录
            resume_record = db.get_resume(request.resume_id)
            job_record = db.get_job(request.job_id)
            match_record_data = {
                "resume_id": request.resume_id,
                "job_id": request.job_id,
                "match_result": cached_match,
                "position_name": job_record.get("position_name", "") if job_record else "",
                "company": job_record.get("company", "") if job_record else ""
            }
            match_id = db.save_match(match_record_data)
            return {
                "success": True,
                "data": {**cached_match, "match_id": match_id},
                "message": "专业级匹配分析完成（缓存）",
                "cached": True
            }

        # 获取数据
        resume_record = db.get_resume(request.resume_id)
        job_record = db.get_job(request.job_id)

        if not resume_record or not job_record:
            raise HTTPException(status_code=404, detail="简历或岗位不存在")

        resume_data = resume_record
        job_data = job_record

        # 执行匹配分析
        match_result = match_engine.calculate(resume_data, job_data)

        # 保存匹配记录
        match_record_data = {
            "resume_id": request.resume_id,
            "job_id": request.job_id,
            "match_result": match_result,
            "position_name": job_data.get("position_name", ""),
            "company": job_data.get("company", "")
        }
        match_id = db.save_match(match_record_data)

        # 缓存匹配结果
        cache.cache_match_result(request.resume_id, request.job_id, match_result)

        logger.info(f"Match analysis completed: {match_id}")

        return {
            "success": True,
            "data": {**match_result, "match_id": match_id},
            "message": "专业级匹配分析完成"
        }

    except Exception as e:
        logger.error(f"Match analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/match/from-upload")
async def match_from_upload(
    resume_file: UploadFile = File(..., description="简历文件"),
    jd_text: str = Form(..., description="JD 文本")
):
    """
    一次性匹配分析 - 上传简历文件 + JD 文本，直接返回匹配结果

    流程：
    1. 接收简历文件（PDF/图片/DOCX）
    2. 接收 JD 文本
    3. 提取简历文本
    4. 调用 LLM 一次性分析：解析简历 + 解析 JD + 匹配分析
    5. 返回匹配结果

    优势：
    - 只调用一次 AI，响应更快
    - AI 同时看到简历和 JD，匹配更准确
    - 用户体验更流畅
    """
    try:
        logger.info(f"一次性匹配分析: {resume_file.filename}")

        # 读取文件
        file_bytes = await resume_file.read()
        filename = resume_file.filename or "resume"

        # 文件大小限制 (10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        if len(file_bytes) > MAX_FILE_SIZE:
            raise ValueError(f"文件过大，请上传小于 10MB 的文件")

        # 获取一次性匹配引擎
        one_shot_matcher = get_one_shot_matcher()

        # 执行一次性分析
        match_result = await one_shot_matcher.analyze(file_bytes, filename, jd_text)

        # 可选：保存到数据库
        db = get_db()
        # 解析简历数据用于存储
        # 这里简化处理，实际可以存储完整记录

        logger.info(f"一次性匹配分析完成")

        return {
            "success": True,
            "data": match_result,
            "message": "匹配分析完成"
        }

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"One-shot match failed: {e}")
        raise HTTPException(status_code=500, detail=f"匹配分析失败: {str(e)}")


# ========== 流式匹配分析接口 ==========

from fastapi.responses import StreamingResponse
import asyncio

@app.post("/api/v1/match/stream")
async def stream_match_analysis(resume_data: str = Form(...), job_data: str = Form(...)):
    """
    Gemini 风格流式匹配分析 - 像真实 HR 思考过程

    输出格式：
    - start: 开始分析
    - thinking: 思考状态
    - section: 分析章节
    - content: 流式文本内容
    - result: 结构化结果
    - complete: 分析完成
    """
    async def event_generator():
        try:
            # 解析输入
            resume_dict = json.loads(resume_data)
            job_dict = json.loads(job_data)

            # 使用 Gemini 风格匹配器
            async for event in gemini_matcher.match_analysis_stream(resume_dict, job_dict):
                yield event

        except Exception as e:
            import traceback
            yield f'event: error\ndata: {{"message": "分析失败: {str(e)}"}}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/v1/match/from-upload/stream")
async def stream_match_from_upload(
    resume_file: Optional[UploadFile] = File(None, description="简历文件"),
    jd_text: str = Form(..., description="JD 文本"),
    use_fixed_resume: bool = Form(False, description="是否使用固定测试简历"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    流式一次性匹配分析 - 支持文件上传

    SSE 事件类型：
    - event: progress     - 进度更新（含 id 支持断线重连）
    - event: thinking     - AI 思考过程
    - event: result       - 最终匹配结果
    - event: error        - 错误信息
    - event: done         - 分析完成
    - event: heartbeat    - 心跳保持连接

    SSE 格式符合最佳实践：
    - 使用 JSON 格式 data 字段
    - 添加 id 字段支持断线重连
    - 添加 retry 字段控制重连间隔
    - 正确的响应头配置
    """
    # ===== 准入：必须已登录且有剩余次数 =====
    quota_service = get_quota_service()
    if not quota_service.check_quota(current_user["id"]):
        raise HTTPException(
            status_code=402,
            detail="免费次数已用完，输入邀请码可再体验一次，或前往升级获取更多次数。"
        )

    # ===== 先读取文件（避免在生成器中读取时文件已关闭）=====
    if use_fixed_resume:
        fixed_resume_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "uploads",
            "fixed-test-resume.pdf"
        )
        if not os.path.exists(fixed_resume_path):
            raise HTTPException(status_code=400, detail="固定测试简历不存在")
        with open(fixed_resume_path, "rb") as f:
            file_bytes = f.read()
        filename = os.path.basename(fixed_resume_path)
        logger.info(f"使用固定测试简历: {filename}")
    else:
        if resume_file is None:
            raise HTTPException(status_code=400, detail="请上传简历文件，或启用固定测试简历")
        file_bytes = await resume_file.read()
        filename = resume_file.filename or "resume"
    one_shot_matcher = get_one_shot_matcher()
    db = get_db()
    atoms = db.list_atoms()

    # 生成唯一会话 ID 用于断线重连
    import uuid
    session_id = str(uuid.uuid4())[:8]
    event_id = 0

    async def event_generator():
        nonlocal file_bytes, filename, one_shot_matcher, jd_text
        nonlocal event_id

        try:
            import asyncio
            import time

            # ===== 初始连接确认 =====
            event_id += 1
            yield f": 连接已建立\n\n"
            yield f"retry: 3000\n\n"
            yield f"event: connected\ndata: {json.dumps({'session_id': session_id, 'filename': filename})}\nid: {event_id}\n\n"

            # ===== 阶段1：读取文件 =====
            event_id += 1
            yield f"event: progress\ndata: {json.dumps({'stage': 'reading', 'message': '🔍 开始分析...'})}\nid: {event_id}\n\n"

            event_id += 1
            yield f"event: progress\ndata: {json.dumps({'stage': 'reading', 'message': '📄 正在读取简历...'})}\nid: {event_id}\n\n"

            # ===== 阶段2：准备AI分析 =====
            start_time = time.time()
            resume_input = file_bytes

            event_id += 1
            yield f"event: progress\ndata: {json.dumps({'stage': 'uploading', 'message': '✓ 简历读取完成'})}\nid: {event_id}\n\n"

            # ===== 阶段3：LLM 流式分析 =====
            event_count = 0
            got_result = False

            logger.info("开始调用 analyze_stream...")

            async for event_type, event_data in one_shot_matcher.analyze_stream(
                resume_input, jd_text, filename, atoms=atoms
            ):
                event_count += 1
                logger.info(f"[SSE] 收到事件 #{event_count}: type={event_type}")

                event_id += 1

                if event_type == "progress":
                    # 进度更新 - 直接传递 event_data
                    yield f"event: progress\ndata: {json.dumps(event_data)}\nid: {event_id}\n\n"

                elif event_type == "connected":
                    yield f"event: connected\ndata: {json.dumps(event_data)}\nid: {event_id}\n\n"

                elif event_type == "thinking":
                    yield f"event: thinking\ndata: {json.dumps(event_data)}\nid: {event_id}\n\n"

                elif event_type == "stage":
                    # 阶段状态更新
                    stage_data = event_data
                    if stage_data.get("status") == "analyzing":
                        stage_title = stage_data.get('title', '分析')
                        if stage_data.get("status") == "analyzing":
                            emoji = "🔍"
                            message = f"{emoji} {stage_title}..."
                            yield f"event: progress\ndata: {json.dumps({'stage': 'analyzing', 'message': message})}\nid: {event_id}\n\n"
                        elif stage_data.get("status") == "done":
                            emoji = "✓"
                            message = f"{emoji} {stage_title}完成"
                            yield f"event: progress\ndata: {json.dumps({'stage': 'done', 'message': message})}\nid: {event_id}\n\n"

                elif event_type == "result":
                    # 最终结果
                    got_result = True
                    yield f"event: result\ndata: {json.dumps(event_data)}\nid: {event_id}\n\n"

                elif event_type == "error":
                    # 错误
                    yield f"event: error\ndata: {json.dumps(event_data)}\nid: {event_id}\n\n"

                elif event_type == "done":
                    # 完成
                    yield f"event: done\ndata: {json.dumps(event_data)}\nid: {event_id}\n\n"

            # ===== 完成 =====
            # 分析成功产出结果才扣减额度；扣减后把最新剩余次数推给前端。
            if got_result:
                try:
                    quota_service.consume(current_user["id"])
                    refreshed = get_db().get_user_by_id(current_user["id"]) or {}
                    event_id += 1
                    yield f"event: quota\ndata: {json.dumps({'remaining_quota': refreshed.get('remaining_quota', 0)})}\nid: {event_id}\n\n"
                except Exception as quota_err:
                    logger.warning(f"额度扣减失败（不影响结果返回）: {quota_err}")

            event_id += 1
            elapsed = time.time() - start_time
            yield f"event: done\ndata: {json.dumps({'message': '分析完成', 'elapsed': f'{elapsed:.1f}秒'})}\nid: {event_id}\n\n"

        except asyncio.CancelledError:
            # 用户主动中止（如刷新页面）
            logger.info(f"SSE 连接被用户取消: session_id={session_id}")
            event_id += 1
            yield f"event: cancelled\ndata: {json.dumps({'message': '分析已取消'})}\nid: {event_id}\n\n"

        except Exception as e:
            import traceback
            error_msg = f"分析失败: {str(e)}"
            logger.error(f"流式分析错误: {traceback.format_exc()}")
            event_id += 1
            yield f"event: error\ndata: {json.dumps({'message': error_msg, 'type': 'system_error'})}\nid: {event_id}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            "X-Content-Type-Options": "nosniff"
        }
    )


# ========== 流式输出辅助函数 ==========

def _get_verb_rating(score: float) -> str:
    """根据动词强度分数返回评级"""
    if score >= 8.5:
        return "优秀 - 表达极具说服力"
    elif score >= 7.5:
        return "良好 - 表达清晰有力"
    elif score >= 6.5:
        return "一般 - 部分表达偏弱"
    else:
        return "需改进 - 建议强化动词"


def _get_verb_suggestions(weak_verbs: list) -> list:
    """获取动词升级建议"""
    verb_upgrade_map = {
        "协助": "负责/主导",
        "参与": "执行/构建",
        "学习": "掌握/精通",
        "帮忙": "支持/协调",
        "负责": "主导/引领",
        "执行": "构建/实现"
    }
    suggestions = []
    for verb in weak_verbs[:3]:
        if verb in verb_upgrade_map:
            suggestions.append(f"'{verb}' → '{verb_upgrade_map[verb]}'")
    return suggestions


def _estimate_pass_rate(score: float) -> str:
    """估算通过率"""
    if score >= 85:
        return "75% - 高通过率"
    elif score >= 75:
        return "50% - 中等通过率"
    elif score >= 65:
        return "30% - 需要优化"
    elif score >= 55:
        return "15% - 建议补缺"
    else:
        return "5% - 匹配度较低"


def _get_score_conclusion(score: float) -> str:
    """获取评分结论"""
    if score >= 85:
        return "简历与岗位高度匹配，建议直接投递"
    elif score >= 75:
        return "匹配度良好，小幅优化后投递"
    elif score >= 65:
        return "存在明显缺口，建议重点优化"
    elif score >= 55:
        return "匹配度不足，建议慎重考虑"
    else:
        return "匹配度较低，不建议投递"


def _estimate_score_improvement(current_score: float, suggestions: list) -> str:
    """估算优化后分数提升"""
    high_priority_count = len([s for s in suggestions if s.get("priority") == "high"])
    estimated_gain = high_priority_count * 5
    new_score = min(95, current_score + estimated_gain)
    improvement = new_score - current_score
    return f"+{improvement:.1f}分 → {new_score:.1f}分"


def _extract_advantages(resume_dict: dict, job_dict: dict) -> list:
    """提取简历优势"""
    advantages = []

    # 大厂背景
    work_exp = resume_dict.get("experience", [])
    big_companies = ["字节", "腾讯", "阿里", "百度", "美团", "京东", "滴滴", "网易", "小米", "华为"]
    for exp in work_exp:
        company = exp.get("company", "")
        if any(bc in company for bc in big_companies):
            advantages.append(f"大厂背景 ({company})")
            break

    # 学历优势
    education = resume_dict.get("education", {})
    degree = education.get("degree", "")
    if "硕士" in degree or "博士" in degree:
        advantages.append(f"高学历 ({degree})")

    # 项目成果量化
    projects = resume_dict.get("projects", [])
    for proj in projects:
        desc = proj.get("description", "")
        if any(char in desc for char in ["%", "倍", "万", "亿"]):
            advantages.append("项目成果量化")
            break

    # 技能广度
    skills = resume_dict.get("skills", [])
    if len(skills) >= 10:
        advantages.append("技能广度")

    return advantages[:3]


def _extract_improvements(resume_dict: dict, job_dict: dict) -> list:
    """提取需要改进的方面"""
    improvements = []

    # 缺少热门技术
    requirements = job_dict.get("requirements", {})
    required_skills = requirements.get("hard_skills", [])
    resume_skills = resume_dict.get("skills", [])
    missing = [s for s in required_skills if s not in resume_skills]
    if missing:
        improvements.append(f"补充技能: {', '.join(missing[:2])}")

    # 经验不足
    work_exp = resume_dict.get("experience", [])
    if len(work_exp) < 2:
        improvements.append("增加工作经验")

    # 项目缺乏量化
    projects = resume_dict.get("projects", [])
    has_quantified = any(
        any(char in proj.get("description", "") for char in ["%", "倍", "万"])
        for proj in projects
    )
    if not has_quantified:
        improvements.append("量化项目成果")

    return improvements[:3]


def _generate_strategy(total_score: float, match_level: str) -> str:
    """生成投递策略建议"""
    if total_score >= 80:
        return "强烈推荐投递，你的背景与岗位高度匹配。建议在面试中突出核心项目经验。"
    elif total_score >= 65:
        return "推荐投递，但建议重点优化简历中的技能描述和项目成果。可先补充短板再投递。"
    elif total_score >= 50:
        return "谨慎投递，存在明显技能或经验缺口。建议先系统学习相关技术栈，补充项目经验。"
    else:
        return "不建议投递，匹配度较低。建议选择更符合当前背景的岗位，或进行系统性技能提升。"


def _infer_job_title_from_text(jd_text: str) -> str:
    lines = [line.strip("•- \t") for line in (jd_text or "").splitlines() if line.strip()]
    return lines[0] if lines else "目标岗位"


def _extract_requirement_groups(match_result: Dict[str, Any], jd_text: str) -> Dict[str, List[str]]:
    requirement_checks = (
        match_result.get("report_requirement_checks")
        or match_result.get("requirement_checks")
        or match_result.get("sections", {}).get("requirement_checks")
        or []
    )
    matched = []
    missing = []
    for item in requirement_checks:
        requirement = str(item.get("requirement") or item.get("title") or "").strip()
        if not requirement:
            continue
        status = str(item.get("status", "")).lower()
        if status in {"matched", "strong_match", "fully_matched"}:
            matched.append(requirement)
        else:
            missing.append(requirement)

    if not matched and not missing:
        jd_decomp = (
            match_result.get("report_jd_decomposition")
            or match_result.get("jd_decomposition")
            or {}
        )
        core_competencies = jd_decomp.get("core_competencies", []) or []
        # 注意：不要把 JD 硬要求直接当成"已匹配"。没有证据时宁可留空，
        # 也不能把岗位标题/职责行误标为候选人的匹配能力（会出现"匹配能力=岗位职责"的怪现象）。
        missing = core_competencies[:3]

    if not missing and jd_text:
        lines = [line.strip("•- \t") for line in jd_text.splitlines() if line.strip()]
        missing = lines[2:5]

    return {
        "matched": matched[:5],
        "missing": missing[:5],
    }


def _tokenize_for_match(text: str) -> List[str]:
    raw_tokens = re.findall(r"[A-Za-z0-9\+\-#/\.]+|[\u4e00-\u9fff]{2,8}", text or "")
    blacklist = {"负责", "参与", "能够", "以及", "进行", "相关", "经验", "能力", "产品", "岗位", "要求", "加分项", "我们提供"}
    tokens = []
    for token in raw_tokens:
        token = token.strip()
        if len(token) < 2 or token in blacklist:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens[:30]


def _extract_basic_info_from_text(resume_text: str) -> Dict[str, str]:
    """从原始简历文本里粗略提取姓名/电话/邮箱，供定制简历 PDF 抬头使用。

    只做轻量正则提取，提取不到就留空，绝不臆造。
    """
    text = (resume_text or "").strip()
    info = {"name": "", "phone": "", "email": ""}
    if not text:
        return info

    m_phone = re.search(r"(?<!\d)(1[3-9]\d{9})(?!\d)", text)
    if m_phone:
        info["phone"] = m_phone.group(1)
    m_email = re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)
    if m_email:
        info["email"] = m_email.group(0)

    # 姓名：在前若干行里找"最像姓名"的一行。
    # 复杂排版（双栏/色块）时第一行常是"联系方式""教育背景"等标签，需跳过。
    label_words = {"联系方式", "教育背景", "工作经历", "实习经历", "项目经历", "核心技能",
                   "专业技能", "个人简介", "自我评价", "求职意向", "语言能力", "技能",
                   "荣誉奖项", "校园经历", "基本信息", "电话", "邮箱", "城市", "简历",
                   "硕士", "博士", "本科", "学士", "大专", "专科", "研究生"}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # 优先：带"姓名/名字"标签的行
    for line in lines[:15]:
        m = re.match(r"^(?:姓名|名字)[：:\s]*([\u4e00-\u9fff]{2,4})\b", line)
        if m:
            info["name"] = m.group(1)
            break
    # 其次：前 8 行里，纯 2-4 个中文字、且不是栏目标签/机构名的行
    if not info["name"]:
        for line in lines[:8]:
            candidate = re.split(r"[\s，,|·/]", line)[0]
            if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", candidate):
                continue
            if candidate in label_words:
                continue
            # 排除明显是机构/院校/专业名的词（避免把"清华大学""计算机"当姓名）
            if re.search(r"(大学|学院|学校|公司|专业|科学|技术|工程|管理|系统)$", candidate):
                continue
            info["name"] = candidate
            break
    return info


async def _build_customize_resume_with_ai(
    resume_text: str,
    jd_text: str,
    match_result: Dict[str, Any],
    atom_refs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """基于 AI 的定制简历改写：严格只允许基于原简历改写，不允许编造经历。

    复用 one_shot 引擎的 Kimi 配置；输出固定 JSON，便于前端稳定渲染与导出 PDF。
    失败时由调用方回退到规则版兜底。
    atom_refs：用户在「经历原子库」里针对该 JD 改写好的表达，作为优先参考喂给模型。
    """
    from litellm import acompletion

    api_key = os.getenv("KIMI_API_KEY", "")
    api_base = os.getenv("KIMI_API_BASE", "https://api.moonshot.cn/v1")
    if not api_key:
        raise RuntimeError("缺少 KIMI_API_KEY，无法进行 AI 定制简历")

    requirement_groups = _extract_requirement_groups(match_result, jd_text)
    matched_requirements = requirement_groups.get("matched", [])
    missing_requirements = requirement_groups.get("missing", [])

    # 组织「原子库已优化表达」参考：用户已针对该 JD 改写过的经历 bullet，优先沿用
    atom_ref_text = ""
    for ref in (atom_refs or [])[:8]:
        title = (ref.get("title") or "").strip()
        bullets = ref.get("bullets") or []
        bullets = [str(b).strip() for b in bullets if str(b).strip()]
        if title and bullets:
            atom_ref_text += f"\n- 【{title}】\n  " + "\n  ".join(bullets)

    # 控制 token：原简历过长时截断
    resume_text = (resume_text or "").strip()
    if len(resume_text) > 3500:
        resume_text = resume_text[:3500]

    atom_ref_block = ("\n【已优化表达参考】（用户已针对该 JD 改写过的经历，请优先沿用）：" + atom_ref_text) if atom_ref_text else ""

    prompt = f"""你是一名资深简历顾问。请基于【原始简历】和【目标 JD】，生成一版更贴合该岗位的定制简历草稿。

【最高原则】
1. 只能基于原始简历里真实存在的经历进行改写、重排、强化表达。
2. 严禁编造任何简历里没有的公司、项目、数据、技能、奖项。
3. 对原简历缺失、但 JD 需要的能力，不要硬写进经历，而是放进 do_not_fake 字段提醒用户。
4. 改写要点：用“场景-动作-结果”结构，能量化就量化（但不能伪造数字）。
5. 若提供了【已优化表达参考】，请优先沿用其中已经针对该 JD 打磨好的 bullet 表达（可微调措辞），但不得引入参考里凭空出现、原简历没有的事实。

【目标 JD】
{jd_text[:1500]}

【JD 已匹配要点】{('、'.join(matched_requirements[:6]) or '无')}
【JD 仍欠缺要点】{('、'.join(missing_requirements[:6]) or '无')}

【原始简历】
{resume_text}
{atom_ref_block}

只输出合法 JSON，不要 Markdown、不要代码块、不要解释。字段如下：
{{
  "headline": "一句话定位，面向该岗位",
  "profile_summary": "3-4 句个人简介，突出与岗位相关的能力与亮点",
  "skills_line": ["按与岗位相关度排序的技能，最多10个"],
  "selected_atoms": [
    {{
      "title": "经历/项目名称（必须来自原简历）",
      "company": "公司/组织，没有则空字符串",
      "type": "work|project",
      "bullets": ["改写后的 bullet，2-4 条，场景-动作-结果结构"]
    }}
  ],
  "ordering_strategy": ["简历排布建议，1-3 条"],
  "do_not_fake": ["JD 需要但原简历没有、不建议硬写的内容"]
}}

要求：
- selected_atoms 必须来自原简历的真实经历，最多 4 段，最相关的放最前。
- skills_line 只列原简历里出现或可合理归纳的技能，不要塞 JD 里但简历没有的。
- 所有字段必须给出，没有内容用空数组或空字符串。
"""

    resp = await acompletion(
        model="openai/moonshot-v1-8k",
        messages=[
            {"role": "system", "content": "你是严谨的简历顾问，只输出合法 JSON，绝不编造简历中不存在的内容。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2500,
        api_key=api_key,
        api_base=api_base,
        timeout=60,
        num_retries=3,  # Kimi 过载(429)时自动退避重试，避免直接掉到规则兜底
    )
    content = resp.choices[0].message.content or ""
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        data = json.loads(stripped)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", stripped)
        if not m:
            raise
        data = json.loads(m.group(0))

    # 规范化为前端已支持的结构
    target_job = _infer_job_title_from_text(jd_text)
    selected = data.get("selected_atoms") or []
    draft_blocks = []
    for atom in selected[:4]:
        if not isinstance(atom, dict):
            continue
        draft_blocks.append({
            "title": str(atom.get("title") or "核心经历"),
            "company": str(atom.get("company") or ""),
            "type": str(atom.get("type") or "project"),
            "reasons": [],
            "bullets": [str(b) for b in (atom.get("bullets") or []) if str(b).strip()][:4],
            "skills": [],
        })

    do_not_fake = [str(x) for x in (data.get("do_not_fake") or []) if str(x).strip()]
    summary_bullets = []
    if matched_requirements:
        summary_bullets.append(f"把简历重心放在：{'、'.join(matched_requirements[:2])}")
    if do_not_fake:
        summary_bullets.append(f"以下内容不要硬写，避免被追问穿帮：{'、'.join(do_not_fake[:2])}")

    return {
        "target_job": target_job,
        "basic_info": _extract_basic_info_from_text(resume_text),
        "headline": str(data.get("headline") or f"面向 {target_job} 的定制简历草稿"),
        "summary": str(data.get("profile_summary") or "已基于你的原始简历与目标 JD 生成定制草稿，仅做真实经历的改写与重排。"),
        "profile_summary": str(data.get("profile_summary") or ""),
        "skills_line": [str(s) for s in (data.get("skills_line") or []) if str(s).strip()][:10],
        "ordering_strategy": [str(s) for s in (data.get("ordering_strategy") or []) if str(s).strip()][:3],
        "matched_requirements": matched_requirements,
        "missing_requirements": missing_requirements,
        "summary_bullets": summary_bullets[:3],
        "selected_atoms": draft_blocks,
        "optimization_notes": do_not_fake[:4],
        "engine": "ai",
    }


def _build_customize_resume_payload(jd_text: str, match_result: Dict[str, Any], atoms: List[Dict[str, Any]]) -> Dict[str, Any]:
    target_job = _infer_job_title_from_text(jd_text)
    requirement_groups = _extract_requirement_groups(match_result, jd_text)
    matched_requirements = requirement_groups["matched"]
    missing_requirements = requirement_groups["missing"]
    jd_keywords = _tokenize_for_match("\n".join(matched_requirements + missing_requirements + [jd_text]))

    def score_atom(atom: Dict[str, Any]) -> Dict[str, Any]:
        atom_text = " ".join([
            str(atom.get("title", "")),
            str(atom.get("company", "")),
            str(atom.get("description", "")),
            " ".join(atom.get("skills") or []),
        ])
        atom_tokens = _tokenize_for_match(atom_text)
        overlap = [token for token in jd_keywords if token in atom_text and token not in {"产品"}]
        score = len(overlap) * 3
        atom_type = str(atom.get("type") or atom.get("atom_type") or "")
        if atom_type in {"project", "work"}:
            score += 2
        if "AI" in atom_text or "Agent" in atom_text or "B端" in atom_text:
            score += 2
        reasons = []
        if overlap:
            reasons.append(f"命中关键词：{'、'.join(overlap[:3])}")
        if atom_type in {"project", "work"}:
            reasons.append("适合作为定制简历的重点经历")
        return {
            **atom,
            "_score": score,
            "_reasons": reasons[:2]
        }

    ranked_atoms = sorted([score_atom(atom) for atom in atoms], key=lambda x: x["_score"], reverse=True)
    selected_atoms = ranked_atoms[:4]

    def build_bullets(atom: Dict[str, Any]) -> List[str]:
        desc = str(atom.get("description", "")).replace("\r", "\n")
        parts = [p.strip("•- \t") for p in re.split(r"[\n。；;]+", desc) if p.strip()]
        bullets = parts[:3]
        if matched_requirements:
            bullets.insert(0, f"优先呼应 JD：{matched_requirements[0]}")
        return bullets[:4]

    draft_blocks = []
    for atom in selected_atoms:
        draft_blocks.append({
            "title": atom.get("title") or "核心经历",
            "company": atom.get("company") or "",
            "type": atom.get("type") or atom.get("atom_type") or "project",
            "reasons": atom.get("_reasons", []),
            "bullets": build_bullets(atom),
            "skills": (atom.get("skills") or [])[:5]
        })

    rewrite_actions = (
        match_result.get("sections", {}).get("optimization_suggestions")
        or match_result.get("sections", {}).get("rewrite_actions")
        or match_result.get("optimization_suggestions")
        or match_result.get("report_rewrite_priorities")
        or []
    )
    optimization_notes = []
    for item in rewrite_actions[:4]:
        target = item.get("target") or item.get("target_section") or "简历模块"
        action = item.get("action") or item.get("rewrite_method") or ""
        if action:
            optimization_notes.append(f"{target}：{action}")

    # 主线版不再依赖历史经历原子库。没有原子时，直接把本次匹配分析里的
    # 改写优先级转成“建议经历/模块排布”，避免定制简历串入旧测试数据。
    if not draft_blocks:
        for item in rewrite_actions[:3]:
            if not isinstance(item, dict):
                continue
            target = item.get("target_section") or item.get("target") or "重点经历"
            problem = item.get("problem") or item.get("issue") or ""
            method = item.get("rewrite_method") or item.get("action") or ""
            example = item.get("example_direction") or item.get("example") or ""
            side_door = item.get("side_door_fix") or ""
            bullets = [text for text in [problem, method, example, side_door] if text]
            draft_blocks.append({
                "title": target,
                "company": "",
                "type": "rewrite",
                "reasons": ["来自本次匹配分析", "用于当前 JD 定制"],
                "bullets": bullets[:4],
                "skills": []
            })

    if not draft_blocks and (matched_requirements or missing_requirements):
        draft_blocks.append({
            "title": "当前简历主项目 / 实习经历",
            "company": "",
            "type": "rewrite",
            "reasons": ["围绕 JD 重新组织表达"],
            "bullets": [
                f"优先突出已匹配要求：{'、'.join(matched_requirements[:2])}" if matched_requirements else "",
                f"补强证据不足项：{'、'.join(missing_requirements[:2])}" if missing_requirements else "",
                "按“场景-动作-结果-量化”重写关键经历，避免只堆技能词。"
            ],
            "skills": []
        })

    summary_bullets = []
    if matched_requirements:
        summary_bullets.append(f"把简历重心放在：{'、'.join(matched_requirements[:2])}")
    if missing_requirements:
        summary_bullets.append(f"对暂时欠缺的 JD 项不要硬写，优先用已有经历去侧写：{'、'.join(missing_requirements[:2])}")
    if selected_atoms:
        summary_bullets.append(f"优先前置 {selected_atoms[0].get('title', '最相关经历')} 这段经历，提高首屏说服力")

    lead_atoms = [atom.get("title") or "相关经历" for atom in selected_atoms[:2]]
    profile_summary = "；".join([
        f"聚焦 {target_job} 场景的产品/项目经历",
        f"优先突出 {'、'.join(lead_atoms)}" if lead_atoms else "优先突出最相关经历",
        f"围绕 {'、'.join(matched_requirements[:2])} 展开能力证据" if matched_requirements else "围绕 JD 核心要求展开能力证据"
    ])
    skills_line = []
    for atom in selected_atoms:
        for skill in atom.get("skills") or []:
            if skill and skill not in skills_line:
                skills_line.append(skill)
    for req in matched_requirements:
        normalized_req = str(req).strip().strip("；;。")
        if normalized_req and len(normalized_req) <= 24 and normalized_req not in skills_line:
            skills_line.append(normalized_req)
    skills_line = skills_line[:8]

    ordering_strategy = []
    if selected_atoms:
        ordering_strategy.append(f"第 1 段经历建议放 {selected_atoms[0].get('title', '最相关经历')}，作为首屏主证据")
    if len(selected_atoms) > 1:
        ordering_strategy.append(f"第 2 段经历建议放 {selected_atoms[1].get('title', '第二相关经历')}，补足业务或执行链路")
    if missing_requirements:
        ordering_strategy.append(f"对 {'、'.join(missing_requirements[:2])} 不单独新造经历，而是在已有项目里补写相关做法或理解")

    return {
        "target_job": target_job,
        "headline": f"面向 {target_job} 的定制简历草稿",
        "summary": "基于当前简历、目标 JD 和本次匹配结果，优先保留与 JD 直接相关的经历表达，弱化无关内容，强化可迁移能力与证据。",
        "profile_summary": profile_summary,
        "skills_line": skills_line,
        "ordering_strategy": ordering_strategy[:3],
        "matched_requirements": matched_requirements,
        "missing_requirements": missing_requirements,
        "summary_bullets": summary_bullets[:3],
        "selected_atoms": draft_blocks,
        "optimization_notes": optimization_notes[:4],
    }


# ========== 简历优化接口 ==========

@app.post("/api/v1/resume/optimize")
async def optimize_resume(request: OptimizeResumeRequest):
    """优化简历"""
    db = get_db()
    try:
        logger.info(f"Optimizing resume: resume={request.resume_id}, job={request.job_id}")

        # 获取数据
        resume_record = db.get_resume(request.resume_id)
        job_record = db.get_job(request.job_id)

        if not resume_record or not job_record:
            raise HTTPException(status_code=404, detail="简历或岗位不存在")

        resume_data = resume_record
        job_data = job_record

        # 获取之前的匹配结果
        matches = db.list_matches()
        match_result = None
        for m in matches:
            if m.get("resume_id") == request.resume_id and m.get("job_id") == request.job_id:
                match_result = m.get("match_result", {})
                break

        if not match_result:
            # 如果没有匹配结果，先执行匹配
            match_result = match_engine.calculate(resume_data, job_data)

        # 执行优化
        optimization_result = resume_optimizer.optimize_resume(
            resume_data, job_data, match_result
        )

        return {
            "success": True,
            "data": optimization_result,
            "message": "简历优化完成"
        }

    except Exception as e:
        logger.error(f"Resume optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/resume/customize")
async def customize_resume(request: CustomizeResumeRequest):
    """基于原始简历 + JD + 匹配结果，用 AI 生成定制简历草稿（只改写、不编造）。

    优先走 AI 改写；拿不到原始简历或 AI 失败时，回退到规则版兜底，保证不报错。
    """
    # 1) 取原始简历文本：优先 resume_text，其次用 resume_id 从库里拼
    resume_text = (request.resume_text or "").strip()
    if not resume_text and request.resume_id:
        try:
            record = get_db().get_resume(request.resume_id)
            if record:
                parts = []
                basic = record.get("basic_info", {}) or {}
                parts.append(" ".join(str(v) for v in basic.values() if v))
                parts.append("技能：" + "、".join(record.get("skills", []) or []))
                for exp in record.get("experience", []) or []:
                    parts.append(" ".join(str(exp.get(k, "")) for k in ("company", "position", "duration", "description")))
                for proj in record.get("projects", []) or []:
                    parts.append(" ".join(str(proj.get(k, "")) for k in ("name", "role", "description")))
                resume_text = "\n".join(p for p in parts if p.strip())
        except Exception as e:
            logger.warning(f"读取简历用于定制失败: {e}")

    # 2) 优先 AI 改写
    if resume_text:
        try:
            # 从原子库提取「针对该 JD 改写好的表达」作为参考（meta.variants[0].bullets）
            atom_refs = []
            for atom in (request.atoms or []):
                meta = atom.get("meta") or {}
                variants = meta.get("variants") or []
                if variants and isinstance(variants[0], dict):
                    bullets = variants[0].get("bullets") or []
                    if bullets:
                        atom_refs.append({"title": atom.get("title", ""), "bullets": bullets})
            payload = await _build_customize_resume_with_ai(
                resume_text, request.jd_text, request.match_result or {}, atom_refs
            )
            return {"success": True, "data": payload, "message": "定制简历草稿生成完成"}
        except Exception as e:
            logger.warning(f"AI 定制简历失败，回退规则版: {e}")

    # 3) 回退：规则版兜底（不依赖原始简历也能出一版）
    try:
        payload = _build_customize_resume_payload(
            request.jd_text,
            request.match_result or {},
            request.atoms or []
        )
        return {"success": True, "data": payload, "message": "定制简历草稿生成完成（基础版）"}
    except Exception as e:
        logger.error(f"Customize resume failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 历史记录接口 ==========

@app.get("/api/v1/history")
async def get_history(limit: int = 20):
    """获取匹配历史记录"""
    db = get_db()
    try:
        matches = db.list_matches(limit=limit)
        return {"success": True, "data": matches, "count": len(matches)}
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 经历原子库接口 ==========

@app.get("/api/v1/atoms")
async def get_atoms(current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取经历原子库（仅当前登录用户自己的）"""
    db = get_db()
    try:
        atoms = db.list_atoms(user_id=current_user["id"])
        return {"success": True, "data": atoms, "count": len(atoms)}
    except Exception as e:
        logger.error(f"Failed to get atoms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/atoms/generate")
async def generate_atoms(resume_id: str = Form(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """从指定简历生成经历原子并入库（归属当前登录用户）"""
    db = get_db()
    try:
        resume_data = db.get_resume(resume_id)
        if not resume_data:
            raise HTTPException(status_code=404, detail="简历不存在")

        atoms = atom_generator.from_resume_data(resume_data)
        saved = []
        for atom in atoms:
            atom_id = db.save_atom(atom, user_id=current_user["id"])
            saved.append({**atom, "id": atom_id})

        logger.info(f"Generated {len(saved)} atoms from resume {resume_id}")
        return {"success": True, "data": saved, "count": len(saved), "message": "经历原子生成成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate atoms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _normalize_skills(skills: Any) -> List[str]:
    """统一 skills 字段为字符串列表（兼容逗号分隔字符串与数组）"""
    if not skills:
        return []
    if isinstance(skills, list):
        return [str(s).strip() for s in skills if str(s).strip()]
    if isinstance(skills, str):
        return [s.strip() for s in re.split(r"[,，;；]", skills) if s.strip()]
    return []


@app.post("/api/v1/atoms")
async def create_atom(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """手动创建经历原子（兼容 FormData 与 JSON 两种提交方式，归属当前登录用户）"""
    db = get_db()
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        else:
            form = await request.form()
            payload = dict(form)

        title = (payload.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="标题不能为空")

        description = payload.get("description", "")
        company = payload.get("company", "")
        atom = {
            "title": title,
            "type": payload.get("atom_type") or payload.get("type") or "work",
            "description": description,
            "company": company,
            "skills": _normalize_skills(payload.get("skills")),
            "meta": {
                "fact": {
                    "company": company,
                    "role": payload.get("role", "") or title,
                    "duration": payload.get("duration", ""),
                },
                "base_description": description,
                "highlight": "",
                "variants": []
            }
        }
        atom_id = db.save_atom(atom, user_id=current_user["id"])
        logger.info(f"Atom created: {atom_id}")
        return {"success": True, "data": {**atom, "id": atom_id}, "message": "经历原子创建成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create atom: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/atoms/{atom_id}")
async def delete_atom(atom_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """删除经历原子（仅能删当前登录用户自己的）"""
    db = get_db()
    try:
        deleted = db.delete_atom(atom_id, user_id=current_user["id"])
        if not deleted:
            raise HTTPException(status_code=404, detail="经历原子不存在")
        logger.info(f"Atom deleted: {atom_id}")
        return {"success": True, "message": "经历原子已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete atom: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RewriteAtomRequest(BaseModel):
    """针对 JD 改写经历原子表达层"""
    jd_text: str


@app.post("/api/v1/atoms/{atom_id}/rewrite")
async def rewrite_atom_for_jd(atom_id: str, request: RewriteAtomRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """针对目标 JD 重写经历原子的表达层，生成并保存一个改写版本(variant)。仅限本人原子。"""
    db = get_db()
    try:
        if not request.jd_text.strip():
            raise HTTPException(status_code=400, detail="请提供目标 JD 文本")

        atom = db.get_atom(atom_id, user_id=current_user["id"])
        if not atom:
            raise HTTPException(status_code=404, detail="经历原子不存在")

        # 兴趣类原子：走「目标用户契合论证」；其余经历类：走 STAR 表达改写
        if atom.get("type") == "interest":
            variant = atom_generator.argue_user_fit(atom, request.jd_text)
            if not variant.get("relevant"):
                # 不契合：不写入版本，直接返回提示，避免教用户硬蹭
                note = variant.get("note") or "此岗位与该兴趣无明显契合，无需在简历中突出。"
                return {"success": True, "data": {"variant": variant, "skipped": True}, "message": note}
            if not variant.get("bullets"):
                raise HTTPException(status_code=502, detail="AI 论证暂不可用，请稍后重试")
            msg = "已生成「目标用户契合」论证"
        else:
            variant = atom_generator.rewrite_for_jd(atom, request.jd_text)
            if not variant.get("bullets"):
                raise HTTPException(status_code=502, detail="AI 改写暂不可用，请稍后重试")
            msg = "已生成针对该 JD 的改写版本"

        meta = atom.get("meta") or {}
        variants = meta.get("variants") or []
        variants.insert(0, variant)
        meta["variants"] = variants[:5]  # 最多保留最近 5 个版本
        db.update_atom_meta(atom_id, meta)

        logger.info(f"Atom rewritten for JD: {atom_id}")
        return {"success": True, "data": {"variant": variant, "meta": meta}, "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rewrite atom: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/resumes/{resume_id}")
async def get_resume_by_id(resume_id: str):
    """按 ID 获取简历数据"""
    db = get_db()
    try:
        resume_data = db.get_resume(resume_id)
        if not resume_data:
            raise HTTPException(status_code=404, detail="简历不存在")
        return {"success": True, "data": {**resume_data, "id": resume_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analysis/deep")
async def deep_analysis(resume_id: str = Form(...), job_id: str = Form(...)):
    """JD 逐句拆解深度分析"""
    db = get_db()
    try:
        resume_data = db.get_resume(resume_id)
        job_data = db.get_job(job_id)
        if not resume_data or not job_data:
            raise HTTPException(status_code=404, detail="简历或岗位不存在")

        result = deep_analysis_service.analyze(resume_data, job_data)
        logger.info(f"Deep analysis completed: resume={resume_id}, job={job_id}")
        return {"success": True, "data": result, "message": "深度分析完成"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deep analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 岗位推荐接口 ==========

@app.post("/api/v1/resume/extract-text")
async def extract_resume_text(file: UploadFile = File(...)):
    """快速提取简历纯文本（不经过 LLM），供岗位推荐等轻量场景使用"""
    try:
        content = await file.read()
        filename = file.filename or ""
        lower = filename.lower()
        text = ""
        engine = "text"  # text=文本层解析；ocr=视觉OCR兜底
        is_image = lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp"))

        if lower.endswith(".pdf"):
            text = get_pdf_parser().extract_text(content, filename)
        elif lower.endswith(".docx"):
            try:
                from docx import Document
                doc = Document(io.BytesIO(content))
                text = "\n".join([p.text for p in doc.paragraphs])
            except Exception:
                text = content.decode("utf-8", errors="ignore")
        elif is_image:
            text = ""  # 图片没有文本层，直接走 OCR
        else:
            text = content.decode("utf-8", errors="ignore")
        text = (text or "").strip()

        def _looks_garbled(t: str) -> bool:
            import re as _re
            meaningful = _re.findall(r"[\u4e00-\u9fff0-9A-Za-z]", t)
            return bool(t) and (len(meaningful) / max(len(t), 1)) < 0.25

        # 兜底：文本层解析不出来（图片型/扫描版 PDF、字体编码乱码、纯图片文件）→ 视觉 OCR
        need_ocr = is_image or len(text) < 120 or _looks_garbled(text)
        if need_ocr and (lower.endswith(".pdf") or is_image):
            try:
                ocr_text = (await vision_parser.extract_text_via_vision(content, filename)).strip()
                # 仅当 OCR 结果明显更可信（更长且不乱码）才采用
                if ocr_text and len(ocr_text) > len(text) and not _looks_garbled(ocr_text):
                    text = ocr_text
                    engine = "ocr"
            except Exception as e:
                logger.warning(f"视觉 OCR 兜底失败: {e}")

        garbled = _looks_garbled(text)
        return {
            "success": True,
            "text": text,
            "char_count": len(text),
            "garbled": garbled,
            "engine": engine,
        }
    except Exception as e:
        logger.error(f"Extract resume text failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RecommendJobsRequest(BaseModel):
    """岗位推荐请求：提供 resume_id / resume 数据 / resume_text 任一即可"""
    resume_id: Optional[str] = None
    resume: Optional[Dict[str, Any]] = None
    resume_text: Optional[str] = None
    top_n: int = 5


@app.post("/api/v1/jobs/recommend")
async def recommend_jobs(request: RecommendJobsRequest):
    """根据简历从内置岗位池推荐匹配度较高的岗位（命中赛题痛点1）"""
    db = get_db()
    try:
        resume_data = request.resume
        if not resume_data and request.resume_id:
            resume_data = db.get_resume(request.resume_id)
        if not resume_data and request.resume_text:
            # 纯文本输入：不经过 LLM，直接做轻量匹配，演示更稳定
            resume_data = {"raw_text": request.resume_text}
        if not resume_data:
            raise HTTPException(status_code=400, detail="请提供 resume_id、resume 或 resume_text")

        recommender = get_job_recommender()
        top_n = max(1, min(10, request.top_n or 5))
        recommendations = recommender.recommend(resume_data, top_n=top_n)

        logger.info(f"Job recommendation done: {len(recommendations)} jobs")
        return {
            "success": True,
            "data": recommendations,
            "count": len(recommendations),
            "message": "岗位推荐完成"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Job recommendation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 投递追踪接口 ==========

@app.post("/api/v1/applications")
async def create_application(data: Dict[str, Any]):
    """创建投递记录"""
    db = get_db()
    try:
        app_id = db.save_application(data)
        logger.info(f"Application created: {app_id}")
        return {"success": True, "data": {"id": app_id}, "message": "投递记录创建成功"}
    except Exception as e:
        logger.error(f"Failed to create application: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/applications")
async def get_applications():
    """获取投递记录"""
    db = get_db()
    try:
        applications = db.list_applications()
        return {"success": True, "data": applications, "count": len(applications)}
    except Exception as e:
        logger.error(f"Failed to get applications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 校招评分接口 ==========

class CampusScoreRequest(BaseModel):
    """校招评分请求"""
    resume_data: Dict[str, Any]
    job_data: Optional[Dict[str, Any]] = None


def _normalize_resume_for_campus_scoring(resume: Dict) -> Dict:
    """将 offer-catcher 简历格式转换为 campus_scorer 期望的格式."""
    normalized = {}

    # 基本信息 -> education 列表
    basic_info = resume.get("basic_info", {})
    if basic_info.get("university") or basic_info.get("school"):
        normalized["education"] = [{
            "institution": basic_info.get("university") or basic_info.get("school", ""),
            "field": basic_info.get("major", ""),  # campus_scorer 期望 field
            "major": basic_info.get("major", ""),
            "degree": basic_info.get("degree", ""),
            "start_date": basic_info.get("start_date", ""),
            "end_date": basic_info.get("graduation_year", ""),
        }]

    # 经历 -> workExperience（campus_scorer 期望的字段名）
    experiences = resume.get("experience", [])
    if experiences:
        work_exp = []
        for exp in experiences:
            work_exp.append({
                "company": exp.get("company", ""),
                "title": exp.get("position", exp.get("title", "")),  # 适配 position/title
                "description": exp.get("description", ""),
            })
        normalized["workExperience"] = work_exp

    # 项目
    normalized["projects"] = resume.get("projects", [])

    # 技能 - 转为字符串列表和 summary 文本
    skills = resume.get("skills", [])
    skill_names = []
    if skills and isinstance(skills, list):
        for skill in skills:
            if isinstance(skill, str):
                skill_names.append(skill)
            elif isinstance(skill, dict):
                skill_names.append(skill.get("name", ""))

    # campus_scorer 技能评分期望 summary 字段包含技能文本
    normalized["skills"] = [s for s in skill_names if s]
    normalized["summary"] = " ".join(skill_names)  # 用于文本匹配

    # 教育（如果有独立的 education 字段）
    if "education" in resume and resume["education"]:
        if "education" not in normalized:
            normalized["education"] = []
        if isinstance(resume["education"], dict):
            edu = resume["education"]
            normalized["education"].append({
                "institution": edu.get("school", "") or edu.get("institution", ""),
                "field": edu.get("major", ""),
                "major": edu.get("major", ""),
                "degree": edu.get("degree", ""),
            })
        else:
            normalized["education"].extend(resume["education"])

    return normalized


@app.post("/api/v1/campus-score")
async def calculate_campus_score(request: CampusScoreRequest):
    """校招HR级评分 - 真实大厂筛选逻辑"""
    try:
        # 转换数据格式
        normalized_resume = _normalize_resume_for_campus_scoring(request.resume_data)
        score_result = campus_scorer.score(normalized_resume, request.job_data)

        return {
            "success": True,
            "data": {
                "total_score": score_result.total_score,
                "grade": score_result.grade,
                "scores": {
                    "university": score_result.university_score,
                    "degree": score_result.degree_score,
                    "major": score_result.major_score,
                    "internship": score_result.internship_score,
                    "project": score_result.project_score,
                    "skill": score_result.skill_score,
                    "achievement": score_result.achievement_score,
                },
                "details": {
                    "university_tier": score_result.university_tier,
                    "degree_level": score_result.degree_level,
                    "internship_companies": score_result.internship_companies,
                    "top_projects": score_result.top_projects,
                    "matched_skills": score_result.matched_skills,
                    "missing_skills": score_result.missing_skills,
                },
                "analysis": {
                    "strengths": score_result.strengths,
                    "weaknesses": score_result.weaknesses,
                    "recommendation": score_result.recommendation,
                }
            },
            "message": "校招评分完成"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"评分失败: {str(e)}")


# ========== 缓存管理接口 ==========

@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    """获取缓存统计信息"""
    try:
        stats = cache.get_stats()
        return {
            "success": True,
            "data": stats,
            "message": "缓存统计获取成功"
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/cache/clear")
async def clear_cache(pattern: str = ""):
    """清除缓存
    - 不传 pattern: 清空所有缓存
    - 传 pattern: 按模式清除，如 "resume" 清除简历缓存
    """
    try:
        if pattern:
            count = cache.delete_pattern(pattern)
            logger.info(f"Cleared cache pattern: {pattern}, count: {count}")
            return {
                "success": True,
                "data": {"cleared_count": count},
                "message": f"已清除 {count} 条缓存"
            }
        else:
            cache.flush_db()
            logger.info("Flushed all cache")
            return {
                "success": True,
                "message": "已清空所有缓存"
            }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Celery 异步任务接口 ==========

class AsyncParseResumeTextRequest(BaseModel):
    """异步简历解析请求"""
    text: str


@app.post("/api/v1/resume/parse-async")
async def parse_resume_async(request: AsyncParseResumeTextRequest):
    """
    异步解析简历文本（后台任务）
    立即返回任务 ID，用户可轮询获取结果
    """
    try:
        task = parse_resume_text_task.delay(request.text)
        logger.info(f"Async resume parse task created: {task.id}")
        return {
            "success": True,
            "task_id": task.id,
            "message": "简历解析任务已创建，请使用 task_id 查询结果"
        }
    except Exception as e:
        logger.error(f"Failed to create async task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AsyncParseJobRequest(BaseModel):
    """异步 JD 解析请求"""
    jd_text: str


@app.post("/api/v1/job/parse-async")
async def parse_job_async(request: AsyncParseJobRequest):
    """异步解析 JD 文本"""
    try:
        task = parse_job_task.delay(request.jd_text)
        logger.info(f"Async job parse task created: {task.id}")
        return {
            "success": True,
            "task_id": task.id,
            "message": "JD 解析任务已创建，请使用 task_id 查询结果"
        }
    except Exception as e:
        logger.error(f"Failed to create async task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AsyncMatchRequest(BaseModel):
    """异步匹配分析请求"""
    resume_id: str
    job_id: str


@app.post("/api/v1/match-async")
async def match_analysis_async(request: AsyncMatchRequest):
    """异步执行匹配分析"""
    try:
        task = match_analysis_task.delay(request.resume_id, request.job_id)
        logger.info(f"Async match task created: {task.id}")
        return {
            "success": True,
            "task_id": task.id,
            "message": "匹配分析任务已创建，请使用 task_id 查询结果"
        }
    except Exception as e:
        logger.error(f"Failed to create async task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    查询异步任务状态

    返回状态：
    - PENDING: 等待执行
    - STARTED: 正在执行
    - SUCCESS: 执行成功
    - FAILURE: 执行失败
    - RETRY: 重试中
    """
    try:
        result = celery_app.AsyncResult(task_id)

        response = {
            "task_id": task_id,
            "status": result.state,
        }

        if result.state == "PENDING":
            response["message"] = "任务等待执行"
        elif result.state == "STARTED":
            response["message"] = "任务正在执行"
        elif result.state == "SUCCESS":
            response["message"] = "任务执行成功"
            response["result"] = result.result
        elif result.state == "FAILURE":
            response["message"] = "任务执行失败"
            response["error"] = str(result.info)
        elif result.state == "RETRY":
            response["message"] = "任务重试中"
            response["retry_count"] = result.info.get("retry_count", 0)

        return response
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消正在执行的任务"""
    try:
        celery_app.control.revoke(task_id, terminate=True)
        logger.info(f"Task cancelled: {task_id}")
        return {
            "success": True,
            "message": "任务已取消"
        }
    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 监控和告警接口 ==========

@app.get("/metrics")
async def metrics():
    """
    Prometheus 指标端点

    返回应用性能指标，供 Prometheus 抓取
    包括：
    - HTTP 请求计数和延迟
    - 缓存命中率
    - LLM 调用统计
    - 数据库操作统计
    - Celery 任务统计
    """
    return get_metrics()


@app.get("/health")
async def health_check():
    """
    健康检查端点

    用于 Kubernetes/Docker 健康检查
    返回各组件状态
    """
    from app.monitoring.metrics import app_info

    checks = {
        "api": "healthy",
        "database": "unknown",
        "redis": "unknown",
        "celery": "unknown",
    }

    # 检查数据库
    try:
        db = get_db()
        db.get_stats()
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"

    # 检查 Redis
    try:
        from app.cache.redis_cache import get_cache
        cache = get_cache()
        cache.get_redis().ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"

    # 检查 Celery
    try:
        inspector = celery_app.control.inspect()
        stats = inspector.stats()
        if stats:
            checks["celery"] = "healthy"
        else:
            checks["celery"] = "unhealthy: no workers"
    except Exception as e:
        checks["celery"] = f"unhealthy: {str(e)}"

    all_healthy = all(v == "healthy" for v in checks.values())
    status_code = 200 if all_healthy else 503

    return Response(
        content=JSONResponse(content=checks).body.decode(),
        status_code=status_code,
        media_type="application/json"
    )


@app.get("/api/v1/status")
async def get_status():
    """
    详细状态端点

    返回应用、依赖服务、队列状态
    """
    from app.monitoring.metrics import http_requests_total, cache_hits_total, cache_misses_total

    status = {
        "app": {
            "version": "1.2.0",
            "name": "Offer 捕手",
        },
        "metrics": {
            "http_requests_total": http_requests_total._value.get() if hasattr(http_requests_total, '_value') else 0,
            "cache_hits": cache_hits_total._value.get() if hasattr(cache_hits_total, '_value') else 0,
            "cache_misses": cache_misses_total._value.get() if hasattr(cache_misses_total, '_value') else 0,
        }
    }

    # 获取 Celery worker 状态
    try:
        inspector = celery_app.control.inspect()
        worker_stats = inspector.stats()
        if worker_stats:
            status["celery_workers"] = list(worker_stats.keys())
            status["celery_active_tasks"] = sum(
                len(s.get('active_tasks', [])) for s in worker_stats.values()
            )
    except Exception:
        status["celery_workers"] = []

    return status


# ========== 测试数据接口 ==========

TEST_RESUME_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "uploads",
    "fixed-test-resume.pdf"
)
TEST_JD = """AI产品实习生

• 薪资：250-300元/天

• 地点：上海·徐汇区·漕河泾

• 要求：4天/周，3个月，本科

• 所属：语核科技校招专场，创始人翟先生发布（今日活跃）

• 标签：B端产品、语义类AI、语音类AI、视觉类AI
【主要职责】

1. 根据公司商业化目标，参与细化产品Roadmap，推动团队实现目标；

2. 完成Agent数字员工的复杂模块产品设计；

3. 支持产品设计评审，指导校招产品经理的能力提升，共同建设产品培训体系；

4. 持续关注各渠道用户需求及反馈，洞察背后真实诉求转化为可交付的产品方案；

5. 与团队密切配合完成从产品定义、构建、验收的全流程工作。
【职位要求】

1. 有B端产品意识，具备B端古典产品经理能力和知识体系；

2. 有协助完成产品模块从0-1的经验或能力；

3. 能够在信息中抽丝剥茧抽象出产品竞争力；

4. 能够对过往项目经验的方案，进行清晰有逻辑的阐述，知其然知其所以然（在简历中能够体现优先）；

5. 对AI生产力工具，有主动探索和学习的兴趣，以及得出见解的能力。
【加分项】

1. 自己动手从0-1做过小产品（低代码搭建或vibe coding）；

2. 能体现探索欲或创造力的任何事；

3. 用过AI Agent低代码开发平台，如扣子、Dify。理解Agent构成的基本逻辑。有Agent实践、2B业务经历、vibe coding能力。
【我们提供】

1. 与全球最前沿的Agent团队共同学习与工作。

2. 为所有的对Agent感兴趣的同学提供一个进入行业的机会。

3. 一个支持创新和持续发展的开放团队环境。

4. 深入了解AI技术及其实际应用的机会。

5. 有竞争力的补贴。
"""

@app.get("/api/v1/test/data")
async def get_test_data():
    """获取测试数据（简历文件 + JD）"""
    import os
    from fastapi.responses import FileResponse

    # 检查文件是否存在
    if not os.path.exists(TEST_RESUME_PATH):
        return {
            "success": False,
            "message": "测试简历文件不存在",
            "jd": TEST_JD
        }

    return {
        "success": True,
        "jd": TEST_JD,
        "resume_filename": os.path.basename(TEST_RESUME_PATH)
    }


@app.get("/api/v1/test/resume")
async def get_test_resume():
    """获取测试简历文件"""
    import os
    from fastapi.responses import FileResponse

    if not os.path.exists(TEST_RESUME_PATH):
        raise HTTPException(status_code=404, detail="测试简历文件不存在")

    return FileResponse(
        TEST_RESUME_PATH,
        media_type="application/pdf",
        filename=os.path.basename(TEST_RESUME_PATH)
    )


# ========== 前端静态托管 ==========
# 注意：这些路由必须放在所有 /api/... 路由之后，避免覆盖 API 路由。
# FRONTEND_DIR 基于 __file__ 计算绝对路径，不受启动时工作目录 / rootDir 影响。
FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend"
)

# 挂载前端资源目录（index.html 引用了 ./assets/cat-outline.png）
_ASSETS_DIR = os.path.join(FRONTEND_DIR, "assets")
if os.path.isdir(_ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")


@app.get("/")
async def serve_index():
    """返回前端首页"""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ========== 应用启动 ==========

if __name__ == "__main__":
    # 用 MetricsMiddleware 包装 ASGI 应用
    wrapped_app = MetricsMiddleware(app)
    uvicorn.run(
        wrapped_app,
        host="0.0.0.0",
        port=8888,
        reload=True,
        log_level="info"
    )
