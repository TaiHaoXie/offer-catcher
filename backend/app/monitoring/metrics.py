"""
Prometheus 监控指标

收集应用性能指标，供 Prometheus 抓取

作者：Claude
创建日期：2026-06-01
"""

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest
from prometheus_client.core import CollectorRegistry
from fastapi import Response
import time
import logging

logger = logging.getLogger(__name__)

# 创建自定义注册表（避免与默认冲突）
registry = CollectorRegistry()

# 应用信息
app_info = Info(
    'offer_catcher',
    'Offer 捕手应用信息',
    registry=registry
)
app_info.info({
    'version': '1.2.0',
    'environment': 'production'
})

# HTTP 请求计数器
http_requests_total = Counter(
    'http_requests_total',
    'HTTP 请求总数',
    ['method', 'endpoint', 'status'],
    registry=registry
)

# HTTP 请求延迟直方图
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP 请求延迟（秒）',
    ['method', 'endpoint'],
    registry=registry
)

# 缓存命中率
cache_hits_total = Counter(
    'cache_hits_total',
    '缓存命中次数',
    ['cache_type'],
    registry=registry
)

cache_misses_total = Counter(
    'cache_misses_total',
    '缓存未命中次数',
    ['cache_type'],
    registry=registry
)

# LLM 调用计数器
llm_requests_total = Counter(
    'llm_requests_total',
    'LLM 调用次数',
    ['provider', 'model'],
    registry=registry
)

# LLM 调用延迟
llm_request_duration_seconds = Histogram(
    'llm_request_duration_seconds',
    'LLM 调用延迟（秒）',
    ['provider', 'model'],
    registry=registry
)

# 匹配分析分数
match_score_gauge = Gauge(
    'match_score',
    '最新匹配分析分数',
    registry=registry
)

# 数据库操作计数器
db_operations_total = Counter(
    'db_operations_total',
    '数据库操作次数',
    ['operation', 'table'],
    registry=registry
)

# Celery 任务计数器
celery_tasks_total = Counter(
    'celery_tasks_total',
    'Celery 任务执行次数',
    ['task_name', 'status'],
    registry=registry
)

# 活跃连接数
active_connections = Gauge(
    'active_connections',
    '当前活跃连接数',
    registry=registry
)


class MetricsMiddleware:
    """Prometheus 中间件 - 自动记录 HTTP 请求指标"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        # 记录开始时间
        start_time = time.time()

        # 拦截响应状态码
        status_code = 200

        async def send_wrapper(message):
            nonlocal status_code
            if message['type'] == 'http.response.start':
                status_code = message['status']
            await send(message)

        # 处理请求
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # 记录指标
            duration = time.time() - start_time
            method = scope['method']
            path = scope['path']

            # 记录请求计数
            http_requests_total.labels(
                method=method,
                endpoint=path,
                status=status_code
            ).inc()

            # 记录请求延迟
            http_request_duration_seconds.labels(
                method=method,
                endpoint=path
            ).observe(duration)


def get_metrics() -> Response:
    """获取 Prometheus 格式的指标"""
    return Response(
        content=generate_latest(registry),
        media_type="text/plain"
    )


def track_cache_hit(cache_type: str):
    """记录缓存命中"""
    cache_hits_total.labels(cache_type=cache_type).inc()
    logger.debug(f"Cache hit: {cache_type}")


def track_cache_miss(cache_type: str):
    """记录缓存未命中"""
    cache_misses_total.labels(cache_type=cache_type).inc()
    logger.debug(f"Cache miss: {cache_type}")


def track_llm_request(provider: str, model: str, duration: float):
    """记录 LLM 调用"""
    llm_requests_total.labels(provider=provider, model=model).inc()
    llm_request_duration_seconds.labels(provider=provider, model=model).observe(duration)


def track_db_operation(operation: str, table: str):
    """记录数据库操作"""
    db_operations_total.labels(operation=operation, table=table).inc()


def track_celery_task(task_name: str, status: str):
    """记录 Celery 任务"""
    celery_tasks_total.labels(task_name=task_name, status=status).inc()


def update_match_score(score: float):
    """更新匹配分数"""
    match_score_gauge.set(score)


def increment_active_connections():
    """增加活跃连接计数"""
    active_connections.inc()


def decrement_active_connections():
    """减少活跃连接计数"""
    active_connections.dec()
