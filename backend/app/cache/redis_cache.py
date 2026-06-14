"""
Redis 缓存层 - 提升性能和减少 LLM 调用

缓存策略：
1. 简历解析结果 (24小时)
2. JD 解析结果 (24小时)
3. 匹配分析结果 (7天)
4. LLM 结果 (7天)

作者：Claude
创建日期：2026-06-01
"""

import redis.asyncio as aioredis
import redis
import json
import hashlib
import logging
import os
from typing import Optional, Any, List
from datetime import timedelta

logger = logging.getLogger(__name__)


class CacheConfig:
    """缓存配置"""

    # Redis 连接配置（支持环境变量）
    HOST = os.getenv("REDIS_HOST", "localhost")
    PORT = int(os.getenv("REDIS_PORT", "6379"))
    DB = int(os.getenv("REDIS_DB", "0"))
    DECODE_RESPONSES = True

    # 缓存过期时间（秒）
    RESUME_PARSE_TTL = 86400      # 24小时
    JOB_PARSE_TTL = 86400         # 24小时
    MATCH_RESULT_TTL = 604800     # 7天
    LLM_RESULT_TTL = 604800        # 7天
    ATOMS_TTL = 3600              # 1小时

    # 缓存键前缀
    KEY_PREFIX = "offer_catcher:"
    RESUME_PREFIX = f"{KEY_PREFIX}resume:"
    JOB_PREFIX = f"{KEY_PREFIX}job:"
    MATCH_PREFIX = f"{KEY_PREFIX}match:"
    LLM_PREFIX = f"{KEY_PREFIX}llm:"


class RedisCache:
    """Redis 缓存管理类"""

    def __init__(self, config: CacheConfig = None):
        """初始化 Redis 连接"""
        self.config = config or CacheConfig()
        self._redis: Optional[redis.Redis] = None
        self._async_redis: Optional[aioredis.Redis] = None

    def get_redis(self) -> redis.Redis:
        """获取同步 Redis 客户端"""
        if self._redis is None:
            self._redis = redis.Redis(
                host=self.config.HOST,
                port=self.config.PORT,
                db=self.config.DB,
                decode_responses=self.config.DECODE_RESPONSES,
                socket_connect_timeout=1,  # 1秒连接超时
                socket_timeout=1,           # 1秒读写超时
                retry_on_timeout=False      # 不重试，快速失败
            )
        return self._redis

    async def get_async_redis(self) -> aioredis.Redis:
        """获取异步 Redis 客户端"""
        if self._async_redis is None:
            self._async_redis = await aioredis.from_url(
                f"redis://{self.config.HOST}:{self.config.PORT}/{self.config.DB}",
                encoding="utf-8",
                decode_responses=True
            )
        return self._async_redis

    def _generate_key(self, prefix: str, data: Any) -> str:
        """生成缓存键"""
        if isinstance(data, str):
            content = data
        elif isinstance(data, dict):
            content = json.dumps(data, sort_keys=True)
        else:
            content = str(data)

        hash_value = hashlib.md5(content.encode()).hexdigest()
        return f"{prefix}{hash_value}"

    def set(self, key: str, value: Any, ttl: int) -> bool:
        """设置缓存"""
        try:
            redis_client = self.get_redis()
            serialized = json.dumps(value, ensure_ascii=False)
            return redis_client.setex(key, ttl, serialized)
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            redis_client = self.get_redis()
            # 添加超时防止卡住
            value = redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None

    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            redis_client = self.get_redis()
            return redis_client.delete(key) > 0
        except Exception as e:
            logger.warning(f"Cache delete failed: {e}")
            return False

    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            redis_client = self.get_redis()
            return redis_client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Cache exists check failed: {e}")
            return False

    # ========== 简历解析缓存 ==========

    def cache_resume_parse(self, resume_text: str, parsed_data: dict) -> bool:
        """缓存简历解析结果"""
        key = self._generate_key(self.config.RESUME_PREFIX, resume_text)
        return self.set(key, parsed_data, self.config.RESUME_PARSE_TTL)

    def get_cached_resume_parse(self, resume_text: str) -> Optional[dict]:
        """获取缓存的简历解析结果"""
        key = self._generate_key(self.config.RESUME_PREFIX, resume_text)
        return self.get(key)

    # ========== JD 解析缓存 ==========

    def cache_job_parse(self, jd_text: str, parsed_data: dict) -> bool:
        """缓存 JD 解析结果"""
        key = self._generate_key(self.config.JOB_PREFIX, jd_text)
        return self.set(key, parsed_data, self.config.JOB_PARSE_TTL)

    def get_cached_job_parse(self, jd_text: str) -> Optional[dict]:
        """获取缓存的 JD 解析结果"""
        key = self._generate_key(self.config.JOB_PREFIX, jd_text)
        return self.get(key)

    # ========== 匹配结果缓存 ==========

    def cache_match_result(self, resume_id: str, job_id: str, match_result: dict) -> bool:
        """缓存匹配结果"""
        key = f"{self.config.MATCH_PREFIX}{resume_id}:{job_id}"
        return self.set(key, match_result, self.config.MATCH_RESULT_TTL)

    def get_cached_match_result(self, resume_id: str, job_id: str) -> Optional[dict]:
        """获取缓存的匹配结果"""
        key = f"{self.config.MATCH_PREFIX}{resume_id}:{job_id}"
        return self.get(key)

    # ========== LLM 结果缓存 ==========

    def cache_llm_result(self, prompt: str, result: Any, ttl: int = None) -> bool:
        """缓存 LLM 结果"""
        key = self._generate_key(self.config.LLM_PREFIX, prompt)
        ttl = ttl or self.config.LLM_RESULT_TTL
        return self.set(key, result, ttl)

    def get_cached_llm_result(self, prompt: str) -> Optional[Any]:
        """获取缓存的 LLM 结果"""
        key = self._generate_key(self.config.LLM_PREFIX, prompt)
        return self.get(key)

    # ========== 批量操作 ==========

    def delete_pattern(self, pattern: str) -> int:
        """删除匹配模式的所有键"""
        try:
            redis_client = self.get_redis()
            keys = redis_client.keys(f"{self.config.KEY_PREFIX}{pattern}")
            if keys:
                return redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Pattern delete failed: {e}")
            return 0

    def flush_db(self) -> bool:
        """清空当前数据库"""
        try:
            redis_client = self.get_redis()
            redis_client.flushdb()
            logger.info("Database flushed")
            return True
        except Exception as e:
            logger.error(f"Flush failed: {e}")
            return False

    def get_stats(self) -> dict:
        """获取缓存统计"""
        try:
            redis_client = self.get_redis()
            info = redis_client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "total_commands": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
        except Exception as e:
            logger.error(f"Stats failed: {e}")
            return {}

    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """计算命中率"""
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)

    def close(self):
        """关闭连接"""
        if self._redis:
            self._redis.close()
            self._redis = None


# 全局缓存实例
_cache_instance: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """获取缓存实例（单例模式）"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance


# 装饰器：缓存函数结果
def cached(prefix: str, ttl: int = 3600):
    """缓存装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # 生成缓存键
            key_data = f"{prefix}:{args}:{kwargs}"
            key = cache._generate_key(CacheConfig.KEY_PREFIX + prefix, key_data)

            # 尝试获取缓存
            cached_result = cache.get(key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {key}")
                return cached_result

            # 执行函数
            result = func(*args, **kwargs)

            # 缓存结果
            cache.set(key, result, ttl)
            logger.debug(f"Cache set: {key}")

            return result
        return wrapper
    return decorator
