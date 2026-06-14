"""
JD 解析异步任务

作者：Claude
创建日期：2026-06-01
"""

from app.tasks.celery_app import celery_app
from app.services.fast_jd_parser import FastJDParser
from app.db.sqlite_db import get_db
import logging

logger = logging.getLogger(__name__)

# 初始化解析器
jd_parser = FastJDParser()


@celery_app.task(name="tasks.parse_job", bind=True, max_retries=3)
def parse_job_task(self, jd_text: str):
    """
    异步解析 JD 文本

    Args:
        jd_text: JD 文本内容

    Returns:
        dict: 解析结果 + job_id
    """
    try:
        logger.info(f"Async parsing job description (task {self.request.id})")

        # 解析 JD
        job_data = jd_parser.parse(jd_text)

        # 保存到数据库
        db = get_db()
        job_id = db.save_job(job_data)

        logger.info(f"Job parsed successfully: {job_id}")

        return {
            "success": True,
            "job_id": job_id,
            "data": {**job_data, "id": job_id},
            "task_id": self.request.id
        }

    except Exception as e:
        logger.error(f"Job parsing failed: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }
