"""
Celery 异步任务配置

用于处理长耗时任务（如 LLM 调用、简历解析等）
避免阻塞 API 响应，提升用户体验

作者：Claude
创建日期：2026-06-01
"""

from celery import Celery
import os

# Redis 作为消息代理和结果后端
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"

# 创建 Celery 应用
celery_app = Celery(
    "offer_catcher_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.resume_tasks",
        "app.tasks.job_tasks",
        "app.tasks.match_tasks",
    ]
)

# Celery 配置
celery_app.conf.update(
    # 任务结果过期时间（1天）
    result_expires=86400,
    # 任务执行时间限制（10分钟）
    task_time_limit=600,
    # 任务软时间限制（8分钟，可捕获异常）
    task_soft_time_limit=480,
    # 任务结果序列化格式
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # 时区设置
    timezone="Asia/Shanghai",
    enable_utc=False,
    # 任务路由（可选，按任务类型分发到不同队列）
    task_routes={
        "app.tasks.resume_tasks.*": {"queue": "resume"},
        "app.tasks.job_tasks.*": {"queue": "job"},
        "app.tasks.match_tasks.*": {"queue": "match"},
    },
    # Worker 预取数量
    worker_prefetch_multiplier=1,
    # 任务 Ack 支持
    task_acks_late=True,
)
