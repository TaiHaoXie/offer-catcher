# Redis 缓存层 - 启动指南

## 已完成的工作

### 1. 代码层面
- 创建 `backend/app/cache/redis_cache.py` - Redis 缓存管理类
- 集成到 `backend/app/main.py` - 简历/JD 解析、匹配分析已支持缓存
- 更新 `requirements.txt` - 添加 redis 依赖
- 更新 `docker-compose.yml` - 添加 Redis 服务

### 2. 新增 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/cache/stats` | GET | 获取缓存统计（命中率、内存使用等） |
| `/api/v1/cache/clear` | POST | 清除缓存（可选 pattern 参数） |

## 缓存策略

| 数据类型 | TTL | 说明 |
|---------|-----|------|
| 简历解析 | 24小时 | 相同简历文本直接返回缓存结果 |
| JD 解析 | 24小时 | 相同 JD 文本直接返回缓存结果 |
| 匹配分析 | 7天 | 相同简历+岗位组合直接返回缓存结果 |
| LLM 结果 | 7天 | 通用 LLM 调用结果缓存 |

## 本地启动方式

### 方式 1：使用 Docker（推荐）

```bash
cd /Users/bytedance/Desktop/offer-catcher
docker-compose up -d
```

### 方式 2：手动安装 Redis

```bash
# macOS 安装 Redis
brew install redis
brew start redis

# 验证 Redis 运行
redis-cli ping  # 应返回 PONG

# 启动后端
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
```

### 方式 3：Redis 未安装时的降级模式

如果 Redis 未运行，缓存层会自动降级（打印警告日志），不影响核心功能。

## 测试缓存是否生效

```bash
# 第一次请求（缓存未命中）
curl -X POST http://localhost:8888/api/v1/resume/parse-text \
  -H "Content-Type: application/json" \
  -d '{"text": "张三\n\n简历内容..."}'

# 第二次请求（缓存命中，响应中会有 "cached": true）
curl -X POST http://localhost:8888/api/v1/resume/parse-text \
  -H "Content-Type: application/json" \
  -d '{"text": "张三\n\n简历内容..."}'

# 查看缓存统计
curl http://localhost:8888/api/v1/cache/stats
```

## 缓存效果预估

- **简历解析**：重复简历从 ~2s 降至 ~50ms（40x 提升）
- **JD 解析**：重复 JD 从 ~1s 降至 ~50ms（20x 提升）
- **匹配分析**：重复组合从 ~5s 降至 ~50ms（100x 提升）
- **LLM 调用**：大幅减少 API 调用成本
