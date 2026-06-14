# 监控和告警系统

## 已完成的工作

### 1. Prometheus 指标端点
- `/metrics` - Prometheus 指标抓取端点
- `/health` - 健康检查端点（供 Kubernetes 使用）
- `/api/v1/status` - 详细状态端点

### 2. 监控指标

| 指标 | 类型 | 说明 |
|------|------|------|
| `http_requests_total` | Counter | HTTP 请求总数（按方法、端点、状态码分组） |
| `http_request_duration_seconds` | Histogram | HTTP 请求延迟分布 |
| `cache_hits_total` | Counter | 缓存命中次数 |
| `cache_misses_total` | Counter | 缓存未命中次数 |
| `llm_requests_total` | Counter | LLM 调用次数 |
| `llm_request_duration_seconds` | Histogram | LLM 调用延迟 |
| `match_score` | Gauge | 最新匹配分数 |
| `db_operations_total` | Counter | 数据库操作次数 |
| `celery_tasks_total` | Counter | Celery 任务执行次数 |
| `active_connections` | Gauge | 当前活跃连接数 |

### 3. 服务端口

| 服务 | 端口 | 访问地址 |
|------|------|----------|
| API | 8888 | http://localhost:8888 |
| Flower (Celery 监控) | 5555 | http://localhost:5555 |
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3001 | http://localhost:3001 (admin/admin) |
| 前端 | 3000 | http://localhost:3000 |

### 4. 预定义告警规则

| 告警 | 级别 | 触发条件 |
|------|------|----------|
| 高错误率 | CRITICAL | 错误率超过 5% |
| 慢查询 | WARNING | 存在超过 1 秒的查询 |
| LLM 高失败率 | CRITICAL | LLM 调用失败率超过 10% |
| 低缓存命中率 | WARNING | 缓存命中率低于 50% |
| Celery 任务积压 | WARNING | 任务积压超过 100 |

## 快速启动

```bash
cd /Users/bytedance/Desktop/offer-catcher
docker-compose up -d
```

## 访问监控面板

1. **Prometheus** - 查看原始指标
   - 访问 http://localhost:9090
   - 查询示例：`rate(http_requests_total[5m])`

2. **Grafana** - 可视化面板
   - 访问 http://localhost:3001
   - 默认账号：admin / admin
   - 需手动导入仪表盘或使用配置的 Provisioning

3. **Flower** - Celery 任务监控
   - 访问 http://localhost:5555
   - 查看任务执行状态、Worker 信息

## 常用 PromQL 查询

```promql
# API 请求 QPS
rate(http_requests_total[5m])

# API P95 延迟
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 缓存命中率
cache_hits_total / (cache_hits_total + cache_misses_total)

# 错误率
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# LLM 调用 QPS
rate(llm_requests_total[5m])
```
