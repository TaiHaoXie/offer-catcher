"""
匹配分析异步任务

执行专业级匹配分析，可能耗时较长

作者：Claude
创建日期：2026-06-01
"""

from app.tasks.celery_app import celery_app
from app.services.professional_match_engine import ProfessionalMatchEngine
from app.services.professional_resume_optimizer import ProfessionalResumeOptimizer
from app.db.sqlite_db import get_db
import logging

logger = logging.getLogger(__name__)

# 初始化服务
match_engine = ProfessionalMatchEngine()
resume_optimizer = ProfessionalResumeOptimizer()


@celery_app.task(name="tasks.match_analysis", bind=True, max_retries=2)
def match_analysis_task(self, resume_id: str, job_id: str):
    """
    异步执行匹配分析

    Args:
        resume_id: 简历 ID
        job_id: 岗位 ID

    Returns:
        dict: 匹配结果 + match_id
    """
    try:
        logger.info(f"Async match analysis: resume={resume_id}, job={job_id} (task {self.request.id})")

        db = get_db()

        # 获取数据
        resume_record = db.get_resume(resume_id)
        job_record = db.get_job(job_id)

        if not resume_record or not job_record:
            raise ValueError("简历或岗位不存在")

        # 执行匹配分析
        match_result = match_engine.calculate(resume_record, job_record)

        # 保存匹配记录
        match_record_data = {
            "resume_id": resume_id,
            "job_id": job_id,
            "match_result": match_result,
            "position_name": job_record.get("position_name", ""),
            "company": job_record.get("company", "")
        }
        match_id = db.save_match(match_record_data)

        logger.info(f"Match analysis completed: {match_id}")

        return {
            "success": True,
            "match_id": match_id,
            "data": {**match_result, "match_id": match_id},
            "task_id": self.request.id
        }

    except Exception as e:
        logger.error(f"Match analysis failed: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }


@celery_app.task(name="tasks.optimize_resume", bind=True, max_retries=2)
def optimize_resume_task(self, resume_id: str, job_id: str):
    """
    异步优化简历

    Args:
        resume_id: 简历 ID
        job_id: 岗位 ID

    Returns:
        dict: 优化结果
    """
    try:
        logger.info(f"Async optimizing resume: resume={resume_id}, job={job_id} (task {self.request.id})")

        db = get_db()

        # 获取数据
        resume_record = db.get_resume(resume_id)
        job_record = db.get_job(job_id)

        if not resume_record or not job_record:
            raise ValueError("简历或岗位不存在")

        # 获取匹配结果
        matches = db.list_matches()
        match_result = None
        for m in matches:
            if m.get("resume_id") == resume_id and m.get("job_id") == job_id:
                match_result = m.get("match_result", {})
                break

        if not match_result:
            # 先执行匹配
            match_result = match_engine.calculate(resume_record, job_record)

        # 执行优化
        optimization_result = resume_optimizer.optimize_resume(
            resume_record, job_record, match_result
        )

        logger.info(f"Resume optimization completed")

        return {
            "success": True,
            "data": optimization_result,
            "task_id": self.request.id
        }

    except Exception as e:
        logger.error(f"Resume optimization failed: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }
