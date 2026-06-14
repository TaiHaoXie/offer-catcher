# Offer 捕手 Memory

## 已确认的项目事实

- 项目定位：学生求职匹配智能体，重点是简历和岗位的匹配闭环。
- 后端：FastAPI + Python，依赖里有 LiteLLM、TinyDB、Redis、Celery、Prometheus。
- 前端：当前主线是 `frontend/` 静态页，入口是 `frontend/index.html`。
- 文档：`docs/项目交接文档.md`、`docs/方案说明.md`、`README.md` 都描述了同一个产品方向。

## 重要差异

- `deprecated-frontend-nextjs/` 与 `deprecated-frontend-nextjs-backup/` 仍在仓库中，但都不再作为运行入口。
- `start.sh` 启动静态前端，并且后端端口是 `8888`。

## 适合继续做的事

- 把一键启动脚本、README 和实际前后端结构统一。
- 继续完善 `frontend/index.html` 的主线体验。
- 以实际代码为准整理部署和运行说明。
